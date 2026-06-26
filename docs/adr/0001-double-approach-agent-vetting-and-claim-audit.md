# ADR 0001: Double Approach -- Agent Vetting and Claim Audit

**Status:** Accepted
**Date:** 2026-06-26

## Context

The buyer panel needs to show users which products to buy and why they can
trust the recommendation. Two sources of trust are available:

1. **Agent vetting** -- Gauntlet probes the shopping agent that found the
   products. A reliable agent (PROVEN on correctness, consistency, safety)
   is more trustworthy than one with prior failures.

2. **Claim audit** -- Each product's marketing claims ("24-month battery")
   can be checked against public evidence. An agent may be reliable but
   still relay an unsubstantiated claim from a vendor.

## Decision

The buyer panel will surface **both** trust signals:

- **Agent reliability** -- shown as a badge on the results table ("ShopperPro
  94%") with expandable probe breakdown.
- **Claim substantiation** -- shown per-product as a collapsed count ("4/5
  backed") with expandable per-claim verdicts.

The table groups results by the vetted shopping agent that discovered them.
Users can buy at any time; unresolved claims show a warning but do not block
purchase.

## Alternatives considered

- **Agent-only (Option A):** Only show agent reliability. Simpler, faster,
  but misses the product-level trust signal. Rejected because claim auditing
  differentiates Gauntlet from a simple agent directory.
- **Claims-only (Option B):** Only audit product claims. The Sentinel
  crossover is clean, but loses the "agent vets agent" thesis that is
  Gauntlet's core differentiator.

## Consequences

- The codebase now has two audit paths: agent probes (existing, via
  /vet) and claim audits (new, via the hunt+judge pipeline re-pointed
  from Sentinel).
- Real-time claim resolution requires Exa search + LLM judging, which
  introduces network dependencies. The mock catalog serves as a fallback
  when Exa is unavailable (preserving the always-runs contract).
- The frontend table component is more complex: two expandable detail
  sections (probe breakdown + claim verdicts) plus an SSE slide-out panel.
- Users can purchase before claims resolve -- the trust signal is
  informational, not a gate.
