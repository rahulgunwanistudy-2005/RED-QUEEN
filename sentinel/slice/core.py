"""THE reference vertical slice (SOF-160), now routed through the shared fire path.

The one hardcoded payload runs end-to-end via `fire()` in Model Armor monitor mode
(enforce=False) — the M0 baseline where the injection reaches the agent and lands a
bypass (41/red). The M1 evolutionary loop reuses the *same* `fire()`; this slice is
just its degenerate one-shot case.
"""
from __future__ import annotations

from sentinel import redteam
from sentinel.fire import fire
from sentinel.models import Verdict


def run_thin_slice() -> tuple[Verdict, dict]:
    """Run the one hardcoded payload end-to-end. Returns (verdict, score_event)."""
    payload = redteam.next_payload()
    outcome = fire(payload, enforce=False, authorized=False)

    verdict = Verdict(
        bypass=outcome.bypass,
        attack_class=outcome.attack_class,
        scan_blocked=outcome.scan_blocked,
        scan_detected=outcome.scan_detected,
        agent_action=outcome.agent_action,
        authorized=outcome.authorized,
        score=outcome.score,
        band=outcome.band,
        trace_id=outcome.trace_id,
        finding_id=outcome.finding_id,
        detail=outcome.detail,
    )

    score_event = {
        "type": "score",
        "value": outcome.score,
        "band": outcome.band,
        "bypass": outcome.bypass,
        "attack_class": outcome.attack_class,
        "trace_id": outcome.trace_id,
        "finding_id": outcome.finding_id,
    }
    return verdict, score_event
