"""P2-4 tests — ReceiptsService.parse_inbound (feedback classifier).

Pure-mock tests: no DB, no LLM calls hit the network.

Covered:
  1.  Acknowledge patterns (ok, thanks, emoji) → intent=acknowledge, confidence=1.0
  2.  Structured correction — English covers patterns → structured_correction
  3.  Structured correction — pax / guests patterns
  4.  Structured correction — numeric value extracted correctly
  5.  Haiku classifier called when no regex matches
  6.  Haiku returns free_form intent → forwarded
  7.  Haiku returns structured_correction → forwarded
  8.  Haiku returns unknown intent → coerced to free_form
  9.  Haiku JSON parse failure → default free_form at confidence 0.5
  10. Haiku exception → fallback free_form at confidence 0.5
  11. requires_confirmation True when confidence < 0.6
  12. requires_confirmation False when confidence >= 0.6
  13. French acknowledge patterns (merci, compris)
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.receipts import ReceiptsService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HOTEL = "hotel_p2"


def _service(llm_response: str | None = None, llm_raises: bool = False) -> ReceiptsService:
    """Return a ReceiptsService with a mocked DB and LLM."""
    db = AsyncMock()
    mock_llm = AsyncMock()
    if llm_raises:
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("timeout"))
    elif llm_response is not None:
        mock_llm.complete = AsyncMock(return_value=llm_response)
    else:
        mock_llm.complete = AsyncMock(return_value='{"intent":"free_form","confidence":0.8,"outcome":"modified","actual_value":null,"notes":""}')
    return ReceiptsService(db, llm=mock_llm)


# ---------------------------------------------------------------------------
# 1–2. Acknowledge patterns
# ---------------------------------------------------------------------------

class TestAcknowledge:
    @pytest.mark.asyncio
    async def test_ok(self):
        result = await _service().parse_inbound("ok")
        assert result.intent == "acknowledge"
        assert result.confidence == 1.0
        assert not result.requires_confirmation

    @pytest.mark.asyncio
    async def test_thanks(self):
        result = await _service().parse_inbound("Thanks!")
        assert result.intent == "acknowledge"

    @pytest.mark.asyncio
    async def test_thumbs_emoji(self):
        result = await _service().parse_inbound("👍")
        assert result.intent == "acknowledge"

    @pytest.mark.asyncio
    async def test_checkmark_emoji(self):
        result = await _service().parse_inbound("✅")
        assert result.intent == "acknowledge"

    @pytest.mark.asyncio
    async def test_got_it(self):
        result = await _service().parse_inbound("Got it")
        assert result.intent == "acknowledge"

    @pytest.mark.asyncio
    async def test_french_merci(self):
        result = await _service().parse_inbound("merci")
        assert result.intent == "acknowledge"

    @pytest.mark.asyncio
    async def test_french_compris(self):
        result = await _service().parse_inbound("compris")
        assert result.intent == "acknowledge"

    @pytest.mark.asyncio
    async def test_acknowledge_does_not_call_llm(self):
        svc = _service()
        await svc.parse_inbound("ok")
        svc._llm.complete.assert_not_awaited()


# ---------------------------------------------------------------------------
# 3–4. Structured correction — regex
# ---------------------------------------------------------------------------

class TestStructuredCorrection:
    @pytest.mark.asyncio
    async def test_dinner_covers_pattern(self):
        result = await _service().parse_inbound("dinner covers 180, not 140")
        assert result.intent == "structured_correction"
        assert result.actual_value == 180.0
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_covers_colon_pattern(self):
        result = await _service().parse_inbound("covers: 80")
        assert result.intent == "structured_correction"
        assert result.actual_value == 80.0

    @pytest.mark.asyncio
    async def test_pax_pattern(self):
        result = await _service().parse_inbound("180 pax tonight")
        assert result.intent == "structured_correction"
        assert result.actual_value == 180.0

    @pytest.mark.asyncio
    async def test_guests_pattern(self):
        result = await _service().parse_inbound("60 guests at lunch")
        assert result.intent == "structured_correction"
        assert result.actual_value == 60.0

    @pytest.mark.asyncio
    async def test_lunch_covers(self):
        result = await _service().parse_inbound("lunch covers 45")
        assert result.intent == "structured_correction"
        assert result.actual_value == 45.0

    @pytest.mark.asyncio
    async def test_structured_correction_does_not_call_llm(self):
        svc = _service()
        await svc.parse_inbound("180 covers")
        svc._llm.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_structured_correction_notes_contains_original_text(self):
        text = "dinner covers 180, not 140"
        result = await _service().parse_inbound(text)
        assert text in result.notes


# ---------------------------------------------------------------------------
# 5–10. Haiku classifier fallback
# ---------------------------------------------------------------------------

class TestHaikuClassifier:
    @pytest.mark.asyncio
    async def test_free_form_forwarded(self):
        llm_json = '{"intent":"free_form","confidence":0.85,"outcome":"modified","actual_value":null,"notes":"private event tomorrow"}'
        result = await _service(llm_response=llm_json).parse_inbound("private event tomorrow")
        assert result.intent == "free_form"
        assert result.confidence == pytest.approx(0.85)
        assert result.notes == "private event tomorrow"

    @pytest.mark.asyncio
    async def test_structured_correction_from_llm(self):
        llm_json = '{"intent":"structured_correction","confidence":0.92,"outcome":"modified","actual_value":95.0,"notes":"95 covers"}'
        result = await _service(llm_response=llm_json).parse_inbound("we expect about 95 tomorrow")
        assert result.intent == "structured_correction"
        assert result.actual_value == pytest.approx(95.0)

    @pytest.mark.asyncio
    async def test_unknown_intent_coerced_to_free_form(self):
        llm_json = '{"intent":"unknown_garbage","confidence":0.7,"outcome":"modified","actual_value":null,"notes":"test"}'
        result = await _service(llm_response=llm_json).parse_inbound("some unusual message")
        assert result.intent == "free_form"

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_fallback(self):
        result = await _service(llm_response="not json at all").parse_inbound("some message")
        assert result.intent == "free_form"
        assert result.confidence == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_llm_exception_returns_fallback(self):
        result = await _service(llm_raises=True).parse_inbound("some message")
        assert result.intent == "free_form"
        assert result.confidence == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_markdown_fence_stripped_before_json_parse(self):
        llm_json = '```json\n{"intent":"free_form","confidence":0.75,"outcome":"modified","actual_value":null,"notes":"test"}\n```'
        result = await _service(llm_response=llm_json).parse_inbound("some message")
        assert result.intent == "free_form"
        assert result.confidence == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# 11–12. requires_confirmation threshold
# ---------------------------------------------------------------------------

class TestConfidenceThreshold:
    @pytest.mark.asyncio
    async def test_requires_confirmation_below_threshold(self):
        llm_json = '{"intent":"free_form","confidence":0.55,"outcome":"modified","actual_value":null,"notes":"test"}'
        result = await _service(llm_response=llm_json).parse_inbound("ambiguous message")
        assert result.requires_confirmation is True

    @pytest.mark.asyncio
    async def test_no_confirmation_at_threshold(self):
        llm_json = '{"intent":"free_form","confidence":0.6,"outcome":"modified","actual_value":null,"notes":"test"}'
        result = await _service(llm_response=llm_json).parse_inbound("clear message")
        assert result.requires_confirmation is False

    @pytest.mark.asyncio
    async def test_no_confirmation_above_threshold(self):
        llm_json = '{"intent":"free_form","confidence":0.9,"outcome":"modified","actual_value":null,"notes":"test"}'
        result = await _service(llm_response=llm_json).parse_inbound("clear message")
        assert result.requires_confirmation is False
