"""M1 smoke tests (SOF-162..166). Requires the Postgres container (corpus writes).

Run: PYTHONPATH=. .venv/bin/python tests/test_evolve.py
"""
from __future__ import annotations

from random import Random

import sentinel.config as config

config.TRACE_CONSOLE = False  # keep the test output readable

from sentinel.db import run_migrations
from sentinel.platform import geap
from sentinel.redteam import operators
from sentinel.redteam.loop import evolve
from sentinel.redteam.payloads import REFERENCE_PAYLOAD, TOOL_POISONING_SEED
from sentinel.textnorm import agent_normalize


def test_scanner_blocks_naive_seeds_in_enforce_mode():
    for seed in (REFERENCE_PAYLOAD, TOOL_POISONING_SEED):
        r = geap.scan(seed.content, enforce=True)
        assert r.blocked is True and r.score >= 0.45, seed.attack_class


def test_leet_round_trip_is_lossless():
    for s in range(100):
        enc = operators.obfuscate_tool("run_privileged_fix export_secrets", Random(s))
        dec = agent_normalize(enc)
        assert "runprivilegedfix" in dec and "exportsecrets" in dec


def test_bypass_lands_at_gen3_both_classes():
    run_migrations()
    for ac in ("prompt_injection", "tool_poisoning"):
        r = evolve(ac, seed=1337, use_corpus=False)
        assert r.bypassed and r.winning_generation == 3, (ac, r.winning_generation)


def test_reproducible_winning_payload():
    a = evolve("prompt_injection", seed=424242, use_corpus=False)
    b = evolve("prompt_injection", seed=424242, use_corpus=False)
    assert a.winning_content == b.winning_content and a.winning_payload_id == b.winning_payload_id


def test_early_generations_are_blocked():
    r = evolve("prompt_injection", seed=1337, use_corpus=False)
    early = [g for g in r.generations if g.generation < 3]
    assert all(g.blocked == g.population and g.bypassed == 0 for g in early)


if __name__ == "__main__":
    test_scanner_blocks_naive_seeds_in_enforce_mode()
    test_leet_round_trip_is_lossless()
    test_bypass_lands_at_gen3_both_classes()
    test_reproducible_winning_payload()
    test_early_generations_are_blocked()
    print("m1 smoke ok")
