"""Minimal Stripe test-mode client -- zero dependencies beyond stdlib.

Uses Stripe's REST API directly (no stripe-python package) so the
buyer-agent stays pip-free.  Test-mode only: fake cards, no real money.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

STRIPE_API = "https://api.stripe.com/v1"

# Stripe pre-built test payment methods (always available in test mode)
TEST_PAYMENT_METHODS = {
    "visa": "pm_card_visa",
    "mastercard": "pm_card_mastercard",
    "amex": "pm_card_amex",
    "declined": "pm_card_visa_chargeDeclined",
    "insufficient_funds": "pm_card_visa_insufficientFunds",
    "three_d_secure": "pm_card_threeDSecure2Required",
}


class StripeError(RuntimeError):
    """Raised when the Stripe API returns an error."""


class StripeTestClient:
    """Stripe test-mode client for agent-driven purchases."""

    def __init__(
        self,
        api_key: str | None = None,
    ):
        self._key = api_key or os.environ.get("STRIPE_TEST_KEY", "")
        if not self._key or not self._key.startswith("sk_test_"):
            raise StripeError(
                "STRIPE_TEST_KEY must be a test secret key (sk_test_...). "
                "Real keys are rejected to prevent accidental charges."
            )

    # -- Products & Prices (catalog) --

    def list_products(self, limit: int = 10) -> list[dict]:
        """List test products (the merchant catalog the agent can buy from)."""
        data = self._get("/products", params={"limit": str(limit), "active": "true"})
        return data.get("data", [])

    def list_prices(self, product_id: str | None = None, limit: int = 10) -> list[dict]:
        """List prices (SKUs with amounts). Optionally filter by product."""
        params: dict = {
            "limit": str(limit),
            "active": "true",
            "expand[]": "data.product",
        }
        if product_id:
            params["product"] = product_id
        data = self._get("/prices", params=params)
        return data.get("data", [])

    # -- PaymentIntent (the purchase) --

    def create_payment_intent(
        self,
        amount: int,
        currency: str = "usd",
        description: str = "Gauntlet buyer-agent purchase",
    ) -> dict:
        """Create a PaymentIntent. amount is in cents (500 = $5.00)."""
        body = {
            "amount": str(amount),
            "currency": currency,
            "description": description,
            "payment_method_types[]": "card",
        }
        return self._post("/payment_intents", body)

    def confirm_payment(
        self,
        payment_intent_id: str,
        payment_method: str = "pm_card_visa",
    ) -> dict:
        """Confirm a PaymentIntent with a test payment method."""
        body = {
            "payment_method": payment_method,
        }
        return self._post(f"/payment_intents/{payment_intent_id}/confirm", body)

    def retrieve_payment_intent(self, payment_intent_id: str) -> dict:
        return self._get(f"/payment_intents/{payment_intent_id}")

    # -- Full purchase flow --

    def purchase(
        self,
        amount: int,
        currency: str = "usd",
        description: str = "Gauntlet buyer-agent purchase",
        payment_method: str = "pm_card_visa",
    ) -> dict:
        """Create and confirm a purchase in one call. Returns the PaymentIntent."""
        pi = self.create_payment_intent(amount, currency, description)
        confirmed = self.confirm_payment(pi["id"], payment_method)
        return confirmed

    # -- Checkout Session (hosted page) --

    def create_checkout_session(
        self,
        amount: int,
        currency: str = "usd",
        product_name: str = "Test Purchase",
        success_url: str = "https://example.com/success",
        cancel_url: str = "https://example.com/cancel",
    ) -> dict:
        """Create a Stripe Checkout Session for a one-time payment.
        Returns a URL the user (or agent) can visit to complete payment.
        In test mode, use card 4242 4242 4242 4242."""
        body = {
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items[0][price_data][currency]": currency,
            "line_items[0][price_data][product_data][name]": product_name,
            "line_items[0][price_data][unit_amount]": str(amount),
            "line_items[0][quantity]": "1",
        }
        return self._post("/checkout/sessions", body)

    # -- Internal HTTP --

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = STRIPE_API + path
        if params:
            url = f"{url}?{urlencode(params)}"
        req = Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {self._key}")
        return self._fetch(req, path)

    def _post(self, path: str, body: dict) -> dict:
        url = STRIPE_API + path
        encoded = urlencode(body).encode()
        req = Request(url, data=encoded, method="POST")
        req.add_header("Authorization", f"Bearer {self._key}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        return self._fetch(req, path)

    def _fetch(self, req: Request, path: str) -> dict:
        try:
            with urlopen(req, timeout=30) as resp:  # noqa: S310
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                detail = json.loads(body)
                msg = detail.get("error", {}).get("message", body)
            except (json.JSONDecodeError, AttributeError):
                msg = body
            raise StripeError(f"{path} returned HTTP {exc.code}: {msg}") from exc
        except URLError as exc:
            raise StripeError(f"{path} connection failed: {exc}") from exc
