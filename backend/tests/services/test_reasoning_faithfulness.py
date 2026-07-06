"""Explanation faithfulness (HOS-299, pilot-readiness plan #15).

Faithfulness = the explanation cites factors that are *actually present in the
inputs*, and does not omit a present major driver. A plausible-but-fabricated
justification (an event that isn't there, a weather it invented) erodes manager
trust more than a plain number.

The deterministic heuristic path (`_heuristic_explanation` / `_extract_factors`)
is asserted in CI here. The LLM path is probed by a marker-gated integration test
(a real model must not invent a factor absent from the inputs).

Exhaustive rendering/format cases live in `tests/services/test_reasoning_service.py`.
"""
from __future__ import annotations

import os
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.reasoning_service import ReasoningService

_DATE = date(2026, 4, 7)


def _svc() -> ReasoningService:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="unused")
    return ReasoningService(llm=llm)


# markers of a cited factor in the heuristic summary.
_WEATHER_MARK = "current weather is"
_EVENT_MARK = "nearby events"
_PATTERN_PRESENT_MARK = "historical data shows"
_PATTERN_ABSENT_MARK = "no close historical pattern"

_FULL_CTX = {
    "weather": {"condition": "snowstorm"},
    "events": [{"title": "PSG vs Arsenal", "category": "Sports"}],
    "occupancy": 0.8,
}
_PATTERNS = [{"date": "2025-12-01", "actual_covers": 120, "score": 0.9}]


# ---------------------------------------------------------------------------
# _extract_factors is a faithful map of present inputs (no more, no less)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "weather,events,patterns,expect_weather,expect_events,expect_pattern",
    [
        (True, True, True, True, True, True),
        (True, False, False, True, False, False),
        (False, True, False, False, True, False),
        (False, False, True, False, False, True),
        (False, False, False, False, False, False),
    ],
)
def test_extract_factors_is_faithful(
    weather, events, patterns, expect_weather, expect_events, expect_pattern
):
    ctx = {}
    if weather:
        ctx["weather"] = {"condition": "rain"}
    if events:
        ctx["events"] = [{"title": "Concert", "category": "Music"}]
    pats = _PATTERNS if patterns else []

    factors = " || ".join(_svc()._extract_factors(ctx, pats)).lower()

    assert ("weather" in factors) is expect_weather
    assert ("events nearby" in factors) is expect_events
    assert ("historical pattern" in factors) is expect_pattern


# ---------------------------------------------------------------------------
# No hallucinated factor — an absent input is never cited
# ---------------------------------------------------------------------------
def test_heuristic_does_not_invent_events():
    summary = _svc()._heuristic_explanation(
        predicted=90, confidence=0.75, dt=_DATE, svc="lunch",
        context={"weather": {"condition": "sunny"}, "events": []},
        patterns=_PATTERNS,
    )["summary"].lower()
    assert _EVENT_MARK not in summary


def test_heuristic_does_not_invent_weather():
    summary = _svc()._heuristic_explanation(
        predicted=90, confidence=0.75, dt=_DATE, svc="lunch",
        context={"events": [{"title": "Concert"}]},
        patterns=_PATTERNS,
    )["summary"].lower()
    assert _WEATHER_MARK not in summary


def test_heuristic_does_not_invent_historical_pattern():
    summary = _svc()._heuristic_explanation(
        predicted=90, confidence=0.75, dt=_DATE, svc="lunch",
        context={"weather": {"condition": "sunny"}},
        patterns=[],
    )["summary"].lower()
    assert _PATTERN_PRESENT_MARK not in summary
    assert _PATTERN_ABSENT_MARK in summary  # states the absence honestly


# ---------------------------------------------------------------------------
# No missing causal factor — every present driver is cited
# ---------------------------------------------------------------------------
def test_heuristic_cites_every_present_factor():
    summary = _svc()._heuristic_explanation(
        predicted=180, confidence=0.9, dt=_DATE, svc="dinner",
        context=_FULL_CTX, patterns=_PATTERNS,
    )["summary"]
    low = summary.lower()
    assert "snowstorm" in low                 # the actual weather condition
    assert "PSG vs Arsenal" in summary        # the actual named event
    assert _PATTERN_PRESENT_MARK in low       # the actual historical pattern
    assert "120" in summary                   # the historical covers figure


# ---------------------------------------------------------------------------
# LLM path — a real model must not invent a factor absent from the inputs
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — live faithfulness probe skipped",
)
@pytest.mark.asyncio
async def test_llm_explanation_grounded_in_inputs():
    from app.providers.factory import get_llm_provider

    service = ReasoningService(llm=get_llm_provider())
    result = await service.generate_explanation(
        predicted_covers=120,
        confidence=0.85,
        target_date=_DATE,
        service_type="dinner",
        context={"weather": {"condition": "clear"}, "events": []},  # NO events
        similar_patterns=[],
    )
    answer = (result.get("summary") or "").lower()
    assert answer, "empty explanation"
    # With no events supplied, the model must not fabricate a specific event driver.
    for invented in ("concert", "festival", "match", "game", "conference"):
        assert invented not in answer, f"hallucinated event driver: {invented!r}"
