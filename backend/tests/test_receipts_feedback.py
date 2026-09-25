"""P2-4 tests — ReceiptsService.parse_inbound (feedback classifier).

Pure-mock tests: no DB, no LLM calls hit the network.

Covered:
  1.  Acknowledge patterns (ok, thanks, emoji) → intent=acknowledge, confidence=1.0
  2.  Structured correction — English covers patterns → structured_correction
  3.  Structured correction — pax / guests patterns
  4.  Structured correction — numeric value extracted correctly
  5.  Haiku classifier called when no regex matches
  6.  Haiku returns free_form intent + stance → forwarded (ADR-0007 §19)
  7.  Haiku returns structured_correction → forwarded
  8.  Haiku answer outside the schema → llm_unmappable, no stance (never coerced)
  9.  Haiku non-JSON answer → llm_unmappable, no stance
  10. Haiku exception → llm_error, no stance
  11. requires_confirmation True when a model stance is below 0.85 (ADR-0007 §16)
  12. requires_confirmation False at / above the threshold
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
        mock_llm.complete = AsyncMock(return_value=_model_json("counter_value", 0.9))
    return ReceiptsService(db, llm=mock_llm)


def _model_json(stance: str, confidence: float, **extra) -> str:
    """A classifier answer in the ADR-0007 §19 schema (a stance, not a decision)."""
    import json

    return json.dumps({"stance": stance, "confidence": confidence, **extra})


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
    async def test_checkmark_emoji_is_not_a_bare_ack(self):
        # ✅ is an explicit acceptance keyword (matched before parse_inbound by
        # parse_action), not a bare acknowledgement (ADR-0007 §16.3).
        from app.schemas.webhook import ActionType
        from app.services.action_logger import parse_action

        assert parse_action("✅") == ActionType.accept
        result = await _service().parse_inbound("✅")
        assert result.source != "ack_regex"

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
        llm_json = _model_json("none", 0.85, intent="free_form", notes="private event tomorrow")
        result = await _service(llm_response=llm_json).parse_inbound("private event tomorrow")
        assert result.intent == "free_form"
        assert result.stance == "none"
        assert result.confidence == pytest.approx(0.85)
        assert result.notes == "private event tomorrow"

    @pytest.mark.asyncio
    async def test_classifier_routed_to_fast_tier(self):
        """HOS-283 AC3 + Décision #35: Pass-3 classifier asks for the "fast" tier
        (Haiku on Claude) and never names a vendor model ID."""
        svc = _service(llm_response=_model_json("counter_value", 0.8))
        await svc.parse_inbound("some free-form manager note")

        svc._llm.complete.assert_awaited_once()
        kwargs = svc._llm.complete.await_args.kwargs
        assert kwargs["tier"] == "fast"
        assert kwargs["temperature"] == 0.0
        assert "model" not in kwargs

    @pytest.mark.asyncio
    async def test_structured_correction_from_llm(self):
        llm_json = _model_json("counter_value", 0.92, intent="structured_correction",
                               corrected_value=95.0, notes="95 covers")
        result = await _service(llm_response=llm_json).parse_inbound("we expect about 95 tomorrow")
        assert result.intent == "structured_correction"
        assert result.stance == "counter_value"
        assert result.actual_value == pytest.approx(95.0)

    @pytest.mark.asyncio
    async def test_reason_and_route_forwarded(self):
        llm_json = _model_json("decline_proposal", 0.9, reason="wedding cancelled",
                               reason_route="upstream_filter", reason_route_confidence=0.8)
        result = await _service(llm_response=llm_json).parse_inbound("non, le mariage est annulé")
        assert result.stance == "decline_proposal"
        assert result.reason == "wedding cancelled"
        assert result.reason_route == "upstream_filter"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("answer", [
        '{"intent":"unknown_garbage","confidence":0.7}',          # no stance
        '{"decision":"accepted","confidence":0.9}',               # §16 schema: a decision, not a stance
        '{"stance":"maybe","confidence":0.7}',                    # stance out of taxonomy
        '{"stance":"adopt_proposal","confidence":1.7}',           # confidence out of range
        '{"stance":"adopt_proposal"}',                            # confidence missing
        '{"stance":"decline_proposal","confidence":0.9,"reason_route":"somewhere"}',
    ])
    async def test_schema_failure_is_typed_never_coerced(self, answer):
        result = await _service(llm_response=answer).parse_inbound("some unusual message")
        assert result.source == "llm_unmappable"
        assert result.stance is None
        assert result.requires_confirmation is False  # nothing to confirm: no stance

    @pytest.mark.asyncio
    async def test_json_parse_failure_has_no_decision(self):
        result = await _service(llm_response="not json at all").parse_inbound("some message")
        assert result.source == "llm_unmappable"
        assert result.stance is None

    @pytest.mark.asyncio
    async def test_llm_exception_has_no_decision(self):
        result = await _service(llm_raises=True).parse_inbound("some message")
        assert result.source == "llm_error"
        assert result.stance is None

    @pytest.mark.asyncio
    async def test_markdown_fence_stripped_before_json_parse(self):
        llm_json = "```json\n" + _model_json("counter_value", 0.75) + "\n```"
        result = await _service(llm_response=llm_json).parse_inbound("some message")
        assert result.source == "llm"
        assert result.confidence == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# 11–12. requires_confirmation threshold (DECISION_CONFIDENCE_THRESHOLD = 0.85)
# ---------------------------------------------------------------------------

class TestConfidenceThreshold:
    @pytest.mark.asyncio
    async def test_requires_confirmation_below_threshold(self):
        result = await _service(llm_response=_model_json("decline_proposal", 0.84)).parse_inbound("hmm")
        assert result.requires_confirmation is True

    @pytest.mark.asyncio
    async def test_no_confirmation_at_threshold(self):
        result = await _service(llm_response=_model_json("decline_proposal", 0.85)).parse_inbound("hmm")
        assert result.requires_confirmation is False

    @pytest.mark.asyncio
    async def test_stance_none_never_needs_confirmation(self):
        result = await _service(llm_response=_model_json("none", 0.2)).parse_inbound("hmm")
        assert result.requires_confirmation is False


# ---------------------------------------------------------------------------
# ADR-0007 §16 — resolution shared with the parser eval
# ---------------------------------------------------------------------------

def _ctx(pending: int = 1, hours_ago: float = 1.0, proposal: str = "add"):
    from datetime import timedelta

    from app.services.manager_decision import PendingContext

    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    return PendingContext(pending, now - timedelta(hours=hours_ago) if pending else None, now,
                          proposal=proposal)


class TestSourceAndRecordedOutcome:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text,kwargs,source",
        [
            ("ok", {}, "ack_regex"),
            ("covers: 80", {}, "covers_regex"),
            ("private event tomorrow", {}, "llm"),
            ("x", {"llm_response": '{"decision":"rejected","confidence":0.9}'}, "llm_unmappable"),
            ("x", {"llm_response": "not json"}, "llm_unmappable"),
            ("x", {"llm_raises": True}, "llm_error"),
        ],
    )
    async def test_source_tells_model_decision_from_fallback(self, text, kwargs, source):
        result = await _service(**kwargs).parse_inbound(text)
        assert result.source == source

    @pytest.mark.asyncio
    async def test_bare_ack_follows_rule_b(self):
        from app.services.receipts import outcome_for_feedback

        fb = await _service().parse_inbound("ok")
        assert outcome_for_feedback(fb, _ctx(1, 1.0)) == "accepted"
        assert outcome_for_feedback(fb, _ctx(0)) is None           # nothing pending
        assert outcome_for_feedback(fb, _ctx(2, 1.0)) is None      # → confirmation
        assert outcome_for_feedback(fb, _ctx(1, 13.0)) is None     # outside window → confirmation

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stance,decision", [
        ("adopt_proposal", "accepted"), ("decline_proposal", "rejected"),
        ("keep_current", "rejected"), ("counter_value", "modified"),
    ])
    async def test_model_stance_written_at_or_above_threshold(self, stance, decision):
        from app.services.receipts import outcome_for_feedback, resolve_feedback

        fb = await _service(llm_response=_model_json(stance, 0.9)).parse_inbound("free text")
        assert outcome_for_feedback(fb, _ctx()) == decision        # proposal: add staff
        assert resolve_feedback(fb, _ctx()).source.value == "model_auto"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("proposal,expected", [
        ("add", "rejected"), ("reduce", "rejected"), ("no_change", "accepted"), ("unknown", None),
    ])
    async def test_same_stance_different_proposal_different_decision(self, proposal, expected):
        """ADR-0007 §19: "keep the current plan" rejects a change, accepts "no
        change", and cannot be written when the direction is unknown."""
        from app.services.receipts import outcome_for_feedback, resolve_feedback

        fb = await _service(llm_response=_model_json("keep_current", 0.95)).parse_inbound(
            "on reste sur le planning prévu")
        assert outcome_for_feedback(fb, _ctx(proposal=proposal)) == expected
        if expected is None:
            assert resolve_feedback(fb, _ctx(proposal=proposal)).action == "confirm"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stance,decision", [
        ("adopt_proposal", "accepted"), ("decline_proposal", "rejected"), ("counter_value", "modified"),
    ])
    async def test_low_confidence_model_stance_is_confirmed_not_written(self, stance, decision):
        from app.services.receipts import outcome_for_feedback, resolve_feedback

        fb = await _service(llm_response=_model_json(stance, 0.6)).parse_inbound("free text")
        res = resolve_feedback(fb, _ctx())
        assert res.action == "confirm" and res.decision == decision and res.origin == "model"
        assert outcome_for_feedback(fb, _ctx()) is None

    @pytest.mark.asyncio
    async def test_unclear_stance_asks_for_the_decision(self):
        from app.services.receipts import resolve_feedback

        fb = await _service(llm_response=_model_json("unclear", 0.9)).parse_inbound("on verra")
        res = resolve_feedback(fb, _ctx())
        assert (res.action, res.why) == ("none", "stance_unclear")

    @pytest.mark.asyncio
    async def test_model_is_shown_the_proposal_and_the_reply_last(self):
        from app.services.manager_decision import Proposal

        svc = _service(llm_response=_model_json("keep_current", 0.9))
        ws = datetime(2026, 9, 25, 19, 0, tzinfo=timezone.utc)
        await svc.parse_inbound("pas besoin", Proposal("add", 2, "staffing.add", ws))
        content = svc._llm.complete.await_args.kwargs["messages"][0]["content"]
        assert content.startswith("Recommendation: ADD 2 staff for Friday 25/09 19:00")
        assert content.endswith("\nManager reply: pas besoin")
        assert "stance" in svc._llm.complete.await_args.kwargs["system"]

    @pytest.mark.asyncio
    async def test_model_without_proposal_is_told_the_direction_is_unknown(self):
        svc = _service(llm_response=_model_json("keep_current", 0.9))
        await svc.parse_inbound("on reste comme prévu")
        content = svc._llm.complete.await_args.kwargs["messages"][0]["content"]
        assert "direction is not recorded" in content

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kwargs", [{"llm_raises": True}, {"llm_response": "garbage"}])
    async def test_model_failure_records_nothing(self, kwargs):
        # The old path recorded "modified" on a model failure (ADR-0007 §15.2).
        from app.services.receipts import outcome_for_feedback, resolve_feedback

        fb = await _service(**kwargs).parse_inbound("free text")
        assert outcome_for_feedback(fb, _ctx()) is None
        assert resolve_feedback(fb, _ctx()).action == "none"

    @pytest.mark.asyncio
    async def test_covers_pattern_records_modified_without_model(self):
        from app.services.receipts import resolve_feedback

        svc = _service()
        res = resolve_feedback(await svc.parse_inbound("covers: 80"), _ctx())
        assert (res.action, res.decision, res.source.value) == ("record", "modified", "correction_pattern")
        svc._llm.complete.assert_not_awaited()


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
