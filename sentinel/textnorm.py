"""Surface-vs-semantic text normalization — the mechanism that makes evolution real.

Model Armor (the `geap.scan` shim) and the target agent see the *same* untrusted
string through *different* normalizers. This asymmetry is why a keyword/similarity
guardrail can be evaded by obfuscation that a language model still reads straight
through — the real-world reason prompt injection defeats filters but not models.

- `armor_normalize`  : what the guardrail matches on. Surface only (casefold,
  collapse whitespace, fold hyphen/underscore). Does NOT decode leet, does NOT
  strip zero-width or interior separators.
- `agent_normalize`  : what the model "understands". Aggressive — strips zero-width
  and non-alphanumeric separators *between* letters, decodes simple leet, collapses.

Lives in its own module so both `platform/geap.py` (armor side) and the red-team /
target (agent side) can import it without an import cycle.
"""
from __future__ import annotations

import re
import unicodedata

# Zero-width / invisible separators mutation operators like to hide inside tokens.
_ZERO_WIDTH = dict.fromkeys(
    map(ord, "​‌‍⁠﻿­"), None
)

# Decode map — the exact inverse of the red-team's leet encoder (operators._LEET_MAP:
# i→1, e→3, o→0, a→4, s→5). Must round-trip losslessly or the agent can't recover an
# obfuscated command; in particular 1 decodes to i (not l).
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s"})

_WS = re.compile(r"\s+")
# A non-alphanumeric run wedged *between* two alphanumerics (agent de-obfuscation).
_INTERIOR_SEP = re.compile(r"(?<=[a-z0-9])[^a-z0-9\s]+(?=[a-z0-9])")


def armor_normalize(text: str) -> str:
    """Guardrail's view: casefold, fold hyphen/underscore to nothing, collapse
    whitespace. Deliberately shallow — no leet decode, no zero-width stripping."""
    t = unicodedata.normalize("NFKC", text).casefold()
    t = t.replace("-", "").replace("_", "")
    return _WS.sub(" ", t).strip()


def agent_normalize(text: str) -> str:
    """Model's view: strip zero-width, decode simple leet, remove separators wedged
    inside words, collapse whitespace. Recovers the command from obfuscated text."""
    t = unicodedata.normalize("NFKC", text).casefold()
    t = t.translate(_ZERO_WIDTH)
    t = t.translate(_LEET)
    # Repeatedly close interior separators (handles r-u-n -> run in one word).
    prev = None
    while prev != t:
        prev = t
        t = _INTERIOR_SEP.sub("", t)
    return _WS.sub(" ", t).strip()
