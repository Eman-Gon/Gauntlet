"""Extract structured products and claims from search result text.

Uses the cheap-tier LLM to parse raw Exa search text into:
  [{name, price, claims: [{text, verdict: PENDING}], source_url}, ...]

Claims default to PENDING verdict -- the claim audit pipeline resolves them.
When LLM is unavailable or fails, falls back to showing raw search results
as product cards so users can see live data even without LLM keys."""

from __future__ import annotations

import logging

from app.schemas import ProductResult
from app.shopping_agent import _find_mock_products

log = logging.getLogger("gauntlet.extraction")


async def extract_products(
    query: str,
    search_texts: list[dict],
    agent_name: str | None = None,
) -> list[ProductResult]:
    """Extract products from search result text using LLM.

    When LLM keys are available, sends the search text to the cheap-tier
    model with a structured extraction prompt. Falls back to mock catalog
    when keys are absent (always-runs contract).
    """
    if not search_texts:
        return []

    # Try real LLM extraction
    try:
        from app.clients import chat
        from app.config import settings

        if (
            not settings.CHEAP_API_KEY
            and not settings.GMI_API_KEY
            and not settings.ANTHROPIC_API_KEY
        ):
            log.info("No LLM keys configured — using raw search results")
            raise RuntimeError("no LLM keys")

        prompt = _build_extraction_prompt(query, search_texts)
        log.info(
            "Extracting products via LLM for query=%r (%d search results)",
            query,
            len(search_texts),
        )
        result = await chat(
            "cheap",
            [
                {"role": "system", "content": _EXTRACTION_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.0,
        )
        products = _parse_extraction_response(result.text)
        if products:
            log.info("LLM extracted %d products for query=%r", len(products), query)
            return products
        log.warning("LLM returned no parseable products, falling back")
    except Exception as exc:
        log.warning("LLM extraction failed for query=%r: %s", query, exc)

    # Fallback: show raw search results as product cards
    if search_texts:
        log.info("Falling back to raw search results (%d items)", len(search_texts))
        return _raw_results_as_products(search_texts)

    # Last resort: mock catalog
    mock = _find_mock_products(query)
    return [
        ProductResult(
            name=p["name"],
            price=p["price"],
            pros=p.get("pros", []),
            cons=p.get("cons", []),
            source_url=p.get("source_url") or p.get("url", ""),
            claims=[{"text": pro, "verdict": "PENDING"} for pro in p.get("pros", [])]
            + [{"text": con, "verdict": "PENDING"} for con in p.get("cons", [])],
        )
        for p in mock
    ]


_EXTRACTION_SYSTEM = """You extract structured product data from search result text.
Return ONLY a valid JSON array. No markdown, no explanation.
Each element must have exactly these keys:
- "name": product name (string)
- "price": price with currency symbol (e.g. "$24.99")
- "claims": array of checkable factual claims about the product (strings)
- "source_url": the URL where this product was found

Include only specific, checkable claims. Skip vague marketing ("best", "amazing").
Example: "24-month battery life" is checkable. "Great value" is not."""


def _build_extraction_prompt(query: str, search_texts: list[dict]) -> str:
    texts = "\n\n".join(
        f"SOURCE: {r.get('title', '')} ({r.get('url', '')})\n{r.get('text', '')}"
        for r in search_texts
    )
    return f"""Extract products matching "{query}" from these search results.
For each product found, extract the name, price, checkable claims, and source URL.

{texts}"""


def _parse_extraction_response(response: str) -> list[ProductResult]:
    import json

    # Strip markdown code fences if present
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    products = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        claims = item.get("claims", [])
        if isinstance(claims, list):
            claims = [
                {"text": str(c), "verdict": "PENDING"} if isinstance(c, str) else c
                for c in claims
            ]
        products.append(
            ProductResult(
                name=str(item.get("name", "Unknown")),
                price=str(item.get("price", "$?")),
                pros=[],
                cons=[],
                source_url=str(item.get("source_url", "")),
                claims=claims if isinstance(claims, list) else [],
            )
        )
    return products


def _raw_results_as_products(search_texts: list[dict]) -> list[ProductResult]:
    """Convert raw Exa search results into product cards when LLM extraction
    is unavailable. Each search result becomes a product card with the title
    as name, snippets as claims, and URL as source."""
    products: list[ProductResult] = []
    seen_urls: set[str] = set()
    for r in search_texts:
        url = r.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        title = r.get("title", "Untitled")
        text = r.get("text", "")
        # Extract checkable claims from the snippet text
        claims: list[dict] = []
        if text:
            sentences = [
                s.strip() for s in text.replace("\n", ". ").split(".") if s.strip()
            ]
            claims = [{"text": s[:200], "verdict": "PENDING"} for s in sentences[:5]]
        products.append(
            ProductResult(
                name=title[:120],
                price="$?",
                pros=[],
                cons=[],
                source_url=url,
                claims=claims,
            )
        )
    return products
