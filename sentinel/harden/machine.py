"""The hardening state machine (SOF-168) — a table + a reducer, not a framework.

One durable row per `(agent_id, payload_hash)` in `hardening_runs`; one `state`
column; one transition function `step()`. Each transition is committed to Postgres
before the next begins, so a `kill -9` at any point resumes from the last durable
state. The load-bearing property is IDEMPOTENCY:

  - The run row is opened with INSERT ... ON CONFLICT (agent_id, payload_hash) DO
    NOTHING, so a Pub/Sub redelivery of the same bypass reuses the SAME run.
  - Intent-to-apply (the drafted policy delta) is written in the BYPASS_FOUND ->
    HARDENING transition, BEFORE `geap.enforce_policy` is ever called.
  - `geap.enforce_policy` is itself exactly-once (INSERT ON CONFLICT on policy_id).
    So re-entering HARDENING after a crash re-invokes enforce_policy but applies
    NOTHING the second time — exactly one policy row, one effect.

State flow (SOF-168 / SOF-171):
    BYPASS_FOUND -> HARDENING -> [AWAIT_APPROVAL ->] VERIFYING -> CLOSED
                                   (only when the delta is_destructive)
Verdict-typed terminals: CLOSED | FALSE_CLOSED | STILL_OPEN (the verifier rules).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy import text

import sentinel.config as config
from sentinel.harden import synthesize
from sentinel.platform import geap

Emit = Callable[[dict], None]

BYPASS_FOUND = "BYPASS_FOUND"
HARDENING = "HARDENING"
AWAIT_APPROVAL = "AWAIT_APPROVAL"
VERIFYING = "VERIFYING"
CLOSED = "CLOSED"
FALSE_CLOSED = "FALSE_CLOSED"
STILL_OPEN = "STILL_OPEN"

TERMINAL = {CLOSED, FALSE_CLOSED, STILL_OPEN}
_VERDICT_STATE = {"CLOSED": CLOSED, "FALSE_CLOSED": FALSE_CLOSED, "STILL_OPEN": STILL_OPEN}


@dataclass
class Run:
    id: int
    agent_id: str
    payload_hash: str
    attack_class: str
    state: str
    finding_id: int | None
    winning_payload: str
    remedy: str
    policy_id: str | None
    policy_intent: dict | None
    is_destructive: bool
    approval: str | None
    verdict: str | None
    sub_scores: dict | None
    verify_seed: int
    attack_trace_id: str | None
    harden_trace_id: str | None
    verify_trace_id: str | None
    created_at: Any = None


def _engine():
    from sentinel.db import engine
    return engine


_COLS = (
    "id, agent_id, payload_hash, attack_class, state, finding_id, winning_payload, "
    "remedy, policy_id, policy_intent, is_destructive, approval, verdict, sub_scores, "
    "verify_seed, attack_trace_id, harden_trace_id, verify_trace_id, created_at"
)


def _row_to_run(r) -> Run:
    def js(v):
        if v is None or isinstance(v, dict):
            return v
        return json.loads(v)

    return Run(
        id=r[0], agent_id=r[1], payload_hash=r[2], attack_class=r[3], state=r[4],
        finding_id=r[5], winning_payload=r[6], remedy=r[7], policy_id=r[8],
        policy_intent=js(r[9]), is_destructive=bool(r[10]), approval=r[11],
        verdict=r[12], sub_scores=js(r[13]), verify_seed=r[14],
        attack_trace_id=r[15], harden_trace_id=r[16], verify_trace_id=r[17],
        created_at=r[18],
    )


def get_run(run_id: int) -> Run | None:
    with _engine().begin() as conn:
        r = conn.execute(
            text(f"SELECT {_COLS} FROM hardening_runs WHERE id = :id"), {"id": run_id}
        ).fetchone()
    return _row_to_run(r) if r else None


def open_run(
    *,
    agent_id: str,
    attack_class: str,
    winning_payload: str,
    payload_hash: str,
    finding_id: int | None = None,
    verify_seed: int = 0,
    remedy: str = "content",
    attack_trace_id: str | None = None,
) -> Run:
    """Create (or return the existing) run for a confirmed bypass. Idempotent on the
    (agent_id, payload_hash) key — a redelivery of the same bypass reuses the row."""
    with _engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO hardening_runs
                    (agent_id, payload_hash, attack_class, state, finding_id,
                     winning_payload, remedy, verify_seed, attack_trace_id)
                VALUES
                    (:aid, :ph, :ac, :state, :fid, :wp, :remedy, :vseed, :atid)
                ON CONFLICT (agent_id, payload_hash) DO NOTHING
                """
            ),
            {
                "aid": agent_id, "ph": payload_hash, "ac": attack_class,
                "state": BYPASS_FOUND, "fid": finding_id, "wp": winning_payload,
                "remedy": remedy, "vseed": verify_seed, "atid": attack_trace_id,
            },
        )
        r = conn.execute(
            text(f"SELECT {_COLS} FROM hardening_runs WHERE agent_id=:aid AND payload_hash=:ph"),
            {"aid": agent_id, "ph": payload_hash},
        ).fetchone()
    return _row_to_run(r)


def _update(run_id: int, **fields) -> None:
    fields["updated_at"] = None  # sentinel; replaced below with now()
    sets = []
    params: dict[str, Any] = {"id": run_id}
    for k, v in fields.items():
        if k == "updated_at":
            sets.append("updated_at = now()")
            continue
        if isinstance(v, (dict, list)):
            sets.append(f"{k} = (:{k})::jsonb")
            params[k] = json.dumps(v)
        else:
            sets.append(f"{k} = :{k}")
            params[k] = v
    with _engine().begin() as conn:
        conn.execute(text(f"UPDATE hardening_runs SET {', '.join(sets)} WHERE id = :id"), params)


def record_span(run_id: int, phase: str, name: str, trace_id: str,
                started_ms: float, duration_ms: float, attributes: dict | None = None) -> None:
    with _engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO run_spans (run_id, phase, name, trace_id, started_ms,
                                       duration_ms, attributes)
                VALUES (:rid, :ph, :nm, :tid, :st, :dur, (:attrs)::jsonb)
                """
            ),
            {"rid": run_id, "ph": phase, "nm": name, "tid": trace_id,
             "st": started_ms, "dur": duration_ms, "attrs": json.dumps(attributes or {})},
        )


def _elapsed_ms(run: Run) -> float:
    if run.created_at is None:
        return 0.0
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    return max(0.0, (now - run.created_at).total_seconds() * 1000.0)


def _crash_hook(label: str, run: Run, emit: Emit) -> None:
    """Fault-injection point for the SOF-168 kill -9 proof. When env CRASH_AT matches
    `label`, publish where we are, write our PID to CRASH_PIDFILE, and BLOCK so an
    EXTERNAL `kill -9 $PID` lands at exactly this durability boundary. This is a real
    SIGKILL of a real process mid-HARDENING — not a simulated crash."""
    if os.environ.get("CRASH_AT") != label:
        return
    pid = os.getpid()
    emit({"type": "state", "run_id": run.id, "state": run.state,
          "note": f"CRASH_HOOK {label} pid={pid} — awaiting external kill -9", "phase": "harden"})
    pidfile = os.environ.get("CRASH_PIDFILE")
    if pidfile:
        with open(pidfile, "w") as fh:
            fh.write(str(pid))
    # Block long enough for the proof script to kill -9 us. If nobody kills, time out
    # so an accidental CRASH_AT can't wedge the worker forever.
    time.sleep(float(os.environ.get("CRASH_STALL_S", "30")))


def step(run: Run, *, emit: Emit, spawn_verifier=None) -> Run:
    """Advance the run by exactly ONE durable transition and return the fresh row.
    Safe to call repeatedly (each state's action is idempotent)."""
    state = run.state

    # BYPASS_FOUND -> HARDENING : draft the policy delta (intent) BEFORE any apply.
    if state == BYPASS_FOUND:
        delta = synthesize.synthesize(
            attack_class=run.attack_class, winning_payload=run.winning_payload,
            agent_id=run.agent_id, remedy=run.remedy,
        )
        _update(
            run.id, state=HARDENING, policy_id=delta.id,
            policy_intent=delta.to_json(), is_destructive=delta.is_destructive,
        )
        emit({"type": "policy", "run_id": run.id, "phase": "harden",
              "policy_id": delta.id, "target": delta.target,
              "is_destructive": delta.is_destructive, "rule": delta.rule,
              "rationale": delta.rationale, "attack_class": run.attack_class})
        emit({"type": "state", "run_id": run.id, "state": HARDENING, "phase": "harden",
              "note": "policy intent persisted (pre-apply)"})
        return get_run(run.id)

    # HARDENING : gate on approval if destructive, else apply the policy (idempotent).
    if state == HARDENING:
        if run.is_destructive and run.approval != "approved":
            if run.approval == "rejected":
                emit({"type": "state", "run_id": run.id, "state": AWAIT_APPROVAL,
                      "phase": "harden", "note": "destructive delta rejected — parked"})
                _update(run.id, state=AWAIT_APPROVAL)
                return get_run(run.id)
            _update(run.id, state=AWAIT_APPROVAL)
            emit({"type": "approval", "run_id": run.id, "phase": "harden",
                  "policy_id": run.policy_id, "attack_class": run.attack_class,
                  "rule": (run.policy_intent or {}).get("rule"),
                  "rationale": (run.policy_intent or {}).get("rationale"),
                  "note": "destructive policy awaiting human approval"})
            emit({"type": "state", "run_id": run.id, "state": AWAIT_APPROVAL, "phase": "harden"})
            return get_run(run.id)

        # apply (exactly-once). CRASH_AT hooks straddle the enforce_policy call.
        _crash_hook("hardening_apply", run, emit)
        t0 = time.perf_counter()
        result = geap.enforce_policy(run.policy_intent or {})
        harden_trace = geap.emit_trace({
            "name": "sentinel.harden.apply", "run_id": run.id,
            "policy_id": result.policy_id, "already_applied": result.already,
            "attack_class": run.attack_class,
        })
        dur = (time.perf_counter() - t0) * 1000.0
        _crash_hook("post_apply", run, emit)  # THE idempotency trap: crash after apply, pre-commit
        record_span(run.id, "harden", "sentinel.harden.apply", harden_trace,
                    _elapsed_ms(run), dur,
                    {"policy_id": result.policy_id, "already_applied": result.already})
        _update(run.id, state=VERIFYING, harden_trace_id=harden_trace)
        emit({"type": "policy", "run_id": run.id, "phase": "harden",
              "policy_id": result.policy_id, "applied": True, "already": result.already,
              "note": "policy applied (no-op replay)" if result.already else "policy applied"})
        emit({"type": "state", "run_id": run.id, "state": VERIFYING, "phase": "harden"})
        return get_run(run.id)

    # AWAIT_APPROVAL : resume on approval (SOF-171).
    if state == AWAIT_APPROVAL:
        if run.approval == "approved":
            _update(run.id, state=HARDENING)
            emit({"type": "state", "run_id": run.id, "state": HARDENING, "phase": "harden",
                  "note": "approved — resuming"})
            return get_run(run.id)
        return run  # parked until an approval event arrives

    # VERIFYING : run the FIREWALLED verifier (SOF-170) and read its independent verdict.
    if state == VERIFYING:
        verify_dur = 0.0
        verdict = _read_verification(run.id)
        if verdict is None:
            spawn = spawn_verifier or _default_spawn_verifier
            t0 = time.perf_counter()
            spawn(run)
            verify_dur = (time.perf_counter() - t0) * 1000.0
            verdict = _read_verification(run.id)
        if verdict is None:
            _update(run.id, error="verifier produced no verdict")
            emit({"type": "state", "run_id": run.id, "state": VERIFYING,
                  "phase": "verify", "note": "verifier produced no verdict"})
            return get_run(run.id)

        vstate = _VERDICT_STATE.get(verdict["verdict"], STILL_OPEN)
        if verdict.get("verify_trace_id"):
            record_span(run.id, "verify", "sentinel.verify", verdict["verify_trace_id"],
                        _elapsed_ms(run), verify_dur or float(verdict.get("duration_ms", 0.0)),
                        verdict.get("sub_scores", {}))
        _update(run.id, state=vstate, verdict=verdict["verdict"],
                sub_scores=verdict["sub_scores"], verify_trace_id=verdict.get("verify_trace_id"))
        emit({"type": "verdict", "run_id": run.id, "phase": "verify",
              "verdict": verdict["verdict"], "sub_scores": verdict["sub_scores"],
              "attack_class": run.attack_class, "policy_id": run.policy_id,
              "evolved_bypass": verdict.get("evolved_bypass"),
              "seed_blocked": verdict.get("seed_blocked")})
        emit({"type": "state", "run_id": run.id, "state": vstate, "phase": "verify"})
        # score event: green when truly CLOSED, red otherwise (drives the dial).
        emit({"type": "score", "value": 96 if vstate == CLOSED else 41,
              "band": "green" if vstate == CLOSED else "red",
              "bypass": vstate != CLOSED, "attack_class": run.attack_class,
              "verdict": verdict["verdict"], "run_id": run.id})
        return get_run(run.id)

    return run  # terminal


def _read_verification(run_id: int) -> dict | None:
    with _engine().begin() as conn:
        r = conn.execute(
            text(
                """
                SELECT verdict, sub_scores, verify_trace_id, evolved_bypass, seed_blocked
                FROM verifications WHERE run_id = :rid ORDER BY id DESC LIMIT 1
                """
            ),
            {"rid": run_id},
        ).fetchone()
    if not r:
        return None
    ss = r[1] if isinstance(r[1], dict) else json.loads(r[1])
    return {"verdict": r[0], "sub_scores": ss, "verify_trace_id": r[2],
            "evolved_bypass": bool(r[3]), "seed_blocked": bool(r[4]), "duration_ms": 0.0}


def _default_spawn_verifier(run: Run) -> None:
    """Launch the firewalled verifier as a SEPARATE PROCESS under its restricted DB
    role (SOF-170). No shared Python objects; the winning payload is NOT passed —
    only (attack_class, seed, run_id). The subprocess re-derives independently."""
    import subprocess
    import sys

    env = dict(os.environ)
    # The isolation seam: the verifier's whole process talks to Postgres as the
    # restricted `sentinel_verifier` role, which is DENIED the corpus + findings.
    env["DATABASE_URL"] = config.VERIFIER_DATABASE_URL
    env.pop("CRASH_AT", None)  # never inherit the fault injector into the verifier
    subprocess.run(
        [sys.executable, "-m", "sentinel.verifier.run",
         "--run-id", str(run.id),
         "--attack-class", run.attack_class,
         "--seed", str(run.verify_seed)],
        env=env, check=False,
    )


def run_to_completion(run: Run, *, emit: Emit, max_steps: int = 12) -> Run:
    """Drive a run through the machine until it parks (AWAIT_APPROVAL) or terminates."""
    for _ in range(max_steps):
        if run.state in TERMINAL:
            return run
        before = run.state
        run = step(run, emit=emit)
        if run.state == before:  # parked (e.g. AWAIT_APPROVAL without approval)
            return run
    return run


def set_approval(run_id: int, decision: str, *, emit: Emit | None = None) -> Run | None:
    """Record a human approve/reject on a run (SOF-171)."""
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be 'approved' or 'rejected'")
    run = get_run(run_id)
    if run is None:
        return None
    _update(run_id, approval=decision)
    if emit:
        emit({"type": "state", "run_id": run_id, "state": run.state, "phase": "harden",
              "note": f"human {decision}", "approval": decision})
    return get_run(run_id)


def pending_runs() -> list[Run]:
    """Non-terminal runs the worker should drive (skips AWAIT_APPROVAL awaiting a human)."""
    with _engine().begin() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT {_COLS} FROM hardening_runs
                WHERE state NOT IN ('CLOSED','FALSE_CLOSED','STILL_OPEN')
                  AND NOT (state = 'AWAIT_APPROVAL' AND (approval IS NULL OR approval = 'rejected'))
                ORDER BY id
                """
            )
        ).all()
    return [_row_to_run(r) for r in rows]
