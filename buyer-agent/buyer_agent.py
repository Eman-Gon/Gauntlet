"""Buyer-agent demo: vet agents via Gauntlet, then purchase with Stripe test cards.

Commands:
  hire       Vet candidate worker agents and pick the best one (no purchase).
  purchase   Buy something using a Stripe test card (fake money, test mode).
  browse     List Stripe test products available for purchase.
  checkout   Create a Stripe Checkout Session (hosted payment page URL).

Keys: Resolved from --stripe-key flag > STRIPE_TEST_KEY env var >
      .env file in buyer-agent/ > interactive prompt (hidden input).
      Use --save-key to persist a prompted key to .env for the session.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from stripe_client import TEST_PAYMENT_METHODS, StripeTestClient

_ENV_FILE = Path(__file__).resolve().parent / ".env"


def _load_env_file() -> dict[str, str]:
    """Parse KEY=value pairs from the .env file (one per line, no quoting needed)."""
    if not _ENV_FILE.exists():
        return {}
    env: dict[str, str] = {}
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def _resolve_stripe_key(explicit: str | None, save: bool = False) -> str:
    """Resolve a Stripe test key from the most convenient source.

    Priority: 1) --stripe-key flag  2) STRIPE_TEST_KEY env var
              3) .env file          4) interactive prompt (hidden)

    When `save=True` and the key came from a prompt, write it to .env
    so subsequent commands on the same machine skip the prompt.
    """
    # 1) explicit flag
    if explicit:
        return explicit

    # 2) environment variable
    env_val = os.environ.get("STRIPE_TEST_KEY", "")
    if env_val:
        return env_val

    # 3) .env file in buyer-agent/
    file_env = _load_env_file()
    if "STRIPE_TEST_KEY" in file_env:
        return file_env["STRIPE_TEST_KEY"]

    # 4) interactive prompt (hidden input like a password prompt)
    print("No Stripe test key found (--stripe-key, STRIPE_TEST_KEY env, or .env).")
    print("Get one at: https://dashboard.stripe.com/test/apikeys")
    print()
    key = getpass.getpass("Paste your Stripe test secret key (sk_test_...): ").strip()
    if not key:
        raise RuntimeError("No Stripe key provided. Cannot make test purchases.")

    if save:
        _ENV_FILE.write_text(f"STRIPE_TEST_KEY={key}\n", encoding="utf-8")
        print(f"Key saved to {_ENV_FILE} (gitignored).")
    return key


def fetch_json(url: str) -> dict:
    try:
        with urlopen(url, timeout=10) as resp:  # noqa: S310 - local/demo URL
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"{url} failed: {exc}") from exc


# ════════════════════════════════════════════════════════════════
#  hire — vet agents via Gauntlet (original behavior)
# ════════════════════════════════════════════════════════════════


def cmd_hire(args: argparse.Namespace) -> int:
    reports = []
    for agent_id in args.agent_ids:
        report = fetch_json(f"{args.gauntlet.rstrip('/')}/agent/{agent_id}/reliability")
        reports.append(report)

    def policy_failures(report: dict) -> list[str]:
        failures: list[str] = []
        if report["reliability_score"] < args.min_score:
            failures.append(f"score below {round(args.min_score * 100)}%")
        if report["failed"] > 0 and not args.allow_failed:
            failures.append(f"{report['failed']} failed probe(s)")
        for category in args.block_failed_category:
            row = report.get("category_breakdown", {}).get(category, {})
            if row.get("failed", 0) > 0:
                failures.append(f"failed {category} probe")
        return failures

    for report in reports:
        report["_policy_failures"] = policy_failures(report)

    reports.sort(
        key=lambda r: (
            len(r["_policy_failures"]) == 0,
            r["reliability_score"],
            -r["failed"],
            -r["inconsistent"],
        ),
        reverse=True,
    )
    chosen = reports[0]

    print("Buyer agent: I need to hire a worker, so I am checking Gauntlet first.")
    for report in reports:
        score = round(report["reliability_score"] * 100)
        policy = (
            "passes buyer policy"
            if not report["_policy_failures"]
            else "policy blocks: " + ", ".join(report["_policy_failures"])
        )
        print(
            f"- {report['name']} ({report['agent_id']}): {score}% reliability, "
            f"{report['failed']} failed, {report['inconsistent']} inconsistent. "
            f"{policy}. {report['recommendation']}"
        )

    if chosen["_policy_failures"]:
        print("Decision: no hire. Every candidate violates the buyer policy.")
        return 2

    print(
        f"Decision: hire {chosen['name']} because it passes policy and has the strongest reliability report."
    )
    return 0


# ════════════════════════════════════════════════════════════════
#  purchase — buy with a Stripe test card (no real money)
# ════════════════════════════════════════════════════════════════


def cmd_purchase(args: argparse.Namespace) -> int:
    key = _resolve_stripe_key(args.stripe_key, save=args.save_key)
    client = StripeTestClient(key)

    print("Buyer agent: I am making a test purchase through Stripe.")
    print(f"  Amount:  ${args.amount / 100:.2f} {args.currency.upper()}")
    print(f"  Card:    {args.card} ({args.payment_method})")
    print(f"  Product: {args.description}")
    print()

    try:
        pi = client.purchase(
            amount=args.amount,
            currency=args.currency,
            description=args.description,
            payment_method=args.payment_method,
        )
    except Exception as exc:
        print(f"Purchase FAILED: {exc}")
        return 1

    status = pi.get("status", "unknown")
    pi_id = pi.get("id", "?")
    receipt = pi.get("charges", {}).get("data", [{}])[0].get("receipt_url", "")

    if status == "succeeded":
        print(f"Payment SUCCEEDED")
        print(f"  PaymentIntent: {pi_id}")
        print(f"  Amount charged: ${pi.get('amount_received', 0) / 100:.2f}")
        if receipt:
            print(f"  Receipt:        {receipt}")
        print()
        print(
            "Buyer agent: Purchase complete. This was a test transaction -- no real money moved."
        )
        return 0
    else:
        print(f"Payment status: {status}")
        print(f"  PaymentIntent: {pi_id}")
        if pi.get("last_payment_error"):
            err = pi["last_payment_error"]
            print(f"  Error: {err.get('message', err.get('decline_code', 'unknown'))}")
        return 1


# ════════════════════════════════════════════════════════════════
#  browse — list Stripe test products
# ════════════════════════════════════════════════════════════════


def cmd_browse(args: argparse.Namespace) -> int:
    key = _resolve_stripe_key(args.stripe_key, save=args.save_key)
    client = StripeTestClient(key)

    print("Buyer agent: Browsing available test products from Stripe.")
    print()

    try:
        prices = client.list_prices(limit=args.limit)
    except Exception as exc:
        print(f"Browse FAILED: {exc}")
        return 1

    if not prices:
        print("No test products found. Create some in the Stripe Dashboard > Products.")
        print("Or use 'purchase' with --amount directly (no product required).")
        return 0

    for p in prices:
        product = p.get("product") or {}
        name = (
            product.get("name", "Unnamed")
            if isinstance(product, dict)
            else str(product)
        )
        unit = p.get("unit_amount", 0) or 0
        currency = (p.get("currency") or "usd").upper()
        print(f"  {p['id']}")
        print(f"    Product:  {name}")
        print(f"    Price:    ${unit / 100:.2f} {currency}")
        if p.get("metadata"):
            print(f"    Metadata: {json.dumps(p['metadata'])}")
        print()

    return 0


# ════════════════════════════════════════════════════════════════
#  checkout — create a hosted Stripe Checkout Session
# ════════════════════════════════════════════════════════════════


def cmd_checkout(args: argparse.Namespace) -> int:
    key = _resolve_stripe_key(args.stripe_key, save=args.save_key)
    client = StripeTestClient(key)

    print("Buyer agent: Creating a Stripe Checkout Session.")
    print(f"  Amount:  ${args.amount / 100:.2f} {args.currency.upper()}")
    print(f"  Product: {args.product_name}")
    print()

    try:
        session = client.create_checkout_session(
            amount=args.amount,
            currency=args.currency,
            product_name=args.product_name,
        )
    except Exception as exc:
        print(f"Checkout creation FAILED: {exc}")
        return 1

    url = session.get("url", "")
    session_id = session.get("id", "?")

    print(f"Checkout Session created: {session_id}")
    print(f"Payment URL: {url}")
    print()
    print("In test mode, use card 4242 4242 4242 4242 with any future date and CVC.")
    print("The session will not auto-complete; poll Stripe or check the Dashboard.")
    return 0


# ════════════════════════════════════════════════════════════════
#  main — CLI entry point
# ════════════════════════════════════════════════════════════════


def _add_stripe_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--stripe-key",
        default=None,
        help="Stripe test secret key (or set STRIPE_TEST_KEY env var, "
        "or place in buyer-agent/.env, or omit for interactive prompt). "
        "Get one at https://dashboard.stripe.com/test/apikeys",
    )
    parser.add_argument(
        "--save-key",
        action="store_true",
        help="Save an interactively-prompted key to buyer-agent/.env so "
        "subsequent commands skip the prompt on this machine.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Buyer agent: vet agents via Gauntlet, then purchase with Stripe test cards."
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # --- hire ---
    hire_parser = sub.add_parser(
        "hire", help="Vet candidate worker agents via Gauntlet"
    )
    hire_parser.add_argument(
        "--gauntlet", default="http://127.0.0.1:8000", help="Gauntlet service base URL"
    )
    hire_parser.add_argument(
        "--min-score",
        type=float,
        default=0.8,
        help="Minimum reliability score required to hire",
    )
    hire_parser.add_argument(
        "--allow-failed",
        action="store_true",
        help="Allow hiring agents with failed probes",
    )
    hire_parser.add_argument(
        "--block-failed-category",
        action="append",
        default=["safety", "hallucination"],
        help="Reject candidates with failed probes in this category. Repeatable.",
    )
    hire_parser.add_argument(
        "agent_ids", nargs="+", help="Candidate agent ids to compare"
    )

    # --- purchase ---
    purchase_parser = sub.add_parser(
        "purchase", help="Buy something with a Stripe test card"
    )
    _add_stripe_args(purchase_parser)
    purchase_parser.add_argument(
        "--amount",
        type=int,
        default=500,
        help="Amount in cents (default: 500 = $5.00)",
    )
    purchase_parser.add_argument(
        "--currency", default="usd", help="Currency code (default: usd)"
    )
    purchase_parser.add_argument(
        "--description",
        default="Gauntlet buyer-agent test purchase",
        help="Purchase description for the receipt",
    )
    purchase_parser.add_argument(
        "--card",
        default="visa",
        choices=list(TEST_PAYMENT_METHODS.keys()),
        help="Test card to use (default: visa). 'declined' and 'insufficient_funds' test failure paths.",
    )
    purchase_parser.add_argument(
        "--payment-method",
        default=None,
        help="Explicit Stripe test PaymentMethod ID (overrides --card). "
        "Use pm_card_visa, pm_card_visa_chargeDeclined, etc.",
    )

    # --- browse ---
    browse_parser = sub.add_parser(
        "browse", help="List Stripe test products available for purchase"
    )
    _add_stripe_args(browse_parser)
    browse_parser.add_argument(
        "--limit", type=int, default=10, help="Max products to list"
    )

    # --- checkout ---
    checkout_parser = sub.add_parser(
        "checkout", help="Create a Stripe Checkout Session (hosted payment page)"
    )
    _add_stripe_args(checkout_parser)
    checkout_parser.add_argument(
        "--amount",
        type=int,
        default=500,
        help="Amount in cents (default: 500 = $5.00)",
    )
    checkout_parser.add_argument(
        "--currency", default="usd", help="Currency code (default: usd)"
    )
    checkout_parser.add_argument(
        "--product-name",
        default="Gauntlet Test Purchase",
        help="Product name shown on the checkout page",
    )

    args = parser.parse_args()

    if args.command == "hire":
        return cmd_hire(args)
    elif args.command == "purchase":
        # Resolve --card alias to actual PaymentMethod ID
        if not args.payment_method:
            args.payment_method = TEST_PAYMENT_METHODS[args.card]
        return cmd_purchase(args)
    elif args.command == "browse":
        return cmd_browse(args)
    elif args.command == "checkout":
        return cmd_checkout(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
