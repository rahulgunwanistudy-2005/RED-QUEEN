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

from sentinel import config
from sentinel.config import USE_REAL
from sentinel.db import engine, ping, provision_verifier_role, run_migrations
from sentinel.gateway import handle_request
from sentinel.harden import machine
from sentinel.harden.orchestrator import run_campaign, run_full_cycle
from sentinel.platform import geap
from sentinel.slice.core import run_thin_slice
from sentinel.stream import bus


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        run_migrations()
        if USE_REAL["cloud_sql"]:
            provision_verifier_role()
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
        # The live model posture (SESSION_7): the Gemini 3.5+ heterogeneous fleet. The
        # range brain drives the hardener, verifier, and multimodal guard; the vulnerable
        # target agent runs the smaller model. Both served on Vertex's `global` endpoint.
        "models": {
            "range_brain": config.VERTEX_GEMINI_MODEL,
            "vulnerable_target_agent": config.TARGET_AGENT_MODEL,
            "gemini_location": config.VERTEX_GEMINI_LOCATION,
        },
        # The red-team GENERATOR posture (SESSION_8). Gemma via the AI Studio Developer
        # API produces gen-0 payloads that enter the campaign; the deterministic operators
        # remain the mutation engine. `ready` is the honest live posture: real only when
        # the flag is on AND a key is present, else the disclosed offline-seed fallback.
        "red_team_generator": {
            "backend": "gemma" if config.gemma_ready() else "offline-seed (fallback)",
            "model": config.GEMMA_MODEL,
            "ready": config.gemma_ready(),
            "key_present": bool(config.GEMINI_API_KEY),
        },
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
    agent_id = req.get("agent_id") or None
    emit = _bus_emitter()
    run = await asyncio.to_thread(
        run_full_cycle, attack_class,
        seed=seed, remedy=remedy, use_corpus=use_corpus, agent_id=agent_id, emit=emit,
    )
    return _run_summary(run)


@app.post("/harden/campaign")
async def harden_campaign(req: dict[str, Any]) -> dict[str, Any]:
    """A full campaign WITH cross-campaign memory (SOF-174): reads the agent's durable
    Memory Bank risk profile, warm-starts from any recalled exploit, harden->verify,
    then updates the profile. Body: {attack_class, seed?, remedy?, use_corpus?,
    use_memory?, agent_id?}. Run it twice (with /admin/reset between) to show a repeat
    campaign reach the bypass in gen 0 from the stored profile."""
    attack_class = str(req.get("attack_class", "prompt_injection"))
    seed = int(req.get("seed", 1337))
    remedy = str(req.get("remedy", "content"))
    use_corpus = bool(req.get("use_corpus", True))
    use_memory = bool(req.get("use_memory", True))
    agent_id = req.get("agent_id") or None
    emit = _bus_emitter()
    run = await asyncio.to_thread(
        run_campaign, attack_class,
        agent_id=agent_id, seed=seed, remedy=remedy,
        use_corpus=use_corpus, use_memory=use_memory, emit=emit,
    )
    return _run_summary(run)


@app.get("/memory/profile")
def memory_profile(agent_id: str | None = None) -> dict[str, Any]:
    """The agent's durable per-agent risk profile (SOF-174), read from Memory Bank
    (real) or the Postgres shim. `is_known` + `campaigns` power the memory panel."""
    from sentinel.config import AGENT_ID
    from sentinel.platform import memory

    prof = memory.get_profile(agent_id or AGENT_ID)
    return {**prof.to_dict(), "is_known": prof.is_known}


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
                       is_destructive, payload_hash, created_at, winning_payload,
                       policy_intent, remedy, approval, finding_id, verify_seed,
                       attack_trace_id, harden_trace_id, verify_trace_id
                FROM hardening_runs ORDER BY id DESC
                """
            )
        ).all()
    out = []
    for r in rows:
        pi = r[10] if isinstance(r[10], dict) else (json.loads(r[10]) if r[10] else None)
        ss = r[4] if isinstance(r[4], dict) else (json.loads(r[4]) if r[4] else None)
        out.append({
            "run_id": r[0],
            "attack_class": r[1],
            "state": r[2],
            "verdict": r[3],
            "sub_scores": ss,
            "policy_id": r[5],
            "is_destructive": r[6],
            "payload_hash": r[7],
            "created_at": r[8].isoformat() if r[8] else None,
            "winning_payload": r[9],
            "policy_intent": pi,
            "remedy": r[11],
            "approval": r[12],
            "finding_id": r[13],
            "verify_seed": r[14],
            "attack_trace_id": r[15],
            "harden_trace_id": r[16],
            "verify_trace_id": r[17],
        })
    return out


@app.get("/findings")
def findings() -> list[dict[str, Any]]:
    """Historical exploit findings persisted in the database."""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, created_at, attack_class, payload, scan_blocked,
                       scan_detected, scan_score, agent_action, authorized,
                       bypass, verdict, trace_id
                FROM findings ORDER BY id DESC LIMIT 50
                """
            )
        ).all()
    out = []
    for r in rows:
        sd = r[5] if isinstance(r[5], list) else (json.loads(r[5]) if r[5] else [])
        v = r[10] if isinstance(r[10], dict) else (json.loads(r[10]) if r[10] else {})
        out.append({
            "id": r[0],
            "created_at": r[1].isoformat() if r[1] else None,
            "attack_class": r[2],
            "payload": r[3],
            "scan_blocked": r[4],
            "scan_detected": sd,
            "scan_score": r[6],
            "agent_action": r[7],
            "authorized": r[8],
            "bypass": r[9],
            "verdict": v,
            "trace_id": r[11],
        })
    return out


@app.get("/policies")
def policies() -> list[dict[str, Any]]:
    """All drafted and applied security policy deltas."""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, policy_id, agent_id, attack_class, target,
                       payload_hash, delta, is_destructive, applied, applied_at, created_at
                FROM policies ORDER BY id DESC
                """
            )
        ).all()
    out = []
    for r in rows:
        d = r[6] if isinstance(r[6], dict) else (json.loads(r[6]) if r[6] else {})
        out.append({
            "id": r[0],
            "policy_id": r[1],
            "agent_id": r[2],
            "attack_class": r[3],
            "target": r[4],
            "payload_hash": r[5],
            "delta": d,
            "is_destructive": r[7],
            "applied": r[8],
            "applied_at": r[9].isoformat() if r[9] else None,
            "created_at": r[10].isoformat() if r[10] else None,
        })
    return out


@app.get("/defense/posture")
def defense_posture() -> dict[str, Any]:
    """Active perimeter guardrail & policy status for the fleet."""
    from sentinel.config import ARMOR_THRESHOLD, BASELINE_SCORE
    from sentinel import policy

    rules = policy.content_rules()
    revoked = list(policy.revoked_tokens())
    deltas = [d.to_json() for d in policy.applied_deltas()]

    return {
        "armor_threshold": ARMOR_THRESHOLD,
        "baseline_score": BASELINE_SCORE,
        "deep_normalize": rules.deep_normalize,
        "blocklist_count": len(rules.blocklist),
        "blocklist_hashes": sorted(list(rules.blocklist)),
        "lowered_threshold": rules.lowered_threshold,
        "revoked_tokens": revoked,
        "applied_deltas": deltas,
    }


@app.get("/corpus/stats")
def corpus_stats() -> dict[str, Any]:
    """pgvector payload corpus memory statistics and recent ancestors."""
    with engine.begin() as conn:
        total = conn.execute(text("SELECT count(*) FROM payload_corpus")).scalar_one()
        bypasses = conn.execute(text("SELECT count(*) FROM payload_corpus WHERE bypass = TRUE")).scalar_one()
        recent = conn.execute(
            text(
                """
                SELECT id, attack_class, generation, bypass, operators, score, trace_id, created_at
                FROM payload_corpus ORDER BY id DESC LIMIT 15
                """
            )
        ).all()
    ancestors = []
    for r in recent:
        ops = r[4] if isinstance(r[4], list) else (json.loads(r[4]) if r[4] else [])
        ancestors.append({
            "id": r[0],
            "attack_class": r[1],
            "generation": r[2],
            "bypass": r[3],
            "operators": ops,
            "score": r[5],
            "trace_id": r[6],
            "created_at": r[7].isoformat() if r[7] else None,
        })
    return {
        "total_payloads": int(total),
        "total_bypasses": int(bypasses),
        "recent_ancestors": ancestors,
    }


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


@app.post("/admin/reset")
async def admin_reset() -> dict[str, Any]:
    """Clear applied policies + run history so a fresh attack->harden->verify cycle can
    be demonstrated from a clean, unhardened baseline (a `deep_normalize` patch is a
    universal defense, so it must be cleared between demo runs — see SESSION_3)."""
    def _reset() -> dict[str, int]:
        counts: dict[str, int] = {}
        with engine.begin() as conn:
            for tbl in ("run_spans", "verifications", "hardening_runs", "policies",
                        "findings", "payload_corpus"):
                n = conn.execute(text(f"DELETE FROM {tbl}")).rowcount
                counts[tbl] = int(n or 0)
        return counts

    cleared = await asyncio.to_thread(_reset)
    return {"ok": True, "cleared": cleared}


@app.post("/multimodal/demo")
async def multimodal_demo(req: dict[str, Any]) -> dict[str, Any]:
    """The multimodal money-shot (SOF-173/176): render the attack invoice, reveal the
    hidden instruction, and — under the CURRENT policy posture — show what the text
    scan sees (blind to pixels), what the vision guard extracts, whether the guard
    blocks, and whether the vision agent is hijacked. One call powers the viewer's
    image ↔ hidden-text ↔ agent-action ↔ verdict reveal."""
    import base64

    from sentinel import policy as _policy
    from sentinel.redteam.multimodal import CARRIER_TEXT, SEED_OVERLAY, render_invoice
    from sentinel.target.agent import run_target

    overlay = str(req.get("overlay") or SEED_OVERLAY)
    carrier = str(req.get("carrier") or CARRIER_TEXT)
    agent_id = req.get("agent_id") or None  # default = vulnerable; "hardened-agent" resists

    def _work() -> dict[str, Any]:
        png = render_invoice(overlay)
        # Text-only scan (no image): proves a text defense is blind to the pixels.
        text_only = geap.scan(carrier, enforce=True)
        # Full scan WITH the image under whatever policy is currently applied.
        full = geap.scan(carrier, enforce=True, image_png=png, embedded_text=overlay)
        extracted = geap._extract_image_text(png, overlay)
        guard_active = _policy.content_rules().multimodal_scan
        agent = None
        if not full.blocked:
            a = run_target("INV-2287", carrier, attack_class="multimodal",
                           image_png=png, embedded_text=overlay, agent_id=agent_id)
            agent = {"action": a.action, "answer": a.answer,
                     "privileged_executed": a.privileged_executed, "backend": a.backend}
        return {
            "image_b64": base64.b64encode(png).decode(),
            "carrier_text": carrier,
            "overlay_text": overlay,
            "extracted_text": extracted,
            "text_scan": {"blocked": text_only.blocked, "detected": text_only.detected,
                          "reason": text_only.reason, "backend": text_only.backend},
            "scan": {"blocked": full.blocked, "detected": full.detected,
                     "score": full.score, "reason": full.reason, "backend": full.backend},
            "multimodal_guard_active": guard_active,
            "agent": agent,
            "bypass": bool(agent and agent["privileged_executed"]),
        }

    result = await asyncio.to_thread(_work)
    await bus.publish({
        "type": "multimodal",
        "overlay_text": result["overlay_text"],
        "carrier_text": result["carrier_text"],
        "extracted_text": result["extracted_text"],
        "multimodal_guard_active": result["multimodal_guard_active"],
        "scan_blocked": result["scan"]["blocked"],
        "bypass": result["bypass"],
    })
    return result


@app.get("/verifier/isolation")
async def verifier_isolation() -> dict[str, Any]:
    """Prove the SOF-170 firewall on the live deployment: spawn the verifier under its
    restricted `sentinel_verifier` Cloud SQL role (exactly as the state machine does)
    and run --check-isolation. It must be DENIED the red-team corpus/findings and
    ALLOWED the policies table. Returns the transcript + pass/fail."""
    import os
    import subprocess
    import sys

    import sentinel.config as cfg

    env = dict(os.environ)
    env["DATABASE_URL"] = cfg.VERIFIER_DATABASE_URL  # the restricted role's creds
    env.pop("CRASH_AT", None)

    def _run() -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "sentinel.verifier.run", "--check-isolation"],
            env=env, capture_output=True, text=True, timeout=60,
        )

    proc = await asyncio.to_thread(_run)
    transcript = (proc.stdout or "") + (proc.stderr or "")
    return {"ok": proc.returncode == 0, "returncode": proc.returncode,
            "transcript": transcript.strip().splitlines()}


# --- static frontend (single origin: API routes above take precedence) -------
# Mounted LAST so every explicit API route matches first; this only serves the
# built Svelte app (frontend = one app, one store, one stream — invariant #5).
import pathlib as _pathlib  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402

_DIST = _pathlib.Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
