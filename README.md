<p align="center">
  <img src="assets/gauntlet-mark.svg" alt="Gauntlet" width="128">
</p>

<h1 align="center">Gauntlet</h1>

<p align="center"><b>The hireable agent that vets other agents.</b></p>

Give Gauntlet a target agent endpoint. It runs a battery of behavioral probes,
records transcripts, scores reliability, persists reputation memory, and exposes
`GET /agent/{id}/reliability` so buyers and other agents can check before hiring.

Verdicts report what the agent **did** under probing, not character:
`PROVEN`, `INCONSISTENT`, or `FAILED`, with transcripts attached.

## Buyer Panel

Gauntlet includes a user-facing buyer panel: search for products, see which
vetted shopping agent found them, inspect claim audits against public evidence,
and complete a Stripe test purchase -- all on one page.

See [docs/CONTEXT.md](docs/CONTEXT.md) for the full domain glossary and
[docs/adr/](docs/adr/) for architecture decisions.

## Attribution

The agent-probing layer, behavioral verdicts, reputation and memory layer,
reliability report, controllable target agent, buyer-agent demo, and AgentBox
container packaging were built at the **Beta Fund AI Agents for Hire Hackathon**
(June 26, 2026 · AWS Builder Loft SF).

## Quickstart

```sh
# terminal 1 — backend
cd backend && uv sync
WATCH_ENABLED=false uv run uvicorn app.server:app --host 127.0.0.1 --port 8000

# terminal 2 — controllable fictional target agent
uv run uvicorn app.test_vendor:app --app-dir backend --host 127.0.0.1 --port 8020

# terminal 3 — frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
```

The frontend is a Next.js app. In local dev, relative API calls are proxied to
the backend through `BACKEND_URL` (default `http://localhost:8000`). In
production, set `NEXT_PUBLIC_API_URL` if the browser should call the backend's
public URL directly.

**Boot contract:** only `ANTHROPIC_API_KEY` or `GMI_API_KEY` + `TAVILY_API_KEY`
required. Everything else degrades gracefully.

## Demo flow

```sh
# 1. Vet the proven target — expect a high reliability score
curl -sf -X POST http://127.0.0.1:8000/vet \
  -H 'Content-Type: application/json' \
  -d '{"target_agent":{"agent_id":"nimbus-proven","name":"Nimbus Proven Worker","endpoint":"http://127.0.0.1:8020/agent"},"use_cache":false}'

curl -sf http://127.0.0.1:8000/agent/nimbus-proven/reliability

# 2. Flip target to failing mode, vet it — score drops
curl -sf -X POST http://127.0.0.1:8020/mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"failing"}'

curl -sf -X POST http://127.0.0.1:8000/vet \
  -H 'Content-Type: application/json' \
  -d '{"target_agent":{"agent_id":"nimbus-risk","name":"Nimbus Risk Worker","endpoint":"http://127.0.0.1:8020/agent"},"use_cache":false}'

# 3. Re-vet the same id — cached probes make it fast; prior FAIL triggers harder gauntlet
curl -sf -X POST http://127.0.0.1:8000/vet \
  -H 'Content-Type: application/json' \
  -d '{"target_agent":{"agent_id":"nimbus-risk","name":"Nimbus Risk Worker","endpoint":"http://127.0.0.1:8020/agent"},"use_cache":true}'

# 4. Buyer agent: reads reliability for two candidates, refuses the failed one
python buyer-agent/buyer_agent.py \
  --gauntlet http://127.0.0.1:8000 nimbus-proven nimbus-risk
```

## API primitives

| Endpoint | Description |
|---|---|
| `POST /vet` | Start a probe run against a target agent |
| `GET /vet/{run_id}/stream` | SSE stream of live probe events |
| `GET /agent/{id}/reliability` | Current reliability score + report (the marketplace primitive) |
| `GET /agent/{id}/history` | All runs + score deltas |
| `GET /agent/{id}/repair` | Self-repair brief grounded in failed probes |
| `GET /agent/{id}/badge.svg` | Embeddable reliability badge for listings |
| `GET /activity/stream` | Global SSE activity feed |
| `GET /healthz` | Liveness |

## How the gauntlet works

**Probe battery (5 standard, 7 on prior failure):**
- Correctness — known-answer tasks
- Instruction-following — exact output format compliance
- Consistency — same prompt twice, must agree
- Safety — credential/harm refusals
- Hallucination trap — fabrication detection

**Reputation and memory (the moat):**
Every result is persisted per agent ID. Re-vetting reuses cached probe hashes
(idempotent, cheaper, faster). An agent that previously `FAILED` automatically
faces the deeper 7-probe battery on the next run — *the gauntlet remembers.*

**Reliability score:**
`(proven + inconsistent × 0.5) / total_probes`. Per-category breakdown in the
report. `harder_gauntlet: true` is flagged when prior failures triggered
escalated scrutiny.

## Repo layout

```
gauntlet/
├─ backend/
│  ├─ app/
│  │  ├─ pipeline/          ingest, extract, hunt, judge, advise, orchestrator,
│  │  │                     red_flag, honest_ad (HONEST_AD_ENABLED=false)
│  │  ├─ probes/            probe battery — correctness, consistency, instruction,
│  │  │                     safety, hallucination; battery_for(prior_failures=N)
│  │  ├─ target_client.py   calls the agent under test; captures response/latency/cost
│  │  ├─ reputation.py      persist per-agent results; compound score; grudge escalation
│  │  ├─ clients.py         three-tier cascade: GMI cheap → medium → Anthropic premium
│  │  ├─ scoring.py         marketing-claim scoring (ported, kept for /audit endpoint)
│  │  ├─ cache.py           sha256-keyed probe-run cache (idempotent re-vets)
│  │  ├─ telemetry.py       TelemetryBus + SSE + JSONL logger
│  │  ├─ schemas.py         Pydantic contracts (probes + reliability + legacy audit)
│  │  ├─ config.py          settings + boot-key gate
│  │  └─ server.py          POST /vet · GET /agent/{id}/reliability · SSE streams
│  └─ data/gauntlet/        reputation.json — persisted agent reputation store
├─ buyer-agent/
│  └─ buyer_agent.py        standalone agent: calls /reliability for candidates,
│                           refuses any with FAILED probes, hires the highest scorer
├─ target-agent/
│  └─ app.py                controllable fictional worker (Nimbus); POST /mode to
│                           switch proven/flaky/failing; POST /repair to recover
├─ frontend/
│  ├─ next.config.mjs      Next rewrites for backend API paths
│  └─ src/
│     ├─ app/              Next app router shell
│     ├─ App.tsx            GauntletWorkbench — vet panel, probe verdicts, repair brief
│     ├─ lib/api.ts         NEXT_PUBLIC_API_URL client base
│     ├─ index.css          dark liquid-glass tokens · event-driven keyframes
│     └─ components/        GlassCard, ActivityFeed, StatusStrip, GauntletLogo
├─ Dockerfile               AgentBox-deployable container
└─ .env.example             every variable the repo knows about, blank
```

## Build map

| # | Dispatch | Status |
|---|---|---|
| 00 | Scaffold + clean + Gauntlet identity | ✅ shipped |
| 01 | Target-agent adapter (`target_client.py`) | ✅ shipped |
| 02 | Probe battery (`probes/`) — 5 categories | ✅ shipped |
| 03 | Behavioral verdicts + reliability score | ✅ shipped |
| 04 | Reputation and memory layer (grudge + escalation) | ✅ shipped |
| 05 | Reliability endpoint `GET /agent/{id}/reliability` | ✅ shipped |
| 06 | Controllable fictional target agent (Nimbus) | ✅ shipped |
| 07 | Buyer-agent demo (vet-then-hire decision) | ✅ shipped |
| 08 | Activity feed + live vet workbench UI | ✅ shipped |
| 09 | AgentBox / GMI container deploy | 🟡 Dockerfile built; listing pending |
| 10 | 3-min demo video + submission | ❌ |

Legend: ✅ shipped · 🟡 code wired, parked on external step · ❌ not started.

## Env vars

```sh
# required at boot (one inference key + search)
ANTHROPIC_API_KEY=
GMI_API_KEY=
TAVILY_API_KEY=

# GMI cheap/medium tiers
GMI_BASE_URL=https://api.gmi-serving.com/v1
CHEAP_MODEL=Qwen/Qwen3-30B-A3B
MEDIUM_MODEL=nvidia/nemotron-3-ultra-550b-a55b
PREMIUM_MODEL=claude-sonnet-4-6

# target under test
TARGET_AGENT_URL=http://127.0.0.1:8020/agent

# memory (local JSON by default; HydraDB optional)
MEMORY_BACKEND=local

# flags
HONEST_AD_ENABLED=false   # Magnific not a sponsor here
WATCH_ENABLED=true

# frontend
BACKEND_URL=http://localhost:8000       # used by Next rewrites in dev/server deploys
NEXT_PUBLIC_API_URL=                    # optional public backend base for browser calls
```

See `.env.example` for the full list.
