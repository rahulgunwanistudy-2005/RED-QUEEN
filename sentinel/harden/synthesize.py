"""Blue-team policy synthesis (SOF-169) — the Hardener's brain.

Given a confirmed bypass finding, propose the TIGHTEST policy delta that closes it,
as DATA (a `PolicyDelta`, JSON) applied via `geap.enforce_policy`. The proposer runs
on Gemini behind `USE_REAL["vertex_gemini"]`, with a deterministic OFFLINE stand-in
whose output shape matches the real path (one-file swap). The synthesis prompt lives
in `sentinel/harden/prompts/synthesize.txt`.

Three remedies map to the three GEAP targets, all in one uniform shape:
  - "content"  -> Model Armor `deep_normalize`  (STRONG, non-destructive) — DEFAULT.
                  Align the guardrail's normalizer with the agent's decoder so the
                  leet/obfuscation evasion the red-team evolved is recovered.
  - "identity" -> Agent Identity `revoke_identity` (STRONG, DESTRUCTIVE) — strips the
                  abused capability from the agent; needs human approval (SOF-171).
  - "exact"    -> Gateway `blocklist_exact` (WEAK, non-destructive) — blocks only the
                  exact raw string; an evolved variant slips past (the FALSE-CLOSED
                  demo for the verifier, SOF-170).
"""
from __future__ import annotations

import pathlib

from sentinel.config import USE_REAL
from sentinel.policy import PolicyDelta, raw_hash

_PROMPTS_DIR = pathlib.Path(__file__).resolve().parent / "prompts"

# The capability each attack class abuses (the Identity-scope revocation target).
_ABUSED_TOOL = {
    "prompt_injection": "run_privileged_fix",
    "tool_poisoning": "export_secrets",
}


def synthesize(
    *,
    attack_class: str,
    winning_payload: str,
    agent_id: str,
    remedy: str = "content",
) -> PolicyDelta:
    """Draft the tightest closing policy for a bypass. `remedy` selects the GEAP
    target; the default 'content' is the strong, autonomous, non-destructive patch."""
    if USE_REAL["vertex_gemini"]:
        return _real_synthesize(
            attack_class=attack_class, winning_payload=winning_payload,
            agent_id=agent_id, remedy=remedy,
        )
    return _offline_synthesize(
        attack_class=attack_class, winning_payload=winning_payload,
        agent_id=agent_id, remedy=remedy,
    )


def _offline_synthesize(
    *, attack_class: str, winning_payload: str, agent_id: str, remedy: str
) -> PolicyDelta:
    ph = raw_hash(winning_payload)

    if remedy == "identity":
        tool = _ABUSED_TOOL.get(attack_class, "run_privileged_fix")
        return PolicyDelta(
            id=f"pol-{attack_class}-identity-{ph}",
            target="identity",
            agent_id=agent_id,
            attack_class=attack_class,
            payload_hash=ph,
            rule={"op": "revoke_identity", "revoke_tokens": [tool]},
            is_destructive=True,
            rationale=(
                f"Revoke '{tool}' from {agent_id}'s identity scope: the bypass proved "
                f"untrusted input can drive this capability. Destructive (removes a "
                f"capability the agent may legitimately need) -> requires approval."
            ),
        )

    if remedy == "exact":
        return PolicyDelta(
            id=f"pol-{attack_class}-exact-{ph}",
            target="gateway",
            agent_id=agent_id,
            attack_class=attack_class,
            payload_hash=ph,
            rule={"op": "blocklist_exact", "hashes": [ph]},
            is_destructive=False,
            rationale=(
                "Gateway blocklist on the exact payload hash. Closes THIS string only; "
                "kept intentionally brittle to exercise the verifier (an evolved variant "
                "has a different hash)."
            ),
        )

    # default: content / deep_normalize (strong, non-destructive, auto-applies)
    return PolicyDelta(
        id=f"pol-{attack_class}-content-{ph}",
        target="model_armor",
        agent_id=agent_id,
        attack_class=attack_class,
        payload_hash=ph,
        rule={"op": "deep_normalize"},
        is_destructive=False,
        rationale=(
            "Model Armor deep-normalization: scan through the agent's own decoder so "
            "leet/zero-width obfuscation is recovered before matching. Closes the whole "
            "evasion family, not one string. Non-destructive -> auto-applies."
        ),
    )


def _real_synthesize(*, attack_class, winning_payload, agent_id, remedy):  # pragma: no cover - needs GCP
    raise NotImplementedError(
        "Real Gemini policy synthesis is gated on SOF-157 GCP access. Set "
        "USE_REAL_VERTEX_GEMINI=1 once Gemini-on-Vertex is reachable; prompt template "
        "in sentinel/harden/prompts/synthesize.txt."
    )
