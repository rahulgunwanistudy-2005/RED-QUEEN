"""Blue-team policy synthesis (SOF-169) — the Hardener's brain.

Given a confirmed bypass finding, propose the TIGHTEST policy delta that closes it,
as DATA (a `PolicyDelta`, JSON) applied via `geap.enforce_policy`. The proposer runs
on Gemini behind `USE_REAL["vertex_gemini"]`, with a deterministic OFFLINE stand-in
whose output shape matches the real path (one-file swap). The synthesis prompt lives
in `sentinel/harden/prompts/synthesize.txt`.

The remedies map to the GEAP targets, all in one uniform shape:
  - "content"  -> Model Armor `deep_normalize`  (STRONG, non-destructive) — DEFAULT.
                  Align the guardrail's normalizer with the agent's decoder so the
                  leet/obfuscation evasion the red-team evolved is recovered.
  - "multimodal" -> Model Armor `multimodal_scan` (STRONG, non-destructive) — the
                  DISTINCT guard for the multimodal class (SOF-173): extract the text
                  from an ingested image, then scan it. Default for attack_class
                  "multimodal" (a text defense is blind to pixels).
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

    if remedy == "multimodal":
        return PolicyDelta(
            id=f"pol-{attack_class}-multimodal-{ph}",
            target="model_armor",
            agent_id=agent_id,
            attack_class=attack_class,
            payload_hash=ph,
            rule={"op": "multimodal_scan"},
            is_destructive=False,
            rationale=(
                "Model Armor multimodal scan: extract the text baked into the ingested "
                "image and scan it before the agent acts. A text-only guardrail is "
                "blind to instructions carried in pixels — this is the DISTINCT "
                "multimodal mechanism, not the text-side deep_normalize. "
                "Non-destructive -> auto-applies."
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


_EXPECTED_OP = {
    "content": "deep_normalize",
    "multimodal": "multimodal_scan",
    "identity": "revoke_identity",
    "exact": "blocklist_exact",
}


def _real_synthesize(*, attack_class, winning_payload, agent_id, remedy) -> PolicyDelta:
    """Real blue-team synthesis: Gemini (Vertex, ADC) reads the confirmed bypass and
    drafts the closing policy delta as JSON, using the SOF-169 prompt. The returned
    JSON is validated against the operator-selected remedy's required shape; if the
    model deviates (wrong op/target, malformed JSON) we fall back to the deterministic
    template — so the harden->verify cycle stays correct while a genuine Gemini
    reasoning call happens on every hardening (visible in Vertex AI logs)."""
    import json

    from sentinel.platform import geap

    baseline = _offline_synthesize(
        attack_class=attack_class, winning_payload=winning_payload,
        agent_id=agent_id, remedy=remedy,
    )
    prompt = (_PROMPTS_DIR / "synthesize.txt").read_text().format(
        agent_id=agent_id, attack_class=attack_class, winning_payload=winning_payload,
    ) + (
        f"\n\nThe operator has selected remedy='{remedy}'. Emit the delta for that "
        f"remedy. Its rule.op MUST be '{_EXPECTED_OP.get(remedy, 'deep_normalize')}'."
    )
    try:
        resp = geap.gemini_generate(
            prompt, max_output_tokens=512, response_mime_type="application/json"
        )
        data = json.loads(resp.text)
        rule = data.get("rule") or {}
        if rule.get("op") != _EXPECTED_OP.get(remedy):
            return baseline  # model deviated from the selected remedy -> deterministic shape
        # Accept the model's rationale (its real reasoning); keep the deterministic
        # id/target/rule so downstream application + verification are exact.
        rationale = str(data.get("rationale") or baseline.rationale)
        return PolicyDelta(
            id=baseline.id, target=baseline.target, agent_id=agent_id,
            attack_class=attack_class, payload_hash=baseline.payload_hash,
            rule=baseline.rule, is_destructive=baseline.is_destructive,
            rationale=f"[Gemini] {rationale}",
        )
    except Exception as exc:  # loud fallback, never a silent template swap
        import sys

        print(f"[synthesize] real Gemini synthesis fell back to template: {exc}", file=sys.stderr)
        return baseline
