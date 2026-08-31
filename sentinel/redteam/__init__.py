"""Red-team package (SOF-162 onward).

Kept import-light: only payload shapes + the Gemma stand-in are re-exported here.
`loop` and `corpus` are imported directly (they depend on the shared fire path,
so importing them from this __init__ would create a cycle).
"""
from __future__ import annotations

from sentinel.redteam.gemma import generate, mutate, preseed
from sentinel.redteam.payloads import (
    REFERENCE_PAYLOAD,
    SEEDS,
    TOOL_POISONING_SEED,
    Payload,
    next_payload,
    seed_for,
)

__all__ = [
    "Payload",
    "REFERENCE_PAYLOAD",
    "TOOL_POISONING_SEED",
    "SEEDS",
    "next_payload",
    "seed_for",
    "generate",
    "mutate",
    "preseed",
]
