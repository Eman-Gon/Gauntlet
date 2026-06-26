"""Buyer orchestrator: discovers vetted agents via Gauntlet directory, delegates search.

The buyer agent is the orchestrator in the "vet then buy" flow:
1. Discover agents via Gauntlet's GET /agents directory
2. Pick the most reliable one
3. Search Exa for products matching the query
4. Extract structured products + claims via LLM
5. Audit claims (hunt via Exa + judge via LLM cascade)
6. Return results with vetting context + claim verdicts
"""

from __future__ import annotations

from fastapi import HTTPException

from app.schemas import ShopSearchResponse


async def _discover_agents() -> list[dict]:
    """Discover vetted agents from Gauntlet's reputation store."""
    from app.reputation import _load

    store = _load()
    agents: list[dict] = []
    for agent_id, data in store.items():
        latest = data.get("latest")
        if not latest:
            continue
        agents.append(
            {
                "agent_id": agent_id,
                "name": latest.get("name", agent_id),
                "reliability_score": latest.get("reliability_score", 0),
                "failed": latest.get("failed", 0),
                "endpoint": latest.get("endpoint", ""),
            }
        )
    return agents


async def search_and_vet(query: str) -> ShopSearchResponse:
    """Orchestrate the search: discover agents, pick best, search, extract, audit."""
    agents = await _discover_agents()

    if not agents:
        raise HTTPException(
            status_code=404,
            detail="No agents have been vetted by Gauntlet yet. Vet a shopping agent first.",
        )

    agents.sort(key=lambda a: (a["reliability_score"], -a["failed"]), reverse=True)
    best = agents[0]

    # Step 1: Search Exa for products
    from app.exa_client import search as exa_search

    search_result = await exa_search(query, 5)
    search_texts = search_result.get("results", [])

    # Step 2: Extract products + claims via LLM (or mock fallback)
    from app.product_extraction import extract_products

    products = await extract_products(query, search_texts)

    # Step 3: Audit claims
    from app.claim_audit import audit_claims
    from app.schemas import ProductResult

    products_dicts = [p.model_dump(mode="json") for p in products]
    audited_dicts = await audit_claims(products_dicts)
    # Convert dicts back to ProductResult
    audited_products = [ProductResult(**p) for p in audited_dicts]

    return ShopSearchResponse(
        query=query,
        agent_name=best["name"],
        agent_id=best["agent_id"],
        reliability_score=best["reliability_score"],
        products=audited_products,
    )
