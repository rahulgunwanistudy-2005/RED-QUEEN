"""FastAPI control plane: /health, one /stream event stream, /slice/run, /events, /registry."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from sqlalchemy import text

from sentinel.config import USE_REAL
from sentinel.db import engine, ping, run_migrations
from sentinel.gateway import handle_request
from sentinel.harden import machine
from sentinel.harden.orchestrator import run_full_cycle
from sentinel.platform import geap
from sentinel.slice.core import run_thin_slice
from sentinel.stream import bus


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        run_migrations()
    except Exception as exc:  # surfaced by /health rather than crashing boot
        app.state.migration_error = str(exc)
    else:
        app.state.migration_error = None
    yield


app = FastAPI(title="Sentinel Evolution", version="0.0.1-m0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # M0 local dev; tighten before any deploy
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        db_ok = ping()
    except Exception:
        db_ok = False
    return {
        "status": "ok",
        "db": db_ok,
        "migration_error": getattr(app.state, "migration_error", None),
        "use_real": USE_REAL,
    }


@app.get("/registry")
def registry() -> list[dict[str, Any]]:
    return [asdict(a) for a in geap.registry_list()]


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


@app.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    async def gen():
        q = await bus.subscribe()
        try:
            yield _sse({"type": "hello", "service": "sentinel-evolution"})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield _sse(event)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/events")
async def emit_event(event: dict[str, Any]) -> dict[str, Any]:
    """Ingest an event from an out-of-process producer (the slice CLI) and fan it
    out on /stream."""
    n = await bus.publish(event)
    return {"delivered_to": n}


@app.post("/gateway/request")
async def gateway_request(req: dict[str, Any]) -> dict[str, Any]:
    """Send a request to the fleet. Every request transits geap.scan() first
    (SOF-159). Benign content -> normal answer; injection -> privileged call."""
    ticket_id = str(req.get("ticket_id", "TICKET-0"))
    content = str(req.get("content", ""))
    authorized = bool(req.get("authorized", False))
    result = await asyncio.to_thread(
        handle_request, ticket_id, content, authorized=authorized
    )
    return {
        "scan": {
            "blocked": result.scan.blocked,
            "detected": result.scan.detected,
            "score": result.scan.score,
            "backend": result.scan.backend,
        },
        "agent": None if result.agent is None else {
            "action": result.agent.action,
            "answer": result.agent.answer,
            "tool_calls": result.agent.tool_calls,
            "privileged_executed": result.agent.privileged_executed,
            "backend": result.agent.backend,
        },
    }


@app.post("/slice/run")
async def slice_run() -> dict[str, Any]:
    """Run the thin slice in-process and broadcast its score event (demo button)."""
    verdict, score_event = await asyncio.to_thread(run_thin_slice)
    await bus.publish(score_event)
    return verdict.model_dump()


# --- M2 harden + verify (SOF-168..172) --------------------------------------


def _bus_emitter():
    """A threadsafe emit() for orchestrator/machine callbacks running in a worker
    thread: schedules bus.publish on the event loop so /stream sees every event."""
    loop = asyncio.get_running_loop()

    def emit(event: dict[str, Any]) -> None:
        asyncio.run_coroutine_threadsafe(bus.publish(event), loop)

    return emit


def _run_summary(run: machine.Run | None) -> dict[str, Any]:
    if run is None:
        return {"opened": False, "reason": "attack did not bypass; nothing to harden"}
    return {
        "opened": True,
        "run_id": run.id,
        "attack_class": run.attack_class,
        "state": run.state,
        "verdict": run.verdict,
        "sub_scores": run.sub_scores,
        "policy_id": run.policy_id,
        "is_destructive": run.is_destructive,
        "await_approval": run.state == machine.AWAIT_APPROVAL,
    }


@app.post("/harden/run")
async def harden_run(req: dict[str, Any]) -> dict[str, Any]:
    """Run one full attack -> harden -> verify cycle and stream every event.
    Body: {attack_class, seed?, remedy?(content|identity|exact), use_corpus?}."""
    attack_class = str(req.get("attack_class", "prompt_injection"))
    seed = int(req.get("seed", 1337))
    remedy = str(req.get("remedy", "content"))
    use_corpus = bool(req.get("use_corpus", True))
    emit = _bus_emitter()
    run = await asyncio.to_thread(
        run_full_cycle, attack_class,
        seed=seed, remedy=remedy, use_corpus=use_corpus, emit=emit,
    )
    return _run_summary(run)


@app.post("/harden/approve")
async def harden_approve(req: dict[str, Any]) -> dict[str, Any]:
    """Approve/reject a run paused at AWAIT_APPROVAL; approval resumes it (SOF-171)."""
    run_id = int(req.get("run_id"))
    decision = "rejected" if req.get("decision") == "rejected" else "approved"
    emit = _bus_emitter()

    def _apply() -> machine.Run | None:
        run = machine.set_approval(run_id, decision, emit=emit)
        if run is not None and decision == "approved":
            run = machine.run_to_completion(run, emit=emit)
        return run

    run = await asyncio.to_thread(_apply)
    if run is None:
        return {"ok": False, "reason": f"run {run_id} not found"}
    return {"ok": True, "decision": decision, **_run_summary(run)}


@app.get("/harden/runs")
def harden_runs() -> list[dict[str, Any]]:
    """Every hardening run + its verifier verdict (verdict-panel hydration)."""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, attack_class, state, verdict, sub_scores, policy_id,
                       is_destructive, payload_hash, created_at
                FROM hardening_runs ORDER BY id DESC
                """
            )
        ).all()
    out = []
    for r in rows:
        out.append({
            "run_id": r[0], "attack_class": r[1], "state": r[2], "verdict": r[3],
            "sub_scores": r[4], "policy_id": r[5], "is_destructive": r[6],
            "payload_hash": r[7], "created_at": r[8].isoformat() if r[8] else None,
        })
    return out


@app.get("/traces/{run_id}")
def traces(run_id: int) -> dict[str, Any]:
    """OTel span summaries for one attack->harden->verify cycle (trace waterfall)."""
    with engine.begin() as conn:
        run = conn.execute(
            text(
                """
                SELECT attack_class, state, verdict, sub_scores, policy_id,
                       attack_trace_id, harden_trace_id, verify_trace_id
                FROM hardening_runs WHERE id = :id
                """
            ),
            {"id": run_id},
        ).fetchone()
        spans = conn.execute(
            text(
                """
                SELECT phase, name, trace_id, started_ms, duration_ms, attributes
                FROM run_spans WHERE run_id = :id ORDER BY started_ms, id
                """
            ),
            {"id": run_id},
        ).all()
    if run is None:
        return {"run_id": run_id, "found": False, "spans": []}
    return {
        "run_id": run_id, "found": True, "attack_class": run[0], "state": run[1],
        "verdict": run[2], "sub_scores": run[3], "policy_id": run[4],
        "trace_ids": {"attack": run[5], "harden": run[6], "verify": run[7]},
        "spans": [
            {"phase": s[0], "name": s[1], "trace_id": s[2],
             "started_ms": s[3], "duration_ms": s[4], "attributes": s[5]}
            for s in spans
        ],
    }
