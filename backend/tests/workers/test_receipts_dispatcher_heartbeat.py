"""HOS-248 — receipts_dispatcher heartbeat wiring (T1/T3).

Verifies the daily Receipt dispatcher emits a heartbeat on a completed run and
trips an aggregated alert when per-hotel dispatches fail.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from app.workers import receipts_dispatcher


class _Session:
    """Async ctx manager whose execute() yields a fixed hotel list."""

    def __init__(self, hotels):
        self._hotels = hotels

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def execute(self, *_a, **_k):
        res = MagicMock()
        res.scalars.return_value.all.return_value = self._hotels
        return res


async def test_records_heartbeat_on_completed_run_no_hotels():
    hb = AsyncMock()
    trip = AsyncMock()
    with (
        patch.object(receipts_dispatcher, "AsyncSessionLocal", lambda: _Session([])),
        patch.object(receipts_dispatcher, "record_heartbeat", hb),
        patch.object(receipts_dispatcher, "record_trip", trip),
    ):
        await receipts_dispatcher._run_receipt_dispatch_job()

    hb.assert_awaited_once_with("receipt_dispatcher")
    trip.assert_not_awaited()


async def test_trips_partial_alert_on_per_hotel_failure():
    hotel = MagicMock(phone_number="+15005550006", notification_email=None, tenant_id="h1")
    hb = AsyncMock()
    trip = AsyncMock()
    with (
        patch.object(receipts_dispatcher, "AsyncSessionLocal", lambda: _Session([hotel])),
        patch.object(
            receipts_dispatcher,
            "_dispatch_receipt_for_hotel",
            AsyncMock(side_effect=RuntimeError("send boom")),
        ),
        patch.object(receipts_dispatcher, "record_heartbeat", hb),
        patch.object(receipts_dispatcher, "record_trip", trip),
    ):
        await receipts_dispatcher._run_receipt_dispatch_job()

    # Job still completed → heartbeat recorded; failure → aggregated trip.
    hb.assert_awaited_once_with("receipt_dispatcher")
    trip.assert_awaited_once()
    assert trip.await_args.args[0] == "receipt_dispatcher"
    assert trip.await_args.args[1] == receipts_dispatcher.REASON_PARTIAL
