"""Per-agent risk profile — the top memory tier (SOF-174).

Memory hierarchy, bottom to top:
  1. within-run state  (the mutation loop's survivors)
  2. pgvector corpus   (cross-run, within-project — SOF-166)
  3. THIS: a durable per-agent risk profile that persists ACROSS campaigns and
     survives restarts — "goldfish -> managed memory".

The REAL tier is Vertex AI Agent Engine **Memory Bank**: an Agent Engine hosts a
memory bank, and the profile is written as a memory scoped to the agent and read
back at the next campaign. The SHIM tier is one Postgres row per agent. Both sit
behind the same seam, gated by `USE_REAL["memory"]` — the one-file swap the
Constitution promises.

The profile is deliberately small (SOF-174: 3-4 fields):
  - known_weaknesses   : attack classes that have bypassed this agent
  - winning_operators  : the operator sequence that won, per attack class — this is
                         what lets a REPEAT campaign recall the exploit and reach the
                         bypass in generation 0 instead of re-evolving from scratch
  - applied_policies   : the policy ops that closed those weaknesses
  - campaigns          : how many campaigns this agent has seen
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

from sentinel.config import USE_REAL


@dataclass
class RiskProfile:
    agent_id: str
    known_weaknesses: list[str] = field(default_factory=list)
    winning_operators: dict[str, list[str]] = field(default_factory=dict)
    applied_policies: list[str] = field(default_factory=list)
    campaigns: int = 0
    backend: str = "shim"

    @property
    def is_known(self) -> bool:
        return self.campaigns > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "known_weaknesses": self.known_weaknesses,
            "winning_operators": self.winning_operators,
            "applied_policies": self.applied_policies,
            "campaigns": self.campaigns,
            "backend": self.backend,
        }

    def warm_ops(self, attack_class: str) -> tuple[str, ...]:
        """The stored winning operator sequence for a class — the warm-start seed."""
        return tuple(self.winning_operators.get(attack_class, ()))


def _merge(profile: RiskProfile, *, attack_class: str, winning_operators, applied_policy_op, bypassed: bool) -> RiskProfile:
    if bypassed and attack_class not in profile.known_weaknesses:
        profile.known_weaknesses.append(attack_class)
    if bypassed and winning_operators:
        profile.winning_operators[attack_class] = list(winning_operators)
    if applied_policy_op and applied_policy_op not in profile.applied_policies:
        profile.applied_policies.append(applied_policy_op)
    profile.campaigns += 1
    return profile


# --- public seam ------------------------------------------------------------


def get_profile(agent_id: str) -> RiskProfile:
    """Load the agent's durable risk profile (empty if never seen)."""
    if USE_REAL["memory"]:
        return _real_get(agent_id)
    return _shim_get(agent_id)


def record_campaign(
    agent_id: str,
    *,
    attack_class: str,
    winning_operators: tuple[str, ...] = (),
    applied_policy_op: str | None = None,
    bypassed: bool = True,
) -> RiskProfile:
    """Fold one campaign's outcome into the agent's profile and persist it."""
    profile = get_profile(agent_id)
    profile = _merge(
        profile, attack_class=attack_class, winning_operators=winning_operators,
        applied_policy_op=applied_policy_op, bypassed=bypassed,
    )
    if USE_REAL["memory"]:
        _real_put(profile)
    else:
        _shim_put(profile)
    return profile


# --- shim tier: one Postgres row per agent ----------------------------------


def _shim_get(agent_id: str) -> RiskProfile:
    from sqlalchemy import text

    from sentinel.db import engine

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT profile FROM agent_memory WHERE agent_id = :a"),
            {"a": agent_id},
        ).fetchone()
    if not row:
        return RiskProfile(agent_id=agent_id, backend="shim")
    data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return _from_data(agent_id, data, backend="shim")


def _shim_put(profile: RiskProfile) -> None:
    from sqlalchemy import text

    from sentinel.db import engine

    body = {
        "known_weaknesses": profile.known_weaknesses,
        "winning_operators": profile.winning_operators,
        "applied_policies": profile.applied_policies,
        "campaigns": profile.campaigns,
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO agent_memory (agent_id, profile, updated_at)
                VALUES (:a, (:p)::jsonb, now())
                ON CONFLICT (agent_id) DO UPDATE
                    SET profile = EXCLUDED.profile, updated_at = now()
                """
            ),
            {"a": profile.agent_id, "p": json.dumps(body)},
        )


# --- real tier: Vertex AI Agent Engine Memory Bank --------------------------

_client = None
_engine_name: str | None = None


def _from_data(agent_id: str, data: dict[str, Any], *, backend: str) -> RiskProfile:
    return RiskProfile(
        agent_id=agent_id,
        known_weaknesses=list(data.get("known_weaknesses", [])),
        winning_operators={k: list(v) for k, v in dict(data.get("winning_operators", {})).items()},
        applied_policies=list(data.get("applied_policies", [])),
        campaigns=int(data.get("campaigns", 0)),
        backend=backend,
    )


def _memory_bank():
    """Lazily bind (and if needed create) the Agent Engine that hosts the memory bank.
    Reuses `AGENT_ENGINE_NAME` if configured, else the first existing engine, else
    creates a bare one. ADC only. Returns (agent_engines_client, engine_resource_name)."""
    global _client, _engine_name
    import sentinel.config as config

    if _client is None:
        import vertexai

        _client = vertexai.Client(project=config.GCP_PROJECT, location=config.MEMORY_LOCATION)
    if _engine_name is None:
        if config.AGENT_ENGINE_NAME:
            _engine_name = config.AGENT_ENGINE_NAME
        else:
            existing = list(_client.agent_engines.list())
            if existing:
                _engine_name = existing[0].api_resource.name
            else:
                eng = _client.agent_engines.create()
                _engine_name = eng.api_resource.name
    return _client.agent_engines, _engine_name


def _real_get(agent_id: str) -> RiskProfile:
    """Read the profile back from Memory Bank. Facts are JSON snapshots scoped to the
    agent; the freshest (highest campaigns) wins. Falls back to the Postgres shim on a
    transport error so a memory hiccup never breaks a campaign (loud, not silent)."""
    try:
        ae, name = _memory_bank()
        scope = {"agent_id": agent_id, "kind": "risk_profile"}
        best: dict[str, Any] | None = None
        for m in ae.memories.retrieve(name=name, scope=scope):
            mem = getattr(m, "memory", m)
            fact = getattr(mem, "fact", None) or ""
            try:
                data = json.loads(fact)
            except (ValueError, TypeError):
                continue
            if best is None or int(data.get("campaigns", 0)) >= int(best.get("campaigns", 0)):
                best = data
        if best is None:
            return RiskProfile(agent_id=agent_id, backend="real")
        return _from_data(agent_id, best, backend="real")
    except Exception as exc:
        print(f"[memory] real Memory Bank read fell back to shim: {exc}", file=sys.stderr)
        return _shim_get(agent_id)


def _real_put(profile: RiskProfile) -> None:
    """Persist the profile to Memory Bank as a scoped JSON fact, and mirror to the
    Postgres shim so a read under either backend agrees. Loud fallback on error."""
    body = json.dumps({
        "known_weaknesses": profile.known_weaknesses,
        "winning_operators": profile.winning_operators,
        "applied_policies": profile.applied_policies,
        "campaigns": profile.campaigns,
    })
    try:
        ae, name = _memory_bank()
        ae.memories.create(
            name=name,
            fact=body,
            scope={"agent_id": profile.agent_id, "kind": "risk_profile"},
        )
    except Exception as exc:
        print(f"[memory] real Memory Bank write fell back to shim: {exc}", file=sys.stderr)
    _shim_put(profile)  # mirror (idempotent) so the profile is durable either way
