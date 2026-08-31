"""Single config edge. Everything else imports settings from here — no module reads os.environ directly."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# --- GEAP / GCP real-vs-shim flags (SOF-157) --------------------------------
# All default to False (shim) until GCP hackathon credits are confirmed and a
# component is verified reachable. Flipping a flag to True is the one-file swap;
# the matching real path in sentinel/platform/geap.py takes over.
USE_REAL = {
    "model_armor": _flag("USE_REAL_MODEL_ARMOR", False),   # Model Armor (Vertex) content scanning
    "vertex_gemini": _flag("USE_REAL_VERTEX_GEMINI", False),  # Gemini via Vertex AI (target agent + verifier + hardener)
    "gemma": _flag("USE_REAL_GEMMA", False),               # Gemma via Vertex AI (red-team generator/mutator)
    "memory": _flag("USE_REAL_MEMORY", False),             # Vertex Agent Engine Memory Bank (per-agent risk profile)
    "cloud_run": _flag("USE_REAL_CLOUD_RUN", False),       # managed Agent Registry / Runtime products
    "cloud_sql": _flag("USE_REAL_CLOUD_SQL", False),       # GCP-managed Postgres (local pgvector stands in)
    "pubsub": _flag("USE_REAL_PUBSUB", False),             # event transport (Pub/Sub)
    "cloud_trace": _flag("USE_REAL_CLOUD_TRACE", False),   # OTel spans exported to Cloud Trace
}

# --- GCP surface config (read only when the matching USE_REAL flag is on) ----
# ADC is the sole credential path (GOOGLE_GENAI_USE_VERTEXAI=TRUE); no API keys.
GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT", "")
GCP_REGION = os.environ.get("GOOGLE_CLOUD_LOCATION") or os.environ.get("GCP_REGION", "us-central1")
# Gemini model reachable for this project in-region (verified: gemini-2.5-flash-lite).
VERTEX_GEMINI_MODEL = os.environ.get("VERTEX_GEMINI_MODEL", "gemini-2.5-flash-lite")
# Model Armor template + regional endpoint (sanitizeUserPrompt).
MODEL_ARMOR_LOCATION = os.environ.get("MODEL_ARMOR_LOCATION", GCP_REGION)
MODEL_ARMOR_TEMPLATE = os.environ.get("MODEL_ARMOR_TEMPLATE", "sentinel-injection")
# Pub/Sub topic every trace/policy event is mirrored onto.
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC", "sentinel-events")

# Vertex AI Agent Engine Memory Bank (SOF-174). The top memory tier: a durable
# per-agent risk profile that persists across campaigns + restarts. The engine
# (reasoningEngine) hosts the memory bank; if unset, the real path discovers an
# existing engine or creates one. Location can differ from GCP_REGION.
MEMORY_LOCATION = os.environ.get("MEMORY_LOCATION", GCP_REGION)
AGENT_ENGINE_NAME = os.environ.get("AGENT_ENGINE_NAME", "")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://sentinel:sentinel@localhost:5544/sentinel",
)

# The FIREWALLED verifier's OWN credentials (SOF-170). A distinct Postgres role
# (`sentinel_verifier`, created in migrations/003) whose grants DENY read on the
# red-team corpus + findings. Stands in for a distinct GCP Agent Identity; the
# verifier subprocess runs with DATABASE_URL set to this so every query it makes
# is under the restricted role. Derived from DATABASE_URL by default (same host)
# so it tracks the compose vs host connection automatically.
def _derive_verifier_url() -> str:
    base = DATABASE_URL
    # swap the leading "user:pass@" for the verifier role's credentials
    if "@" in base and "://" in base:
        scheme, rest = base.split("://", 1)
        _creds, host = rest.split("@", 1)
        return f"{scheme}://sentinel_verifier:verifierpass@{host}"
    return base


VERIFIER_DATABASE_URL = os.environ.get("VERIFIER_DATABASE_URL", _derive_verifier_url())

# The single agent under test in the shim fleet (matches geap._SHIM_FLEET).
AGENT_ID = os.environ.get("SENTINEL_AGENT_ID", "triage-agent")

# Baseline Hardening Score for the M0 unhardened fleet (demo DoD: 41/red).
BASELINE_SCORE = int(os.environ.get("BASELINE_SCORE", "41"))

# Model Armor shim blocking threshold (SOF-163): in enforce mode a payload is
# blocked when its risk score >= this. Tuned so naive payloads are blocked and a
# bypass only emerges once the red-team has evolved past it (~gen 3-4).
ARMOR_THRESHOLD = float(os.environ.get("ARMOR_THRESHOLD", "0.45"))

SERVER_URL = os.environ.get("SENTINEL_SERVER_URL", "http://localhost:8099")

# Print each OTel span to the console (M0 slice proof). The evolutionary loop fires
# many candidates, so the CLI turns this off unless --trace is passed; spans (and
# their trace_ids) are still created either way.
TRACE_CONSOLE = _flag("TRACE_CONSOLE", True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def any_real() -> bool:
    return any(USE_REAL.values())
