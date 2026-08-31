"""SESSION_8 Gemma generator tests — demo-safety invariants (no live calls).

The load-bearing claims: the gen-0 seed population is Gemma-INDEPENDENT (so the
deterministic ladder reproduces identically whether Gemma is on or off), and the
real generator degrades to the offline seed on any failure — so Gemma can never
break a demo take. These run fully offline (no network, no key needed).

Run: PYTHONPATH=. .venv/bin/pytest tests/test_gemma.py
"""
from __future__ import annotations

import sentinel.config as config

config.TRACE_CONSOLE = False

from sentinel.redteam import gemma


def test_generate_is_gemma_independent_seed_only():
    """generate() returns exactly the deterministic naive seed regardless of the flag —
    the population that drives the evolutionary ladder must not depend on Gemma."""
    for flag in (False, True):
        config.USE_REAL["gemma"] = flag
        pop = gemma.generate("prompt_injection", seed=1337)
        assert [p.id for p in pop] == ["prompt_injection-g0-0"]
        assert [p.origin for p in pop] == ["seed"]


def test_preseed_empty_without_key(monkeypatch):
    """With the flag on but no key, preseed() yields nothing (loud fallback) — the
    campaign then simply proceeds on the seed. No network is touched."""
    config.USE_REAL["gemma"] = True
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    assert config.gemma_ready() is False
    assert gemma.preseed("prompt_injection", seed=1337) == []


def test_preseed_out_of_scope_class():
    """Gemma only generates for the text classes; the multimodal beat is untouched."""
    config.USE_REAL["gemma"] = True
    assert gemma.preseed("multimodal", seed=1337) == []


def test_mutation_is_deterministic():
    """The mutation engine stays deterministic (Gemma is the generator, not the engine)."""
    config.USE_REAL["gemma"] = False
    seed_pop = gemma.generate("prompt_injection", seed=1337)
    a = gemma.mutate(seed_pop[0], seed=1337, child_index=0)
    b = gemma.mutate(seed_pop[0], seed=1337, child_index=0)
    assert a is not None and a.content == b.content and a.operators == b.operators
