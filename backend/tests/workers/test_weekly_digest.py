"""P2-5 tests — weekly KPI digest worker + ReceiptsService.weekly_digest.

Pure-mock tests: no DB, no LLM, no Twilio/SendGrid.

Covered:
  1.  register_weekly_digest_job injects Sunday cron job without starting scheduler
  2.  _run_weekly_digest_job dispatches ops_error and re-raises on fatal DB failure
  3.  weekly_digest returns WeeklyDigestPayload with correct aggregates
  4.  weekly_digest sets week_start = week_end - 6 days
  5.  weekly_digest zero actions → success_rate=0, error_count=0
  6.  weekly_digest MV row absent → memory_writes=0, pending_pct=0
  7.  compose_weekly_narrative returns LLM output
  8.  compose_weekly_narrative fallback on LLM error
  9.  _dispatch_weekly_digest_for_hotel sends WhatsApp + email
  10. Hotels with neither phone nor email are skipped
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.receipts import ReceiptsService, WeeklyDigestPayload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HOTEL = "hotel_weekly"
WEEK_END = date(2026, 5, 18)  # Sunday


def _make_log_row(status: str = "ok") -> Any:
    row = MagicMock()
    row.status = status
    row.hotel_id = HOTEL
    row.created_at = datetime(2026, 5, 17, 10, 0, tzinfo=timezone.utc)
    return row


def _make_db(log_rows: list, mv_row: tuple | None = (5, 2.5)) -> Any:
    """Mock AsyncSession with two execute() results: log rows + MV row."""
    db = AsyncMock()

    # First execute: agent_action_log SELECT
    log_result = MagicMock()
    log_result.scalars.return_value.all.return_value = log_rows

    # Second execute: memory_instrumentation_daily text() query
    mv_result = MagicMock()
    mv_result.fetchone.return_value = mv_row

    db.execute = AsyncMock(side_effect=[log_result, mv_result])
    return db


def _service(llm_response: str | None = None, llm_raises: bool = False) -> ReceiptsService:
    db = _make_db([_make_log_row("ok"), _make_log_row("tool_error")])
    mock_llm = AsyncMock()
    if llm_raises:
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("timeout"))
    else:
        mock_llm.complete = AsyncMock(return_value=llm_response or "Weekly digest text")
    return ReceiptsService(db, llm=mock_llm)


@dataclass
class _FakeHotel:
    tenant_id: str = "hotel_weekly"
    property_name: str = "Grand Hôtel Test"
    outlet_name: str = "Le Restaurant"
    phone_number: str | None = "+33612345678"
    notification_email: str | None = None
    is_active: bool = True


class _AsyncSessionCtx:
    def __init__(self, session: Any):
        self._session = session
    async def __aenter__(self):
        return self._session
    async def __aexit__(self, *_):
        return False


class _FailingSessionCtx:
    async def __aenter__(self):
        raise RuntimeError("DB down")
    async def __aexit__(self, *_):
        return False


# ---------------------------------------------------------------------------
# 1. register_weekly_digest_job
# ---------------------------------------------------------------------------

def test_register_weekly_digest_job_injects_without_starting():
    mock_sched = MagicMock()
    from app.workers.receipts_dispatcher import register_weekly_digest_job

    register_weekly_digest_job(mock_sched)

    mock_sched.add_job.assert_called_once()
    mock_sched.start.assert_not_called()
    kwargs = mock_sched.add_job.call_args.kwargs
    assert kwargs.get("id") == "weekly_digest"
    assert kwargs.get("day_of_week") == "sun"
    assert kwargs.get("replace_existing") is True


# ---------------------------------------------------------------------------
# 2. _run_weekly_digest_job — fatal DB failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_weekly_digest_dispatches_on_db_failure():
    from app.workers.receipts_dispatcher import _run_weekly_digest_job

    dispatch = AsyncMock()
    with (
        patch(
            "app.workers.receipts_dispatcher.AsyncSessionLocal",
            return_value=_FailingSessionCtx(),
        ),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
        pytest.raises(RuntimeError, match="DB down"),
    ):
        await _run_weekly_digest_job()

    dispatch.assert_awaited_once()
    kwargs = dispatch.await_args.kwargs
    assert "weekly_digest" in kwargs["title"]
    assert "job_id" in kwargs["detail"]


# ---------------------------------------------------------------------------
# 3–6. weekly_digest payload
# ---------------------------------------------------------------------------

class TestWeeklyDigest:
    @pytest.mark.asyncio
    async def test_payload_aggregates_correctly(self):
        log_rows = [_make_log_row("ok"), _make_log_row("ok"), _make_log_row("tool_error")]
        db = _make_db(log_rows, mv_row=(10, 5.0))
        svc = ReceiptsService(db, llm=AsyncMock())

        payload = await svc.weekly_digest(HOTEL, WEEK_END)

        assert payload.total_agent_actions == 3
        assert payload.tool_success_rate_pct == pytest.approx(66.7, abs=0.2)
        assert payload.agent_error_count == 1
        assert payload.memory_writes_week == 10
        assert payload.memory_pending_pct == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_week_start_is_6_days_before_week_end(self):
        db = _make_db([], mv_row=None)
        svc = ReceiptsService(db, llm=AsyncMock())

        payload = await svc.weekly_digest(HOTEL, WEEK_END)

        from datetime import timedelta
        assert payload.week_start == WEEK_END - timedelta(days=6)
        assert payload.week_end == WEEK_END

    @pytest.mark.asyncio
    async def test_zero_actions_gives_zero_success_rate(self):
        db = _make_db([], mv_row=(3, 10.0))
        svc = ReceiptsService(db, llm=AsyncMock())

        payload = await svc.weekly_digest(HOTEL, WEEK_END)

        assert payload.total_agent_actions == 0
        assert payload.tool_success_rate_pct == 0.0
        assert payload.agent_error_count == 0

    @pytest.mark.asyncio
    async def test_mv_none_gives_zero_memory(self):
        db = _make_db([_make_log_row("ok")], mv_row=None)
        svc = ReceiptsService(db, llm=AsyncMock())

        payload = await svc.weekly_digest(HOTEL, WEEK_END)

        assert payload.memory_writes_week == 0
        assert payload.memory_pending_pct == 0.0


# ---------------------------------------------------------------------------
# 7–8. compose_weekly_narrative
# ---------------------------------------------------------------------------

class TestComposeWeeklyNarrative:
    def _payload(self) -> WeeklyDigestPayload:
        return WeeklyDigestPayload(
            hotel_id=HOTEL,
            week_start=date(2026, 5, 12),
            week_end=WEEK_END,
            total_agent_actions=20,
            tool_success_rate_pct=95.0,
            agent_error_count=1,
            memory_writes_week=8,
            memory_pending_pct=0.0,
        )

    @pytest.mark.asyncio
    async def test_returns_llm_output(self):
        db = AsyncMock()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="  Weekly digest text  ")
        svc = ReceiptsService(db, llm=mock_llm)

        result = await svc.compose_weekly_narrative(self._payload(), "Grand Hôtel")

        assert result == "Weekly digest text"
        mock_llm.complete.assert_awaited_once()
        call_kwargs = mock_llm.complete.await_args.kwargs
        assert call_kwargs["max_tokens"] == 350
        assert "OQ4" in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        db = AsyncMock()
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("timeout"))
        svc = ReceiptsService(db, llm=mock_llm)

        result = await svc.compose_weekly_narrative(self._payload(), "Grand Hôtel")

        assert WEEK_END.isoformat() in result
        assert "20" in result  # total_agent_actions in fallback


# ---------------------------------------------------------------------------
# 9. _dispatch_weekly_digest_for_hotel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_weekly_sends_whatsapp():
    from app.workers.receipts_dispatcher import _dispatch_weekly_digest_for_hotel

    hotel = _FakeHotel(phone_number="+33612345678")
    mock_service = AsyncMock(spec=ReceiptsService)
    mock_service.weekly_digest = AsyncMock(return_value=WeeklyDigestPayload(
        hotel_id=HOTEL, week_start=date(2026, 5, 12), week_end=WEEK_END,
        total_agent_actions=10, tool_success_rate_pct=90.0,
        agent_error_count=1, memory_writes_week=5, memory_pending_pct=0.0,
    ))
    mock_service.compose_weekly_narrative = AsyncMock(return_value="Weekly text")

    mock_twilio = AsyncMock()
    mock_twilio.send_whatsapp = AsyncMock(return_value="SM_weekly_sid")

    with patch("app.workers.receipts_dispatcher._twilio", mock_twilio):
        await _dispatch_weekly_digest_for_hotel(mock_service, hotel, WEEK_END)

    mock_twilio.send_whatsapp.assert_awaited_once_with(hotel.phone_number, "Weekly text")


# ---------------------------------------------------------------------------
# 10. Hotels without contact are skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_weekly_digest_skips_no_contact_hotels():
    from app.workers.receipts_dispatcher import _run_weekly_digest_job

    no_contact = _FakeHotel(phone_number=None, notification_email=None)

    mock_session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [no_contact]
    mock_session.execute = AsyncMock(return_value=result_mock)

    twilio_mock = AsyncMock()
    twilio_mock.send_whatsapp = AsyncMock()

    with (
        patch("app.workers.receipts_dispatcher.AsyncSessionLocal",
              side_effect=[_AsyncSessionCtx(mock_session)]),
        patch("app.workers.receipts_dispatcher._twilio", twilio_mock),
    ):
        await _run_weekly_digest_job()

    twilio_mock.send_whatsapp.assert_not_awaited()
