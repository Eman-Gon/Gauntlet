# Sentinel — Project Story

> **Autonomous burden of proof for the agentic web.**

## Inspiration

Software is increasingly bought by agents, not people. An AI assistant picking a
support tool, an SDR platform, or a vector database reads the vendor's marketing
page and takes it at face value — because that page is the only machine-readable
thing on offer.

But marketing copy is written to persuade humans. "Best-in-class." "Trusted by
thousands." "10x faster." None of it is substantiated, and an agent has no way to
tell a claim with a public receipt behind it from one invented in a growth
meeting. **Marketing inflated for humans is invisible to agents** — and that gap
is about to get expensive, because agents are starting to spend real money on
what those pages tell them.

We wanted to build the missing layer: a system that treats every vendor claim as
a **burden of proof**, hunts for public evidence, renders a verdict an agent can
cite, and — crucially — keeps doing it *without a human in the loop*. If the
agentic web is going to transact, it needs machine-readable trust. Sentinel
produces it, keeps it fresh, and gets paid per fetch for the service.

One principle anchored the whole project: **we measure public substantiation,
never truth.** Every verdict is one of

$$\text{verdict} \in \{\ \texttt{SUPPORTED},\ \ \texttt{SELF\_REPORTED\_ONLY},\ \ \texttt{NO\_PUBLIC\_RECEIPT\_FOUND}\ \}$$

surfaced to readers as *"Publicly substantiated / Self-reported only / No public
receipt."* We never say a vendor is lying — we say whether the open web backs
them up.

## What it does

Sentinel watches the marketing pages of every vendor in a category. When a claim
changes, it re-audits that vendor against public evidence on a self-improving
inference cascade, publishes the structured result to **cited.md** where other
agents can read it, and charges those agents per fetch via **x402**.

The audit pipeline is a chain of specialized stages:

```
ingest → extract → hunt → judge → advise
```

- **ingest / extract** pull the page and lift out atomic, checkable claims.
- **hunt** searches the open web (Tavily) for corroborating receipts.
- **judge** assigns a verdict + confidence per claim.
- **advise / scoring** roll the verdicts into a per-vendor *substantiation score*
  and a category-wide **claim inflation index** — the hero number on the
  dashboard.

The substantiation score for a vendor is just the receipt-backed share of its
checkable claims:

$$S_v = \frac{\#\{\,c \in C_v : \text{verdict}(c) = \texttt{SUPPORTED}\,\}}{|C_v|}$$

and market inflation is the gap between what the category asserts and what it can
prove:

$$I = 1 - \frac{1}{N}\sum_{v=1}^{N} S_v$$

## How we built it

**Architecture.** A FastAPI backend runs the pipeline and a `asyncio` **watch
loop** that ticks every `WATCH_INTERVAL_S`, re-fetches each vendor page,
`sha256`-diffs it against the last snapshot, and fires an autonomous re-audit on
any change. A React + Vite frontend renders a dark "liquid-glass" dashboard whose
status strip polls `/sentinel/status` and whose activity feed subscribes to
`/activity/stream` over SSE — so the entire autonomous loop is visible in real
time. **Motion only fires on real events**; nothing on the screen is decorative.

**The inference cascade.** Cost was a first-class design constraint. Every audit
starts on a cheap tier and only escalates to a premium model when confidence is
below `JUDGE_CONFIDENCE_THRESHOLD`:

$$\text{route}(c) = \begin{cases} \texttt{cheap} & \text{conf}_{\text{cheap}}(c) \ge \tau \\ \texttt{premium} & \text{otherwise} \end{cases}$$

The cheap client resolves through a priority chain — **TrueFoundry gateway →
Pioneer adaptive tier → local stand-in** — and on every escalation it fires a
fire-and-forget `{claim, cheap_verdict, premium_verdict}` feedback POST so the
cheap tier can *learn from the premium tier's corrections*. That's the
"self-improving" part: the cascade gets cheaper over time as the small model
absorbs where the big model overruled it.

**Schemas-first.** Every stage boundary is a Pydantic contract (`schemas.py`), so
the pipeline stages are independently testable and the telemetry is structured
from the first byte. A `sha256`-keyed cache means an unchanged re-audit is free
and never double-publishes.

**Env-gated integrations.** The hardest product decision was making a demo that
*always runs* while leaving room for a dozen sponsor integrations. We settled on a
strict boot contract: only `ANTHROPIC_API_KEY` + `TAVILY_API_KEY` are required to
start. Every later integration — Pioneer, TrueFoundry, Senso, x402, ClickHouse,
Composio, Thesys — stays silently disabled until *both* its key and its config
land. The publish and notify seams still emit `skipped:no_key` activity events
when a key is absent, so the feed renders the full loop end-to-end even on a
laptop with nothing configured.

**Telemetry → warehouse.** Every run logs structured JSONL; 49 historical runs are
checked in for a ClickHouse Cloud backfill, with Airbyte syncing external context
into the same warehouse for leaderboard analytics.

## What we learned

- **"Substantiation, not truth" is a feature, not a hedge.** Once we stopped
  trying to adjudicate whether a vendor was *right* and only measured whether the
  public web *backed them up*, the whole product got sharper — verdicts became
  defensible, the vocabulary got disciplined (we banned *Verified / Unverified /
  Unsupported / No evidence* from the UI), and the legal surface shrank to nearly
  nothing.
- **A confidence-gated cascade is most of the cost story.** Routing the easy
  claims to a small model and reserving the premium model for genuine ambiguity
  did far more for unit economics than any single model swap — and the feedback
  loop means that ratio improves with use.
- **Designing for "key-absent" makes a system honest.** Forcing every integration
  to degrade gracefully to a visible `skipped:no_key` event meant we were never
  faking the demo — the loop you see is the loop that runs.
- **The money moment is a paywall, not a pitch.** The clearest way to prove agents
  *need* this is to make one pay for it: a buyer agent fetching a verdict through
  an x402 paywall is worth more than any slide.

## Challenges we faced

- **Real autonomy needs a controllable stunt.** To demo "claim changes → Sentinel
  notices → re-audits → republishes" live, we couldn't wait for a real vendor to
  edit their site. We built a fictional, controllable test vendor
  (`/test-vendor/nimbus`) we can mutate on stage to trigger the autonomous
  re-audit on demand.
- **Idempotency under a watch loop.** A loop that re-audits on every tick will
  happily publish duplicates. Hash-keying audits and caching by content was
  essential to keep cited.md clean — an unchanged page costs nothing and
  republishes nothing.
- **External schema gaps.** The cited.md publish path is fully built — markdown
  compiler, idempotency cache, conditional POST — but parked on a
  `geo_question_id` schema requirement in the publisher's onboarding flow, which
  we deliberately chose not to force during the hack. Knowing *when not to ship a
  half-integration* was its own discipline.
- **Scope under a clock.** Sentinel's audit engine was adapted from our prior
  project **Receipts**; everything in the autonomy, inference-cascade, publish,
  and payment layers was built in a single day at **Harness Engineering Hack**
  (June 12, 2026 · AWS Builder Loft SF). Deciding what to wire as a *seam* (ready
  the moment a key lands) versus what to fully ship was the constant trade.

## What's next

Close the loop end-to-end: ship the **x402 paywall** on the verdict endpoint and
the **buyer agent** that pays for a fetch — the full money moment — then turn on
the ClickHouse sink for the 49-run backfill and the Composio claim-change alerts
that are already seamed in. The vision is simple: **every claim on the agentic
web, carrying its own receipt, priced per read.**
