"""Buyer orchestrator: discovers vetted agents via Gauntlet directory, delegates search.

The buyer agent is the orchestrator in the "vet then buy" flow:
1. Discover agents via Gauntlet's GET /agents directory
2. Pick the most reliable one
3. Delegate the product search to that agent
4. Return results with vetting context
"""

from __future__ import annotations

from fastapi import HTTPException

from app.schemas import ShopSearchResponse
from app.shopping_agent import search as shop_search


async def _discover_agents() -> list[dict]:
    """Discover vetted agents from Gauntlet's reputation store.

    Reads the same store that GET /agents serves. Every agent Gauntlet
    vets automatically appears here -- no hardcoded list.
    """
    from app.reputation import _load
    store = _load()
    agents: list[dict] = []
    for agent_id, data in store.items():
        latest = data.get("latest")
        if not latest:
            continue
        agents.append({
            "agent_id": agent_id,
            "name": latest.get("name", agent_id),
            "reliability_score": latest.get("reliability_score", 0),
            "failed": latest.get("failed", 0),
            "endpoint": latest.get("endpoint", ""),
        })
    return agents


async def search_and_vet(query: str) -> ShopSearchResponse:
    """Orchestrate the search: discover agents, pick best, delegate."""
    agents = await _discover_agents()

    if not agents:
        raise HTTPException(
            status_code=404,
            detail="No agents have been vetted by Gauntlet yet. Vet a shopping agent first.",
        )

    # Pick the best: highest score, fewest failures
    agents.sort(key=lambda a: (a["reliability_score"], -a["failed"]), reverse=True)
    best = agents[0]

    # Delegate the search to the shopping agent (mock or real)
    result = await shop_search(query)

    # Attach vetting context to the response
    return ShopSearchResponse(
        query=query,
        agent_name=best["name"],
        agent_id=best["agent_id"],
        reliability_score=best["reliability_score"],
        products=result.products,
    )
