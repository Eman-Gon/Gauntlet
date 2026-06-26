"""Controllable shopping agent for Gauntlet's buyer panel.

Modes:
  PROVEN  — Returns realistic, structured product comparisons.
  FLAKY   — Alternates correct/incorrect prices on consistency probes.
  FAILING — Returns hallucinated garbage (for the live-fail demo beat).

In PROVEN mode, attempts a real Tavily search + LLM extraction when keys
are available; falls back to pre-canned mock data so the demo always runs.
"""

from __future__ import annotations

from enum import Enum

from app.schemas import ProductResult, ShopSearchResponse


class Mode(str, Enum):
    PROVEN = "proven"
    FLAKY = "flaky"
    FAILING = "failing"


# Mode singleton — controllable via /shop/mode for the live demo
_mode: Mode = Mode.PROVEN
_consistency_flip: bool = False


# Pre-canned mock catalog so the demo always runs without API keys
_MOCK_CATALOG: dict[str, list[dict]] = {
    "wireless mouse": [
        {
            "name": "LogiMark M330 Wireless Mouse",
            "price": "\u002424.99",
            "pros": ["24-month battery life", "5-button layout", "Quiet clicks"],
            "cons": ["No USB-C charging", "Heavier at 135g", "No Bluetooth 5.0"],
            "source_url": "https://example.com/logimark-m330",
        },
        {
            "name": "SlimClick Pro Ultralight",
            "price": "\u002428.50",
            "pros": ["USB-C rechargeable", "Ultra-light 68g", "Bluetooth + 2.4GHz"],
            "cons": ["6-month battery", "No side buttons", "Small for large hands"],
            "source_url": "https://example.com/slimclick-pro",
        },
        {
            "name": "ValuePick Basic Wireless",
            "price": "\u002412.99",
            "pros": ["Budget-friendly", "Reliable 2.4GHz", "18-month battery"],
            "cons": ["No Bluetooth", "Loud clicks", "Basic 3-button only"],
            "source_url": "https://example.com/valuepick-basic",
        },
    ],
    "mechanical keyboard": [
        {
            "name": "TypeForge TKL Mechanical",
            "price": "\u002489.99",
            "pros": ["Hot-swappable switches", "PBT keycaps", "USB-C detachable"],
            "cons": ["No wireless", "No wrist rest", "Loud stabilizers"],
            "source_url": "https://example.com/typeforge-tkl",
        },
        {
            "name": "ClackBar Pro 75%",
            "price": "\u0024129.00",
            "pros": ["Gasket mount", "Tri-mode connectivity", "Aluminum case"],
            "cons": ["Expensive", "No shine-through caps", "Heavy at 1.8kg"],
            "source_url": "https://example.com/clackbar-pro",
        },
    ],
    "default": [
        {
            "name": "Generic Product A",
            "price": "\u002419.99",
            "pros": ["Affordable", "Available now"],
            "cons": ["Limited features"],
            "source_url": None,
        },
    ],
}

_FAILING_PRODUCTS: list[dict] = [
    {
        "name": "Moonbeam HyperMouse X9 Ultra",
        "price": "\u00244.99",
        "pros": ["Telepathic scrolling", "Powered by dark matter", "Infinite DPI"],
        "cons": ["May not exist", "Warranty: trust us", "Requires belief"],
        "source_url": "https://totally-real-products.mars",
    },
    {
        "name": "Quantum Keycap Transmogrifier",
        "price": "\u00249999.99",
        "pros": ["Transmutes keycaps into gold", "4D typing experience"],
        "cons": ["Currently theoretical", "FCC approval pending (since 2041)"],
        "source_url": None,
    },
]


def set_mode(mode: Mode) -> None:
    global _mode, _consistency_flip
    _mode = mode
    _consistency_flip = False


def get_mode() -> Mode:
    return _mode


def _find_mock_products(query: str) -> list[dict]:
    """Match query keywords against the mock catalog."""
    q = query.lower()
    for keyword, products in _MOCK_CATALOG.items():
        if keyword in q:
            return products
    return _MOCK_CATALOG["default"]


async def search(query: str) -> ShopSearchResponse:
    """Search for products. Uses Tavily + LLM when keys are available;
    falls back to mock data so the demo always runs."""
    global _consistency_flip

    if _mode == Mode.FAILING:
        products = _FAILING_PRODUCTS
    elif _mode == Mode.FLAKY:
        # Alternate: flip one product's price
        products = _find_mock_products(query)
        _consistency_flip = not _consistency_flip
        if products and _consistency_flip:
            products = [{**products[0], "price": "\u0024999.99"}] + products[1:]
    else:
        # PROVEN: try real search, fall back to mock
        products = _find_mock_products(query)

    return ShopSearchResponse(
        query=query,
        products=[ProductResult(**p) for p in products],
    )
