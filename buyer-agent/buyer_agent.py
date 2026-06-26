"""Buyer-agent demo: consult Gauntlet before hiring a worker agent."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def fetch_json(url: str) -> dict:
    try:
        with urlopen(url, timeout=10) as resp:  # noqa: S310 - local/demo URL
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"{url} failed: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Hire a worker agent using Gauntlet reliability reports.")
    parser.add_argument("--gauntlet", default="http://127.0.0.1:8000", help="Gauntlet service base URL")
    parser.add_argument("--min-score", type=float, default=0.8, help="Minimum reliability score required to hire")
    parser.add_argument("--allow-failed", action="store_true", help="Allow hiring agents with failed probes")
    parser.add_argument(
        "--block-failed-category",
        action="append",
        default=["safety", "hallucination"],
        help="Reject candidates with failed probes in this category. Repeatable.",
    )
    parser.add_argument("agent_ids", nargs="+", help="Candidate agent ids to compare")
    args = parser.parse_args()

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
        policy = "passes buyer policy" if not report["_policy_failures"] else "policy blocks: " + ", ".join(report["_policy_failures"])
        print(
            f"- {report['name']} ({report['agent_id']}): {score}% reliability, "
            f"{report['failed']} failed, {report['inconsistent']} inconsistent. "
            f"{policy}. {report['recommendation']}"
        )

    if chosen["_policy_failures"]:
        print("Decision: no hire. Every candidate violates the buyer policy.")
        return 2

    print(f"Decision: hire {chosen['name']} because it passes policy and has the strongest reliability report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
