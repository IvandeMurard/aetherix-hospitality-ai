"""HOS-250 (Epic 12 G-3) — feedback bounds guard unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.services import feedback_guard
from app.services.feedback_guard import evaluate

# ---------------------------------------------------------------------------
# evaluate() — pure plausibility logic
# ---------------------------------------------------------------------------

def test_within_capacity_is_plausible():
    v = evaluate(100, total_seats=50, turns_sum=4.5)  # ceiling = 337.5
    assert v.plausible is True
    assert v.severity == "ok"


def test_above_capacity_is_rejected():
    v = evaluate(400, total_seats=50, turns_sum=4.5)  # ceiling = 337.5
    assert v.plausible is False
    assert v.severity == "reject"
    assert v.reason == feedback_guard.REASON_IMPLAUSIBLE


def test_negative_is_rejected():
    v = evaluate(-5, total_seats=50, turns_sum=4.5)
    assert v.plausible is False
    assert v.severity == "reject"


def test_zero_is_rejected():
    v = evaluate(0, total_seats=50, turns_sum=4.5)
    assert v.plausible is False
    assert v.severity == "reject"


def test_above_history_within_capacity_is_flagged_not_rejected():
    # 100 > 20 × 3 (history) but < 337.5 (capacity) → flag, never reject.
    v = evaluate(100, total_seats=50, turns_sum=4.5, historical_max=20)
    assert v.plausible is False
    assert v.severity == "flag"


def test_capacity_skipped_when_profile_unknown():
    # No seats/turns known → capacity not enforced (only lower bound applies).
    v = evaluate(100_000, total_seats=None, turns_sum=None)
    assert v.plausible is True


def test_capacity_enforced_with_default_turns_when_turns_missing():
    # Seats known but turns NULL → turns_sum == 0 (falsy). The ceiling must still
    # be enforced via the default-turns fallback, not silently skipped (HOS-250
    # hardening: a falsy turns_sum previously bypassed the capacity guard).
    v = evaluate(50_000, total_seats=120, turns_sum=0)  # ceiling = 120×3×1.5 = 540
    assert v.plausible is False
    assert v.severity == "reject"
    assert v.reason == feedback_guard.REASON_IMPLAUSIBLE


def test_plausible_value_passes_with_default_turns():
    # A realistic surge stays plausible even when turns are unconfigured.
    v = evaluate(300, total_seats=120, turns_sum=None)  # ceiling = 540
    assert v.plausible is True
    assert v.severity == "ok"


def test_policy_flag_downgrades_capacity_breach(monkeypatch):
    monkeypatch.setattr(feedback_guard.config, "FEEDBACK_BOUNDS_POLICY", "flag")
    v = evaluate(400, total_seats=50, turns_sum=4.5)
    assert v.plausible is False
    assert v.severity == "flag"


# ---------------------------------------------------------------------------
# record_feedback_trip() — typed row + ops alert (AC3)
# ---------------------------------------------------------------------------

class _CapturingSession:
    def __init__(self, store):
        self._store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def add(self, obj):
        self._store.append(obj)

    async def commit(self):
        return None


async def test_record_trip_reject_writes_row_and_dispatches_error():
    store: list = []
    err = AsyncMock()
    anomaly = AsyncMock()
    with (
        patch.object(feedback_guard, "AsyncSessionLocal", lambda: _CapturingSession(store)),
        patch("app.services.ops_dispatcher.dispatch_error", err),
        patch("app.services.ops_dispatcher.dispatch_anomaly", anomaly),
    ):
        await feedback_guard.record_feedback_trip(
            "hotel_x", feedback_guard.REASON_IMPLAUSIBLE, "too big", "reject"
        )

    assert len(store) == 1
    row = store[0]
    assert row.tool_name == feedback_guard.FEEDBACK_TOOL
    assert row.status == "tool_error"
    assert row.error_code == feedback_guard.REASON_IMPLAUSIBLE
    assert row.hotel_id == "hotel_x"
    err.assert_awaited_once()
    anomaly.assert_not_awaited()


async def test_record_trip_flag_dispatches_anomaly():
    err = AsyncMock()
    anomaly = AsyncMock()
    with (
        patch.object(feedback_guard, "AsyncSessionLocal", lambda: _CapturingSession([])),
        patch("app.services.ops_dispatcher.dispatch_error", err),
        patch("app.services.ops_dispatcher.dispatch_anomaly", anomaly),
    ):
        await feedback_guard.record_feedback_trip(
            "hotel_x", feedback_guard.REASON_IMPLAUSIBLE, "above history", "flag"
        )

    anomaly.assert_awaited_once()
    err.assert_not_awaited()
