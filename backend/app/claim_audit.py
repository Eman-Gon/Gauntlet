"""Claim audit pipeline: hunt (Exa) -> judge (LLM cascade) -> verdict.

For each product claim marked PENDING, searches for corroborating evidence
and assigns a verdict. When LLM keys are absent, assigns mock verdicts so
the demo always runs.

SSE events fire via the global activity bus as claims resolve."""

from __future__ import annotations

import asyncio
import json
import logging
import random

from app.config import settings

log = logging.getLogger("gauntlet.claims")


async def audit_claims(products: list[dict]) -> list[dict]:
    """Resolve PENDING claims to verdicts. Runs hunt+judge per claim.
    Without Exa+LLM keys, assigns mock verdicts instantly."""
    has_exa = bool(settings.EXA_API_KEY)
    has_llm = bool(
        settings.GMI_API_KEY or settings.CHEAP_API_KEY or settings.ANTHROPIC_API_KEY
    )

    for product in products:
        claims = product.get("claims", [])
        for claim in claims:
            if claim.get("verdict") != "PENDING":
                continue
            if has_exa and has_llm:
                await _audit_claim_live(claim)
            else:
                _audit_claim_mock(claim)
    return products


async def _audit_claim_live(claim: dict) -> None:
    """Hunt via Exa + judge via LLM cascade."""
    text = claim.get("text", "")
    if not text:
        claim["verdict"] = "NO_PUBLIC_RECEIPT_FOUND"
        claim["receipts"] = []
        return

    # Hunt: search Exa for evidence
    try:
        from app.exa_client import search as exa_search

        result = await exa_search(f"{text} review evidence", 3)
        snippets = [r.get("text", "")[:300] for r in result.get("results", [])]
        urls = [r.get("url", "") for r in result.get("results", [])]
    except Exception:
        snippets, urls = [], []

    # Judge: LLM evaluates evidence
    try:
        from app.clients import chat
        from app.pipeline.judge import _SYSTEM as JUDGE_SYSTEM

        evidence_text = "\n\n".join(
            f"SOURCE {i + 1}: {s}" for i, s in enumerate(snippets) if s
        )
        if not evidence_text.strip():
            claim["verdict"] = "NO_PUBLIC_RECEIPT_FOUND"
            claim["receipts"] = []
            return

        user = f"""Claim: "{text}"

Evidence snippets from web search:
{evidence_text}

Is this claim publicly substantiated by the evidence above?"""

        result = await chat(
            "cheap",
            [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": user},
            ],
            max_tokens=256,
            temperature=0.0,
        )
        verdict_data = json.loads(_clean_json(result.text))
        claim["verdict"] = verdict_data.get("verdict", "NO_PUBLIC_RECEIPT_FOUND")
        claim["receipts"] = verdict_data.get("receipts", urls[:2])
        claim["rationale"] = verdict_data.get("rationale", "")
    except Exception:
        claim["verdict"] = "NO_PUBLIC_RECEIPT_FOUND"
        claim["receipts"] = []


def _audit_claim_mock(claim: dict) -> None:
    """Assign a mock verdict for demo purposes (no API keys needed)."""
    text = claim.get("text", "").lower()
    # Heuristic: claims about battery, weight, specs -> likely SUPPORTED
    if any(
        kw in text
        for kw in (
            "battery",
            "gram",
            "weight",
            "button",
            "click",
            "layout",
            "charging",
            "month",
        )
    ):
        claim["verdict"] = "SUPPORTED"
        claim["receipts"] = ["https://example.com/review"]
    elif any(kw in text for kw in ("quiet", "light", "comfort", "design")):
        claim["verdict"] = "SELF_REPORTED_ONLY"
        claim["receipts"] = []
    else:
        claim["verdict"] = "NO_PUBLIC_RECEIPT_FOUND"
        claim["receipts"] = []


def _clean_json(text: str) -> str:
    """Strip markdown fences and extract JSON."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines[-1].strip() == "```":
            t = "\n".join(lines[1:-1])
        else:
            t = "\n".join(lines[1:])
    return t
