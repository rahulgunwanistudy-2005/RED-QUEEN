"""M3 multimodal attack-class tests (SOF-173). Requires the Postgres container.

The load-bearing claim: the multimodal bypass is closed by a DISTINCT mechanism
(vision extraction), not by the text-side deep_normalize — a text defense is blind
to an instruction carried in pixels. These run in shim mode (deterministic).

Run: PYTHONPATH=. .venv/bin/pytest tests/test_multimodal.py
"""
from __future__ import annotations

import sentinel.config as config

config.TRACE_CONSOLE = False

from sqlalchemy import text

from sentinel.db import engine, run_migrations
from sentinel.fire import fire
from sentinel.harden.orchestrator import run_full_cycle
from sentinel.harden.synthesize import synthesize
from sentinel.platform import geap
from sentinel.policy import PolicyDelta, raw_hash
from sentinel.redteam.multimodal import SEED_OVERLAY, render_invoice
from sentinel.redteam.payloads import MULTIMODAL_SEED

run_migrations()


def _reset():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE hardening_runs, policies, verifications, run_spans, "
                          "findings, payload_corpus RESTART IDENTITY"))


def test_invoice_renders_png():
    png = render_invoice(SEED_OVERLAY)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 1000


def test_unhardened_multimodal_bypasses_and_text_scan_is_blind():
    _reset()
    o = fire(MULTIMODAL_SEED, enforce=True, persist_finding=False)
    assert o.bypass is True          # the hidden-instruction image hijacks the agent
    assert o.scan_blocked is False   # the text guardrail never saw the malicious text


def test_deep_normalize_alone_does_not_close_multimodal():
    # A text defense (deep_normalize) applied to the multimodal class must remain blind.
    _reset()
    ph = raw_hash(MULTIMODAL_SEED.content)
    dn = PolicyDelta(id=f"pol-mm-content-{ph}", target="model_armor",
                     agent_id=config.AGENT_ID, attack_class="multimodal", payload_hash=ph,
                     rule={"op": "deep_normalize"}, is_destructive=False)
    geap.enforce_policy(dn.to_json())
    o = fire(MULTIMODAL_SEED, enforce=True, persist_finding=False)
    assert o.bypass is True and o.scan_blocked is False
    _reset()


def test_multimodal_guard_blocks_after_hardening():
    _reset()
    mm = synthesize(attack_class="multimodal", winning_payload=MULTIMODAL_SEED.content,
                    agent_id=config.AGENT_ID, remedy="multimodal")
    assert mm.rule["op"] == "multimodal_scan" and mm.target == "model_armor"
    geap.enforce_policy(mm.to_json())
    o = fire(MULTIMODAL_SEED, enforce=True, persist_finding=False)
    assert o.scan_blocked is True and o.bypass is False
    _reset()


def test_multimodal_full_cycle_closes():
    _reset()
    run = run_full_cycle("multimodal", seed=1337)
    assert run is not None and run.verdict == "CLOSED" and run.remedy == "multimodal"
    _reset()
