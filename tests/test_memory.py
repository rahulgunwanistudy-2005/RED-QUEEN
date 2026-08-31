"""M3 Memory Bank tests (SOF-174). Requires the Postgres container.

Runs against the shim tier (deterministic). The real Vertex Agent Engine Memory Bank
branch is exercised behind USE_REAL_MEMORY=1 in the handoff verification, not in unit
tests (it needs GCP + is eventually consistent).

Run: PYTHONPATH=. .venv/bin/pytest tests/test_memory.py
"""
from __future__ import annotations

import sentinel.config as config

config.TRACE_CONSOLE = False

from sqlalchemy import text

from sentinel.db import engine, run_migrations
from sentinel.harden.orchestrator import run_campaign
from sentinel.platform import memory

run_migrations()

AGENT = "triage-agent"


def _wipe(include_memory: bool):
    tbls = ["run_spans", "verifications", "hardening_runs", "policies", "findings", "payload_corpus"]
    if include_memory:
        tbls.append("agent_memory")
    with engine.begin() as conn:
        for t in tbls:
            conn.execute(text(f"DELETE FROM {t}"))


def test_profile_empty_then_recorded():
    _wipe(include_memory=True)
    p = memory.get_profile(AGENT)
    assert p.is_known is False and p.campaigns == 0
    memory.record_campaign(AGENT, attack_class="prompt_injection",
                           winning_operators=("obfuscate_tool",), applied_policy_op="deep_normalize")
    p2 = memory.get_profile(AGENT)
    assert p2.campaigns == 1 and "prompt_injection" in p2.known_weaknesses
    assert p2.winning_operators["prompt_injection"] == ["obfuscate_tool"]
    _wipe(include_memory=True)


def test_repeat_campaign_recalls_and_is_faster():
    _wipe(include_memory=True)
    # Campaign 1: cold, evolve from scratch.
    ev1 = []
    run1 = run_campaign("prompt_injection", seed=1337, emit=lambda e: ev1.append(e))
    gen1 = next(e["winning_generation"] for e in ev1 if e.get("type") == "memory" and "winning_generation" in e)
    assert run1.verdict == "CLOSED" and gen1 >= 1  # earned the bypass over generations

    # Between campaigns: wipe attack state + corpus (the "goldfish"), KEEP Memory Bank.
    _wipe(include_memory=False)

    # Campaign 2: warm — recalls the exploit from Memory Bank, bypass in gen 0.
    ev2 = []
    run2 = run_campaign("prompt_injection", seed=1337, emit=lambda e: ev2.append(e))
    gen2 = next(e["winning_generation"] for e in ev2 if e.get("type") == "memory" and "winning_generation" in e)
    recalled = next(e["recalled"] for e in ev2 if e.get("type") == "memory" and "recalled" in e)
    assert run2.verdict == "CLOSED"
    assert gen2 == 0 and recalled is True and gen2 < gen1  # faster to the bypass
    _wipe(include_memory=True)
