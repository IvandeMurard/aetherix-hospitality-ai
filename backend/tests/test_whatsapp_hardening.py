"""Tests for HOS-132 — WhatsApp & alert pipeline production hardening.

Coverage:
- AC4: generate_and_send() sets "answered" only on confirmed Twilio 2xx
- AC4: generate_and_send() leaves status unchanged when Twilio fails
- AC5: _validate_phone() correctly identifies valid/invalid E.164 numbers
- AC5: alert_dispatcher sets "config_error" on invalid phone (existing — smoke)
- AC6: run_pending() query excludes "config_error" status
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.alert_dispatcher import _validate_phone
from app.services.explainability_service import ExplainabilityService


# ===========================================================================
# AC5 — _validate_phone E.164 validation
# ===========================================================================

class TestValidatePhone:
    @pytest.mark.parametrize("number", [
        "+33612345678",
        "+447911123456",
        "+12025551234",
        "+1800555000",   # exactly 8 chars after +
    ])
    def test_valid_e164_numbers_return_true(self, number: str):
        assert _validate_phone(number) is True

    @pytest.mark.parametrize("number", [
        "",
        None,
        "0612345678",       # no leading +
        "+123",             # too short (< 8 chars total)
        "whatsapp:+336",    # prefix not stripped
        "not-a-number",
    ])
    def test_invalid_numbers_return_false(self, number):
        assert _validate_phone(number) is False


# ===========================================================================
# AC4 — generate_and_send(): "answered" gated on Twilio success
# ===========================================================================

def _make_db_objects():
    """Build minimal ConversationalQuery + StaffingRecommendation mocks."""
    cq_id = uuid.uuid4()

    cq = MagicMock()
    cq.id = cq_id
    cq.status = "processing"
    cq.from_number = "+33612345678"
    cq.body = "Why do we need extra staff?"
    cq.recommendation_id = uuid.uuid4()

    rec = MagicMock()
    rec.id = uuid.uuid4()
    rec.anomaly_id = None
    rec.window_start = None
    rec.window_end = None
    rec.roi_net = None
    rec.roi_labor_cost = None
    rec.message_text = "Add 2 servers for dinner rush"
    rec.recommended_headcount = 8
    rec.triggering_factor = "surge"

    return cq, rec, cq_id


def _make_session(cq, rec):
    """Build a mock AsyncSession that returns cq then rec on successive execute() calls."""
    session = MagicMock()
    session.commit = AsyncMock()

    results = [
        MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=cq)))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=rec)))),
    ]
    session.execute = AsyncMock(side_effect=results)
    return session


class TestGenerateAndSendStatusUpdate:
    @pytest.mark.asyncio
    async def test_sets_answered_on_twilio_success(self):
        """AC4: status = "answered" only when Twilio returns 2xx."""
        cq, rec, cq_id = _make_db_objects()
        session = _make_session(cq, rec)

        llm = MagicMock()
        llm.complete = AsyncMock(return_value="Here is your explanation.")

        with patch(
            "app.services.explainability_service._send_twilio_reply",
            new_callable=AsyncMock,
            return_value=True,
        ):
            service = ExplainabilityService(llm=llm)
            result = await service.generate_and_send(cq_id, session)

        assert cq.status == "answered"
        session.commit.assert_awaited()
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_does_not_set_answered_on_twilio_failure(self):
        """AC4: status must NOT be updated when Twilio fails."""
        cq, rec, cq_id = _make_db_objects()
        cq.status = "processing"
        session = _make_session(cq, rec)

        llm = MagicMock()
        llm.complete = AsyncMock(return_value="Explanation text.")

        with patch(
            "app.services.explainability_service._send_twilio_reply",
            new_callable=AsyncMock,
            return_value=False,  # Twilio failure
        ):
            service = ExplainabilityService(llm=llm)
            await service.generate_and_send(cq_id, session)

        assert cq.status != "answered"

    @pytest.mark.asyncio
    async def test_fallback_sets_answered_on_twilio_success(self):
        """AC4: fallback path (no recommendation) also gates 'answered' on Twilio success."""
        cq = MagicMock()
        cq.id = uuid.uuid4()
        cq.status = "processing"
        cq.from_number = "+33612345678"
        cq.body = "??"
        cq.recommendation_id = None  # no linked recommendation

        session = MagicMock()
        session.commit = AsyncMock()
        # Only one execute call — for the ConversationalQuery
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=cq)))
        ))

        with patch(
            "app.services.explainability_service._send_twilio_reply",
            new_callable=AsyncMock,
            return_value=True,
        ):
            service = ExplainabilityService(llm=MagicMock())
            result = await service.generate_and_send(cq.id, session)

        assert cq.status == "answered"
        assert result["status"] == "sent_fallback"

    @pytest.mark.asyncio
    async def test_fallback_does_not_set_answered_on_twilio_failure(self):
        """AC4: fallback path leaves status unchanged when Twilio fails."""
        cq = MagicMock()
        cq.id = uuid.uuid4()
        cq.status = "processing"
        cq.from_number = "+33612345678"
        cq.body = "??"
        cq.recommendation_id = None

        session = MagicMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=cq)))
        ))

        with patch(
            "app.services.explainability_service._send_twilio_reply",
            new_callable=AsyncMock,
            return_value=False,
        ):
            service = ExplainabilityService(llm=MagicMock())
            await service.generate_and_send(cq.id, session)

        assert cq.status != "answered"


# ===========================================================================
# AC6 — run_pending() excludes config_error
# ===========================================================================

class TestRunPendingExcludesConfigError:
    @pytest.mark.asyncio
    async def test_run_pending_only_fetches_ready_to_push(self):
        """run_pending() must query status='ready_to_push', never 'config_error'."""
        from app.services.alert_dispatcher import AlertDispatcherService

        session = MagicMock()
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ))

        await AlertDispatcherService().run_pending(session)

        call_args = session.execute.call_args
        stmt = call_args[0][0]
        # SQLAlchemy parameterises the value — check compiled params, not raw SQL string
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql_str = str(compiled)
        assert "ready_to_push" in sql_str
        assert "config_error" not in sql_str
