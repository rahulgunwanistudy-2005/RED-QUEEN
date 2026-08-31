"""Gemma red-team generator + mutator (SOF-162).

The adversary runs on Gemma (not Gemini). Per the frozen invariant, both calls
sit behind the same USE_REAL gate as everything else, with a deterministic
OFFLINE stand-in whose interface matches the real path so the swap is one file.
Generation and mutation are separate functions (SOF-162 build note); real prompts
live in `redteam/prompts/`.

Determinism: the offline path is a pure function of the seed + payload, so the
same seed reproduces the same generations and the same winning payload.
"""
from __future__ import annotations

import pathlib
from random import Random

from sentinel.config import USE_REAL
from sentinel.redteam import operators
from sentinel.redteam.payloads import Payload, seed_for

_PROMPTS_DIR = pathlib.Path(__file__).resolve().parent / "prompts"


def _rng_for(seed: int, *tags: object) -> Random:
    """A child RNG deterministically derived from the run seed and a set of tags
    (generation, parent id, ...) so every candidate is independently reproducible."""
    return Random(f"{seed}:" + ":".join(str(t) for t in tags))


# --- generation (gen-0 ancestors) -------------------------------------------


def generate(attack_class: str, *, seed: int, context: list[str] | None = None) -> list[Payload]:
    """Return the gen-0 seed population for an attack class."""
    if USE_REAL["gemma"]:
        return _real_generate(attack_class, seed=seed, context=context)
    base = seed_for(attack_class)
    return [
        Payload(
            attack_class=base.attack_class,
            content=base.content,
            ticket_id=base.ticket_id,
            id=f"{attack_class}-g0-0",
            generation=0,
            parent_id=None,
            operators=(),
            origin="seed",
            modality=base.modality,
            carrier_text=base.carrier_text,
        )
    ]


# --- mutation ----------------------------------------------------------------


def mutate(
    parent: Payload,
    *,
    seed: int,
    child_index: int,
    corpus_ops: tuple[str, ...] = (),
) -> Payload | None:
    """Produce ONE mutated child from `parent` by applying a not-yet-used operator.
    `corpus_ops` are operators observed in retrieved successful ancestors (SOF-166):
    the offline mutator prefers them (few-shot bias), the real path few-shots on the
    retrieved payloads. Returns None when every operator is already exhausted."""
    if USE_REAL["gemma"]:
        return _real_mutate(parent, seed=seed, child_index=child_index, corpus_ops=corpus_ops)

    rng = _rng_for(seed, parent.id, child_index)
    remaining = [op for op in operators.OPERATOR_NAMES if op not in parent.operators]
    if not remaining:
        return None

    preferred = [op for op in remaining if op in corpus_ops]
    used_corpus = bool(preferred)
    op = rng.choice(preferred if preferred else remaining)

    new_content = operators.apply_operator(op, parent.content, rng)
    gen = parent.generation + 1
    return Payload(
        attack_class=parent.attack_class,
        content=new_content,
        ticket_id=parent.ticket_id,
        id=f"{parent.attack_class}-g{gen}-{parent.id.split('-')[-1]}{child_index}",
        generation=gen,
        parent_id=parent.id,
        operators=parent.operators + (op,),
        origin="corpus" if used_corpus else "mutation",
        modality=parent.modality,
        carrier_text=parent.carrier_text,
    )


# --- real Gemma path (gated on SOF-157 GCP access) ---------------------------


def _load_prompt(name: str) -> str:  # pragma: no cover - used by real path
    return (_PROMPTS_DIR / name).read_text()


def _real_generate(attack_class, *, seed, context):  # pragma: no cover - needs GCP
    raise NotImplementedError(
        "Real Gemma generation is gated on SOF-157 GCP access. Set USE_REAL_GEMMA=1 "
        "once Gemma-on-Vertex is reachable; prompt template in redteam/prompts/generate.txt."
    )


def _real_mutate(parent, *, seed, child_index, corpus_ops):  # pragma: no cover - needs GCP
    raise NotImplementedError(
        "Real Gemma mutation is gated on SOF-157 GCP access. Set USE_REAL_GEMMA=1 "
        "once Gemma-on-Vertex is reachable; prompt template in redteam/prompts/mutate.txt."
    )
