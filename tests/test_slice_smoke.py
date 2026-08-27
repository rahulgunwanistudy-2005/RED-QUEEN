"""Smoke test for the M0 thin slice. Requires the Postgres container (docker compose up db).

Run: .venv/bin/python -m pytest tests/ -q   (or plain: python tests/test_slice_smoke.py)
"""
from __future__ import annotations

from sentinel.db import run_migrations
from sentinel.platform import geap
from sentinel.slice.core import run_thin_slice


def test_scan_detects_reference_injection():
    from sentinel.redteam import REFERENCE_PAYLOAD

    result = geap.scan(REFERENCE_PAYLOAD.content)
    assert "prompt_injection" in result.detected
    assert result.blocked is False  # M0 baseline: detection-only, injection passes through


def test_thin_slice_reports_bypass_and_persists():
    run_migrations()
    verdict, score_event = run_thin_slice()
    assert verdict.bypass is True
    assert verdict.agent_action == "run_privileged_fix"
    assert verdict.score == 41 and verdict.band == "red"
    assert len(verdict.trace_id) == 32
    assert verdict.finding_id is not None
    assert score_event["type"] == "score" and score_event["bypass"] is True


if __name__ == "__main__":
    test_scan_detects_reference_injection()
    test_thin_slice_reports_bypass_and_persists()
    print("smoke ok")
