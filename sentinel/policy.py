"""Active-policy seam (SOF-169). Policy is DATA, not code.

A hardening run drafts a `PolicyDelta` (JSON), the state machine applies it via
`geap.enforce_policy`, and this module is the single place the rest of the system
consults to see which deltas are currently active for an agent. Both GEAP surfaces
read from here:
  - `sentinel/platform/geap.py` (Model Armor / Gateway side) calls `content_rules`
    to decide how to scan.
  - `sentinel/target/agent.py` (Identity side) calls `revoked_tokens` to honour a
    capability revocation.

The applied shape is uniform across the three GEAP targets — one `rule.op` string
drives the behaviour, so adding a target is a new op, not new plumbing.

Ops (the whole taxonomy):
  - deep_normalize   (model_armor)  strong: scan through the agent's own decoder so
                                    leet/obfuscation evasions are recovered. Non-destructive.
  - multimodal_scan  (model_armor)  strong: a DIFFERENT mechanism — extract text from an
                                    ingested image, then scan it, so a hidden-instruction
                                    image is caught (a text defense is blind to pixels).
                                    Non-destructive. (SOF-173.)
  - blocklist_exact  (gateway)      weak: block only the exact raw-string hash; an
                                    evolved variant slips past. Non-destructive.
  - revoke_identity  (identity)     strong: strip a capability token from the agent so
                                    the privileged/exfil tool cannot execute. DESTRUCTIVE.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

import sentinel.config as config


def raw_hash(content: str) -> str:
    """Hash of the RAW payload string (first 16 hex of sha256). Used both as the
    idempotency-key payload_hash and as the blocklist_exact signature — raw (not
    normalized) so an evolved variant of the same intent has a DIFFERENT hash and
    a weak exact-match patch fails to block it (that is the FALSE-CLOSED demo)."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class PolicyDelta:
    id: str
    target: str          # model_armor | gateway | identity
    agent_id: str
    attack_class: str
    payload_hash: str
    rule: dict[str, Any]
    is_destructive: bool = False
    rationale: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target": self.target,
            "agent_id": self.agent_id,
            "attack_class": self.attack_class,
            "payload_hash": self.payload_hash,
            "rule": self.rule,
            "is_destructive": self.is_destructive,
            "rationale": self.rationale,
        }


@dataclass
class ContentRules:
    """The resolved content-side effect of every applied policy for an agent."""
    deep_normalize: bool = False
    blocklist: set[str] = field(default_factory=set)   # raw_hash values to block
    lowered_threshold: float | None = None
    multimodal_scan: bool = False   # SOF-173: extract text from images, then scan it


def _engine():
    # Imported lazily so a process that never touches policy (e.g. the pure M1 loop)
    # doesn't require the table to exist, and so the verifier's restricted engine is
    # picked up from config at call time.
    from sentinel.db import engine
    return engine


def applied_deltas(agent_id: str | None = None) -> list[PolicyDelta]:
    """Every currently-applied policy delta for the agent (reads `policies`)."""
    agent_id = agent_id or config.AGENT_ID
    with _engine().begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT policy_id, target, agent_id, attack_class, payload_hash,
                       delta, is_destructive
                FROM policies
                WHERE applied = TRUE AND agent_id = :aid
                ORDER BY id
                """
            ),
            {"aid": agent_id},
        ).all()
    out: list[PolicyDelta] = []
    for r in rows:
        delta = r[5] if isinstance(r[5], dict) else {}
        out.append(
            PolicyDelta(
                id=r[0],
                target=r[1],
                agent_id=r[2],
                attack_class=r[3],
                payload_hash=r[4],
                rule=delta.get("rule", {}),
                is_destructive=bool(r[6]),
                rationale=delta.get("rationale", ""),
            )
        )
    return out


def content_rules(agent_id: str | None = None) -> ContentRules:
    """Resolve the Model-Armor/Gateway-side effect of the applied policies."""
    rules = ContentRules()
    for d in applied_deltas(agent_id):
        op = d.rule.get("op")
        if op == "deep_normalize":
            rules.deep_normalize = True
        elif op == "multimodal_scan":
            rules.multimodal_scan = True
        elif op == "blocklist_exact":
            for h in d.rule.get("hashes", []):
                rules.blocklist.add(h)
        elif op == "lower_threshold":
            thr = d.rule.get("threshold")
            if thr is not None:
                rules.lowered_threshold = (
                    thr if rules.lowered_threshold is None else min(rules.lowered_threshold, thr)
                )
    return rules


def revoked_tokens(agent_id: str | None = None) -> set[str]:
    """Resolve the Identity-side effect: capability tokens revoked from the agent."""
    revoked: set[str] = set()
    for d in applied_deltas(agent_id):
        if d.rule.get("op") == "revoke_identity":
            for tok in d.rule.get("revoke_tokens", []):
                revoked.add(tok)
    return revoked
