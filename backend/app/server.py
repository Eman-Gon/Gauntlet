"""FastAPI surface.

POST /audit                       — start a run, returns its run_id (D00)
GET  /audit/{run_id}/stream       — per-run SSE telemetry (D00)
GET  /audit/{run_id}/results      — per-run partial/final MarketResult (D00)
GET  /healthz                     — liveness

D03 additions (gauntlet autonomy layer):
GET  /test-vendor/nimbus          — fictional editable vendor page (HTML)
POST /test-vendor/nimbus          — replace claims on the test page (JSON)
GET  /gauntlet/status             — live watcher state (watching/triggers/etc.)
GET  /activity/stream             — SSE of the global activity bus
                                    (every gauntlet_trigger + per-trigger
                                    pipeline event, ready for D07's feed)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Optional

import orjson
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from app import gauntlet_watch, test_vendor
from app.schemas import TelemetryEvent, VetAccepted, VetRequest
from app.telemetry import TelemetryBus


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Start the gauntlet loop on boot, cancel on shutdown. Lazy state init
    means the watcher's MarketResult and activity bus exist before the first
    request hits the dashboard."""
    await gauntlet_watch.start()
    try:
        yield
    finally:
        await gauntlet_watch.stop()


app = FastAPI(
    title="Gauntlet — Autonomous burden of proof for the agentic web",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# run_id -> bus. In-memory is fine for the demo (single process, no restart).
_RUNS: dict[str, TelemetryBus] = {}
# run_id -> task running the orchestrator. Held so we don't GC the coroutine.
_TASKS: dict[str, asyncio.Task] = {}


class AuditRequest(BaseModel):
    category: str
    vendor_urls: list[tuple[str, str]] = Field(
        ...,
        description="List of (vendor_name, url) tuples to audit.",
    )
    naive: bool = False
    n: Optional[int] = None


class AuditAccepted(BaseModel):
    run_id: str
    stream_url: str
    results_url: str


@app.post("/audit", response_model=AuditAccepted)
async def audit(req: AuditRequest) -> AuditAccepted:
    bus = TelemetryBus()
    _RUNS[bus.run_id] = bus

    from app.pipeline.orchestrator import run_market

    task = asyncio.create_task(
        run_market(
            req.category,
            req.vendor_urls,
            bus=bus,
            naive=req.naive,
            n=req.n,
        )
    )
    _TASKS[bus.run_id] = task

    return AuditAccepted(
        run_id=bus.run_id,
        stream_url=f"/audit/{bus.run_id}/stream",
        results_url=f"/audit/{bus.run_id}/results",
    )


@app.post("/vet", response_model=VetAccepted)
async def vet(req: VetRequest) -> VetAccepted:
    """Run a Gauntlet probe battery against a black-box target agent."""
    bus = TelemetryBus(parent_bus=gauntlet_watch.state().activity_bus)
    _RUNS[bus.run_id] = bus

    from app.gauntlet import vet_agent

    task = asyncio.create_task(
        vet_agent(
            req.target_agent,
            bus=bus,
            use_cache=req.use_cache,
            force_deeper=req.force_deeper,
        )
    )
    _TASKS[bus.run_id] = task

    return VetAccepted(
        run_id=bus.run_id,
        stream_url=f"/vet/{bus.run_id}/stream",
        results_url=f"/vet/{bus.run_id}/results",
        reliability_url=f"/agent/{req.target_agent.agent_id}/reliability",
    )


@app.get("/vet/{run_id}/stream")
async def vet_stream(run_id: str) -> EventSourceResponse:
    bus = _RUNS.get(run_id)
    if bus is None:
        raise HTTPException(status_code=404, detail="run not found")

    queue = bus.subscribe(replay=True)

    async def gen():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue
                yield {
                    "event": "telemetry",
                    "data": orjson.dumps(event.model_dump(mode="json")).decode("utf-8"),
                }
                if event.stage == "gauntlet_done":
                    break
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(gen())


@app.get("/vet/{run_id}/results")
async def vet_results(run_id: str) -> Any:
    bus = _RUNS.get(run_id)
    if bus is None:
        raise HTTPException(status_code=404, detail="run not found")

    task = _TASKS.get(run_id)
    if task and task.done():
        if task.exception():
            raise HTTPException(status_code=500, detail=str(task.exception()))
        final = task.result()
        return orjson.loads(orjson.dumps(final.model_dump(mode="json")))

    if bus.partial_result is not None:
        return orjson.loads(orjson.dumps(bus.partial_result.model_dump(mode="json")))  # type: ignore[attr-defined]

    return {"status": "running", "run_id": run_id}


@app.get("/agent/{agent_id}/reliability")
async def agent_reliability(agent_id: str) -> Any:
    """Marketplace primitive: current reliability report for an agent id."""
    from app.reputation import latest_report

    report = latest_report(agent_id)
    if report is None:
        raise HTTPException(status_code=404, detail="agent has not been vetted yet")
    return orjson.loads(orjson.dumps(report.model_dump(mode="json")))


@app.get("/agents")
async def agent_directory(q: str | None = None) -> list[dict]:
    """Marketplace directory: all vetted agents, sorted by reliability.

    This is the programmatic AgentBox — every agent Gauntlet vets
    automatically appears here. Other agents call this to discover
    candidates before calling /agent/{id}/reliability to verify.
    """
    from app.reputation import _load

    store = _load()
    agents: list[dict] = []
    for agent_id, data in store.items():
        latest = data.get("latest")
        if not latest:
            continue
        entry = {
            "agent_id": agent_id,
            "name": latest.get("name", agent_id),
            "reliability_score": latest.get("reliability_score", 0),
            "failed": latest.get("failed", 0),
            "endpoint": latest.get("endpoint", ""),
            "last_vetted_at": latest.get("last_vetted_at"),
        }
        if (
            q
            and q.lower() not in entry["name"].lower()
            and q.lower() not in agent_id.lower()
        ):
            continue
        agents.append(entry)
    agents.sort(key=lambda a: a["reliability_score"], reverse=True)
    return agents


@app.get("/agent/{agent_id}/history")
async def agent_history(agent_id: str) -> Any:
    """Reputation memory: prior reports plus score/category deltas."""
    from app.reputation import reliability_diff, report_history

    runs = report_history(agent_id)
    if not runs:
        raise HTTPException(status_code=404, detail="agent has not been vetted yet")
    return {
        "agent_id": agent_id,
        "diff": reliability_diff(agent_id),
        "runs": [orjson.loads(orjson.dumps(r.model_dump(mode="json"))) for r in runs],
    }


@app.get("/agent/{agent_id}/repair")
async def agent_repair(agent_id: str) -> Any:
    """Self-repair brief grounded in failed and inconsistent probes."""
    from app.reputation import repair_brief

    brief = repair_brief(agent_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="agent has not been vetted yet")
    return brief


@app.get("/agent/{agent_id}/badge.svg")
async def agent_badge(agent_id: str) -> Response:
    """Tiny embeddable marketplace badge for AgentBox listings."""
    from html import escape

    from app.reputation import latest_report

    report = latest_report(agent_id)
    if report is None:
        label = "Gauntlet"
        value = "not vetted"
        color = "#737373"
    else:
        pct = round(report.reliability_score * 100)
        label = "Gauntlet"
        value = f"{pct}% reliable"
        color = (
            "#22c55e"
            if pct >= 80 and report.failed == 0
            else "#f59e0b"
            if pct >= 60
            else "#ef4444"
        )

    label_w = 68
    value_w = max(92, 8 * len(value) + 18)
    width = label_w + value_w
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="28" role="img" aria-label="{escape(label)}: {escape(value)}">
  <linearGradient id="g" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".08"/>
    <stop offset="1" stop-color="#000" stop-opacity=".08"/>
  </linearGradient>
  <rect width="{width}" height="28" rx="6" fill="#111827"/>
  <rect x="{label_w}" width="{value_w}" height="28" rx="6" fill="{color}"/>
  <rect width="{width}" height="28" rx="6" fill="url(#g)"/>
  <text x="34" y="18" text-anchor="middle" fill="#f9fafb" font-family="Inter,Arial,sans-serif" font-size="11" font-weight="700">{escape(label)}</text>
  <text x="{label_w + value_w / 2:.1f}" y="18" text-anchor="middle" fill="#111827" font-family="Inter,Arial,sans-serif" font-size="11" font-weight="700">{escape(value)}</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/audit/{run_id}/stream")
async def stream(run_id: str) -> EventSourceResponse:
    bus = _RUNS.get(run_id)
    if bus is None:
        raise HTTPException(status_code=404, detail="run not found")

    queue = bus.subscribe()

    async def gen():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue
                yield {
                    "event": "telemetry",
                    "data": orjson.dumps(event.model_dump(mode="json")).decode("utf-8"),
                }
                if event.stage == "market_done":
                    break
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(gen())


@app.get("/audit/{run_id}/results")
async def results(run_id: str) -> Any:
    """Returns partial or final MarketResult as the audit progresses."""
    bus = _RUNS.get(run_id)
    if bus is None:
        raise HTTPException(status_code=404, detail="run not found")

    task = _TASKS.get(run_id)
    partial = bus.partial_result

    if task and task.done() and not task.exception():
        final = task.result()
        # Keep gauntlet state in sync so /interrogate sees live data
        if final and final.vendors:
            gauntlet_watch.state().market = final
        return orjson.loads(orjson.dumps(final.model_dump(mode="json")))

    if partial is not None:
        return orjson.loads(orjson.dumps(partial.model_dump(mode="json")))  # type: ignore[attr-defined]

    return {
        "category": "",
        "vendors": [],
        "claim_inflation_index": 0.0,
        "telemetry_summary": {},
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/debug/config")
async def debug_config() -> dict:
    from app.clients import _use_gmi
    from app.config import settings as cfg

    return {
        "use_gmi": _use_gmi(),
        "cheap_model": cfg.CHEAP_MODEL,
        "premium_model": cfg.PREMIUM_MODEL,
        "anthropic_key_set": bool(cfg.ANTHROPIC_API_KEY),
        "gmi_key_set": bool(cfg.GMI_API_KEY),
        "tavily_key_set": bool(cfg.TAVILY_API_KEY),
    }


# ─────────────────────────────────────────────────────────────────────────────
# D03 — Gauntlet autonomy layer
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/test-vendor/nimbus", response_class=HTMLResponse)
async def test_vendor_nimbus_get() -> HTMLResponse:
    """Fictional vendor marketing page. Trafilatura extracts the claim list
    as plain text; the gauntlet loop hashes that to detect changes."""
    return HTMLResponse(content=test_vendor.render_html())


class NimbusUpdate(BaseModel):
    headline: Optional[str] = None
    tagline: Optional[str] = None
    claims: Optional[list[str]] = None


@app.post("/test-vendor/nimbus")
async def test_vendor_nimbus_post(payload: NimbusUpdate) -> JSONResponse:
    """Replace any subset of headline/tagline/claims. On stage this is the
    one-line curl that triggers the autonomous re-audit within one interval."""
    s = await test_vendor.update(
        headline=payload.headline,
        tagline=payload.tagline,
        claims=payload.claims,
    )
    return JSONResponse(
        {
            "headline": s.headline,
            "tagline": s.tagline,
            "claims": s.claims,
            "last_modified_ts": s.last_modified_ts,
        }
    )


@app.get("/gauntlet/status")
async def gauntlet_status() -> dict:
    return gauntlet_watch.status_snapshot()


# ─────────────────────────────────────────────────────────────────────────────
# D05 — x402 verdict endpoint
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/api/market/{category}/verdicts")
async def market_verdicts(
    category: str,
    intent: Optional[str] = None,
    request: Request = None,
) -> Any:
    """Paywalled verdict endpoint. Returns HTTP 402 + quote until payment is
    proved via X-Payment header. Passes through in demo mode (no wallet set)."""
    from app.config import settings as cfg
    from app.x402 import (
        build_quote,
        demo_hash_for,
        parse_payment_header,
        verify_payment,
    )

    payment_header = request.headers.get("X-Payment") if request else None
    txn_hash = parse_payment_header(payment_header)

    # If wallet is configured, enforce payment
    if cfg.X402_PAY_TO:
        if not txn_hash:
            quote = build_quote(category)
            return JSONResponse(status_code=402, content=quote)
        ok, reason = await verify_payment(txn_hash, category)
        if not ok:
            return JSONResponse(
                status_code=402,
                content={"error": reason, **build_quote(category)},
            )
    else:
        # Demo mode — accept a deterministic hash or no header at all
        if txn_hash:
            from app.x402 import _mark_used

            _mark_used(txn_hash)

    # Fetch live market result from gauntlet state
    market = gauntlet_watch.state().market
    data = market.model_dump(mode="json")

    # Intent filtering: re-rank vendors by specified categories
    if intent:
        intent_cats = [i.strip() for i in intent.split(",") if i.strip()]
        for vendor in data.get("vendors", []):
            judgments = vendor.get("judgments", [])
            claims = vendor.get("claims", [])
            claim_map = {c["claim_id"]: c for c in claims}
            filtered = [
                j
                for j in judgments
                if claim_map.get(j["claim_id"], {}).get("claim_type", "") in intent_cats
            ]
            if filtered:
                supported = sum(1 for j in filtered if j["verdict"] == "SUPPORTED")
                vendor["intent_score"] = supported / len(filtered)
            else:
                vendor["intent_score"] = None

    # Emit paid_fetch event so the dashboard "Agents paid" counter ticks
    gauntlet_watch.state().activity_bus.emit(
        TelemetryEvent(
            stage="paid_fetch",
            vendor=None,
            payload={
                "category": category,
                "txn_hash": txn_hash or demo_hash_for(category),
            },
        )
    )

    data["paid"] = True
    data["txn_hash"] = txn_hash or demo_hash_for(category)
    data["audit_age_hrs"] = 0  # live data, always fresh from watch loop
    return JSONResponse(content=data)


@app.get("/api/market/{category}/status/{job_id}")
async def market_status(category: str, job_id: str) -> Any:
    """Stub for buyer agent polling. Returns 'complete' for the live loop."""
    return {"status": "complete", "category": category}


@app.get("/activity/stream")
async def activity_stream(request: Request) -> EventSourceResponse:
    """Global activity feed — gauntlet_trigger, every per-trigger pipeline
    stage event (ingest/extract/hunt/judge_*/advise/vendor_done), and
    gauntlet_reaudit_done. D07's UI subscribes here."""
    bus = gauntlet_watch.state().activity_bus
    queue = bus.subscribe(replay=True)

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
                    continue
                yield {
                    "event": "activity",
                    "data": orjson.dumps(event.model_dump(mode="json")).decode("utf-8"),
                }
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(gen())


# ════════════════════════════════════════════════════════════════
#  Buyer panel — shop search + Stripe purchase
# ════════════════════════════════════════════════════════════════

from app.schemas import ShopSearchRequest, ShopSearchResponse


@app.post("/shop/search", response_model=ShopSearchResponse)
async def shop_search(req: ShopSearchRequest) -> ShopSearchResponse:
    """Search for products via the controllable shopping agent."""
    from app.shopping_agent import search as shop_search_fn

    return await shop_search_fn(req.query)


class ShopModeRequest(BaseModel):
    mode: str  # "proven" | "flaky" | "failing"


@app.post("/shop/mode")
async def shop_mode(req: ShopModeRequest) -> dict[str, str]:
    """Switch the shopping agent mode for demo control."""
    from app.shopping_agent import Mode, set_mode

    try:
        set_mode(Mode(req.mode))
        return {"mode": req.mode}
    except ValueError:
        raise HTTPException(status_code=422, detail=f"unknown mode: {req.mode}")


@app.post("/buyer/search", response_model=ShopSearchResponse)
async def buyer_search(req: ShopSearchRequest) -> ShopSearchResponse:
    """Orchestrated search: vet shopping agents, delegate to the best one."""
    from app.buyer import search_and_vet

    return await search_and_vet(req.query)


class PurchaseRequest(BaseModel):
    amount_cents: int = Field(..., gt=0, description="Amount in cents (500 = $5.00)")
    currency: str = "usd"
    description: str = "Gauntlet buyer panel purchase"


@app.post("/buyer/purchase")
async def buyer_purchase(req: PurchaseRequest) -> dict:
    """Create a Stripe test-mode PaymentIntent and confirm it.

    Uses the STRIPE_TEST_KEY env var. Test cards always succeed in test mode.
    Returns the PaymentIntent status, id, and receipt.
    """
    import os
    import sys
    from pathlib import Path

    # Add buyer-agent to path so we can import stripe_client
    buyer_agent_dir = Path(__file__).resolve().parent.parent.parent / "buyer-agent"
    sys.path.insert(0, str(buyer_agent_dir))

    try:
        from stripe_client import StripeError, StripeTestClient
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="stripe_client not found — ensure buyer-agent/stripe_client.py exists",
        )

    try:
        client = StripeTestClient()
        pi = client.purchase(
            amount=req.amount_cents,
            currency=req.currency,
            description=req.description,
        )
    except StripeError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    receipt = ""
    charges = pi.get("charges", {}).get("data", [])
    if charges:
        receipt = charges[0].get("receipt_url", "")

    return {
        "status": pi.get("status", "unknown"),
        "id": pi.get("id", ""),
        "amount_received": pi.get("amount_received", 0),
        "currency": req.currency,
        "receipt_url": receipt,
        "test_mode": True,
    }


# ════════════════════════════════════════════════════════════════
#  Exa search endpoint
# ════════════════════════════════════════════════════════════════


class ExaSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    num_results: int = Field(default=5, ge=1, le=10)


@app.post("/exa/search")
async def exa_search(req: ExaSearchRequest) -> dict:
    """Search Exa for products or claim evidence.
    Falls back to mock data when EXA_API_KEY is absent."""
    from app.exa_client import search as exa_search_fn

    return await exa_search_fn(req.query, req.num_results)


class ExtractRequest(BaseModel):
    query: str = Field(..., min_length=1)
    search_texts: list[dict] = Field(default_factory=list)


@app.post("/shop/extract")
async def shop_extract(req: ExtractRequest) -> dict:
    """Extract structured products from search result text."""
    from app.product_extraction import extract_products

    products = await extract_products(req.query, req.search_texts)
    return {"products": [p.model_dump(mode="json") for p in products]}


class AuditClaimsRequest(BaseModel):
    products: list[dict] = Field(default_factory=list)


@app.post("/shop/audit-claims")
async def shop_audit_claims(req: AuditClaimsRequest) -> dict:
    """Resolve PENDING claim verdicts via hunt + judge pipeline."""
    from app.claim_audit import audit_claims

    products = await audit_claims(req.products)
    return {"products": products}
