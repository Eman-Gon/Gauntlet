"""Tests for product extraction from search results."""

from __future__ import annotations


class TestProductExtraction:
    """POST /shop/extract turns Exa results into structured products."""

    def test_extract_returns_products_from_text(self, client):
        """Given search result text, the LLM extracts products with claims."""
        resp = client.post(
            "/shop/extract",
            json={
                "query": "wireless mouse under 30",
                "search_texts": [
                    {
                        "title": "Mouse A",
                        "url": "https://ex.com/a",
                        "text": "Mouse A has 24-month battery and quiet clicks. $24.99.",
                    },
                    {
                        "title": "Mouse B",
                        "url": "https://ex.com/b",
                        "text": "Mouse B is ultralight at 68g. USB-C charging. $28.50.",
                    },
                ],
            },
        )
        # Without LLM keys, falls back to mock data — but the response shape is valid
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        assert isinstance(data["products"], list)
        assert len(data["products"]) > 0
        for p in data["products"]:
            assert "name" in p
            assert "price" in p
            assert "claims" in p
            assert isinstance(p["claims"], list)
            for claim in p["claims"]:
                assert "text" in claim
                assert "verdict" in claim
                assert claim["verdict"] in (
                    "PENDING",
                    "SUPPORTED",
                    "SELF_REPORTED_ONLY",
                    "NO_PUBLIC_RECEIPT_FOUND",
                )

    def test_extract_empty_search_texts(self, client):
        """Empty search texts returns empty products."""
        resp = client.post(
            "/shop/extract",
            json={
                "query": "nothing",
                "search_texts": [],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["products"] == []
