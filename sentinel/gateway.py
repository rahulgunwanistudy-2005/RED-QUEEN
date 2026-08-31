"""Gateway passthrough (SOF-159): every inbound request transits geap.scan()
before reaching the target agent. This is the only door to the fleet."""
from __future__ import annotations

from dataclasses import dataclass

from sentinel.platform import geap
from sentinel.target.agent import AgentResult, run_target


@dataclass
class GatewayResult:
    scan: geap.ScanResult
    agent: AgentResult | None  # None when the scan blocked the request


def handle_request(
    ticket_id: str,
    content: str,
    *,
    authorized: bool = False,
    enforce: bool = False,
    attack_class: str = "prompt_injection",
    image_png: bytes | None = None,
    embedded_text: str | None = None,
) -> GatewayResult:
    """`content` is the request text the guardrail scans. For the multimodal class
    (SOF-173) `content` is the BENIGN carrier text, `image_png` is the ingested image,
    and `embedded_text` is the shim's stand-in for what a vision model reads from it."""
    scan = geap.scan(
        content, enforce=enforce, image_png=image_png, embedded_text=embedded_text
    )
    if scan.blocked:
        return GatewayResult(scan=scan, agent=None)
    agent = run_target(
        ticket_id, scan.sanitized, authorized=authorized, attack_class=attack_class,
        image_png=image_png, embedded_text=embedded_text,
    )
    return GatewayResult(scan=scan, agent=agent)
