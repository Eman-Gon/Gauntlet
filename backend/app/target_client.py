"""Black-box adapter for the agent being vetted.

The target can expose a tiny demo endpoint (`{"prompt": "..."}`), an
OpenAI-compatible `/chat/completions` endpoint, or a plain text response. The
adapter normalizes all of those into AgentTranscript evidence.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.schemas import AgentTranscript, TargetAgent


def _extract_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return str(payload)

    for key in ("response", "answer", "output", "content", "text", "message"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            nested = _extract_text(value)
            if nested:
                return nested

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]

    return str(payload)


async def call_target_agent(target: TargetAgent, prompt: str, *, timeout_s: float = 20.0) -> AgentTranscript:
    started = time.perf_counter()
    status_code: int | None = None
    response_text = ""

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            resp = await client.post(
                target.endpoint,
                json={
                    "prompt": prompt,
                    "input": prompt,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            status_code = resp.status_code
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                response_text = _extract_text(resp.json())
            else:
                response_text = resp.text
            if resp.is_error:
                response_text = f"HTTP {resp.status_code}: {response_text[:500]}"
        except Exception as exc:  # noqa: BLE001 - transcript should capture failures
            response_text = f"CALL_FAILED: {exc}"

    latency_ms = (time.perf_counter() - started) * 1000.0
    return AgentTranscript(
        prompt=prompt,
        response=response_text.strip(),
        latency_ms=latency_ms,
        status_code=status_code,
    )
