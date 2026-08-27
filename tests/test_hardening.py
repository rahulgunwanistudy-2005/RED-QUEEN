"""M2 smoke tests (SOF-168..171). Requires the Postgres container + the
`sentinel_verifier` role (created by migrations/003). The verifier runs as a real
subprocess, so this is an integration smoke of the whole harden+verify loop.

Run: PYTHONPATH=. .venv/bin/python tests/test_hardening.py
"""
from __future__ import annotations

import sentinel.config as config

config.TRACE_CONSOLE = False  # keep output readable

from sqlalchemy import text

from sentinel.db import engine, run_migrations
from sentinel.harden import machine
from sentinel.harden.orchestrator import run_full_cycle
from sentinel.harden.synthesize import synthesize
from sentinel.platform import geap
from sentinel.policy import content_rules, raw_hash
from sentinel.redteam.loop import evolve
from sentinel.redteam.payloads import REFERENCE_PAYLOAD

NOOP = lambda _e: None  # noqa: E731


def _reset():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE hardening_runs, policies, verifications, run_spans RESTART IDENTITY"))


def _winner(attack_class="prompt_injection", seed=1337):
    _reset()  # measure the UNHARDENED baseline (no active policy)
    r = evolve(attack_class, seed=seed, use_corpus=False, persist_corpus=False, persist_finding=False)
    assert r.bypassed and r.winning_content
    return r.winning_content


def test_synthesis_shapes_and_destructiveness():
    w = _winner()
    content = synthesize(attack_class="prompt_injection", winning_payload=w, agent_id="triage-agent")
    assert content.rule["op"] == "deep_normalize" and content.is_destructive is False
    exact = synthesize(attack_class="prompt_injection", winning_payload=w, agent_id="triage-agent", remedy="exact")
    assert exact.rule["op"] == "blocklist_exact" and raw_hash(w) in exact.rule["hashes"]
    ident = synthesize(attack_class="prompt_injection", winning_payload=w, agent_id="triage-agent", remedy="identity")
    assert ident.rule["op"] == "revoke_identity" and ident.is_destructive is True


def test_deep_normalize_closes_the_hole():
    _reset()
    w = _winner()
    # before: the evolved winner slips past Model Armor (risk below threshold)
    assert geap.scan(w, enforce=True).blocked is False
    delta = synthesize(attack_class="prompt_injection", winning_payload=w, agent_id="triage-agent")
    geap.enforce_policy(delta.to_json())
    assert content_rules("triage-agent").deep_normalize is True
    # after: same winner is now blocked (leet families recovered by the agent decoder)
    assert geap.scan(w, enforce=True).blocked is True
    _reset()


def test_enforce_policy_is_idempotent():
    _reset()
    w = _winner()
    delta = synthesize(attack_class="prompt_injection", winning_payload=w, agent_id="triage-agent")
    r1 = geap.enforce_policy(delta.to_json())
    r2 = geap.enforce_policy(delta.to_json())
    assert r1.already is False and r2.already is True
    with engine.begin() as conn:
        n = conn.execute(text("SELECT count(*) FROM policies WHERE policy_id = :p"),
                         {"p": delta.id}).scalar_one()
    assert n == 1
    _reset()


def test_naive_seed_still_blocked_by_base_armor():
    # The base scanner blocks the naive seed regardless of any patch (risk 1.0).
    assert geap.scan(REFERENCE_PAYLOAD.content, enforce=True).blocked is True


def test_content_cycle_closes():
    _reset()
    run = run_full_cycle("prompt_injection", seed=1337, remedy="content", use_corpus=False, emit=NOOP)
    assert run is not None and run.state == machine.CLOSED, run.state
    assert run.verdict == "CLOSED"
    assert all(run.sub_scores.values()), run.sub_scores
    _reset()


def test_weak_exact_patch_is_false_closed():
    _reset()
    run = run_full_cycle("prompt_injection", seed=1337, remedy="exact", use_corpus=False, emit=NOOP)
    assert run is not None and run.state == machine.FALSE_CLOSED, run.state
    # the independent verifier re-evolved a variant the exact-hash blocklist misses
    assert run.sub_scores["armor_blocked"] is False
    _reset()


def test_destructive_gate_and_approval_resume():
    _reset()
    run = run_full_cycle("prompt_injection", seed=1337, remedy="identity", use_corpus=False, emit=NOOP)
    assert run is not None and run.state == machine.AWAIT_APPROVAL, run.state
    # no policy applied while awaiting approval
    with engine.begin() as conn:
        applied = conn.execute(text("SELECT count(*) FROM policies WHERE applied")).scalar_one()
    assert applied == 0
    run = machine.set_approval(run.id, "approved", emit=NOOP)
    run = machine.run_to_completion(run, emit=NOOP)
    assert run.state == machine.CLOSED, run.state
    _reset()


def test_verifier_role_cannot_read_corpus():
    from sqlalchemy import create_engine

    veng = create_engine(config.VERIFIER_DATABASE_URL, future=True)
    for denied in ("payload_corpus", "findings"):
        try:
            with veng.begin() as conn:
                conn.execute(text(f"SELECT count(*) FROM {denied}")).scalar_one()
            raise AssertionError(f"firewall breached: verifier read {denied}")
        except Exception as exc:
            assert "permission denied" in str(exc).lower(), str(exc)
    # but it CAN read the policies it must test
    with veng.begin() as conn:
        conn.execute(text("SELECT count(*) FROM policies")).scalar_one()
    veng.dispose()


if __name__ == "__main__":
    run_migrations()
    test_synthesis_shapes_and_destructiveness()
    test_deep_normalize_closes_the_hole()
    test_enforce_policy_is_idempotent()
    test_naive_seed_still_blocked_by_base_armor()
    test_content_cycle_closes()
    test_weak_exact_patch_is_false_closed()
    test_destructive_gate_and_approval_resume()
    test_verifier_role_cannot_read_corpus()
    print("m2 smoke ok")
