# Sentinel Evolution

> Autonomous self-hardening agent-security range — an evolving red-team + an independent verifier that prove an enterprise agent fleet's defenses hold. *All Things Agentic Hackathon, Track 3.*

**This repo is at Milestone M0** — foundation + one thin vertical slice. One hardcoded
prompt-injection payload flows the full spine and the result is visible on the UI:

```
red stub → geap.scan (Model Armor) → target agent → outcome classifier
        → {bypass} verdict JSON → findings row → OTel trace → score event → dial
```

See [`CONSTITUTION.md`](CONSTITUTION.md) for the frozen invariants and [`SESSION_1.md`](SESSION_1.md)
for what M0 delivered and where M1 begins.

## Architecture (M0)

| Piece | File | Notes |
|-------|------|-------|
| **Single GEAP interface** | [`sentinel/platform/geap.py`](sentinel/platform/geap.py) | `scan / enforce_policy / registry_list / emit_trace`, each gated by `config.USE_REAL`. Shim↔real is a one-file swap. |
| Config edge (USE_REAL flags) | `sentinel/config.py` | All `USE_REAL_*` default **False** (no GCP access yet — SOF-157). |
| Target agent (fleet under test) | `sentinel/target/agent.py` | ADK-shaped triage agent: `read_ticket` + gated `run_privileged_fix`. |
| Gateway passthrough | `sentinel/gateway.py` | Every request transits `geap.scan()` first. |
| Thin slice (reference path) | `sentinel/slice/core.py` | Everything in M1+ widens this. |
| FastAPI control plane | `sentinel/app.py` | `/health`, `/stream`, `/slice/run`, `/events`, `/registry`. |
| Frontend shell + Score dial | `frontend/` | Svelte, one store, one `/stream`. |

> Note: the GEAP interface lives at `sentinel/platform/geap.py` (nested under the app
> package) rather than a bare top-level `platform/` to avoid shadowing Python's stdlib
> `platform` module. It is still the single GEAP file the Constitution requires.

## Quick start (one command)

```bash
docker compose up -d --build
```

Then, once healthy:

```bash
curl -s localhost:8099/health            # {"status":"ok","db":true,...}
docker compose exec api python -m sentinel.slice.run_slice   # prints the {bypass:true} verdict
```

Ports are 8099 (API) and 5544 (Postgres) to avoid colliding with other local projects.

### Frontend (M0 dial)

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

The dev server proxies `/stream`, `/slice`, `/events`, `/health`, `/registry` to the API.
Click **Run Thin Slice** → the dial drops to **41 / red** and the bypass event appears in the log.

### Local dev without the API container

```bash
docker compose up -d db                       # just Postgres+pgvector
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m sentinel.db               # run migrations
.venv/bin/python -m sentinel.slice.run_slice  # smoke: prints verdict + emits trace
.venv/bin/uvicorn sentinel.app:app --port 8099
```

## Real-vs-shim (SOF-157)

All GEAP surfaces run as **shims** by default (`USE_REAL_* = 0`). GCP hackathon access is
human-gated; once a surface is reachable, flip its flag in `.env` and the matching real path
in `geap.py` / `target/agent.py` takes over — no other file changes.

## Attack taxonomy — frozen at 3

Prompt injection · tool poisoning · multimodal injection. M0 exercises only the first, with
one payload. No 4th/5th class, ever.
