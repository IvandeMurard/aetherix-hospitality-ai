"""P2-3 tests — receipts_dispatcher worker + ReceiptsService.compose_narrative.

Pure-mock tests: no DB, no Twilio, no SendGrid, no LLM calls hit the network.

Covered:
  1. register_receipt_dispatch_job injects job onto scheduler (no start call)
  2. _run_receipt_dispatch_job dispatches ops_error and re-raises on fatal DB failure
  3. _dispatch_receipt_for_hotel sends WhatsApp when phone_number is set
  4. _dispatch_receipt_for_hotel skips WhatsApp when NotConfiguredError
  5. _dispatch_receipt_for_hotel sends email when notification_email is set
  6. _dispatch_receipt_for_hotel skips email silently when SendGrid not configured
  7. Hotels with neither phone nor email are skipped (no dispatch calls)
  8. compose_narrative returns LLM output on success
  9. compose_narrative returns fallback string when LLM raises
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotConfiguredError
from app.services.receipts import ReceiptPayload, ReceiptLine, ReceiptsService

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

HOTEL = "hotel_p2"
TODAY = date(2026, 5, 16)


def _make_payload(total: int = 2) -> ReceiptPayload:
    ts = datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc)
    lines = [
        ReceiptLine(timestamp=ts, tool_name="get_operational_predictions",
                    status="ok", request_id=f"rid-{i}")
        for i in range(total)
    ]
    return ReceiptPayload(
        hotel_id=HOTEL,
        receipt_date=TODAY,
        total_actions=total,
        counts_by_status={"ok": total},
        counts_by_tool={"get_operational_predictions": total},
        lines=lines,
    )


@dataclass
class _FakeHotel:
    """Minimal RestaurantProfile stand-in."""
    tenant_id: str = "hotel_p2"
    property_name: str = "Grand Hôtel Test"
    outlet_name: str = "Le Restaurant"
    phone_number: str | None = "+33612345678"
    notification_email: str | None = None
    is_active: bool = True


class _AsyncSessionCtx:
    """Async context manager returning a MagicMock DB session."""
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
# 1. register_receipt_dispatch_job
# ---------------------------------------------------------------------------

def test_register_receipt_dispatch_job_injects_without_starting():
    mock_sched = MagicMock()
    from app.workers.receipts_dispatcher import register_receipt_dispatch_job

    register_receipt_dispatch_job(mock_sched)

    mock_sched.add_job.assert_called_once()
    mock_sched.start.assert_not_called()
    kwargs = mock_sched.add_job.call_args.kwargs
    assert kwargs.get("id") == "receipt_dispatcher"
    assert kwargs.get("replace_existing") is True


# ---------------------------------------------------------------------------
# 2. _run_receipt_dispatch_job — fatal DB failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_receipt_dispatch_dispatches_on_db_failure():
    from app.workers.receipts_dispatcher import _run_receipt_dispatch_job

    dispatch = AsyncMock()
    with (
        patch(
            "app.workers.receipts_dispatcher.AsyncSessionLocal",
            return_value=_FailingSessionCtx(),
        ),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
        pytest.raises(RuntimeError, match="DB down"),
    ):
        await _run_receipt_dispatch_job()

    dispatch.assert_awaited_once()
    kwargs = dispatch.await_args.kwargs
    assert "receipts_dispatcher" in kwargs["title"]
    assert "job_id" in kwargs["detail"]


# ---------------------------------------------------------------------------
# 3 & 4. _dispatch_receipt_for_hotel — WhatsApp path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_sends_whatsapp_when_phone_set():
    from app.workers.receipts_dispatcher import _dispatch_receipt_for_hotel

    hotel = _FakeHotel(phone_number="+33612345678")
    payload = _make_payload()

    mock_service = AsyncMock(spec=ReceiptsService)
    mock_service.daily_receipt = AsyncMock(return_value=payload)
    mock_service.compose_narrative = AsyncMock(return_value="Receipt text")

    mock_twilio = AsyncMock()
    mock_twilio.send_whatsapp = AsyncMock(return_value="SM_test_sid")

    with patch("app.workers.receipts_dispatcher._twilio", mock_twilio):
        await _dispatch_receipt_for_hotel(mock_service, hotel, TODAY)

    mock_twilio.send_whatsapp.assert_awaited_once_with(
        hotel.phone_number, "Receipt text"
    )


@pytest.mark.asyncio
async def test_dispatch_skips_whatsapp_on_not_configured():
    from app.workers.receipts_dispatcher import _dispatch_receipt_for_hotel

    hotel = _FakeHotel(phone_number="+33612345678")
    payload = _make_payload()

    mock_service = AsyncMock(spec=ReceiptsService)
    mock_service.daily_receipt = AsyncMock(return_value=payload)
    mock_service.compose_narrative = AsyncMock(return_value="Receipt text")

    mock_twilio = AsyncMock()
    mock_twilio.send_whatsapp = AsyncMock(side_effect=NotConfiguredError("Twilio"))

    with patch("app.workers.receipts_dispatcher._twilio", mock_twilio):
        # Should not raise — silently skipped
        await _dispatch_receipt_for_hotel(mock_service, hotel, TODAY)

    mock_twilio.send_whatsapp.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5 & 6. _dispatch_receipt_for_hotel — email path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_sends_email_when_notification_email_set():
    from app.workers.receipts_dispatcher import _dispatch_receipt_for_hotel

    hotel = _FakeHotel(
        phone_number=None,
        notification_email="manager@hotel.com",
    )
    payload = _make_payload()

    mock_service = AsyncMock(spec=ReceiptsService)
    mock_service.daily_receipt = AsyncMock(return_value=payload)
    mock_service.compose_narrative = AsyncMock(return_value="Receipt text")

    mock_sendgrid = AsyncMock()
    mock_sendgrid.send_email = AsyncMock(return_value=True)

    with patch("app.workers.receipts_dispatcher._sendgrid", mock_sendgrid):
        await _dispatch_receipt_for_hotel(mock_service, hotel, TODAY)

    mock_sendgrid.send_email.assert_awaited_once()
    args = mock_sendgrid.send_email.await_args
    assert args.args[0] == "manager@hotel.com"
    assert "Receipt" in args.args[1]
    assert "Receipt text" == args.args[2]


@pytest.mark.asyncio
async def test_dispatch_skips_email_on_not_configured():
    from app.workers.receipts_dispatcher import _dispatch_receipt_for_hotel

    hotel = _FakeHotel(phone_number=None, notification_email="mgr@hotel.com")
    payload = _make_payload()

    mock_service = AsyncMock(spec=ReceiptsService)
    mock_service.daily_receipt = AsyncMock(return_value=payload)
    mock_service.compose_narrative = AsyncMock(return_value="text")

    mock_sendgrid = AsyncMock()
    mock_sendgrid.send_email = AsyncMock(side_effect=NotConfiguredError("SendGrid"))

    with patch("app.workers.receipts_dispatcher._sendgrid", mock_sendgrid):
        await _dispatch_receipt_for_hotel(mock_service, hotel, TODAY)

    mock_sendgrid.send_email.assert_awaited_once()


# ---------------------------------------------------------------------------
# 7. Hotels with neither phone nor email are skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_receipt_dispatch_skips_hotels_without_contact():
    from app.workers.receipts_dispatcher import _run_receipt_dispatch_job

    no_contact_hotel = _FakeHotel(phone_number=None, notification_email=None)

    mock_session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [no_contact_hotel]
    mock_session.execute = AsyncMock(return_value=result_mock)

    async def fake_session_ctx():
        return _AsyncSessionCtx(mock_session)

    twilio_mock = AsyncMock()
    twilio_mock.send_whatsapp = AsyncMock()
    sendgrid_mock = AsyncMock()
    sendgrid_mock.send_email = AsyncMock()

    with (
        patch("app.workers.receipts_dispatcher.AsyncSessionLocal",
              side_effect=[_AsyncSessionCtx(mock_session)]),
        patch("app.workers.receipts_dispatcher._twilio", twilio_mock),
        patch("app.workers.receipts_dispatcher._sendgrid", sendgrid_mock),
    ):
        await _run_receipt_dispatch_job()

    twilio_mock.send_whatsapp.assert_not_awaited()
    sendgrid_mock.send_email.assert_not_awaited()


# ---------------------------------------------------------------------------
# 8. compose_narrative — LLM success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compose_narrative_returns_llm_output():
    db = AsyncMock()
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value="  Luxury receipt text  ")

    service = ReceiptsService(db, llm=mock_llm)
    payload = _make_payload()

    result = await service.compose_narrative(payload, "Grand Hôtel", "http://test/receipts/x")

    assert result == "Luxury receipt text"
    mock_llm.complete.assert_awaited_once()
    call_kwargs = mock_llm.complete.await_args.kwargs
    assert call_kwargs["max_tokens"] == 400
    assert call_kwargs["temperature"] == 0.2
    assert "OQ4" in call_kwargs["system"]


# ---------------------------------------------------------------------------
# 9. compose_narrative — LLM failure → fallback string
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compose_narrative_fallback_on_llm_error():
    db = AsyncMock()
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(side_effect=RuntimeError("API timeout"))

    service = ReceiptsService(db, llm=mock_llm)
    payload = _make_payload()

    result = await service.compose_narrative(payload, "Grand Hôtel", "http://test/receipts/x")

    # Fallback must include the date and the drill-down URL
    assert TODAY.isoformat() in result
    assert "http://test/receipts/x" in result
