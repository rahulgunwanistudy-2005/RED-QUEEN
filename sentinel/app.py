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

from sentinel.config import USE_REAL
from sentinel.db import ping, run_migrations
from sentinel.gateway import handle_request
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
