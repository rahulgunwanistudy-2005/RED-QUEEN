"""The durable hardening worker (SOF-168). Polls for non-terminal runs and steps
each through the state machine, one durable transition at a time. This is the
process the demo `kill -9`s mid-HARDENING: because every state is persisted and
`geap.enforce_policy` is exactly-once, a killed worker resumes from Postgres and
drives the run to CLOSED with NO duplicate policy.

Stands in for a Cloud Run worker consuming Pub/Sub: `pending_runs()` is the queue,
the (agent_id, payload_hash) key is the dedupe key, and re-processing is safe.
"""
from __future__ import annotations

import time
from typing import Callable

from sentinel.harden import machine

Emit = Callable[[dict], None]


def drain_once(*, emit: Emit) -> int:
    """Step every pending run one transition. Returns how many runs advanced."""
    runs = machine.pending_runs()
    for run in runs:
        machine.run_to_completion(run, emit=emit)
    return len(runs)


def serve(*, emit: Emit, poll_s: float = 0.5, once: bool = False, max_idle: int = 0) -> None:
    """Durable poll loop. `once`=True drains and returns (used post-crash to resume).
    `max_idle`>0 exits after that many consecutive empty polls (keeps the CLI finite)."""
    idle = 0
    while True:
        advanced = drain_once(emit=emit)
        if once:
            return
        if advanced == 0:
            idle += 1
            if max_idle and idle >= max_idle:
                return
        else:
            idle = 0
        time.sleep(poll_s)
