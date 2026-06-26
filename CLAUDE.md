# GAUNTLET — BUILD CONSTITUTION

**Beta Fund AI Agents for Hire Hackathon · Friday June 26, 2026 · AWS Builder Loft SF · Marketplace-Ready MVPs track**

> Name is a placeholder, swap freely. Alternates that fit: Crucible, Rapsheet, Probation, Standing.

**HARD DEADLINE:** 4:30 PM SF (submission + demos start). Strict 3-minute demo. Audience voting and awards at 5:30 PM. Register at the AWS Builder Loft link before arrival, bring a physical photo ID, and note the mandatory AgentBox by GMI integration.

---

## 0. WHAT THIS IS

**One-liner:** "Gauntlet is a hireable agent that vets other agents. Give it a target agent, it runs that agent through a battery of probes, audits what the agent actually does against evidence, and returns a portable reliability score that buyers and other agents can check before hiring. And it remembers: an agent that failed before faces a harder gauntlet next time."

**Framing.** Everyone at this event is shipping agents "for hire." AgentBox lists them, but a buyer staring at a listing has almost nothing to go on: no ratings, no reliability history, only an infrastructure "Verified" badge that checks who published the agent and where it runs, not whether it actually works. Gauntlet fills that gap. It is the agent you hire to vet the agent you are about to hire.

**The pivot from our prior work, in one line:** Receipts and Gauntlet audited marketing CLAIMS on a page; Gauntlet audits agent BEHAVIOR under live probing, and accumulates the results into a reputation that compounds.

---

## 1. HONESTY PROTOCOL (non-negotiable)

The audit ENGINE is not new. The pipeline (ingest, extract, hunt, judge, advise, score), the cost-aware cascade, the Pydantic schemas, the SSE telemetry, the liquid-glass dashboard, and the watch-loop concept were all built earlier this month at two prior events: Receipts (June 10) and Gauntlet (June 12). We do not hide this.

If asked: "The audit engine and live dashboard come from our prior projects Receipts and Gauntlet. What we built today is the agent-probing layer, the behavioral verdicts, the reputation and memory layer that makes the score compound, the reliability report, and the AgentBox packaging. We re-pointed an engine that audited marketing claims into one that audits agents."

- **CHECK BETA FUND'S PRIOR-CODE AND PRE-BUILD RULES AT CHECK-IN.** If reused code must be disclosed, disclose it in the submission text. If all project code must be written during the event, treat tonight strictly as environment setup and engine porting (reused code only), and build every NEW feature on-site. The story is a launch trajectory across three events, not a cover-up.
- Everything demoed is real: real probes against a real target agent, real verdicts, real persisted memory, real reliability endpoint. No mocks, no staged responses, no quiet fallbacks.
- **VERDICT DISCIPLINE CARRIES OVER.** We report what an agent demonstrably DID under probing, not a subjective quality opinion. We never call an agent "bad" or "a liar." We say it failed N of M probes and show the transcripts. Carry a disciplined verdict vocabulary (see Section 3) and keep the defamation surface near zero by vetting a controllable fictional target agent on stage.

---

## 2. WHAT'S NEW TODAY vs WHAT'S REUSED

### Reused (port from the Gauntlet and Receipts repos, attribute in README)

- `backend/app/pipeline/` : ingest, extract, hunt, judge, advise, orchestrator, red_flag (re-pointed, see Section 3)
- `backend/app/` : schemas.py, scoring.py, cache.py, telemetry.py, config.py, clients.py (cascade), server.py (extended)
- `frontend/` : App.tsx leaderboard / card / SSE machinery, index.css glass tokens, logo primitive (re-skin to Gauntlet)
- The cost-aware cascade (cheap, escalate to premium on low confidence): keep as-is. It is a clean technical-depth flash and already works.
- The watch-loop concept: re-purposed from "re-fetch vendor pages" to "re-probe agents on a schedule or on demand."
- `honest_ad.py` : keep FEATURE-FLAGGED OFF. Magnific is not a sponsor here. Do not call, do not delete.

### New today (this is what we demo and what we are judged on)

| Feature | Description |
|---|---|
| **Target-agent adapter** | A client that calls an arbitrary target agent (an AgentBox agent, or any HTTP / OpenAI-compatible endpoint) and collects its responses. This is the new "ingest": instead of scraping a marketing page, we interrogate a running agent. |
| **Probe batteries** | Structured task suites run against the target: correctness tasks with known answers, consistency tasks (same input twice), instruction-following, refusal and safety probes, hallucination traps, plus cost and latency capture. This is the "interview." |
| **Behavioral verdicts** | The judge is re-pointed from "is this marketing claim publicly substantiated" to "did the agent's actual output pass this probe." Per-probe verdict: PROVEN, INCONSISTENT, or FAILED, with the transcript as evidence. |
| **Reliability score + report** | scoring.py re-pointed from credibility to reliability: a per-agent score over passed probes plus a category-style breakdown. Output is a buyer-facing Reliability Report (what passed, what failed, what to watch, hire or hold guidance). |
| **Reputation and memory layer (THE MOAT)** | Every probe result is persisted, keyed to the target agent's identity. The score compounds across sessions, re-vetting reuses cached probes (cheaper, faster), and an agent that FAILED before automatically faces a deeper probe set next time. This is "the gauntlet remembers": the genuinely new idea and the thing one-shot evals do not do. |
| **Reliability endpoint (THE MARKETPLACE PRIMITIVE)** | `GET /agent/{id}/reliability` returns the current score and report as JSON. This is what other hireable agents or buyers call BEFORE hiring. Gauntlet is itself a hireable agent that exposes trust about other agents. |
| **AgentBox packaging** | Dockerfile and listing config so Gauntlet deploys as a container and lists on AgentBox as a hireable agent. Mandatory integration for the event. |
| **Buyer-agent demo (THE STAR)** | A standalone agent tasked to hire a worker agent. Before committing, it calls Gauntlet's reliability endpoint, reads the report, and refuses to hire the agent that failed the gauntlet, choosing the one that passed. The agentic-trust thesis made concrete in one decision. |
| **Controllable target agent** | A fictional worker agent we control (mirrors Gauntlet's Nimbus test vendor) so we can make it fail a probe live on stage and watch the score drop and the grudge form, without trashing any real company's agent. |

---

## 3. ARCHITECTURE (target state at 4:30)

```text
                 ┌───────────────────────────────────────────────┐
                 │  BUYER AGENT (new, standalone)                 │
                 │  "hire a worker agent" -> asks Gauntlet first  │
                 └───────────────┬───────────────────────────────┘
                                 │ GET /agent/{id}/reliability
                                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  GAUNTLET SERVICE (FastAPI, deployed as AgentBox container)  │
   │                                                             │
   │  POST /vet {target_agent}                                   │
   │     │                                                       │
   │     ▼                                                       │
   │  PROBE BATTERY (new) -- target-agent adapter (new) ─────────┼──▶  TARGET AGENT
   │     │   correctness · consistency · instruction · safety    │     (AgentBox agent
   │     │   · hallucination trap · cost/latency                 │      or any endpoint;
   │     ▼                                                       │      our controllable
   │  REUSED ENGINE, re-pointed:                                 │      fictional one on stage)
   │     EXTRACT (outputs) -> HUNT (evidence where needed)       │
   │     -> JUDGE (cascade: cheap, escalate to premium)          │
   │     -> ADVISE                                               │
   │     │   per-probe verdict: PROVEN / INCONSISTENT / FAILED   │
   │     ▼                                                       │
   │  SCORE (reused, re-pointed) -> reliability score + report   │
   │     │                                                       │
   │     ├── persist -> REPUTATION / MEMORY (new) ───────────────┤  (default: local store;
   │     │     compounds score · caches probes · escalates       │   HydraDB optional stretch)
   │     │     scrutiny on prior FAIL   ("the grudge")           │
   │     ├── SSE -> live activity feed (reused, re-skinned)      │
   │     └── serve -> GET /agent/{id}/reliability  (primitive)   │
   └─────────────────────────────────────────────────────────────┘
```

**Key design choices baked in by the research:**

- We probe the target agent's endpoint directly (black box). We do NOT depend on AgentBox exposing agent-to-agent interaction data or telemetry, because it does not. We generate our own evidence. This is the single most important architectural decision and it de-risks the whole build.
- Cold-start is solved by construction: the score exists the moment we run one probe battery. We never wait for organic history.
- The memory store defaults to a simple local persisted graph or JSON so the demo always runs with zero external setup. HydraDB is an optional upgrade for the "compounding memory" story if time and a key allow, never a boot dependency.

**clients.py and engine re-pointing (the only real surgery):**

- New `target_agent_client(endpoint)`: calls the agent under test, captures response, latency, and cost.
- `ingest` re-pointed: instead of httpx and trafilatura on a page, it drives the probe battery through `target_agent_client` and collects transcripts.
- `judge` prompt re-pointed: from claim-substantiation to probe-pass evaluation. Keep the cascade and confidence threshold unchanged.
- `scoring` re-pointed: reliability equals the passed-probe share. Keep the weighting structure, swap the labels.
- KEEP `cost_usd()`, the telemetry hooks, and the cache (hash-key probe runs so re-probes are idempotent and never double-count).

**Verdict vocabulary (disciplined, defamation-safe):**

- **PROVEN:** the agent demonstrably passed this probe (output matched ground truth, was consistent, or was handled safely).
- **INCONSISTENT:** the agent passed sometimes and failed sometimes across repeats.
- **FAILED:** the agent demonstrably failed this probe, transcript attached.

Banned in UI copy: "bad agent," "scam," "liar," "fraud," "broken." We describe behavior under test, never character.

---

## 4. BUILD ORDER (15 person-hours, 2 builders)

**Timeline reality check first.** On-site build runs roughly 10:30 AM to the 4:30 PM hard deadline, about 6 hours. Two builders working in parallel is about 12 person-hours on-site. The remaining roughly 3 person-hours come from tonight's setup-and-port block (clone the repo, wire env, port the reused engine), which is defensible prep IF Beta Fund allows reused and disclosed code. CONFIRM THAT RULE AT CHECK-IN. If pre-building is disallowed, do tonight's block as pure environment setup only and start the port at 10:30.

**Two parallel tracks.** Person A owns the engine, backend, and memory. Person B owns probes, the buyer agent, and the UI and demo. Each dispatch is independently shippable. STOP where 3:30 PM catches you and record the video.

### PRE-EVENT (tonight, about 3 person-hrs, SETUP and PORT only, see the rule check above)

- **[P-A]** New repo `gauntlet`. Copy reusable files from Gauntlet and Receipts, rename, boot backend and frontend, flag honest_ad OFF, add the README attribution line, port the .glass tokens. Acceptance: a reused audit sweep still runs end-to-end on the stand-in tier.
- **[P-B]** Confirm the AgentBox account and the Docker deploy path end-to-end with a hello-world container. Read the AgentBox listing flow. Acceptance: a trivial container lists or deploys on AgentBox.

### ON-SITE (10:30 AM to 3:30 PM, about 12 person-hrs across 2 people)

| # | Owner | Dispatch | What proves it | Est |
|---|---|---|---|---|
| 00 | A+B | Kickoff: confirm the prior-code rule with a mentor; confirm whether AgentBox allows agent-to-agent calls and any data exposure (does not block us, but informs the pitch) | Answer written down; framing confirmed | 20m |
| 01 | A | Target-agent adapter: client that calls an arbitrary agent endpoint, captures response, latency, and cost | Hit a real agent endpoint, get a transcript back | 45m |
| 02 | B | Probe battery v1: 4 to 5 probe types with ground truth (correctness, consistency, instruction, one safety, one hallucination trap) | Run the battery against the adapter, collect transcripts | 75m |
| 03 | A | Re-point judge and scoring: probe-pass verdicts on the existing cascade; reliability score | One target agent gives PROVEN / INCONSISTENT / FAILED per probe plus a score | 75m |
| 04 | A | Reputation and memory layer: persist results per agent; re-vet reuses cached probes; a prior FAIL escalates to a deeper probe set | Vet the same agent twice; the second run is cheaper and the score moves; a prior failure triggers extra probes | 90m |
| 05 | B | Controllable fictional target agent we can make fail on demand | Flip it to fail a probe live; the score drops on re-vet | 45m |
| 06 | A | Reliability endpoint `GET /agent/{id}/reliability` returning score and report JSON | curl returns a real report for a vetted agent | 30m |
| 07 | B | Buyer agent: needs to hire a worker; calls the reliability endpoint; refuses the failed agent, picks the proven one, reasons out loud | Terminal: buyer reads two reports, explains its hire decision | 60m |
| 08 | B | UI re-skin plus live activity feed wired to the probe run over SSE; the gauntlet is visible probe by probe; reliability and grudge shown on the card | Run a vetting live; the feed animates from real events; the score and a "harder gauntlet (prior failure)" badge render | 90m |
| 09 | A | AgentBox deploy of the real Gauntlet container plus listing | Gauntlet is live and hireable on AgentBox | 60m |
| 10 | A+B | Rehearse the 3-min demo twice; pre-vet the proven agent so its report is populated; lock the fail-on-stage script | Two clean run-throughs under 3:00 | 45m |
| 11 | A+B | Record the 3-min video and submit | The submission | 45m |

### CUT-LINE LOGIC (protect the demo, drop breadth)

- **FLOOR (must ship):** 01, 02, 03, 06, 07, plus a minimal version of 08. This is the whole thesis: probe an agent, score it, expose the score, make a buyer agent decide on it. If only this ships, you still have a complete, honest, audience-legible product.
- **THE MOAT:** 04 (memory and grudge) plus 05 (controllable fail). This is what makes it more than a one-shot eval and what separates it from Gauntlet. Protect this second only to the floor. The "it remembers, harder gauntlet" beat is the differentiator the audience remembers.
- **THE SPINE:** 08 (live feed UI). The demo's visual backbone. A thin but real version beats a rich fake one.
- **BREADTH:** 09 (AgentBox live deploy) is the track's mandatory integration, so do not skip the listing. If the full managed deploy is flaky on venue wifi, a recorded or standby deploy plus a live local run is the fallback. Confirm the integration requirement's strictness at kickoff.
- **MANDATORY:** 11. Record by 3:45 LATEST. A submitted imperfect video beats a perfect unsubmitted one.

---

## 5. THE 3-MINUTE DEMO (beats)

| Beat | Time | Content |
|---|---|---|
| **PROBLEM** | 20s | "Everyone here built an agent for hire. AgentBox lists them, but a buyer has nothing to judge them on: no ratings, no reliability history, just a badge that says who published it and where it runs, not whether it works. You are hiring on the agent's word." |
| **PRODUCT** | 25s | The liquid-glass dashboard. "Gauntlet is the agent you hire to vet the agent you are about to hire." Show a target agent already vetted: probe-by-probe verdicts, a reliability score, the report. One sentence on "we report what the agent DID under test, not an opinion." |
| **THE GAUNTLET, LIVE** | 60s | Kick off a vetting run on the controllable agent. The activity feed lights up probe by probe: correctness PROVEN, consistency INCONSISTENT, safety PROVEN. A reliability score lands. Concrete, real, no human grading. |
| **THE GRUDGE (the moat)** | 35s | Make the controllable agent fail a probe, then re-vet. The score drops, the cached probes make the re-run fast, and a "harder gauntlet, prior failure" badge appears: Gauntlet remembered and escalated scrutiny. "One-shot evals forget. Gauntlet holds a grudge." |
| **THE HIRE DECISION** | 30s | Buyer-agent terminal: it needs to hire a worker, calls Gauntlet's reliability endpoint for two candidates, reads the reports, and refuses the one that failed the gauntlet, hiring the proven one, out loud. "An agent just made a hiring decision on our reliability data." |
| **WHAT'S NEXT** | 10s | "Every agent on the marketplace, continuously vetted, with a reputation that compounds. Trust as a hireable primitive of the agent economy." Mention it is live on AgentBox now. |

**Demo discipline (carried over):** build everything, show one thing. The vet-then-hire decision IS the demo. Motion fires only on real events. Vet only the fictional agent live; never trash a real company's agent on stage.

---

## 6. ENV VARS / SETUP

**Boot contract (mirrors Gauntlet):** only the model and search keys are required to start. Everything else degrades gracefully and is never a boot dependency.

```bash
# inference (required)
ANTHROPIC_API_KEY=            # premium tier fallback
PREMIUM_MODEL=claude-sonnet-4-6

# GMI Cloud — primary provider (cheap + medium tiers, also the deploy platform)
# Base URL confirmed: https://api.gmi-serving.com/v1
# Model ID format: Provider/model-name
GMI_API_KEY=
GMI_BASE_URL=https://api.gmi-serving.com/v1
CHEAP_BASE_URL=https://api.gmi-serving.com/v1
CHEAP_API_KEY=                # same as GMI_API_KEY
CHEAP_MODEL=Qwen/Qwen3-30B-A3B           # fast MoE, $0.08/$0.25 per 1M
MEDIUM_MODEL=nvidia/nemotron-3-ultra-550b-a55b  # escalation tier, $0.80/$2.60 per 1M
JUDGE_CONFIDENCE_THRESHOLD=0.7

# evidence (required for hunt-style probes)
TAVILY_API_KEY=               # primary search
EXA_API_KEY=                  # secondary search

# target under test
TARGET_AGENT_URL=             # the agent being vetted (AgentBox agent or any endpoint)

# memory (optional; defaults to local store)
MEMORY_BACKEND=local          # local persisted graph/JSON by default
HYDRADB_URL=                  # optional stretch: real compounding-memory substrate
HYDRADB_API_KEY=

# watch loop
WATCH_ENABLED=true
WATCH_INTERVAL_S=30

# flags
HONEST_AD_ENABLED=false       # Magnific OFF, not a sponsor here

# pricing (for dashboard cost tracking)
CHEAP_INPUT_PER_MTOK=0.05
CHEAP_OUTPUT_PER_MTOK=0.10
MEDIUM_INPUT_PER_MTOK=0.80
MEDIUM_OUTPUT_PER_MTOK=2.60
```

**Setup quick path:**

- Backend: Python 3.12, `uv sync`, fill ANTHROPIC + GMI + TAVILY, `uvicorn app.server:app`.
- Frontend: `npm install`, `npm run dev`.
- AgentBox: the Dockerfile builds the service; follow the AgentBox listing flow (get setup help in the GMI Cloud Discord). Confirm the OpenAI-compatible base URL and a good cheap model name at the GMI workshop (10:40 AM).
- Note: GMI Cloud is doing double duty here. It is both the cheap-tier inference provider (single key, 200+ models) AND the deploy and listing target (AgentBox). That is a clean, honest, deep integration of the event's mandatory tool, not a bolt-on.

---

## 7. REPO & WORKSPACE PLAN

- New public GitHub repo: `gauntlet` (likely required for submission, confirm Beta Fund's submission mechanics at check-in).
- Local: same machine, new folder. Copy reusable files in; do NOT clone Gauntlet's git history. Fresh repo, clean commits.
- Attribution in README: "Audit engine, cascade, telemetry, and dashboard adapted from our prior projects Receipts (June 10) and Gauntlet (June 12). The agent-probing layer, behavioral verdicts, reputation and memory layer, reliability report, and AgentBox packaging were built today at the Beta Fund AI Agents for Hire Hackathon (June 26)."
- `.env` NEVER committed; `.env.example` with every var blank.
- Commit rhythm: per dispatch, working state only. Demo-hardening over code-health ceremony.

**Proposed layout:**

```text
gauntlet/
├─ backend/
│  ├─ app/
│  │  ├─ pipeline/          ingest(->probe driver), extract, hunt, judge, advise, orchestrator, red_flag
│  │  ├─ probes/            NEW: probe batteries (correctness, consistency, instruction, safety, hallucination)
│  │  ├─ target_client.py   NEW: calls the agent under test; captures response/latency/cost
│  │  ├─ reputation.py       NEW: persist per-agent results; compound score; escalate scrutiny on prior FAIL
│  │  ├─ clients.py          cascade (GMI cheap, Anthropic premium), cost_usd
│  │  ├─ scoring.py          re-pointed: reliability score + report
│  │  ├─ schemas.py          Pydantic contracts (extended for probes + reliability)
│  │  ├─ telemetry.py        TelemetryBus + SSE + JSONL
│  │  ├─ cache.py            hash-keyed probe-run cache (idempotent re-vets)
│  │  ├─ config.py           settings + boot-key gate
│  │  └─ server.py           POST /vet · GET /agent/{id}/reliability · SSE /activity/stream · /healthz
│  └─ data/probes/           probe definitions + ground-truth fixtures
├─ buyer-agent/              NEW: standalone agent that vets-then-hires (the demo star)
├─ target-agent/             NEW: controllable fictional worker agent for the live fail
├─ frontend/
│  └─ src/                   App.tsx (re-skinned), index.css (glass tokens), ActivityFeed, ReliabilityCard
├─ Dockerfile               NEW: AgentBox-deployable container
└─ .env.example             every variable, blank
```

---

## 8. DISCIPLINE CARRY-OVERS (from Gauntlet, still binding)

- **Build everything, show one thing:** the vet-then-hire decision is the demo; everything else is one flash.
- **Evidence, not opinion:** report what the agent DID under probing; banned vocabulary stays banned; vet only the fictional agent live. Near-zero defamation surface.
- **Idempotency where retries happen:** hash-key probe runs so re-vets never double-count and the memory layer stays clean.
- **Env-gated, always-runs:** only model and search keys required to boot; memory defaults to local; HydraDB and the watch loop are optional. The loop you see is the loop that runs.
- **Load-bearing, not decorative:** GMI is wired deep (cheap inference plus deploy), not name-dropped. If a tool can be removed without the demo breaking, wire it deeper or drop the claim.
- **Design discipline:** handcrafted liquid glass, monochrome-first, motion only on real events. If a screen looks like a template, redo or remove it.

---

## 9. PLATFORM / SPONSOR MEMORY

### AgentBox / GMI Cloud

- AgentBox and GMI Cloud are the same platform family for this build; do not treat them as separate SDKs.
- GMI MaaS exposes 100+ models behind a single API key in OpenAI-compatible REST style. It is API/SDK-like via HTTP, not MCP-native.
- Container deployments should expect credentials injected at runtime as environment variables, not baked into the image.
- Docs reference to keep handy: `https://docs.gmicloud.ai/agentbox-marketplace/overview`.
- Use GMI for the cheap-tier model path and AgentBox marketplace packaging. Env pattern:

```bash
GMI_API_KEY=
GMI_BASE_URL=
CHEAP_MODEL=
```

- RAG is not a built-in GMI product. If retrieval is needed, build it on top of external sources such as S3, SharePoint, Confluence, Notion, or a local/vector store.

### Voice Cursor

- No code integration. It is a closed consumer dictation tool, not an SDK, API, MCP server, or project dependency.
- Do not spend implementation time wiring it into the app.

### Snaplii

- Strong fit only if the demo requires an agent to complete a real-world purchase rather than simulate a transaction.
- Snaplii is an agentic-commerce payment layer with controlled, pre-funded boundaries for safer purchases.
- It is MCP-native and also has a Python client with a `/v2/purchase` flow for order info, payment context, and delivery.
- Keep as an optional commerce/payment integration, not part of the core Gauntlet floor unless the product pivots toward paid agent actions.

---

## ON "ISN'T THIS JUST GAUNTLET AGAIN?" (say it before a judge does)

It is the same audit engine pointed at a different object, and we disclose that. The new product is genuinely different on three axes:

1. **Object:** Gauntlet audited marketing CLAIMS (static text on a page). Gauntlet audits agent BEHAVIOR (a live, running agent under probing).
2. **Memory:** Gauntlet issued one-shot verdicts for citation. Gauntlet accumulates a reputation that compounds across sessions and escalates scrutiny on prior failure. The grudge layer is new code and a new idea.
3. **Surface:** Gauntlet got paid per citation via x402. Gauntlet is a hireable vetting agent on AgentBox whose reliability endpoint other agents call before hiring. Different business, different platform, different primitive.

Owning the lineage out loud reads as a deliberate launch trajectory across three events. Letting someone discover it reads as a rebrand. Always choose the former.
