"""Tests for the buyer orchestrator — vets shopping agents, delegates search."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.reputation import DATA_DIR


def _seed_reputation(agent_id: str, name: str, score: float, passed: int, failed: int):
    """Pre-seed the reputation store so the buyer orchestrator has agents to vet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    store_path = DATA_DIR / "reputation.json"
    if store_path.exists():
        data = json.loads(store_path.read_text())
    else:
        data = {}
    data[agent_id] = {
        "runs": [
            {
                "agent_id": agent_id,
                "name": name,
                "endpoint": f"http://localhost:9999/{agent_id}",
                "reliability_score": score,
                "total_probes": 5,
                "passed": passed,
                "inconsistent": 0,
                "failed": failed,
                "prior_failures": 0,
                "harder_gauntlet": False,
                "recommendation": "Hire" if score >= 0.8 else "Hold",
                "category_breakdown": {},
                "probe_results": [],
                "last_vetted_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "latest": {
            "agent_id": agent_id,
            "name": name,
            "endpoint": f"http://localhost:9999/{agent_id}",
            "reliability_score": score,
            "total_probes": 5,
            "passed": passed,
            "inconsistent": 0,
            "failed": failed,
            "prior_failures": 0,
            "harder_gauntlet": False,
            "recommendation": "Hire" if score >= 0.8 else "Hold",
            "category_breakdown": {},
            "probe_results": [],
            "last_vetted_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    store_path.write_text(json.dumps(data, indent=2))


class TestBuyerSearch:
    """Integration tests for POST /buyer/search."""

    def test_buyer_search_returns_vetted_agent_and_products(self, client):
        """The buyer orchestrator vets shopping agents and returns product results."""
        # Seed reputation for a reliable shopping agent
        _seed_reputation("shopper-pro", "ShopperPro", 0.94, 5, 0)

        resp = client.post("/buyer/search", json={"query": "wireless mouse"})
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()

        # Top-level shape
        assert "query" in data
        assert data["query"] == "wireless mouse"
        assert "agent_name" in data
        assert "agent_id" in data
        assert "reliability_score" in data
        assert isinstance(data["reliability_score"], (int, float))
        assert "products" in data
        assert len(data["products"]) > 0

        # Products have the right shape
        for p in data["products"]:
            assert "name" in p
            assert "price" in p
            assert "$" in p["price"]

    def test_buyer_search_uses_direct_fallback_without_vetted_agents(self, client):
        """Runs the direct pipeline when no shopping agents have been vetted."""
        # Clear reputation by writing empty store
        store_path = DATA_DIR / "reputation.json"
        store_path.write_text("{}")

        resp = client.post("/buyer/search", json={"query": "anything"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "gauntlet-direct"
        assert data["agent_name"] == "Gauntlet Direct"
        assert data["reliability_score"] is None
        assert data["products"]


class TestAgentDirectory:
    """Integration tests for GET /agents — the marketplace directory."""

    def test_directory_lists_vetted_agents(self, client):
        """GET /agents returns all vetted agents sorted by reliability."""
        _seed_reputation("shopper-pro", "ShopperPro", 0.94, 5, 0)
        _seed_reputation("deals-bot", "DealsBot-3000", 0.62, 3, 2)

        resp = client.get("/agents")
        assert resp.status_code == 200
        agents = resp.json()
        assert isinstance(agents, list)
        assert len(agents) >= 2

        # Sorted by reliability_score descending
        scores = [a["reliability_score"] for a in agents]
        assert scores == sorted(scores, reverse=True), (
            f"Agents not sorted by score: {scores}"
        )

        # Each agent has required fields
        shopper = next(a for a in agents if a["agent_id"] == "shopper-pro")
        assert shopper["name"] == "ShopperPro"
        assert shopper["reliability_score"] == 0.94
        assert "endpoint" in shopper
        assert "last_vetted_at" in shopper

    def test_directory_empty_when_no_agents(self, client):
        """Empty directory when no agents vetted."""
        store_path = DATA_DIR / "reputation.json"
        store_path.write_text("{}")

        resp = client.get("/agents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_directory_filters_by_name(self, client):
        """GET /agents?q=shopper returns matching agents."""
        _seed_reputation("shopper-pro", "ShopperPro", 0.94, 5, 0)
        _seed_reputation("deals-bot", "DealsBot-3000", 0.62, 3, 2)

        resp = client.get("/agents", params={"q": "shopper"})
        agents = resp.json()
        assert len(agents) >= 1
        assert all(
            "shopper" in a["name"].lower() or "shopper" in a["agent_id"].lower()
            for a in agents
        )

        resp = client.get("/agents", params={"q": "nonexistent"})
        assert resp.json() == []
