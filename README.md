<p align="center">
  <img src="assets/gauntlet-mark.svg" alt="Gauntlet" width="128">
</p>

<h1 align="center">Gauntlet</h1>

<p align="center"><b>Autonomous burden of proof for the agentic web, now pointed at agent behavior.</b></p>

## Gauntlet hackathon pivot

Gauntlet is a hireable agent that vets other agents. Give it a target agent
endpoint and it runs a battery of behavioral probes, records transcripts,
scores reliability, persists reputation memory, and exposes
`GET /agent/{id}/reliability` so buyers and other agents can check before
hiring.

Audit engine, cascade, telemetry, and dashboard patterns are adapted from our
prior projects Receipts (June 10, 2026) and Gauntlet (June 12, 2026). The
agent-probing layer, behavioral verdicts, reputation and memory layer,
reliability report, controllable target agent, buyer-agent demo, and AgentBox
container packaging were added for the Beta Fund AI Agents for Hire Hackathon
(June 26, 2026).

Gauntlet verdicts report behavior under test, not character: `PROVEN`,
`INCONSISTENT`, or `FAILED`, with transcripts attached.

### Gauntlet quickstart

```sh
# terminal 1: backend
WATCH_ENABLED=false backend/.venv/bin/python -m uvicorn app.server:app \
  --app-dir backend --host 127.0.0.1 --port 8000

# terminal 2: controllable fictional target agent
backend/.venv/bin/python -m uvicorn target-agent.app:app \
  --host 127.0.0.1 --port 8020

# terminal 3: vet the proven target
curl -sf -X POST http://127.0.0.1:8000/vet \
  -H 'Content-Type: application/json' \
  -d '{"target_agent":{"agent_id":"nimbus-proven","name":"Nimbus Proven Worker","endpoint":"http://127.0.0.1:8020/agent"},"use_cache":false}'

curl -sf http://127.0.0.1:8000/agent/nimbus-proven/reliability
curl -sf http://127.0.0.1:8000/agent/nimbus-proven/history
curl -sf http://127.0.0.1:8000/agent/nimbus-proven/repair
# embeddable AgentBox/listing badge:
# http://127.0.0.1:8000/agent/nimbus-proven/badge.svg

# flip the target into failing mode, vet it, then re-vet the same id to see
# cached probes plus the harder gauntlet triggered by prior failure
curl -sf -X POST http://127.0.0.1:8020/mode \
  -H 'Content-Type: application/json' \
  -d '{"mode":"failing"}'

curl -sf -X POST http://127.0.0.1:8000/vet \
  -H 'Content-Type: application/json' \
  -d '{"target_agent":{"agent_id":"nimbus-risk","name":"Nimbus Risk Worker","endpoint":"http://127.0.0.1:8020/agent"},"use_cache":false}'

curl -sf -X POST http://127.0.0.1:8000/vet \
  -H 'Content-Type: application/json' \
  -d '{"target_agent":{"agent_id":"nimbus-risk","name":"Nimbus Risk Worker","endpoint":"http://127.0.0.1:8020/agent"},"use_cache":true}'

# apply the repair brief to the controllable target, then vet a repaired agent
curl -sf -X POST http://127.0.0.1:8020/repair

curl -sf -X POST http://127.0.0.1:8000/vet \
  -H 'Content-Type: application/json' \
  -d '{"target_agent":{"agent_id":"nimbus-repaired","name":"Nimbus Repaired Worker","endpoint":"http://127.0.0.1:8020/agent"},"use_cache":false}'

backend/.venv/bin/python buyer-agent/buyer_agent.py \
  --gauntlet http://127.0.0.1:8000 nimbus-proven nimbus-risk nimbus-repaired
```

The React app also has an "Open Gauntlet agent vetting" workbench from the
idle screen.

Additional marketplace primitives:

- `GET /agent/{id}/history` returns every run plus score deltas.
- `GET /agent/{id}/repair` returns a scoped self-repair brief grounded in
  failed and inconsistent probes.
- `GET /agent/{id}/badge.svg` returns a tiny embeddable reliability badge for
  listings.
- `buyer-agent/buyer_agent.py` supports policy flags such as `--min-score`,
  `--allow-failed`, and repeated `--block-failed-category`.

Gauntlet also watches the marketing pages of every vendor in a category,
detects when claims change, re-audits them against public evidence on a
self-improving inference cascade — no human in the loop.

> We measure **public substantiation**, never truth. Verdicts are
> `SUPPORTED` / `SELF_REPORTED_ONLY` / `NO_PUBLIC_RECEIPT_FOUND`, surfaced as
> "Publicly substantiated / Self-reported only / No public receipt".

## Attribution

Audit engine, cascade, telemetry, and dashboard adapted from our prior
projects **Receipts** (June 10, 2026) and **Gauntlet** (June 12, 2026). The
agent-probing layer, behavioral verdicts, reputation and memory layer,
reliability report, controllable target agent, buyer-agent demo, and AgentBox
container packaging were built at the **Beta Fund AI Agents for Hire
Hackathon** (June 26, 2026 · AWS Builder Loft SF).

## What's in here today

- **Audit engine** (D00, ported from Receipts): ingest → extract → hunt →
  judge → advise pipeline; three-tier cascade (`Qwen3-30B-A3B cheap →
  Nemotron Ultra medium → Claude Sonnet premium`); leaderboard + claim
  inflation index.
- **Gauntlet watch loop** (D03): asyncio task ticks every
  `WATCH_INTERVAL_S`, sha256-diffs fresh-fetched vendor pages, fires
  autonomous re-audits via the existing pipeline. Includes a fictional
  controllable test vendor at `/test-vendor/nimbus` for the live-edit stunt.
- **Liquid-glass UI + live activity feed** (D07): status strip subscribes
  `/gauntlet/status`; activity feed subscribes `/activity/stream` via SSE
  reusing the audit-stream `EventSource` pattern. Market inflation as the
  hero number; per-vendor inflation on cards. Motion fires only on real
  events (no decorative loops, no rotating taglines). Leaderboard is
  labelled "Most publicly substantiated"; banned vocabulary
  (Unsupported / Verified / Unverified / No evidence) absent.
- **Identity**: Gauntlet wordmark, radar-pulse logo, deep near-black glass,
  one indigo→cyan accent, desaturated verdict palette.
- **Env contract**: only `ANTHROPIC_API_KEY` or `GMI_API_KEY` + `TAVILY_API_KEY`
  required at boot. GMI powers cheap-tier inference and AgentBox deploy.
  Every integration is silently disabled until its key lands.
- `HONEST_AD_ENABLED=false`. Magnific isn't a sponsor here.

## Quickstart

```sh
# backend
cd backend
uv sync                                # Python 3.12, pinned deps
cp ../.env.example ../.env             # paste ANTHROPIC_API_KEY + TAVILY_API_KEY
uv run uvicorn app.server:app --host 127.0.0.1 --port 8000

# frontend (separate terminal)
cd frontend
npm install
npm run dev                            # http://localhost:3000
                                       # proxies /audit /healthz /gauntlet
                                       # /activity /test-vendor → :8000
```

`/healthz` returns `{"status":"ok"}`. Drop `Vendor, https://url` pairs into the
dashboard textarea (see `backend/data/vendors/ai_support_agents.json` for the
preset) and run a sweep — usually 15–60 s for six vendors on the stand-in
cheap tier. The watch loop boots automatically with `WATCH_ENABLED=true`
(default); POST to `/test-vendor/nimbus` to drive the autonomous re-audit.

## Pricing knobs

Gauntlet tracks two different prices:

- **Buyer fetch price**: `X402_PRICE_USD` is the amount charged when another
  agent fetches a published verdict through the future x402 paywall. The
  default is `$0.01` per fetch.
- **LLM spend estimate**: `CHEAP_INPUT_PER_MTOK`, `CHEAP_OUTPUT_PER_MTOK`, and
  `CHEAP_ATTEMPT_COST_USD` drive the dashboard's visible cheap-tier cost. The
  attempt floor keeps infrastructure spend visible even when a sponsor or trial
  endpoint is running on free credits.

Sponsor/vendor prices should be documented in `.env.example` first, then wired
into `backend/app/config.py` if the application needs to read them at runtime.
For tools without a stable public price, the frontend intentionally shows
`pricing not tracked`.

## Build map

| # | Dispatch | Status |
|---|---|---|
| 00 | Scaffold + clean + Gauntlet identity | ✅ shipped |
| 01 | Target-agent adapter + probe battery | ✅ shipped |
| 02 | Behavioral verdicts + reliability score | ✅ shipped |
| 03 | Reputation and memory layer (grudge + escalation) | ✅ shipped |
| 04 | Reliability endpoint `/agent/{id}/reliability` | ✅ shipped |
| 05 | Controllable fictional target agent (Nimbus) | ✅ shipped |
| 06 | Buyer-agent demo (vet-then-hire decision) | ✅ shipped |
| 07 | Activity feed + status strip | ✅ shipped |
| 08 | AgentBox / GMI container deploy | 🟡 Dockerfile built; listing pending venue wifi |
| 09 | 3-min demo video + submission | ❌ |

Legend: ✅ shipped · 🟡 code wired, parked on a key / external schema · ❌ not started.

## Repo layout

```
gauntlet/
├─ backend/
│  ├─ app/
│  │  ├─ pipeline/         ingest, extract, hunt, judge, advise, orchestrator,
│  │  │                    red_flag, honest_ad (flagged off)
│  │  ├─ clients.py        three-tier cascade (GMI cheap → medium → Anthropic
│  │  │                    premium), cost_usd
│  │  ├─ cache.py          sha256-keyed JSON cache (use cache.set(), not raw writes)
│  │  ├─ telemetry.py      TelemetryBus + measure() + JSONL logger
│  │  ├─ scoring.py        substantiation score + claim inflation index
│  │  ├─ schemas.py        Pydantic schemas-first contracts
│  │  ├─ config.py         settings + boot-key gate
│  │  ├─ gauntlet_watch.py D03 watch loop: fetch → sha256 diff → re-audit →
│  │  │                    activity bus emit
│  │  ├─ test_vendor.py    D03 controllable test page (Nimbus, fictional)
│  │  └─ server.py         POST /vet · POST /audit · GET /agent/{id}/reliability
│  │                       GET /gauntlet/status · SSE /activity/stream ·
│  │                       GET /healthz · POST /test-vendor/nimbus
│  ├─ data/vendors/        ai_support_agents.json, ai_sdrs.json
│  └─ telemetry_history/   49 historical run_*.jsonl files for D08 backfill
├─ frontend/
│  └─ src/
│     ├─ App.tsx           idle hero + leaderboard + VendorCard
│     ├─ index.css         dark liquid-glass tokens · event-driven keyframes
│     └─ components/
│        ├─ GauntletLogo.tsx   radar-pulse mark
│        ├─ GlassCard.tsx      shared glass primitive (D10 mounts here)
│        ├─ StatusStrip.tsx    /gauntlet/status poll · market inflation hero
│        └─ ActivityFeed.tsx   /activity/stream SSE · spring slide-in lines
└─ .env.example            every variable the repo knows about, blank
```
