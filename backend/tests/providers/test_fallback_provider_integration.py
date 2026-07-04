"""Real integration canary for the LLM fallback (HOS-282).

These tests make a **real** network call to Gemini to prove the fallback
parachute actually works — the mocked suite in ``test_fallback_provider.py``
only validates routing logic, never a live Gemini contract.

Excluded from the default / CI run (``addopts = -m 'not integration'``). Run
explicitly, with a live key, via::

    GEMINI_API_KEY=... uv run --project backend pytest \
        backend/tests/providers/test_fallback_provider_integration.py -m integration

Also runs on the nightly schedule. When the canary fails, see the runbook:
``docs/ops/llm-fallback-runbook.md``.
"""
from __future__ import annotations

import os

import pytest

from app.providers.fallback_provider import FallbackLLMProvider
from app.providers.gemini_provider import GeminiProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("GEMINI_API_KEY"),
        reason="GEMINI_API_KEY not set — live fallback canary skipped",
    ),
]

_MESSAGES = [{"role": "user", "content": "Reply with the single word: pong"}]


class _AlwaysDownProvider:
    """A primary that always fails with a transient (5xx-like) error, forcing
    the composite to exercise the real fallback path end-to-end (AC2)."""

    model_id = "test/always-down"

    async def complete(self, *args, **kwargs) -> str:  # noqa: D401
        raise TimeoutError("simulated primary outage")


@pytest.mark.asyncio
async def test_gemini_fallback_answers_for_real():
    """AC1: a real GeminiProvider.complete() returns a non-empty response."""
    gemini = GeminiProvider(
        api_key=os.getenv("GEMINI_API_KEY", ""),
        model=os.getenv("LLM_FALLBACK_MODEL", "gemini-2.0-flash"),
    )
    text = await gemini.complete(messages=_MESSAGES, max_tokens=16, temperature=0.0)
    assert text and text.strip(), "Gemini returned an empty response"


@pytest.mark.asyncio
async def test_failover_reaches_real_gemini_end_to_end():
    """AC2: a transient primary failure fails over to the *real* Gemini fallback."""
    provider = FallbackLLMProvider(
        primary=_AlwaysDownProvider(),
        fallback=GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("LLM_FALLBACK_MODEL", "gemini-2.0-flash"),
        ),
    )
    text = await provider.complete(messages=_MESSAGES, max_tokens=16, temperature=0.0)
    assert text and text.strip(), "end-to-end failover produced no text"


@pytest.mark.asyncio
async def test_health_check_passes_against_real_gemini():
    """The boot/scheduled canary returns True against a live fallback key."""
    provider = FallbackLLMProvider(
        primary=_AlwaysDownProvider(),
        fallback=GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("LLM_FALLBACK_MODEL", "gemini-2.0-flash"),
        ),
    )
    assert await provider.check_fallback_health() is True
