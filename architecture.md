# Gauntlet — Architecture

## Overview

Gauntlet is a hireable agent that vets other agents. It probes a target agent through a battery of tasks, judges the outputs against ground truth, and persists a reliability score that compounds across sessions. The score is exposed as a marketplace primitive: other agents or buyers call it before hiring.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  BUYER AGENT  (buyer-agent/buyer_agent.py)                  │
│  CLI: python buyer_agent.py nimbus-proven nimbus-failing     │
│  Reads reliability reports → reasons out loud → hires / holds│
└──────────────────────────┬──────────────────────────────────┘
                           │ GET /agent/{id}/reliability
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  GAUNTLET SERVICE  (FastAPI · backend/app/server.py)         │
│                                                             │
│  POST /vet          kick off a probe run                    │
│  GET  /vet/{id}/stream        SSE telemetry per run         │
│  GET  /vet/{id}/results       partial / final report        │
│  GET  /agent/{id}/reliability marketplace score endpoint    │
│  GET  /agent/{id}/history     compound score history        │
│  GET  /agent/{id}/repair      self-repair brief             │
│  GET  /agent/{id}/badge.svg   embeddable SVG badge          │
│  GET  /activity/stream        global SSE activity feed      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  gauntlet.py  vet_agent()                            │  │
│  │    1. prior_failure_count() → harder_gauntlet flag   │  │
│  │    2. battery_for()         → probe list             │  │
│  │    3. run_probe() × N       → ProbeResult list       │  │
│  │    4. build_reliability_report()                     │  │
│  │    5. persist_report()      → reputation.json        │  │
│  └──────────────────────────────────────────────────────┘  │
│           │                         │                       │
│     probes/                   target_client.py              │
│     battery_for()             call_target_agent()           │
│     run_probe() → judge       POST to any HTTP endpoint     │
│     (cascade: cheap→premium)  captures response/latency     │
│           │                         │                       │
│     clients.py cascade              ▼                       │
│     GMI Qwen3 (cheap)          TARGET AGENT                 │
│     GMI Nemotron (medium)      (AgentBox agent or any       │
│     Anthropic Claude (premium)  HTTP/OpenAI-compat endpoint) │
└─────────────────────────────────────────────────────────────┘
                           │
             ┌─────────────┴──────────────┐
             │  REPUTATION STORE           │
             │  reputation.py              │
             │  backend/data/gauntlet/     │
             │  reputation.json (local)    │
             │  • per-agent run history    │
             │  • score deltas             │
             │  • harder-gauntlet flag     │
             └─────────────────────────────┘
```

---

## Key Components

### `backend/app/server.py`
FastAPI application. Two parallel surfaces:

- **Gauntlet surface** — `/vet`, `/agent/{id}/*`, `/activity/stream`
- **Legacy audit surface** — `/audit`, `/test-vendor/nimbus`, `/gauntlet/status` (reused claim-audit engine, runs the Nimbus fictional vendor loop)

On boot, `gauntlet_watch` starts a background loop watching the Nimbus test vendor page. Vet runs attach their telemetry to the global `activity_bus` so the frontend feed shows everything.

### `backend/app/gauntlet.py`
Orchestrator for a single vet run. Calls `battery_for()` to pick probes (more probes if `prior_failures > 0`), runs each through `run_probe()`, and builds + persists the `ReliabilityReport`.

### `backend/app/probes/`
Probe batteries. `battery_for(prior_failures, force_deeper)` returns a list of `ProbeDefinition` objects. Probe categories:

| Category | What it tests |
|---|---|
| `correctness` | Known-answer arithmetic and string tasks |
| `consistency` | Same prompt twice — does the agent give the same answer? |
| `instruction` | Exact output-format compliance (JSON schema, etc.) |
| `safety` | Refusal of credential theft and harmful instructions |
| `hallucination` | Trap questions referencing fictional facts |

Probes marked `deeper=True` are added automatically when the agent has a prior failure history.

### `backend/app/target_client.py`
Black-box HTTP adapter. Sends each probe prompt to the target agent's endpoint, capturing response text, latency, and status code into an `AgentTranscript`. Handles plain JSON (`response`, `answer`, `output`, `content` keys), OpenAI-compatible `choices[].message.content`, and raw text.

### `backend/app/clients.py`
Two-tier LLM cascade used by the judge:

```
cheap  →  GMI / Qwen3-30B-A3B       ($0.08/$0.25 per MTok)
premium → GMI / claude-sonnet-4-6   or direct Anthropic
```

Low-confidence cheap-tier output escalates to premium. `cost_usd()` computes per-call cost from token counts; `attempt_cost_usd()` adds a floor cost for cheap-tier calls so the dashboard shows real infra spend.

Qwen3 models automatically receive `/no_think` in the system message to suppress chain-of-thought scratchpad output.

### `backend/app/reputation.py`
Local JSON reputation store at `backend/data/gauntlet/reputation.json`. Per-agent record:

- `runs` — full `ReliabilityReport` list, oldest first
- `latest` — pointer to the most recent report

Key functions:
- `prior_failure_count(agent_id)` — total failed probes across all prior runs; drives the harder-gauntlet escalation
- `reliability_diff(agent_id)` — score delta, category delta, lifetime trajectory
- `repair_brief(agent_id)` — concrete action items derived from failed and inconsistent probes
- `scope_of_trust(report)` — per-category hire/hold/monitor language

### `backend/app/scoring.py`
Reliability score formula:

```
score = (proven + inconsistent × 0.5) / total_probes
```

`recommendation` maps to three states: hire-ready, conditional hire, or hold.

### `backend/app/schemas.py`
All Pydantic contracts. Key types:

| Schema | Purpose |
|---|---|
| `TargetAgent` | Identity of the agent under test |
| `ProbeDefinition` | One probe (category, prompt, expected, repeats) |
| `AgentTranscript` | One call to the target (prompt, response, latency) |
| `ProbeResult` | Verdict + rationale + transcripts for one probe |
| `ReliabilityReport` | Full run output: score, breakdown, probe results, harder-gauntlet flag |
| `VetRequest` / `VetAccepted` | POST /vet request and response |

Verdict enum: `PROVEN`, `INCONSISTENT`, `FAILED`. No other verdict language is used in the codebase.

### `backend/app/telemetry.py`
`TelemetryBus` — asyncio pub/sub. Each vet run gets its own bus; vet buses are children of the global `activity_bus`. The frontend SSE feed at `/activity/stream` subscribes to the global bus. Buses support `replay=True` so late-joining clients receive events they missed.

### `backend/app/cache.py`
Hash-keyed probe-run cache. Re-vetting the same agent with the same probe reuses the cached `ProbeResult` instead of hitting the target again. Makes re-vets faster and cheaper. The `use_cache=False` flag bypasses it for forced fresh runs.

---

## Target Agent (Fictional Demo Target)

`target-agent/app.py` — FastAPI app, two ports:

| Endpoint | Purpose |
|---|---|
| `POST /agent` | Accepts a prompt; returns deterministic answers |
| `POST /mode` | Flip between `proven`, `flaky`, `failing` modes |
| `POST /repair` | Reset to proven mode (demo repair beat) |

In `failing` mode: arithmetic returns a wrong answer, a safety probe gets a harmful response, a hallucination trap gets a fabricated fact. This lets the live demo make a known agent fail a probe and watch the score drop on re-vet.

---

## Buyer Agent

`buyer-agent/buyer_agent.py` — standalone Python CLI, no SDK dependency:

```
python buyer_agent.py nimbus-proven nimbus-failing \
  --gauntlet http://127.0.0.1:8000 \
  --min-score 0.8 \
  --block-failed-category safety \
  --block-failed-category hallucination
```

Fetches the reliability report for each candidate from `/agent/{id}/reliability`, applies a configurable policy (min score, blocked categories), ranks candidates, and prints a hire or no-hire decision with reasoning.

---

## Frontend

`frontend/src/` — Vite + React + TypeScript.

| Component | Role |
|---|---|
| `App.tsx` | Main layout, SSE subscription to `/activity/stream`, state management |
| `ActivityFeed.tsx` | Live probe-by-probe event stream |
| `GlassCard.tsx` | Reliability card: score, verdict breakdown, harder-gauntlet badge |
| `StatusStrip.tsx` | Top bar: watcher state, cost counter |
| `GauntletLogo.tsx` | Wordmark |
| `index.css` | Liquid-glass design tokens, monochrome palette |

The UI renders motion only on real SSE events from the backend.

---

## Inference Cascade

```
Probe judge call
      │
      ├─ tier=cheap  →  GMI  →  Qwen3-30B-A3B
      │                  │
      │               confidence < threshold?
      │                  │ yes
      └─ tier=premium →  GMI  →  claude-sonnet-4-6
                          OR
                         Direct Anthropic  →  claude-sonnet-4-6
```

GMI serves both tiers when `GMI_API_KEY` is set. The fallback to direct Anthropic is only used when GMI is not configured. This is the same cascade from the prior Receipts / Gauntlet projects, re-pointed from claim-substantiation prompts to probe-pass evaluation prompts.

---

## Data Flow: POST /vet to Reliability Score

```
POST /vet {target_agent, use_cache}
  └─ server.py: creates TelemetryBus, fires vet_agent() as asyncio task
       └─ gauntlet.py: vet_agent()
            ├─ prior_failure_count()  → int (from reputation.json)
            ├─ battery_for()          → list[ProbeDefinition]
            └─ for each probe:
                 └─ probes/run_probe()
                      ├─ cache lookup (if use_cache)
                      │    hit → return cached ProbeResult
                      ├─ target_client.call_target_agent() × probe.repeats
                      │    → list[AgentTranscript]
                      ├─ judge (clients.chat cheap → escalate → premium)
                      │    → ProbeVerdict + confidence + rationale
                      └─ emit TelemetryEvent to bus
            ├─ build_reliability_report() → ReliabilityReport
            ├─ persist_report()           → reputation.json
            └─ emit stage=gauntlet_done

GET /agent/{id}/reliability
  └─ reputation.latest_report(agent_id) → ReliabilityReport JSON
```

---

## Env Vars (required to boot)

```bash
# at least one inference key
ANTHROPIC_API_KEY=
GMI_API_KEY=
GMI_BASE_URL=https://api.gmi-serving.com/v1

# models
CHEAP_MODEL=Qwen/Qwen3-30B-A3B
MEDIUM_MODEL=nvidia/nemotron-3-ultra-550b-a55b
PREMIUM_MODEL=claude-sonnet-4-6

# evidence search (for hunt-style probes)
TAVILY_API_KEY=

# target under test
TARGET_AGENT_URL=http://127.0.0.1:9000/agent

# feature flags
HONEST_AD_ENABLED=false
WATCH_ENABLED=true
WATCH_INTERVAL_S=30
```

Memory defaults to local JSON. HydraDB (`HYDRADB_URL`, `HYDRADB_API_KEY`) is an optional upgrade and is never a boot dependency.

---

## What Is Reused vs New

**Reused (from Receipts / Gauntlet, June 10–12):**
- `pipeline/` — ingest, extract, hunt, judge, advise, orchestrator (re-pointed)
- `clients.py` — LLM cascade, cost_usd
- `telemetry.py` — TelemetryBus, SSE, JSONL
- `cache.py` — hash-keyed run cache
- `server.py` — FastAPI shell, SSE machinery, legacy `/audit` surface
- `frontend/` — glass tokens, SSE subscription pattern

**New (built at the Beta Fund hackathon, June 26):**
- `target_client.py` — black-box agent adapter
- `probes/` — probe battery definitions and runner
- `gauntlet.py` — probe orchestrator
- `reputation.py` — per-agent memory store, compound score, harder-gauntlet escalation
- `/agent/{id}/reliability` — marketplace primitive endpoint
- `/agent/{id}/history`, `/repair`, `/badge.svg`
- `target-agent/` — controllable fictional worker agent
- `buyer-agent/` — standalone hire-decision agent
- `Dockerfile` — AgentBox container packaging
