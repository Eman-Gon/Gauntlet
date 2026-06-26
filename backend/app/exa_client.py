"""Exa search client -- product discovery and claim hunting.

Exa is a search API optimized for content-rich results (titles, URLs,
text snippets). Used in two modes:
  1. Product search: "best wireless mouse under $30" -> product listings
  2. Claim hunt: "LogiMark M330 24-month battery review" -> evidence

Falls back to mock data when EXA_API_KEY is absent (always-runs contract).
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXA_API = "https://api.exa.ai/search"

# Mock search results so the demo always runs without an Exa key.
# Structured like real Exa responses for the LLM extraction prompt.
MOCK_SEARCH_RESULTS: dict[str, list[dict]] = {
    "wireless mouse": [
        {
            "title": "LogiMark M330 Wireless Mouse Review",
            "url": "https://example.com/logimark-m330",
            "text": "The LogiMark M330 offers 24-month battery life, a 5-button layout, and quiet clicks. At $24.99 it is a solid mid-range pick. No USB-C charging, and at 135g it is heavier than competitors.",
        },
        {
            "title": "SlimClick Pro Ultralight -- Best Travel Mouse 2026",
            "url": "https://example.com/slimclick-pro",
            "text": "The SlimClick Pro weighs just 68g and charges via USB-C. Bluetooth and 2.4GHz dual-mode. Battery lasts 6 months. No side buttons and small for large hands. $28.50.",
        },
        {
            "title": "ValuePick Basic Wireless Mouse",
            "url": "https://example.com/valuepick-basic",
            "text": "Budget option at $12.99. Reliable 2.4GHz connection, 18-month battery life. No Bluetooth support and the clicks are noticeably loud. Basic 3-button design.",
        },
    ],
    "default": [
        {
            "title": "Sample Product A",
            "url": "https://example.com/product-a",
            "text": "A generic product with some features and a price of $19.99.",
        },
    ],
}


def _mock_search(query: str, num_results: int = 5) -> list[dict]:
    """Match query keywords against the mock catalog."""
    q = query.lower()
    for keyword, results in MOCK_SEARCH_RESULTS.items():
        if keyword in q:
            return results[:num_results]
    return MOCK_SEARCH_RESULTS["default"][:num_results]


async def search(query: str, num_results: int = 5) -> dict:
    """Search Exa. Returns {"results": [...], "mock": bool}."""
    from app.config import settings

    key = settings.EXA_API_KEY

    if not key:
        return {"results": _mock_search(query, num_results), "mock": True}

    try:
        body = json.dumps(
            {
                "query": query,
                "numResults": num_results,
                "contents": {"text": True},
            }
        ).encode()
        req = Request(EXA_API, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=15) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        results = []
        for r in data.get("results", []):
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "text": r.get("text", ""),
                }
            )
        return {"results": results, "mock": False}
    except (HTTPError, URLError, Exception) as exc:
        import logging

        logging.getLogger("gauntlet.exa").warning(
            "Exa search failed, using mock: %s", exc
        )
        return {"results": _mock_search(query, num_results), "mock": True}
