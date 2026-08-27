"""The firewalled independent verifier (SOF-170) — the anti-reward-hacking core.

Runs as a SEPARATE PROCESS under a DISTINCT DB identity (`sentinel_verifier`) that
has ZERO read access to red-team state (corpus + findings). It re-derives the
outcome INDEPENDENTLY by re-running an EVOLVED attack (reusing the M1 mutation loop)
against the patched agent — never by replaying the attacker's stored winner — and
rules CLOSED / FALSE_CLOSED / STILL_OPEN with orthogonal sub-scores.
"""
