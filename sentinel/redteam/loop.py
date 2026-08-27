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
        "scan_score": o.scan_score,
        "scan_detected": o.scan_detected,
        "agent_action": o.agent_action,
        "score": o.score,
        "band": o.band,
        "trace_id": o.trace_id,
        "preview": payload.content[:140],
    }


def evolve(
    attack_class: str,
    *,
    seed: int,
    max_gen: int = 6,
    population: int = 4,
    survivors: int = 2,
    use_corpus: bool = True,
    emit: Emit | None = None,
) -> EvolveResult:
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
        o = fire(p, enforce=True)
        emit(_candidate_event(o, p))
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

    # --- gen 0: seed population ---------------------------------------------
    gen0 = gemma.generate(attack_class, seed=seed)
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
