"""Tests for the shopping agent search endpoint."""
from __future__ import annotations


def test_shop_search_returns_products(client):
    """POST /shop/search returns structured product data."""
    resp = client.post("/shop/search", json={"query": "wireless mouse under 30"})

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    # Response shape
    assert "query" in data
    assert data["query"] == "wireless mouse under 30"
    assert "products" in data
    assert isinstance(data["products"], list)
    assert len(data["products"]) > 0

    # Product shape
    product = data["products"][0]
    assert "name" in product
    assert "price" in product
    assert "pros" in product
    assert "cons" in product
    assert isinstance(product["pros"], list)
    assert isinstance(product["cons"], list)


def test_shop_search_returns_valid_prices(client):
    """Product prices are strings with dollar signs."""
    resp = client.post("/shop/search", json={"query": "mechanical keyboard"})
    assert resp.status_code == 200
    data = resp.json()

    for product in data["products"]:
        price = product["price"]
        assert isinstance(price, str)
        assert "$" in price, f"Price should contain $: {price}"


def test_shop_search_handles_empty_query(client):
    """Empty query returns 422 (validation error)."""
    resp = client.post("/shop/search", json={"query": ""})
    # Should fail validation
    assert resp.status_code == 422


def test_shop_search_missing_query_field(client):
    """Missing query field returns 422."""
    resp = client.post("/shop/search", json={})
    assert resp.status_code == 422
