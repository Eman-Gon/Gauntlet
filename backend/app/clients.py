"""Two-tier LLM client.

Boundary: messages-in, text+token-counts-out. We deliberately do NOT unify SDK-native
tool_use here — OpenAI and Anthropic tool schemas diverge enough that abstracting
them at this seam leaks complexity into every caller. Structured output for the
judge is done in the STAGE by prompting for JSON and pydantic-validating the parse.
A parse failure or low confidence on cheap-tier just escalates to premium — the
cascade is the safety net.

Routing (decided at chat() call time):
  GMI_API_KEY + GMI_BASE_URL set
    → cheap tier uses GMI with CHEAP_MODEL
    → premium tier uses GMI with PREMIUM_MODEL
  GMI not configured
    → cheap tier uses CHEAP_BASE_URL + cheap_effective_api_key() + CHEAP_MODEL
      (defaults to Anthropic OpenAI-compat + haiku-4-5)
    → premium tier uses direct AsyncAnthropic native + PREMIUM_MODEL

The `generate_image` symbol is preserved (no-op) so honest_ad.py keeps its
import surface; Magnific is feature-flagged OFF for this hack."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal, Optional

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.config import cheap_effective_api_key, settings


log = logging.getLogger("gauntlet.clients")


Tier = Literal["cheap", "premium"]


def _effective_gmi_key() -> str:
    """Prefer GMI_MAAS_API_KEY (injected by AgentBox) over GMI_API_KEY."""
    return settings.GMI_MAAS_API_KEY or settings.GMI_API_KEY


def _effective_gmi_base_url() -> str:
    """Prefer GMI_MAAS_BASE_URL (injected by AgentBox) over GMI_BASE_URL."""
    return settings.GMI_MAAS_BASE_URL or settings.GMI_BASE_URL


def _use_gmi() -> bool:
    return bool(_effective_gmi_key() and _effective_gmi_base_url())


# COST TABLE — verified at platform.claude.com on 2026-06-10.
# Sonnet 4.6: $3 / MTok input, $15 / MTok output (base, no cache, no batch).
# Cheap tier is imputed (per-attempt floor in CHEAP_ATTEMPT_COST_USD) so the
# dashboard shows visible infra cost even when the cheap endpoint is on free credits.
_PREMIUM_RATES = {"input_per_mtok": 3.0, "output_per_mtok": 15.0}
_CHEAP_RATES = {
    "input_per_mtok": settings.CHEAP_INPUT_PER_MTOK,
    "output_per_mtok": settings.CHEAP_OUTPUT_PER_MTOK,
}

COST_TABLE: dict[str, dict[str, float]] = {
    settings.CHEAP_MODEL: _CHEAP_RATES,
    settings.PREMIUM_MODEL: _PREMIUM_RATES,
}


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    rates = COST_TABLE.get(model)
    # Fall back to basename if model has a provider prefix
    if rates is None and "/" in model:
        rates = COST_TABLE.get(model.rsplit("/", 1)[-1])
    if rates is None:
        return 0.0
    return (
        tokens_in / 1_000_000.0 * rates["input_per_mtok"]
        + tokens_out / 1_000_000.0 * rates["output_per_mtok"]
    )


def attempt_cost_usd(model: str) -> float:
    cheap_ids = {settings.CHEAP_MODEL}
    if model in cheap_ids:
        return settings.CHEAP_ATTEMPT_COST_USD
    if "/" in model and model.rsplit("/", 1)[-1] in cheap_ids:
        return settings.CHEAP_ATTEMPT_COST_USD
    return 0.0


@dataclass
class ChatResult:
    text: str
    tokens_in: int
    tokens_out: int
    model: str
    tier: Tier
    raw: Any = None
    inference_id: Optional[str] = None


_cheap_client_oai: Optional[AsyncOpenAI] = None
_gmi_client_oai: Optional[AsyncOpenAI] = None
_premium_client_native: Optional[AsyncAnthropic] = None


def _gmi_client() -> AsyncOpenAI:
    global _gmi_client_oai
    url = _effective_gmi_base_url()
    if _gmi_client_oai is None or str(_gmi_client_oai.base_url) != url:
        _gmi_client_oai = AsyncOpenAI(
            base_url=url,
            api_key=_effective_gmi_key(),
            max_retries=0,
        )
    return _gmi_client_oai


def cheap_client() -> AsyncOpenAI:
    """OpenAI-shaped cheap client. Priority: GMI → Anthropic OpenAI-compat stand-in."""
    if _use_gmi():
        return _gmi_client()
    global _cheap_client_oai
    if _cheap_client_oai is None or _cheap_client_oai.base_url != settings.CHEAP_BASE_URL:
        _cheap_client_oai = AsyncOpenAI(
            base_url=settings.CHEAP_BASE_URL,
            api_key=cheap_effective_api_key(),
            max_retries=0,
        )
    return _cheap_client_oai


def premium_client_native() -> AsyncAnthropic:
    """Direct-Anthropic native client. Used when GMI is not configured."""
    global _premium_client_native
    if _premium_client_native is None:
        _premium_client_native = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _premium_client_native


# Back-compat alias — earlier code paths import `premium_client`.
def premium_client() -> AsyncAnthropic:
    return premium_client_native()


def _needs_no_think(model: str) -> bool:
    """`/no_think` disables Qwen3's chain-of-thought scratchpad. Harmless on
    Claude/Haiku (they ignore it). Forward-compat: any future Qwen-class
    CHEAP_MODEL lights this up automatically."""
    return "qwen" in model.lower()


def _inject_no_think(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    injected = False
    for m in messages:
        if m["role"] == "system" and not injected:
            out.append({**m, "content": "/no_think\n" + m["content"]})
            injected = True
        else:
            out.append(m)
    if not injected:
        out.insert(0, {"role": "system", "content": "/no_think"})
    return out


async def _openai_chat(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict[str, str]],
    *,
    tier: Tier,
    max_tokens: int,
    temperature: float,
    timeout: float,
) -> ChatResult:
    """Shared OpenAI-SDK call path."""
    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        ),
        timeout=timeout + 0.5,
    )
    msg = resp.choices[0].message if resp.choices else None
    text = (msg.content or "") if msg else ""
    usage = resp.usage
    return ChatResult(
        text=text,
        tokens_in=usage.prompt_tokens if usage else 0,
        tokens_out=usage.completion_tokens if usage else 0,
        model=model,
        tier=tier,
        raw=resp,
    )


async def chat(
    tier: Tier,
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 512,
    temperature: float = 0.0,
    timeout_s: Optional[float] = None,
) -> ChatResult:
    """Unified messages-in / text+usage-out entrypoint. Both tiers go through here
    so the telemetry wrapper has ONE surface to instrument. Messages use the
    OpenAI shape: [{"role": "system"|"user"|"assistant", "content": "..."}]."""
    if tier == "cheap" and settings.CHEAP_FALLBACK_TO_PREMIUM:
        tier = "premium"

    if timeout_s is not None:
        timeout = timeout_s
    elif tier == "cheap":
        timeout = min(settings.LLM_TIMEOUT_S, settings.CHEAP_LLM_TIMEOUT_S)
    else:
        timeout = settings.LLM_TIMEOUT_S

    if tier == "cheap":
        model = settings.CHEAP_MODEL
        msgs = _inject_no_think(messages) if _needs_no_think(model) else messages
        return await _openai_chat(
            cheap_client(),
            model,
            msgs,
            tier="cheap",
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )

    # premium — GMI if configured, else direct Anthropic native
    if _use_gmi():
        return await _openai_chat(
            _gmi_client(),
            settings.PREMIUM_MODEL,
            messages,
            tier="premium",
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )

    # Direct-Anthropic native fallback. Split out system message; Anthropic
    # takes it separately.
    model = settings.PREMIUM_MODEL
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    convo = [m for m in messages if m["role"] != "system"]
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": convo,
    }
    if system_parts:
        kwargs["system"] = "\n\n".join(system_parts)
    resp = await premium_client_native().messages.create(**kwargs, timeout=timeout)
    text = "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )
    return ChatResult(
        text=text,
        tokens_in=resp.usage.input_tokens,
        tokens_out=resp.usage.output_tokens,
        model=model,
        tier="premium",
        raw=resp,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Magnific image generation — FEATURE-FLAGGED OFF for the Harness hack.
# Symbols kept so honest_ad.py imports succeed; the body is a no-op. The flag
# lives at settings.HONEST_AD_ENABLED — orchestrator.py gates the call there.
# ─────────────────────────────────────────────────────────────────────────────

MAGNIFIC_CREDIT_ESTIMATE: dict[str, int] = {"1k": 25, "2k": 50, "4k": 100}


async def generate_image(
    prompt: str,
    *,
    model: str = "realism",
    resolution: str = "1k",
    aspect_ratio: str = "widescreen_16_9",
    timeout_s: float = 60.0,
    poll_interval_s: float = 1.5,
) -> Optional[str]:
    """No-op while HONEST_AD_ENABLED=false. Returns None unconditionally so
    honest_ad.py's IMAGE_UNAVAILABLE grey-card branch is the only outcome if
    the stage is ever invoked with the flag off."""
    return None
