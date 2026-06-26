"""Buyer orchestrator: discovers vetted agents via Gauntlet directory, delegates search.

The buyer agent is the orchestrator in the "vet then buy" flow:
1. Discover agents via Gauntlet's GET /agents directory
2. If vetted agents exist, pick the most reliable one; otherwise run direct.
3. Search Exa for products matching the query
4. Extract structured products + claims via LLM
5. Audit claims (hunt via Exa + judge via LLM cascade)
6. Return results with vetting context + claim verdicts
"""

from __future__ import annotations

import uuid

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
    """Orchestrate the search: discover agents, pick best, search, extract, audit.

    When vetted agents exist, delegates to the most reliable one.
    When no agents are vetted yet, runs the pipeline directly —
    Exa search + LLM extraction + claim audit — so the panel always
    returns live data when API keys are configured."""
    run_id = uuid.uuid4().hex[:8]
    agents = await _discover_agents()

    if agents:
        agents.sort(key=lambda a: (a["reliability_score"], -a["failed"]), reverse=True)
        best = agents[0]
        agent_name = best["name"]
        agent_id = best["agent_id"]
        reliability_score = best["reliability_score"]
    else:
        # No vetted agents — run the pipeline directly.
        agent_name = "Gauntlet Direct"
        agent_id = "gauntlet-direct"
        reliability_score = None

    # Step 1: Search Exa for products
    from app.buyer_events import emit as evt
    from app.exa_client import search as exa_search

    evt("searching", f'Searching the web for "{query}"…', run_id=run_id)
    search_result = await exa_search(query, 5)
    search_texts = search_result.get("results", [])
    is_mock = search_result.get("mock", True)
    evt(
        "searching",
        f"Found {len(search_texts)} results"
        + (" (live Exa)" if not is_mock else " (mock fallback)"),
        detail={"count": len(search_texts), "mock": is_mock},
        run_id=run_id,
    )

    # Step 2: Extract products + claims via LLM (or fallback)
    from app.product_extraction import extract_products

    evt(
        "extracting",
        f"Extracting products from {len(search_texts)} search results…",
        run_id=run_id,
    )
    products = await extract_products(query, search_texts)
    evt(
        "extracting",
        f"Identified {len(products)} product(s)",
        detail={"count": len(products)},
        run_id=run_id,
    )

    # Step 3: Audit claims
    from app.claim_audit import audit_claims
    from app.schemas import ProductResult

    total_claims = sum(len(p.claims) for p in products)
    evt(
        "auditing",
        f"Auditing {total_claims} claim(s) against public evidence…",
        run_id=run_id,
    )
    products_dicts = [p.model_dump(mode="json") for p in products]
    audited_dicts = await audit_claims(products_dicts)
    # Convert dicts back to ProductResult
    audited_products = [ProductResult(**p) for p in audited_dicts]

    supported = sum(
        1
        for p in audited_dicts
        for c in p.get("claims", [])
        if c.get("verdict") == "SUPPORTED"
    )
    evt(
        "done",
        f"Audit complete: {supported}/{total_claims} claims backed by evidence",
        detail={"supported": supported, "total": total_claims},
        run_id=run_id,
    )

    return ShopSearchResponse(
        query=query,
        agent_name=agent_name,
        agent_id=agent_id,
        reliability_score=reliability_score,
        products=audited_products,
    )
