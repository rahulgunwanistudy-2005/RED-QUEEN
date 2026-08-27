"""The single GEAP interface (SOF-157 / SOF-158).

Every GEAP / Model Armor / GCP call in the whole system hides behind this one
file, gated per-component by `config.USE_REAL`. Shim <-> real is a one-file swap:
each public function checks its flag and dispatches to `_real_*` or `_shim_*`.

Public surface (frozen for downstream):
    scan(payload)          -> ScanResult      # Model Armor content scan
    enforce_policy(policy)  -> PolicyResult    # apply a Gateway/Model Armor/Identity policy
    registry_list()         -> list[Agent]     # Agent Registry (the fleet)
    emit_trace(event)       -> str             # OTel trace, returns trace_id

M0 posture: all USE_REAL flags False (no GCP access yet — see SOF-157). The
shims are faithful stand-ins, not stubs: `scan` really detects injection classes,
`emit_trace` really emits an OpenTelemetry span.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from sentinel.config import USE_REAL

# --- data shapes (the contract) ---------------------------------------------


@dataclass
class ScanResult:
    blocked: bool                       # did Model Armor block the payload?
    detected: list[str] = field(default_factory=list)  # detected attack-class signals
    score: float = 0.0                  # 0..1 risk score
    sanitized: str = ""                 # content forwarded to the agent
    backend: str = "shim"               # "real" | "shim"
    reason: str = ""


@dataclass
class PolicyResult:
    applied: bool
    policy_id: str
    backend: str = "shim"


@dataclass
class Agent:
    id: str
    name: str
    model: str
    tools: list[str]
    risk: str  # low | medium | high


# --- Model Armor scan -------------------------------------------------------

# Injection signals for the 3 frozen attack classes (deep matching comes later;
# M0 needs only enough to flag the one reference payload).
_INJECTION_PATTERNS: dict[str, list[str]] = {
    "prompt_injection": [
        r"ignore (?:all |your |the )?(?:previous|prior|above) instructions",
        r"disregard (?:the )?(?:system|previous) prompt",
        r"you are now",
        r"new instructions:",
    ],
    "tool_poisoning": [
        r"call\s+run_privileged_fix",
        r"invoke\s+the\s+privileged",
        r"use the .* tool to (?:delete|escalate|exfiltrate|run)",
    ],
    "multimodal_injection": [
        r"<!--.*instruction.*-->",
        r"hidden text",
    ],
}


def scan(payload: str, *, enforce: bool = False) -> ScanResult:
    """Model Armor content scan. `enforce=False` = detection-only (M0 baseline:
    signals are reported but the payload is still forwarded, so an injection can
    reach the agent). Hardening (M2) flips policies to enforce=True to block."""
    if USE_REAL["model_armor"]:
        return _real_scan(payload, enforce=enforce)
    return _shim_scan(payload, enforce=enforce)


def _shim_scan(payload: str, *, enforce: bool) -> ScanResult:
    detected: list[str] = []
    for attack_class, patterns in _INJECTION_PATTERNS.items():
        if any(re.search(p, payload, re.IGNORECASE | re.DOTALL) for p in patterns):
            detected.append(attack_class)
    score = min(1.0, 0.34 * len(detected))
    blocked = enforce and bool(detected)
    return ScanResult(
        blocked=blocked,
        detected=detected,
        score=round(score, 3),
        sanitized="" if blocked else payload,
        backend="shim",
        reason="enforced-block" if blocked else ("detected-monitor" if detected else "clean"),
    )


def _real_scan(payload: str, *, enforce: bool) -> ScanResult:  # pragma: no cover - needs GCP
    raise NotImplementedError(
        "Real Model Armor path is gated on SOF-157 GCP access. "
        "Set USE_REAL_MODEL_ARMOR=1 only once Vertex Model Armor is reachable."
    )


# --- policy enforcement -----------------------------------------------------


def enforce_policy(policy: dict[str, Any]) -> PolicyResult:
    """Apply a Gateway / Model Armor / Identity policy. M0 records intent only;
    the crash-recoverable state machine that really writes policy is M2 (SOF-16x)."""
    if USE_REAL["cloud_run"] or USE_REAL["vertex_gemini"]:
        return _real_enforce(policy)
    pid = str(policy.get("id", "policy-unnamed"))
    return PolicyResult(applied=True, policy_id=pid, backend="shim")


def _real_enforce(policy: dict[str, Any]) -> PolicyResult:  # pragma: no cover - needs GCP
    raise NotImplementedError("Real policy enforcement is gated on SOF-157 GCP access.")


# --- agent registry ---------------------------------------------------------

_SHIM_FLEET: list[Agent] = [
    Agent(
        id="triage-agent",
        name="Support Triage Agent",
        model="gemini-2.0-flash",
        tools=["read_ticket", "run_privileged_fix"],
        risk="high",
    ),
]


def registry_list() -> list[Agent]:
    """The fleet under test (Agent Registry)."""
    if USE_REAL["cloud_run"]:
        return _real_registry()
    return list(_SHIM_FLEET)


def _real_registry() -> list[Agent]:  # pragma: no cover - needs GCP
    raise NotImplementedError("Real Agent Registry is gated on SOF-157 GCP access.")


# --- OTel tracing -----------------------------------------------------------

_tracer_provider: TracerProvider | None = None


def _tracer():
    global _tracer_provider
    if _tracer_provider is None:
        _tracer_provider = TracerProvider(
            resource=Resource.create({"service.name": "sentinel-evolution"})
        )
        # Shim exporter = console. Real path swaps in Cloud Trace / OTLP.
        _tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    return trace.get_tracer("sentinel.geap", tracer_provider=_tracer_provider)


def emit_trace(event: dict[str, Any]) -> str:
    """Emit one OTel span for a slice event and return its trace_id (hex)."""
    name = str(event.get("name", "sentinel.event"))
    tracer = _tracer()
    with tracer.start_as_current_span(name) as span:
        for key, value in event.items():
            if key == "name":
                continue
            span.set_attribute(f"sentinel.{key}", _attr(value))
        span.set_attribute("sentinel.backend", "real" if USE_REAL["pubsub"] else "shim")
        trace_id = format(span.get_span_context().trace_id, "032x")
    return trace_id


def _attr(value: Any) -> Any:
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)
