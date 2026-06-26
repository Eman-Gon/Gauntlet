"""Lightweight event bus for buyer search progress streaming.

Each stage of the buyer pipeline (exa search, LLM extraction, claim audit)
emits an event. The SSE endpoint drains these events to the frontend so
users see live "thinking" progress instead of a static spinner.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BuyerEvent:
    stage: str  # "searching" | "extracting" | "auditing" | "done" | "error"
    message: str
    detail: Optional[dict] = None
    run_id: str = ""
    ts: float = field(default_factory=time.time)

    def sse_data(self) -> str:
        return json.dumps(
            {
                "stage": self.stage,
                "message": self.message,
                "detail": self.detail,
                "run_id": self.run_id,
                "ts": self.ts,
            }
        )


class BuyerEventBus:
    """In-process bus for buyer search progress."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[BuyerEvent]] = []

    def subscribe(self) -> asyncio.Queue[BuyerEvent]:
        q: asyncio.Queue[BuyerEvent] = asyncio.Queue(maxsize=64)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[BuyerEvent]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def emit(self, event: BuyerEvent) -> None:
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass


_bus: Optional[BuyerEventBus] = None


def get_bus() -> BuyerEventBus:
    global _bus
    if _bus is None:
        _bus = BuyerEventBus()
    return _bus


def emit(stage: str, message: str, *, detail: dict | None = None, run_id: str = "") -> None:
    get_bus().emit(BuyerEvent(stage=stage, message=message, detail=detail, run_id=run_id))
