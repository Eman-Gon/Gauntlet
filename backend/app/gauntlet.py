"""Gauntlet orchestrator: probe a target agent and persist reliability memory."""

from __future__ import annotations

from app.probes import battery_for, run_probe
from app.reputation import build_reliability_report, persist_report, prior_failure_count
from app.schemas import ReliabilityReport, TargetAgent, TelemetryEvent
from app.telemetry import TelemetryBus


async def vet_agent(
    target: TargetAgent,
    *,
    bus: TelemetryBus,
    use_cache: bool = True,
    force_deeper: bool = False,
) -> ReliabilityReport:
    prior_failures = prior_failure_count(target.agent_id)
    harder_gauntlet = force_deeper or prior_failures > 0
    probes = battery_for(prior_failures=prior_failures, force_deeper=force_deeper)

    bus.emit(TelemetryEvent(
        stage="gauntlet_started",
        vendor=target.name,
        payload={
            "agent_id": target.agent_id,
            "probe_count": len(probes),
            "prior_failures": prior_failures,
            "harder_gauntlet": harder_gauntlet,
        },
    ))

    results = []
    for probe in probes:
        results.append(
            await run_probe(target, probe, bus=bus, use_cache=use_cache)
        )

    report = build_reliability_report(
        target,
        results,
        prior_failures=prior_failures,
        harder_gauntlet=harder_gauntlet,
    )
    persist_report(report)
    bus.partial_result = report
    bus.emit(TelemetryEvent(
        stage="gauntlet_done",
        vendor=target.name,
        payload={
            "agent_id": target.agent_id,
            "score": report.reliability_score,
            "passed": report.passed,
            "inconsistent": report.inconsistent,
            "failed": report.failed,
            "harder_gauntlet": report.harder_gauntlet,
        },
    ))
    return report
