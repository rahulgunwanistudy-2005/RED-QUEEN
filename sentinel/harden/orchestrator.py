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
from sentinel.platform import memory
from sentinel.policy import raw_hash
from sentinel.redteam.loop import EvolveResult, evolve
from sentinel.redteam.payloads import Payload

Emit = Callable[[dict], None]


def _default_remedy(attack_class: str, remedy: str) -> str:
    """The multimodal class (SOF-173) must be closed by the distinct multimodal guard,
    not the text-side deep_normalize. When a caller leaves the remedy at the default
    ('content'), coerce it to 'multimodal' for that class. Explicit remedies (to demo a
    deliberately-wrong patch — e.g. 'content' on multimodal proving text defenses are
    blind) are respected via the sentinel value 'content_explicit'."""
    if attack_class == "multimodal" and remedy == "content":
        return "multimodal"
    if remedy == "content_explicit":
        return "content"
    return remedy


def _open_from_result(
    attack_class: str, result: EvolveResult, *, seed: int, remedy: str,
    verify_seed: int | None, agent_id: str, emit: Emit,
) -> machine.Run | None:
    """Open the hardening run for a confirmed-bypass evolve result. Returns None if the
    attack never bypassed (nothing to harden)."""
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
    outcome = fire(winner, enforce=True, persist_finding=True, agent_id=agent_id)

    run = machine.open_run(
        agent_id=agent_id,
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
    recalled = " (recalled from Memory Bank)" if result.recalled_bypass else ""
    emit({"type": "state", "run_id": run.id, "state": run.state, "phase": "attack",
          "attack_class": attack_class,
          "note": f"bypass confirmed @gen{winner.generation}{recalled}",
          "finding_id": outcome.finding_id})
    return run


def attack_and_open(
    attack_class: str,
    *,
    seed: int = 1337,
    remedy: str = "content",
    verify_seed: int | None = None,
    use_corpus: bool = True,
    warm_ops: tuple[str, ...] = (),
    agent_id: str | None = None,
    emit: Emit | None = None,
) -> machine.Run | None:
    """Run the evolutionary campaign; on a bypass, open the hardening run for it.
    Returns None if the attack never bypassed (nothing to harden). `agent_id` selects
    the fleet member under attack (default = the vulnerable `triage-agent`)."""
    emit = emit or (lambda _e: None)
    agent_id = agent_id or config.AGENT_ID
    remedy = _default_remedy(attack_class, remedy)
    result = evolve(attack_class, seed=seed, use_corpus=use_corpus, warm_ops=warm_ops,
                    agent_id=agent_id, emit=emit)
    return _open_from_result(
        attack_class, result, seed=seed, remedy=remedy, verify_seed=verify_seed,
        agent_id=agent_id, emit=emit,
    )


def run_full_cycle(
    attack_class: str,
    *,
    seed: int = 1337,
    remedy: str = "content",
    verify_seed: int | None = None,
    use_corpus: bool = True,
    agent_id: str | None = None,
    emit: Emit | None = None,
) -> machine.Run | None:
    """attack → harden → verify, end to end. Returns the final (possibly parked) run.
    `agent_id` picks the fleet member (default vulnerable); point it at `hardened-agent`
    to show the frontier-model agent resist the same attack (no bypass to harden)."""
    emit = emit or (lambda _e: None)
    run = attack_and_open(
        attack_class, seed=seed, remedy=remedy, verify_seed=verify_seed,
        use_corpus=use_corpus, agent_id=agent_id, emit=emit,
    )
    if run is None:
        return None
    return machine.run_to_completion(run, emit=emit)


def run_campaign(
    attack_class: str,
    *,
    agent_id: str | None = None,
    seed: int = 1337,
    remedy: str = "content",
    verify_seed: int | None = None,
    use_corpus: bool = True,
    use_memory: bool = True,
    emit: Emit | None = None,
) -> machine.Run | None:
    """A full campaign WITH cross-campaign memory (SOF-174). Reads the agent's durable
    risk profile from Memory Bank, warm-starts the evolution from any recalled exploit
    (so a repeat campaign reaches the bypass in gen 0 instead of re-evolving), drives
    the harden->verify cycle, then folds the outcome back into the profile."""
    emit = emit or (lambda _e: None)
    agent_id = agent_id or config.AGENT_ID
    remedy = _default_remedy(attack_class, remedy)

    profile = memory.get_profile(agent_id) if use_memory else memory.RiskProfile(agent_id=agent_id)
    warm = profile.warm_ops(attack_class) if use_memory else ()
    if use_memory and profile.is_known:
        emit({"type": "memory", "phase": "attack", "attack_class": attack_class,
              "note": f"known agent — {profile.campaigns} prior campaign(s) recalled",
              "campaigns": profile.campaigns, "known_weaknesses": profile.known_weaknesses,
              "warm_ops": list(warm), "backend": profile.backend})

    result = evolve(attack_class, seed=seed, use_corpus=use_corpus, warm_ops=warm,
                    agent_id=agent_id, emit=emit)

    if not result.bypassed or not result.winning_content:
        if use_memory:
            memory.record_campaign(agent_id, attack_class=attack_class, bypassed=False)
        return None

    run = _open_from_result(
        attack_class, result, seed=seed, remedy=remedy, verify_seed=verify_seed,
        agent_id=agent_id, emit=emit,
    )
    if run is None:
        return None
    run = machine.run_to_completion(run, emit=emit)

    if use_memory:
        applied_op = ((run.policy_intent or {}).get("rule") or {}).get("op")
        prof = memory.record_campaign(
            agent_id, attack_class=attack_class,
            winning_operators=result.winning_operators,
            applied_policy_op=applied_op, bypassed=True,
        )
        emit({"type": "memory", "phase": "verify", "attack_class": attack_class,
              "note": "per-agent risk profile updated in Memory Bank",
              "campaigns": prof.campaigns, "known_weaknesses": prof.known_weaknesses,
              "applied_policies": prof.applied_policies,
              "winning_generation": result.winning_generation,
              "recalled": result.recalled_bypass, "backend": prof.backend})
    return run
