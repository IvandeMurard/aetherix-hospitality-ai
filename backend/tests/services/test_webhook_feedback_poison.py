"""HOS-250 (Epic 12 G-3, QA S4) — feedback-memory poison guard at the webhook.

Regression test for the cross-path gap found in QA: a manager-reported
``actual_covers`` is written into retrievable (embedded) feedback memory via
``tool_submit_feedback_to_memory`` *and* onto the recommendation via
``persist_actual_covers``. HOS-250 guards the latter but the former runs first,
so an aberrant/rejected value still poisoned the model through the feedback row.

The fix runs the plausibility guard first and strips the numeric from the
feedback-memory write when it is rejected. This test drives the real
``_bg_receipt_feedback`` background handler end-to-end (in-memory SQLite, real
parser + real ``persist_actual_covers``) and asserts the rejected number never
reaches feedback memory.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import webhook
from app.db.models import (
    Base,
    RestaurantProfile,
    StaffingRecommendation,
)
from app.services.receipts import ReceiptsService

HOTEL = "hotel_poison"
PHONE = "+15551234567"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


class _SessionCtx:
    """Async-context wrapper so webhook's ``async with AsyncSessionLocal()`` reuses
    the test session without closing it (the fixture owns the lifecycle)."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


async def _seed(session, *, total_seats=50):
    profile = RestaurantProfile(
        id=_uuid.uuid4(),
        tenant_id=HOTEL,
        property_name="Poison Test Hotel",
        outlet_name="Poison Test Restaurant",
        phone_number=PHONE,
        total_seats=total_seats,  # turns default 4.5 → ceiling 50×4.5×1.5 = 337.5
    )
    session.add(profile)
    await session.commit()

    now = datetime.now(tz=timezone.utc)
    rec = StaffingRecommendation(
        id=_uuid.uuid4(),
        tenant_id=HOTEL,
        property_id=profile.id,
        anomaly_id=_uuid.uuid4(),
        message_text="Add 2 servers.",
        triggering_factor="Event",
        recommended_headcount=2,
        window_start=now,
        window_end=now,
        predicted_covers=140.0,
        status="dispatched",
    )
    session.add(rec)
    await session.commit()
    return profile, rec


@pytest.mark.asyncio
async def test_rejected_value_not_written_to_feedback_memory(db_session):
    _profile, rec = await _seed(db_session)

    submit_mock = AsyncMock(return_value={"status": "ok"})

    with (
        patch.object(webhook, "AsyncSessionLocal", lambda: _SessionCtx(db_session)),
        patch.object(webhook, "ReceiptsService", lambda db: ReceiptsService(db, llm=AsyncMock())),
        patch.object(webhook._twilio_client, "send_whatsapp", AsyncMock()),
        patch("app.mcp_server.tool_submit_feedback_to_memory", submit_mock),
        patch("app.services.ops_dispatcher.dispatch_error", AsyncMock()),
        patch("app.services.ops_dispatcher.dispatch_anomaly", AsyncMock()),
    ):
        # 99999 covers for a 337.5 ceiling → rejected by the HOS-250 guard.
        await webhook._bg_receipt_feedback(
            from_number=f"whatsapp:{PHONE}", body="dinner covers 99999, not 140"
        )

    # The feedback-memory write happened, but the rejected numeric is no longer
    # propagated as a structured training signal: actual_value is None and the
    # system-generated "actual=<n>" marker is absent. (The manager's verbatim note
    # is intentionally preserved as-is — it is qualitative context, not the bounded
    # numeric label that HOS-250 guards.)
    submit_mock.assert_awaited_once()
    kwargs = submit_mock.await_args.kwargs
    assert kwargs["actual_value"] is None
    assert "actual=99999" not in (kwargs["notes"] or "")

    # And the ground-truth path stayed blocked (recommendation untouched).
    refreshed = (
        await db_session.execute(
            select(StaffingRecommendation).where(StaffingRecommendation.id == rec.id)
        )
    ).scalars().one()
    assert refreshed.actual_covers is None


@pytest.mark.asyncio
async def test_plausible_value_still_written_to_feedback_memory(db_session):
    _profile, rec = await _seed(db_session)

    submit_mock = AsyncMock(return_value={"status": "ok"})

    with (
        patch.object(webhook, "AsyncSessionLocal", lambda: _SessionCtx(db_session)),
        patch.object(webhook, "ReceiptsService", lambda db: ReceiptsService(db, llm=AsyncMock())),
        patch.object(webhook._twilio_client, "send_whatsapp", AsyncMock()),
        patch("app.mcp_server.tool_submit_feedback_to_memory", submit_mock),
        patch("app.services.ops_dispatcher.dispatch_error", AsyncMock()),
        patch("app.services.ops_dispatcher.dispatch_anomaly", AsyncMock()),
    ):
        # 120 covers is within the 337.5 ceiling → plausible, carried through.
        await webhook._bg_receipt_feedback(
            from_number=f"whatsapp:{PHONE}", body="dinner covers 120, not 140"
        )

    submit_mock.assert_awaited_once()
    kwargs = submit_mock.await_args.kwargs
    assert kwargs["actual_value"] == 120.0
    assert "120" in (kwargs["notes"] or "")

    refreshed = (
        await db_session.execute(
            select(StaffingRecommendation).where(StaffingRecommendation.id == rec.id)
        )
    ).scalars().one()
    assert float(refreshed.actual_covers) == 120.0
