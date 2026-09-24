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

import uuid as _uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base, OperationalMemory, StaffingRecommendation
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
    async def test_classifier_routed_to_fast_tier(self):
        """HOS-283 AC3 + Décision #35: Pass-3 classifier asks for the "fast" tier
        (Haiku on Claude) and never names a vendor model ID."""
        llm_json = '{"intent":"free_form","confidence":0.8,"outcome":"modified","actual_value":null,"notes":""}'
        svc = _service(llm_response=llm_json)
        await svc.parse_inbound("some free-form manager note")

        svc._llm.complete.assert_awaited_once()
        kwargs = svc._llm.complete.await_args.kwargs
        assert kwargs["tier"] == "fast"
        assert "model" not in kwargs

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


# ===========================================================================
# HOS-200 (Story 10.10 / P3-10) — persist_actual_covers
#
# Closes the prediction → recommendation → feedback → actual outcome loop.
# These use a real in-memory SQLite session (the parse_inbound tests above are
# pure-mock; do not fold these into them). Section is intentionally appended at
# the end of the file to avoid colliding with the parse_inbound regex/Haiku zone.
# (Imports for this section live in the top-of-file import block — E402.)
# ===========================================================================


@pytest_asyncio.fixture
async def db_session():
    """Fresh in-memory SQLite DB with the full ORM schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_recommendation(
    session: AsyncSession,
    *,
    tenant_id: str = "hotel_p2",
    predicted_covers: float | None = 140.0,
) -> StaffingRecommendation:
    now = datetime.now(tz=timezone.utc)
    rec = StaffingRecommendation(
        id=_uuid.uuid4(),
        tenant_id=tenant_id,
        property_id=_uuid.uuid4(),
        anomaly_id=_uuid.uuid4(),
        message_text="Add 2 servers for dinner.",
        triggering_factor="Tech conference",
        recommended_headcount=2,
        window_start=now,
        window_end=now,
        predicted_covers=predicted_covers,
        status="dispatched",
    )
    session.add(rec)
    await session.commit()
    return rec


class TestPersistActualCovers:
    @pytest.mark.asyncio
    async def test_structured_correction_persists_actual_covers(self, db_session):
        """AC5: parse_inbound("dinner covers 60") → actual_value == 60.0 →
        StaffingRecommendation.actual_covers == 60 + one ground_truth memory row."""
        rec = await _seed_recommendation(db_session, predicted_covers=140.0)
        svc = ReceiptsService(db_session, llm=AsyncMock())

        # The parser leg (unchanged, regex path) yields the numeric correction.
        feedback = await svc.parse_inbound("dinner covers 60")
        assert feedback.intent == "structured_correction"
        assert feedback.actual_value == 60.0

        await svc.persist_actual_covers(rec, feedback.actual_value, request_id="req-1")
        await db_session.commit()

        # AC1 — recommendation now carries the ground truth.
        refreshed = (
            await db_session.execute(
                select(StaffingRecommendation).where(
                    StaffingRecommendation.id == rec.id
                )
            )
        ).scalars().one()
        assert float(refreshed.actual_covers) == 60.0
        assert refreshed.actual_covers_source == "manager_feedback"
        assert refreshed.actual_covers_at is not None

        # AC2 — exactly one ground_truth memory row, linked + tagged.
        mem_rows = (
            await db_session.execute(
                select(OperationalMemory).where(
                    OperationalMemory.memory_type == "ground_truth"
                )
            )
        ).scalars().all()
        assert len(mem_rows) == 1
        mem = mem_rows[0]
        assert mem.hotel_id == "hotel_p2"
        assert mem.request_id == "req-1"
        assert mem.tags == ["ground_truth", "covers_correction"]
        assert "actual covers 60.0 vs predicted 140" in mem.reflection

    @pytest.mark.asyncio
    async def test_reflection_handles_missing_predicted_covers(self, db_session):
        """predicted_covers may be NULL on older rows — reflection still writes."""
        rec = await _seed_recommendation(db_session, predicted_covers=None)
        svc = ReceiptsService(db_session, llm=AsyncMock())

        mem = await svc.persist_actual_covers(rec, 80.0, request_id="req-2")
        await db_session.commit()

        assert "actual covers 80.0 vs predicted None" in mem.reflection
        assert float(rec.actual_covers) == 80.0
