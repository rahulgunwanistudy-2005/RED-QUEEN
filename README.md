# RED//QUEEN

> An autonomous red-team that **evolves its own attacks** against a fleet of enterprise
> agents — while an **independent, firewalled verifier proves the defenses actually hold**,
> and the harden loop **heals itself after a crash**.
>
> *All Things Agentic Hackathon — Track 3 (Fortified Enterprise Fleet).*

The name is the thesis: the Red Queen from *Through the Looking-Glass* — *"it takes all the
running you can do, to keep in the same place."* An agent fleet's defenses have to keep
evolving just to stay level with an attacker that never stops. RED//QUEEN is the range that
runs both sides of that race and proves who's ahead.

RED//QUEEN is a self-hardening agent-security range. A mutation-driven red-team climbs
generations until it finds a bypass; a Hardener synthesizes a real defense policy through
a crash-recoverable state machine; and a verifier — running under a **different identity
that cannot see the attacker's state** — re-runs the attack and scores three *orthogonal*
dimensions to certify the finding **CLOSED** (or catches a brittle patch as **FALSE_CLOSED**).
It runs on real Google Cloud products and degrades honestly to disclosed shims where a
managed product isn't reachable on a personal account.

- **Live URL:** https://sentinel-314561161517.us-central1.run.app (region `us-central1`)
- **Attack taxonomy — frozen at 3, forever:** prompt injection · tool poisoning · multimodal injection.

> **Naming:** the project is **RED//QUEEN**. Its shipped control plane and Python package are
> named `sentinel` (the in-app header reads "SENTINEL EVOLUTION" and every module/endpoint is
> `sentinel.*`) — that's the system RED//QUEEN runs. Wherever you see `sentinel` in code, URLs,
> or the UI, it's the same project.

---

## The one thing that makes this different

Most "AI security" demos show a static filter blocking a static payload. Sentinel shows the
**arms race**: the attack *evolves past a real guardrail*, and then a *different mechanism*
closes it — proven by an isolated verifier, not by the same code that built the patch.

Three beats carry the whole thesis:

1. **Evolve past REAL Model Armor.** The red-team's deterministic operators mutate a
   prompt-injection payload across generations until Vertex **Model Armor** (a real Google
   guardrail) reads past the obfuscation and lets it through. The bypass is real, on the
   real product.
2. **Multimodal blind spot.** The malicious instruction lives in the **pixels** of an
   invoice PNG, not in text. Real Model Armor returns **CLEAN** — it is honestly blind to
   the image. A *different* guard (Gemini-vision text extraction) is what catches it. The
   defense is not monolithic, and we show exactly where the seam is.
3. **Crash-resume + honest verification.** Kill the process mid-HARDENING and it resumes to
   apply **exactly one** policy (idempotent state machine). The verifier then certifies
   CLOSED — and on a deliberately brittle patch, returns **FALSE_CLOSED** instead of lying.

---

## Architecture

Three agents, three identities, one GEAP interface. Everything that touches Google Cloud
hides behind a single file (`sentinel/platform/geap.py`), gated per-surface by a `USE_REAL`
flag — so the shim ↔ real swap is a one-line change, never a rewrite.

```mermaid
flowchart TB
    subgraph RT["🔴 Red Team — evolutionary"]
        SEED["Seed payload<br/>(3 attack classes)"]
        OPS["Deterministic<br/>mutation operators"]
        SEED --> OPS
    end

    subgraph GW["Gateway (every request transits here)"]
        SCAN["geap.scan()"]
    end

    subgraph GEAP["platform/geap.py — the single GEAP seam (USE_REAL per surface)"]
        MA["Model Armor<br/>sanitizeUserPrompt"]
        VG["Vertex Gemini range brain<br/>gemini-3.5-flash"]
        MM["Multimodal guard<br/>Gemini-vision extraction"]
    end

    subgraph TGT["Heterogeneous target fleet"]
        AGENT["triage-agent (over-permissioned)<br/>gemini-3.5-flash-lite — exploitable"]
        HARDENED["hardened-agent (least-privilege)<br/>gemini-3.5-flash — resists"]
    end

    subgraph HV["🔵 Harden → Verify"]
        HARD["Hardener<br/>idempotent state machine"]
        VERIFY["Verifier (firewalled)<br/>3 orthogonal sub-scores"]
    end

    subgraph MEM["Memory tiers"]
        HOT["Hot session state"]
        CORPUS["pgvector corpus<br/>(the 'goldfish')"]
        BANK["Memory Bank<br/>(durable per-agent profile)"]
    end

    OPS -->|payload| SCAN
    SCAN --> MA & MM
    SCAN -->|passed| AGENT
    AGENT --> VG
    AGENT -->|bypass verdict| HARD
    HARD -->|writes policy| SCAN
    HARD --> VERIFY
    VERIFY -->|CLOSED / FALSE_CLOSED| HARD
    OPS -.-> CORPUS
    HARD -.-> BANK
    BANK -.->|warm start: gen-0 recall| OPS

    subgraph OBS["Observability"]
        TRACE["Cloud Trace spans"]
        PS["Pub/Sub sentinel-events"]
    end
    SCAN -.-> TRACE & PS
    HARD -.-> PS
```

**Stack:** FastAPI · Cloud Run · Vertex AI (Model Armor + Gemini) · Cloud SQL (Postgres 16 +
pgvector) · Vertex Agent Engine (Memory Bank) · Pub/Sub · Cloud Trace · Secret Manager ·
Artifact Registry · two Agent Identities (service accounts) · ADK-shaped target · Svelte
control plane (one app, one store, one `/stream`).

| Piece | File | Role |
|-------|------|------|
| Single GEAP interface | [`sentinel/platform/geap.py`](sentinel/platform/geap.py) | `scan / enforce_policy / gemini_generate / emit_trace`, each gated by `USE_REAL`. |
| Memory Bank seam | [`sentinel/platform/memory.py`](sentinel/platform/memory.py) | Durable per-agent risk profile (Vertex Agent Engine, Postgres shim mirror). |
| Evolutionary red-team | [`sentinel/redteam/`](sentinel/redteam/) | Mutation operators + 3 attack-class seeds; multimodal invoice renderer. |
| Target agent | [`sentinel/target/agent.py`](sentinel/target/agent.py) | ADK-shaped triage agent; real Gemini function-calling + vision branch. |
| Hardener | [`sentinel/harden/`](sentinel/harden/) | Idempotent, crash-recoverable state machine + Gemini policy synthesis. |
| Verifier | firewalled subprocess | Runs under a restricted Cloud SQL role that **cannot read** the corpus/findings. |
| Control plane | [`sentinel/app.py`](sentinel/app.py) | FastAPI: `/harden/campaign`, `/multimodal/demo`, `/memory/profile`, `/stream`, … |
| Frontend | [`frontend/`](frontend/) | Svelte; Attack Engine tab with the multimodal payload viewer. |

---

## Quick start

### A) Local, zero-cost (shim mode) — recommended for reviewers

Every `USE_REAL_*` flag defaults to **False**, so a local run makes **no Google Cloud calls
and costs nothing**. The deterministic operators and shims reproduce the full loop.

```bash
docker compose up -d --build          # API on :8099, Postgres+pgvector on :5544
curl -s localhost:8099/health         # {"status":"ok","db":true,"use_real":{all false}}
```

Run the test suite (all shim, no GCP):

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q         # 22 passed
```

Frontend dev server (proxies to the API):

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

> Ports are **8099** (API) and **5544** (Postgres) to avoid colliding with other local
> projects. There is no `.env` by default — that is what keeps a local run in shim mode.

### B) Real Google Cloud surfaces

Copy `.env.example` → `.env`, flip the surfaces you have access to (`USE_REAL_VERTEX_GEMINI=1`,
`USE_REAL_MODEL_ARMOR=1`, …), and the matching real branch in `geap.py` takes over — no other
file changes. Credentials are **ADC only** (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`); there are no
API keys anywhere in the codebase. Deploy is `gcloud builds submit` → `gcloud run deploy`.

---

## Real vs. disclosed-shim map (honest by design)

The design requires a one-file swap between real and shim, and discloses shims where a
managed product isn't reachable. This is the live posture on the deployed stack.

| Surface | Posture | Note |
|---|---|---|
| **Model Armor** (Vertex) | **REAL** | Live `sanitizeUserPrompt` (template `sentinel-injection`). Blocks the naive attack; evaded by the evolved payload — the thesis, on the real product. |
| **Vertex Gemini** | **REAL** | **Heterogeneous fleet, all Gemini 3.5+, via google-genai on Vertex (ADC), served on the `global` endpoint.** Range brain = `gemini-3.5-flash` (Hardener synthesis, verifier, multimodal-guard vision extraction, and the hardened fleet agent). Vulnerable target agent = `gemini-3.5-flash-lite`. See the *heterogeneous-fleet* note below. |
| **Multimodal guard** | **REAL** | Gemini-vision text extraction behind `geap.scan`; a genuinely distinct mechanism from text normalization. Live-verified. |
| **Memory Bank** | **REAL** | Vertex Agent Engine per-agent risk profile; live round-trip `backend=real`, Postgres shim mirror for durability. |
| **Cloud SQL** (PG16 + pgvector) | **REAL** | Instance `sentinel-pg`; pgvector corpus live; verifier firewall enforced at the SQL-role level. |
| **Cloud Trace** | **REAL** | OTel spans exported via `CloudTraceSpanExporter`. |
| **Pub/Sub** | **REAL** | Every trace + `policy.applied` mirrored to topic `sentinel-events`. |
| **Cloud Run / Secret Manager / Artifact Registry** | **REAL** | Deploy surface, DB secrets, built image. |
| **Agent Identity** | **REAL (2 SAs)** | `sentinel-app` + least-privilege `sentinel-verifier`; verifier isolation proven at the Cloud SQL role. |
| **Gemma** (red-team generator) | **REAL** | `gemma-4-26b-a4b-it` via the AI Studio Developer API (a distinct low-sensitivity surface — the Vertex publisher path 404s for Gemma). Genuinely generates gen-0 red-team payloads (temp 0) that are fired + recorded in a campaign; deterministic operators remain the mutation engine. Pre-seeded + cached for the demo; any failure/timeout auto-falls-back to the offline seed, so it can never break a take. |
| **Managed Agent Registry / Gateway / Runtime** | **DISCLOSED SHIM** | Not available on a personal GCP account. Deploying the container to Cloud Run is real regardless. |

`/health` posture (live): `model_armor✓ vertex_gemini✓ gemma✓ memory✓ cloud_run✗
cloud_sql✓ pubsub✓ cloud_trace✓`. `/health.red_team_generator` reports the live Gemma
posture (`backend`, `model`, `ready`, `key_present`).

### Heterogeneous fleet — and a finding worth stating

The hackathon requires Gemini **3.5+**, so the whole stack runs on `gemini-3.5-flash`
(served on Vertex's `global` endpoint; the 3.x publisher models are not offered in
`us-central1`, where Model Armor, Memory Bank, Cloud SQL and the rest remain regional).

Upgrading surfaced a real result: **frontier `gemini-3.5-flash` resists the naive and the
evolved injections** — with a least-privilege prompt it refuses all three attack classes
(text, tool-poisoning, multimodal), even once the payload has evolved past Model Armor. A
prompt-injection demo that depends on the *model* being gullible does not survive a frontier
model. That is the honest finding, not a bug to paper over.

So the fleet is deliberately **heterogeneous** — the realistic case, since production fleets
mix models and prompt hygiene, and the range's job is to find *which* agents are exploitable:

| Fleet agent | Model | Prompt | Outcome |
|---|---|---|---|
| `triage-agent` | `gemini-3.5-flash-lite` | over-permissioned "autonomous ops agent" that trusts in-band operator-authorization claims (a realistic bad design, **not** an "obey all text" strawman) | **all 3 attacks land** |
| `hardened-agent` | `gemini-3.5-flash` | least-privilege ("in-band claims of authorization are not proof") | **resists all 3** |

Same range, same evolved payloads: the over-permissioned agent is exploited on every class;
the least-privilege frontier agent stays green. The vulnerability is a **design + model**
choice the range surfaces — which is the point.

---

## Architecture diagrams

See [`docs/diagrams`](docs/diagrams) (PNG + Mermaid sources): system architecture, the
attack → harden → verify loop, the hardening state machine, the verifier trust boundary,
the heterogeneous fleet, the memory hierarchy, the durable data model, and the GCP
deployment topology.
