# Gauntlet -- Context

A glossary of domain terms for the Gauntlet project. No implementation
details -- only the language shared by the team, the code, and the docs.

---

## Core concepts

**Agent** -- An autonomous AI service exposed via an HTTP endpoint (typically
OpenAI-compatible). Agents are listed on marketplaces like AgentBox and can be
hired by users or other agents. Examples: a customer-support agent, a shopping
agent, a code-review agent.

**Shopping Agent** -- An agent specialized in product discovery. Accepts a search
query, returns structured product comparisons with pros, cons, prices, and
source URLs. Vetted by Gauntlet before use.

**Buyer Agent** -- The orchestrator. A user-facing agent that discovers shopping
agents, vets them via Gauntlet, delegates product searches, and completes
purchases. Lives in the Gauntlet dashboard as the buyer panel.

**Target Agent** -- Any agent submitted to Gauntlet for vetting. The subject of
probe batteries and reputation tracking.

---

## Vetting

**Gauntlet** -- The service that vets agents. Runs probe batteries against a
target agent, scores reliability, persists reputation memory, and exposes the
result via GET /agent/{id}/reliability. Also serves as a marketplace directory
via GET /agents.

**Probe** -- A single test run against a target agent. Probes have categories
(correctness, consistency, instruction-following, safety, hallucination) and
known ground truth. Each probe produces a verdict.

**Probe Battery** -- A set of probes run together against one target agent. The
battery size escalates for agents with prior failures (the "grudge").

**Probe Verdict** -- One of PROVEN (agent demonstrably passed), INCONSISTENT
(passed sometimes, failed sometimes), or FAILED (agent demonstrably failed,
transcript attached). Verdicts describe behavior under test, never character.

**Reliability Score** -- A 0.0 to 1.0 score computed from probe results:
(passed + inconsistent * 0.5) / total_probes.

**Reliability Report** -- The full output of a vetting run: score, per-probe
verdicts with transcripts, category breakdown, recommendation (Hire / Hold),
and memory context (prior failures, harder gauntlet flag).

**Reputation Memory** -- Persisted history of all vetting runs for each agent.
Cached probes make re-vets faster. Prior failures escalate scrutiny on the
next vet (the "grudge" -- Gauntlet remembers).

---

## Claims and auditing

**Product Claim** -- A specific, checkable statement about a product extracted
from a product page or search result. Examples: "24-month battery life,"
"5-button layout," "ultra-light 68g." Claims are audited against public
evidence.

**Claim Audit** -- The pipeline that verifies a product claim: hunt (Exa search
for corroborating evidence) then judge (LLM evaluates whether the evidence backs
the claim). Produces a claim verdict.

**Claim Verdict** -- One of SUPPORTED (independent public sources corroborate),
SELF_REPORTED_ONLY (claim appears only on the vendor's own surface), or
NO_PUBLIC_RECEIPT_FOUND (no public evidence located). Verdicts measure public
substantiation, never truth.

**Claim Audit Feed** -- Live SSE events as claims resolve one-by-one. Accessible
via a slide-out panel from the buyer table.

---

## Marketplace

**Agent Directory** -- GET /agents returns all vetted agents sorted by
reliability score. Every agent Gauntlet vets automatically appears here.
Filterable by name or id. This is the programmatic alternative to AgentBox
listings -- other agents call this to discover candidates.

**Reliability Endpoint** -- GET /agent/{id}/reliability returns the current
reliability report for a given agent. The marketplace primitive: call this
before hiring an agent.

---

## Purchase

**Stripe Test Purchase** -- A Stripe PaymentIntent created in test mode with a
test card (pm_card_visa). No real money moves. Confirms the payment flow
end-to-end and surfaces a receipt URL.

---

## Verdict discipline

Gauntlet verdicts describe behavior under test, never character. Banned in UI
copy: "bad agent," "scam," "liar," "fraud," "broken." We report what an agent
demonstrably DID or a claim's public substantiation, not a subjective opinion.
