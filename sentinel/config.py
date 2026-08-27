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
    "vertex_gemini": _flag("USE_REAL_VERTEX_GEMINI", False),  # Gemini via Vertex AI (target agent + verifier)
    "gemma": _flag("USE_REAL_GEMMA", False),               # Gemma via Vertex AI (red-team generator/mutator)
    "cloud_run": _flag("USE_REAL_CLOUD_RUN", False),       # deploy surface
    "cloud_sql": _flag("USE_REAL_CLOUD_SQL", False),       # GCP-managed Postgres (local pgvector stands in)
    "pubsub": _flag("USE_REAL_PUBSUB", False),             # event transport
}

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
