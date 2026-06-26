"""Pydantic-settings Settings(). Reads `.env`. No network at import time.

Hard requirement at boot: ANTHROPIC_API_KEY or GMI_API_KEY + TAVILY_API_KEY.
Every other key defaults to empty so the app boots cleanly with only those set;
the service each key gates silently no-ops until its dispatch wires it up."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── inference ────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    PREMIUM_MODEL: str = "claude-sonnet-4-6"

    # Cheap tier — defaults to Anthropic OpenAI-compat endpoint with Haiku 4.5
    # (the stand-in we shipped at Receipts on 2026-06-10). CHEAP_API_KEY blank →
    # falls back to ANTHROPIC_API_KEY (so the stand-in boots from one key).
    CHEAP_BASE_URL: str = "https://api.anthropic.com/v1/"
    CHEAP_API_KEY: str = ""
    CHEAP_MODEL: str = "claude-haiku-4-5-20251001"
    CHEAP_INPUT_PER_MTOK: float = 0.05
    CHEAP_OUTPUT_PER_MTOK: float = 0.10
    CHEAP_ATTEMPT_COST_USD: float = 0.0002

    # Medium tier — escalation step between cheap and premium (Nemotron Ultra)
    MEDIUM_MODEL: str = ""
    MEDIUM_INPUT_PER_MTOK: float = 0.80
    MEDIUM_OUTPUT_PER_MTOK: float = 2.60

    # Strip blank-string .env placeholders from numeric fields before
    # pydantic validates them, so the class-level defaults apply.
    @model_validator(mode="before")
    @classmethod
    def _drop_empty_numerics(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        _float_fields = {
            "CHEAP_INPUT_PER_MTOK",
            "CHEAP_OUTPUT_PER_MTOK",
            "CHEAP_ATTEMPT_COST_USD",
            "X402_PRICE_USD",
            "MEDIUM_INPUT_PER_MTOK",
            "MEDIUM_OUTPUT_PER_MTOK",
            "JUDGE_CONFIDENCE_THRESHOLD",
            "SCRAPE_TIMEOUT_S",
            "LLM_TIMEOUT_S",
            "CHEAP_LLM_TIMEOUT_S",
        }
        return {k: v for k, v in data.items() if not (k in _float_fields and v == "")}

    # ── evidence ─────────────────────────────────────────────────────────────
    TAVILY_API_KEY: str = ""
    TAVILY_API_KEY_BACKUP: str = ""
    EXA_API_KEY: str = ""

    # ── x402 paywall (optional) ──────────────────────────────────────────────
    X402_PAY_TO: str = ""
    X402_PRICE_USD: float = 0.01

    # ── GMI Cloud / AgentBox ─────────────────────────────────────────────────
    # GMI is the primary cheap/medium inference provider and the deploy target.
    # Single key unlocks 200+ OpenAI-compatible models.
    GMI_API_KEY: str = ""
    GMI_BASE_URL: str = ""
    # Injected by AgentBox at container runtime — take priority over GMI_API_KEY
    # when present. Never hardcode these; GMI injects them into the environment.
    GMI_MAAS_API_KEY: str = ""
    GMI_MAAS_BASE_URL: str = ""
    GMI_MODELS: str = ""

    # ── gauntlet agent-vetting layer ─────────────────────────────────────────
    TARGET_AGENT_URL: str = ""
    MEMORY_BACKEND: str = "local"
    HYDRADB_URL: str = ""
    HYDRADB_API_KEY: str = ""

    # ── stripe (test-mode purchases) ─────────────────────────────────────────
    STRIPE_TEST_KEY: str = ""

    # ── gauntlet loop ────────────────────────────────────────────────────────
    # WATCH_ENABLED=false disables the autonomous watcher (useful for local
    # dev when you don't want the loop hitting external sites). The demo runs
    # with this on. WATCH_INTERVAL_S is the tick cadence.
    WATCH_ENABLED: bool = True
    WATCH_INTERVAL_S: int = 30
    # Where the live-editable test page lives. Gauntlet watches this URL as
    # the is_test vendor. The demo lever — edit a claim here on stage and
    # the loop fires within one interval.
    TEST_VENDOR_NAME: str = "Nimbus Support AI"
    TEST_VENDOR_URL: str = "http://127.0.0.1:8010/test-vendor/nimbus"

    # ── flags ────────────────────────────────────────────────────────────────
    # Magnific honest-ad stage. Magnific is not a sponsor at this hack — OFF.
    # honest_ad.py stays in-tree so toggling this flag back on works;
    # orchestrator.py gates the call on this flag.
    HONEST_AD_ENABLED: bool = False
    # Kept blank so honest_ad.py imports cleanly when re-enabled.
    # Not surfaced in .env.example because Magnific isn't a sponsor here.
    FREEPIK_API_KEY: str = ""
    HONEST_AD_IMAGE_COMMAND: str = ""
    HONEST_AD_TOP_N: int = 25

    # ── run knobs (cascade tuning — same as Receipts) ────────────────────────
    N_VENDORS: int = 10
    SEMAPHORE: int = 8
    JUDGE_CONFIDENCE_THRESHOLD: float = 0.7
    SCRAPE_TIMEOUT_S: float = 10.0
    LLM_TIMEOUT_S: float = 45.0
    CHEAP_LLM_TIMEOUT_S: float = 8.0
    # Belt-and-suspenders: route cheap-tier calls to premium when cheap is down.
    CHEAP_FALLBACK_TO_PREMIUM: bool = False


settings = Settings()


def cheap_effective_api_key() -> str:
    """Cheap-tier API key with the Anthropic stand-in fallback. When CHEAP_API_KEY
    is unset, the default cheap base URL is Anthropic OpenAI-compat — reuse the
    ANTHROPIC_API_KEY so a one-key .env still runs the cascade."""
    return settings.CHEAP_API_KEY or settings.ANTHROPIC_API_KEY


def require_boot_keys() -> None:
    """Hard-require an inference key (Anthropic OR GMI) plus Tavily."""
    missing = []
    if not settings.ANTHROPIC_API_KEY and not settings.GMI_API_KEY:
        missing.append("ANTHROPIC_API_KEY or GMI_API_KEY")
    if not settings.TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")
    if missing:
        raise RuntimeError(
            "Gauntlet boot requires " + " + ".join(missing) + " in .env."
        )
