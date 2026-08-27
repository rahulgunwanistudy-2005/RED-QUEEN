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


def handle_request(ticket_id: str, content: str, *, authorized: bool = False) -> GatewayResult:
    scan = geap.scan(content)
    if scan.blocked:
        return GatewayResult(scan=scan, agent=None)
    agent = run_target(ticket_id, scan.sanitized, authorized=authorized)
    return GatewayResult(scan=scan, agent=agent)
