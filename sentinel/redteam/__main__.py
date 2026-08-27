"""Run the evolutionary red-team loop from the command line.

    python -m sentinel.redteam --attack-class prompt_injection --seed 1337
    python -m sentinel.redteam --both --seed 1337
    python -m sentinel.redteam --attack-class tool_poisoning --no-corpus   # reproducible

Streams every candidate/score event to the running server (best-effort, so the
frontend lineage tree updates live) and prints a readable generation-by-generation
transcript.
"""
from __future__ import annotations

import argparse
import sys

from sentinel.config import SERVER_URL
from sentinel.db import run_migrations
from sentinel.redteam.loop import EvolveResult, evolve

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
                pass  # server not running is fine for the CLI
        if quiet:
            return
        _print_event(event)

    return emit


def _print_event(e: dict) -> None:
    kind = e.get("type")
    if kind == "candidate":
        flag = "BYPASS ✅" if e["bypass"] else ("BLOCKED 🛡" if e["blocked"] else "passed")
        ops = ",".join(e["operators"]) or "—"
        corpus = " [corpus]" if e.get("origin") == "corpus" else ""
        print(
            f"  gen{e['generation']} {e['id']:<26} risk={e['scan_score']:<4} "
            f"{flag:<10} ops=[{ops}]{corpus}"
        )
    elif kind == "corpus":
        print(
            f"  ↺ corpus: gen{e['generation']} reused ancestors {e['used_ancestors']} "
            f"ops={e['operators']}"
        )
    elif kind == "score":
        print(f"  ── gen{e['generation']} score={e['value']} band={e['band']}")


def _print_summary(r: EvolveResult) -> None:
    print(f"\n=== {r.attack_class} (seed={r.seed}) ===")
    for g in r.generations:
        print(
            f"  gen{g.generation}: pop={g.population} blocked={g.blocked} "
            f"bypassed={g.bypassed} best_risk={g.best_scan_score}"
        )
    if r.bypassed:
        print(
            f"  → BYPASS landed at generation {r.winning_generation} "
            f"(payload {r.winning_payload_id})"
        )
        print(f"  → winning payload:\n      {r.winning_content!r}")
    else:
        print("  → no bypass within max_gen")
    if r.used_corpus_ancestors:
        print(f"  → mutation used retrieved ancestors: {sorted(set(r.used_corpus_ancestors))}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel.redteam")
    parser.add_argument("--attack-class", choices=_ATTACK_CLASSES, default="prompt_injection")
    parser.add_argument("--both", action="store_true", help="run both attack classes")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--max-gen", type=int, default=6)
    parser.add_argument("--population", type=int, default=4)
    parser.add_argument("--survivors", type=int, default=2)
    parser.add_argument("--no-corpus", action="store_true", help="disable corpus retrieval (reproducible)")
    parser.add_argument("--trace", action="store_true", help="print OTel spans to console")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not args.trace:
        import sentinel.config as cfg

        cfg.TRACE_CONSOLE = False

    run_migrations()
    emit = _make_emitter(args.quiet)
    classes = _ATTACK_CLASSES if args.both else (args.attack_class,)

    all_bypassed = True
    for ac in classes:
        print(f"\n▶ evolving {ac} …")
        result = evolve(
            ac,
            seed=args.seed,
            max_gen=args.max_gen,
            population=args.population,
            survivors=args.survivors,
            use_corpus=not args.no_corpus,
            emit=emit,
        )
        _print_summary(result)
        all_bypassed = all_bypassed and result.bypassed

    return 0 if all_bypassed else 1


if __name__ == "__main__":
    raise SystemExit(main())
