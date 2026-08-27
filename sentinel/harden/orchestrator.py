"""Wire the M1 red-team campaign to the M2 hardening machine (SOF-168/169/170).

One full cycle: EVOLVE an attack (reusing the M1 loop) → on a confirmed bypass,
open a durable hardening run keyed by (agent_id, payload_hash) → drive the state
machine to a terminal verdict. The verifier re-runs its OWN evolved attack under a
firewalled identity (SOF-170).
"""
from __future__ import annotations

from typing import Callable

import sentinel.config as config
from sentinel.fire import fire
from sentinel.harden import machine
from sentinel.policy import raw_hash
from sentinel.redteam.loop import evolve
from sentinel.redteam.payloads import Payload

Emit = Callable[[dict], None]


def attack_and_open(
    attack_class: str,
    *,
    seed: int = 1337,
    remedy: str = "content",
    verify_seed: int | None = None,
    use_corpus: bool = True,
    emit: Emit | None = None,
) -> machine.Run | None:
    """Run the evolutionary campaign; on a bypass, open the hardening run for it.
    Returns None if the attack never bypassed (nothing to harden)."""
    emit = emit or (lambda _e: None)
    result = evolve(attack_class, seed=seed, use_corpus=use_corpus, emit=emit)
    if not result.bypassed or not result.winning_content:
        return None

    # Re-fire the confirmed winner once to pin the bypass finding + attack trace that
    # the hardener acts on (still the shared fire path — the THIRD reuse is the verifier).
    winner = Payload(
        attack_class=attack_class,
        content=result.winning_content,
        id=result.winning_payload_id or f"{attack_class}-winner",
        generation=result.winning_generation or 0,
    )
    outcome = fire(winner, enforce=True, persist_finding=True)

    run = machine.open_run(
        agent_id=config.AGENT_ID,
        attack_class=attack_class,
        winning_payload=result.winning_content,
        payload_hash=raw_hash(result.winning_content),
        finding_id=outcome.finding_id,
        verify_seed=seed + 4242 if verify_seed is None else verify_seed,
        remedy=remedy,
        attack_trace_id=outcome.trace_id,
    )
    machine.record_span(run.id, "attack", "sentinel.fire", outcome.trace_id, 0.0, 1.0,
                        {"attack_class": attack_class, "bypass": outcome.bypass,
                         "generation": winner.generation})
    emit({"type": "state", "run_id": run.id, "state": run.state, "phase": "attack",
          "attack_class": attack_class, "note": f"bypass confirmed @gen{winner.generation}",
          "finding_id": outcome.finding_id})
    return run


def run_full_cycle(
    attack_class: str,
    *,
    seed: int = 1337,
    remedy: str = "content",
    verify_seed: int | None = None,
    use_corpus: bool = True,
    emit: Emit | None = None,
) -> machine.Run | None:
    """attack → harden → verify, end to end. Returns the final (possibly parked) run."""
    emit = emit or (lambda _e: None)
    run = attack_and_open(
        attack_class, seed=seed, remedy=remedy, verify_seed=verify_seed,
        use_corpus=use_corpus, emit=emit,
    )
    if run is None:
        return None
    return machine.run_to_completion(run, emit=emit)
