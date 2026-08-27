"""Drive the M2 harden+verify loop from the command line.

    # one full attack -> harden -> verify cycle (strong content patch -> CLOSED)
    python -m sentinel.harden cycle --attack-class prompt_injection --seed 1337

    # weak exact-string patch -> verifier flags FALSE_CLOSED (SOF-170 honesty proof)
    python -m sentinel.harden cycle --attack-class prompt_injection --remedy exact

    # destructive identity revocation -> pauses at AWAIT_APPROVAL (SOF-171)
    python -m sentinel.harden cycle --attack-class prompt_injection --remedy identity

    # the durable worker (the process the kill -9 proof restarts)
    python -m sentinel.harden worker --max-idle 4

Streams state/policy/approval/verdict events to the running server (best-effort) so
the frontend verdict panel + trace waterfall update live.
"""
from __future__ import annotations

import argparse

from sentinel.config import SERVER_URL
from sentinel.db import run_migrations
from sentinel.harden import machine, worker
from sentinel.harden.orchestrator import run_full_cycle

_ATTACK_CLASSES = ("prompt_injection", "tool_poisoning")


def _make_emitter(quiet: bool):
    try:
        import httpx

        client = httpx.Client(timeout=2.0)
    except Exception:
        client = None

    def emit(event: dict) -> None:
        if client is not None:
            try:
                client.post(f"{SERVER_URL}/events", json=event)
            except Exception:
                pass
        if not quiet:
            _print_event(event)

    return emit


def _print_event(e: dict) -> None:
    kind = e.get("type")
    if kind == "candidate":
        flag = "BYPASS ✅" if e["bypass"] else ("BLOCKED 🛡" if e["blocked"] else "passed")
        ops = ",".join(e["operators"]) or "—"
        print(f"  gen{e['generation']} {e['id']:<26} risk={e['scan_score']:<4} {flag:<10} ops=[{ops}]")
    elif kind == "state":
        note = f" — {e['note']}" if e.get("note") else ""
        print(f"  ▸ [{e.get('phase','')}] STATE={e['state']} (run {e.get('run_id')}){note}")
    elif kind == "policy":
        if e.get("applied"):
            tag = "APPLIED (no-op replay)" if e.get("already") else "APPLIED"
            print(f"  ⛊ policy {e['policy_id']} {tag}")
        else:
            print(f"  ✎ policy drafted {e['policy_id']} target={e.get('target')} "
                  f"destructive={e.get('is_destructive')} rule={e.get('rule')}")
    elif kind == "approval":
        print(f"  ⏸ AWAIT_APPROVAL run={e['run_id']} policy={e['policy_id']} — {e.get('note')}")
    elif kind == "verdict":
        print(f"  ⚖ VERDICT run={e['run_id']} = {e['verdict']}  sub_scores={e['sub_scores']}")
    elif kind == "score":
        print(f"  ══ score={e['value']} band={e['band']} verdict={e.get('verdict')}")


def _print_run(run) -> None:
    if run is None:
        print("  → attack did not bypass; nothing to harden")
        return
    print(f"\n  === run {run.id} [{run.attack_class}] ===")
    print(f"    state    : {run.state}")
    print(f"    policy   : {run.policy_id} (destructive={run.is_destructive})")
    print(f"    verdict  : {run.verdict}  sub_scores={run.sub_scores}")
    if run.state == machine.AWAIT_APPROVAL:
        print(f"    → paused for approval: python -m sentinel.harden approve --run-id {run.id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel.harden")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cycle", help="run one full attack->harden->verify cycle")
    c.add_argument("--attack-class", choices=_ATTACK_CLASSES, default="prompt_injection")
    c.add_argument("--both", action="store_true")
    c.add_argument("--seed", type=int, default=1337)
    c.add_argument("--remedy", choices=("content", "identity", "exact"), default="content")
    c.add_argument("--no-corpus", action="store_true")
    c.add_argument("--quiet", action="store_true")

    w = sub.add_parser("worker", help="durable worker: drive pending runs to completion")
    w.add_argument("--once", action="store_true", help="drain once and exit (post-crash resume)")
    w.add_argument("--max-idle", type=int, default=4)
    w.add_argument("--quiet", action="store_true")

    a = sub.add_parser("approve", help="approve/reject a run paused at AWAIT_APPROVAL")
    a.add_argument("--run-id", type=int, required=True)
    a.add_argument("--reject", action="store_true")
    a.add_argument("--no-resume", action="store_true", help="record decision only; don't drive")

    sub.add_parser("check-isolation", help="prove the verifier DB firewall")

    args = parser.parse_args(argv)

    # Keep OTel spans off the transcript (they're still emitted); mirrors the M1 CLI.
    import sentinel.config as cfg
    cfg.TRACE_CONSOLE = False

    run_migrations()

    if args.cmd == "check-isolation":
        # Prove the firewall under the ACTUAL restricted role: spawn the verifier
        # subprocess with DATABASE_URL pointed at the sentinel_verifier credentials.
        import os
        import subprocess
        import sys

        from sentinel.config import VERIFIER_DATABASE_URL

        env = dict(os.environ)
        env["DATABASE_URL"] = VERIFIER_DATABASE_URL
        print(f"  (running as restricted role: {VERIFIER_DATABASE_URL.split('@')[0].split('//')[-1]})")
        return subprocess.run(
            [sys.executable, "-m", "sentinel.verifier.run", "--check-isolation"],
            env=env, check=False,
        ).returncode

    emit = _make_emitter(getattr(args, "quiet", False))

    if args.cmd == "cycle":
        classes = _ATTACK_CLASSES if args.both else (args.attack_class,)
        rc = 0
        for ac in classes:
            print(f"\n▶ harden cycle: {ac} (remedy={args.remedy}, seed={args.seed})")
            run = run_full_cycle(ac, seed=args.seed, remedy=args.remedy,
                                 use_corpus=not args.no_corpus, emit=emit)
            _print_run(run)
            if run is not None and run.state not in (machine.CLOSED, machine.AWAIT_APPROVAL):
                rc = 1
        return rc

    if args.cmd == "worker":
        worker.serve(emit=emit, once=args.once, max_idle=args.max_idle)
        return 0

    if args.cmd == "approve":
        decision = "rejected" if args.reject else "approved"
        run = machine.set_approval(args.run_id, decision, emit=emit)
        if run is None:
            print(f"  run {args.run_id} not found")
            return 1
        print(f"  run {args.run_id} -> {decision}")
        if decision == "approved" and not args.no_resume:
            run = machine.run_to_completion(run, emit=emit)
            _print_run(run)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
