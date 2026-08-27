"""pgvector payload corpus (SOF-166) — memory tier 2.

Every candidate + verdict is stored with a deterministic embedding; the mutation
loop retrieves the top-k most-similar *successful* ancestors and few-shots the
mutator from the operators that worked. Reuses the Postgres already running; one
table (`payload_corpus`) + one ivfflat index.

The embedding is a deterministic hashing bag-of-words (stable across processes via
md5, so reproducible) — no embedding model needed offline. Real Vertex embeddings
swap in behind the same `embed()` seam.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from sqlalchemy import text

from sentinel.db import engine
from sentinel.textnorm import agent_normalize

EMBED_DIM = 768


def embed(payload: str) -> list[float]:
    """Deterministic 768-d hashing embedding, L2-normalized."""
    vec = [0.0] * EMBED_DIM
    for token in agent_normalize(payload).split():
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[h % EMBED_DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
        vec = [v / norm for v in vec]
    return vec


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


@dataclass
class Ancestor:
    id: int
    payload: str
    operators: tuple[str, ...]
    generation: int
    bypass: bool
    distance: float


def add(
    *,
    attack_class: str,
    payload: str,
    generation: int,
    bypass: bool,
    operators: tuple[str, ...],
    parent_id: str | None,
    score: int,
    trace_id: str,
) -> int:
    """Persist one candidate + verdict; returns the corpus row id."""
    emb = _vec_literal(embed(payload))
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO payload_corpus
                    (attack_class, payload, generation, bypass, operators,
                     parent_id, score, trace_id, embedding)
                VALUES
                    (:ac, :p, :gen, :bypass, :ops, :parent, :score, :trace,
                     (:emb)::vector)
                RETURNING id
                """
            ),
            {
                "ac": attack_class,
                "p": payload,
                "gen": generation,
                "bypass": bypass,
                "ops": json.dumps(list(operators)),
                "parent": parent_id,
                "score": score,
                "trace": trace_id,
                "emb": emb,
            },
        ).one()
    return int(row[0])


def similar(
    query_payload: str,
    *,
    attack_class: str,
    k: int = 3,
    only_bypass: bool = True,
) -> list[Ancestor]:
    """Top-k most similar ancestors by cosine distance, optionally only bypasses."""
    emb = _vec_literal(embed(query_payload))
    clause = "AND bypass = TRUE" if only_bypass else ""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT id, payload, operators, generation, bypass,
                       embedding <=> (:emb)::vector AS distance
                FROM payload_corpus
                WHERE attack_class = :ac {clause}
                ORDER BY distance ASC
                LIMIT :k
                """
            ),
            {"emb": emb, "ac": attack_class, "k": k},
        ).all()
    out: list[Ancestor] = []
    for r in rows:
        ops = r[2] if isinstance(r[2], list) else json.loads(r[2] or "[]")
        out.append(
            Ancestor(
                id=int(r[0]),
                payload=r[1],
                operators=tuple(ops),
                generation=int(r[3]),
                bypass=bool(r[4]),
                distance=float(r[5]),
            )
        )
    return out


def count(attack_class: str | None = None) -> int:
    q = "SELECT count(*) FROM payload_corpus"
    params: dict = {}
    if attack_class:
        q += " WHERE attack_class = :ac"
        params["ac"] = attack_class
    with engine.begin() as conn:
        return int(conn.execute(text(q), params).scalar_one())
