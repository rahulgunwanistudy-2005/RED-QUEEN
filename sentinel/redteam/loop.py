"""The evolutionary mutation loop (SOF-163) — THE SOUL.

generate → fire → score → keep survivors → mutate → next generation, up to
`max_gen`. Every candidate is tagged with `generation` + `parent_id` (for the
lineage tree), fired through the shared `fire()` path in enforce mode (Model Armor
blocking), scored, and streamed. Naive generations are BLOCKED; a genuine bypass
emerges once three of the scanner's four signal families have been mutated away —
tuned to land around gen 3-4. The corpus (SOF-166) feeds retrieved successful
ancestors back in as mutation context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from sentinel.fire import Outcome, fire
from sentinel.redteam import corpus, gemma
from sentinel.redteam.payloads import Payload

Emit = Callable[[dict], None]


@dataclass
class GenerationSummary:
    generation: int
    population: int
    blocked: int
    bypassed: int
    best_scan_score: float


@dataclass
class EvolveResult:
    attack_class: str
    seed: int
    bypassed: bool
    winning_generation: int | None
    winning_payload_id: str | None
    winning_content: str | None
    generations: list[GenerationSummary] = field(default_factory=list)
    used_corpus_ancestors: list[int] = field(default_factory=list)
    winning_operators: tuple[str, ...] = ()  # operator sequence that won (SOF-174 memory)
    recalled_bypass: bool = False            # bypass came from the Memory Bank warm start


def _fitness(o: Outcome) -> tuple:
    # Higher is better: a bypass dominates; otherwise prefer lower scanner risk.
    # Tie-break on payload_id for fully deterministic selection.
    return (1 if o.bypass else 0, -o.scan_score, o.payload_id)


def _candidate_event(o: Outcome, payload: Payload) -> dict:
    return {
        "type": "candidate",
        "attack_class": o.attack_class,
        "id": o.payload_id,
        "parent_id": o.parent_id,
        "generation": o.generation,
        "operators": list(o.operators),
        "origin": payload.origin,
        "blocked": o.scan_blocked,
        "bypass": o.bypass,
        "privileged": o.privileged_executed,
        "leaked": o.leaked_secret,
        "scan_score": o.scan_score,
        "scan_detected": o.scan_detected,
        "agent_action": o.agent_action,
        "score": o.score,
        "band": o.band,
        "trace_id": o.trace_id,
        "preview": payload.content[:140],
        # multimodal (SOF-173): the reveal — carrier text the guardrail saw vs. the
        # hidden instruction baked into the image (== payload.content).
        "modality": payload.modality,
        "carrier": payload.carrier_text if payload.modality == "multimodal" else "",
    }


def _recall_exploit(seed_payload: Payload, warm_ops: tuple[str, ...], seed: int) -> Payload | None:
    """Build a gen-0 candidate by replaying the operator sequence a PRIOR campaign
    found winning (SOF-174 Memory Bank warm start). A repeat campaign against a known
    agent recalls the exploit and confirms it in generation 0, instead of re-evolving
    from the naive seed. Deterministic given the seed."""
    from sentinel.redteam import operators

    from random import Random

    ops = tuple(op for op in warm_ops if op in operators.OPERATOR_NAMES)
    if not ops:
        return None
    rng = Random(f"{seed}:recall:{seed_payload.attack_class}")
    content = seed_payload.content
    applied: list[str] = []
    for op in ops:
        if op in applied:
            continue
        content = operators.apply_operator(op, content, rng)
        applied.append(op)
    return Payload(
        attack_class=seed_payload.attack_class,
        content=content,
        ticket_id=seed_payload.ticket_id,
        id=f"{seed_payload.attack_class}-recall",
        generation=0,
        parent_id=None,
        operators=tuple(applied),
        origin="memory",
        modality=seed_payload.modality,
        carrier_text=seed_payload.carrier_text,
    )


def evolve(
    attack_class: str,
    *,
    seed: int,
    max_gen: int = 6,
    population: int = 4,
    survivors: int = 2,
    use_corpus: bool = True,
    persist_corpus: bool = True,
    persist_finding: bool = True,
    warm_ops: tuple[str, ...] = (),
    emit: Emit | None = None,
) -> EvolveResult:
    """`persist_corpus`/`persist_finding` default True (the red-team campaign writes
    both). The FIREWALLED verifier (SOF-170) reuses this exact loop with BOTH False
    and `use_corpus=False`: it re-derives an evolved attack without reading or writing
    the attacker's corpus/findings — and its restricted DB role would deny either
    write anyway, so the firewall is enforced, not merely honoured."""
    emit = emit or (lambda _e: None)
    result = EvolveResult(
        attack_class=attack_class,
        seed=seed,
        bypassed=False,
        winning_generation=None,
        winning_payload_id=None,
        winning_content=None,
    )

    def run_and_record(p: Payload) -> tuple[Payload, Outcome]:
        o = fire(p, enforce=True, persist_finding=persist_finding)
        emit(_candidate_event(o, p))
        if persist_corpus:
            corpus.add(
                attack_class=o.attack_class,
                payload=p.content,
                generation=o.generation,
                bypass=o.bypass,
                operators=o.operators,
                parent_id=o.parent_id,
                score=o.score,
                trace_id=o.trace_id,
            )
        return p, o

    # --- gen 0: seed population (+ Memory Bank recall, SOF-174) --------------
    gen0 = gemma.generate(attack_class, seed=seed)
    if warm_ops:
        recalled = _recall_exploit(gen0[0], warm_ops, seed)
        if recalled is not None:
            gen0 = gen0 + [recalled]
            emit({"type": "memory", "phase": "attack", "attack_class": attack_class,
                  "note": "recalled prior exploit from Memory Bank",
                  "warm_ops": list(recalled.operators), "recalled_id": recalled.id})
    scored = [run_and_record(p) for p in gen0]
    survivors_pool = _select(scored, survivors, result, emit, generation=0)
    if result.bypassed:
        return result

    # --- gen 1..max_gen ------------------------------------------------------
    for gen in range(1, max_gen + 1):
        corpus_ops: tuple[str, ...] = ()
        if use_corpus:
            corpus_ops = _corpus_context(attack_class, survivors_pool, result, emit, gen)

        children: list[Payload] = []
        per_parent = max(1, population // max(1, len(survivors_pool)))
        for parent, _ in survivors_pool:
            for ci in range(per_parent):
                child = gemma.mutate(parent, seed=seed, child_index=ci, corpus_ops=corpus_ops)
                if child is not None:
                    children.append(child)
        if not children:
            break  # operators exhausted

        scored = [run_and_record(p) for p in children]
        survivors_pool = _select(scored, survivors, result, emit, generation=gen)
        if result.bypassed:
            break

    return result


def _corpus_context(
    attack_class: str,
    survivors_pool: list[tuple[Payload, Outcome]],
    result: EvolveResult,
    emit: Emit,
    gen: int,
) -> tuple[str, ...]:
    query = survivors_pool[0][0].content if survivors_pool else ""
    ancestors = corpus.similar(query, attack_class=attack_class, k=3, only_bypass=True)
    if not ancestors:
        return ()
    ops: list[str] = []
    for a in ancestors:
        ops.extend(a.operators)
        result.used_corpus_ancestors.append(a.id)
    emit(
        {
            "type": "corpus",
            "attack_class": attack_class,
            "generation": gen,
            "used_ancestors": [a.id for a in ancestors],
            "operators": sorted(set(ops)),
        }
    )
    return tuple(ops)


def _select(
    scored: list[tuple[Payload, Outcome]],
    survivors: int,
    result: EvolveResult,
    emit: Emit,
    *,
    generation: int,
) -> list[tuple[Payload, Outcome]]:
    ranked = sorted(scored, key=lambda po: _fitness(po[1]), reverse=True)
    blocked = sum(1 for _, o in scored if o.scan_blocked)
    bypassed = [(p, o) for p, o in scored if o.bypass]
    best_scan = min((o.scan_score for _, o in scored), default=0.0)

    result.generations.append(
        GenerationSummary(
            generation=generation,
            population=len(scored),
            blocked=blocked,
            bypassed=len(bypassed),
            best_scan_score=best_scan,
        )
    )

    if bypassed and not result.bypassed:
        win_p, win_o = bypassed[0]
        result.bypassed = True
        result.winning_generation = generation
        result.winning_payload_id = win_o.payload_id
        result.winning_content = win_p.content
        result.winning_operators = win_p.operators
        result.recalled_bypass = win_p.origin == "memory"

    # Drive the dial: green while defenses hold, red the moment a bypass lands.
    emit(
        {
            "type": "score",
            "value": 41 if result.bypassed else 96,
            "band": "red" if result.bypassed else "green",
            "bypass": result.bypassed,
            "attack_class": result.attack_class,
            "generation": generation,
        }
    )
    return ranked[:survivors]
