"""Tests for the Stripe purchase endpoint."""
from __future__ import annotations

import os
import pytest


class TestBuyerPurchase:
    """Integration tests for POST /buyer/purchase."""

    @pytest.mark.skipif(
        not os.environ.get("STRIPE_TEST_KEY") and not os.environ.get("SNAPLII_TEST_MODE"),
        reason="STRIPE_TEST_KEY not set — set it to run Stripe integration tests",
    )
    def test_purchase_creates_payment_intent(self, client):
        """POST /buyer/purchase creates a Stripe test-mode PaymentIntent."""
        resp = client.post("/buyer/purchase", json={
            "amount_cents": 500,
            "currency": "usd",
            "description": "Test purchase from buyer panel",
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        assert data["status"] == "succeeded"
        assert "id" in data
        assert data["id"].startswith("pi_")
        assert "amount_received" in data
        assert data["amount_received"] == 500

    def test_purchase_requires_amount(self, client):
        """Missing amount_cents returns 422."""
        resp = client.post("/buyer/purchase", json={"description": "test"})
        assert resp.status_code == 422

    def test_purchase_missing_body(self, client):
        """Empty body returns 422."""
        resp = client.post("/buyer/purchase", json={})
        assert resp.status_code == 422
