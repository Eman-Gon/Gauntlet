"""Tests for the claim audit pipeline."""

from __future__ import annotations


class TestClaimAudit:
    """POST /shop/audit-claims resolves PENDING claims to verdicts."""

    def test_audit_resolves_pending_claims(self, client):
        """Given products with PENDING claims, the audit resolves them."""
        resp = client.post(
            "/shop/audit-claims",
            json={
                "products": [
                    {
                        "name": "Test Mouse",
                        "price": "$24.99",
                        "source_url": "https://example.com/test",
                        "claims": [
                            {"text": "24-month battery life", "verdict": "PENDING"},
                            {"text": "Quiet clicks", "verdict": "PENDING"},
                        ],
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "products" in data
        products = data["products"]
        assert len(products) == 1
        for claim in products[0]["claims"]:
            assert claim["verdict"] != "PENDING"
            assert claim["verdict"] in (
                "SUPPORTED",
                "SELF_REPORTED_ONLY",
                "NO_PUBLIC_RECEIPT_FOUND",
            )
            assert "receipts" in claim

    def test_audit_handles_no_claims(self, client):
        """Products with no claims return unchanged."""
        resp = client.post(
            "/shop/audit-claims",
            json={
                "products": [
                    {"name": "No Claims Mouse", "price": "$10", "claims": []},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["products"][0]["claims"] == []

    def test_audit_handles_missing_products(self, client):
        """Missing products field returns empty list gracefully."""
        resp = client.post("/shop/audit-claims", json={})
        assert resp.status_code == 200
        assert resp.json()["products"] == []
