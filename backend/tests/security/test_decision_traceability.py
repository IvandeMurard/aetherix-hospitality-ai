"""Decision traceability / replay (HOS-293, plan #10).

A design-partner (or an audit) must be able to ask *"why this recommendation?"*
and get the chain reconstructed from the structured log: inputs → which model →
output → any guardrail trip. The join key is ``agent_action_log.request_id``;
guardrail trips carry a typed reason (NFR2).

This suite proves what is reconstructible today and pins the one remaining gap
(model identity is not persisted in the structured log — app-log only).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.context import request_id_var
from app.db.models import AgentActionLog, Base
from app.services.forecast_guardrail import (
    GUARDRAIL_TOOL,
    REASON_TIER1,
    TIER1_FLAG,
    ForecastVerdict,
    record_forecast_trip,
)

# The reconstruction fields a decision replay needs from one action-log row.
_REPLAY_FIELDS = {
    "request_id",       # join key across the decision's events
    "hotel_id",         # tenant scope
    "tool_name",        # which step
    "status",
    "error_code",
    "latency_ms",
    "payload",          # event detail
    "abstention_reason",   # typed guardrail reason (NFR2)
    "abstention_layer",
    "abstention_context",
    "created_at",
}


@pytest_asyncio.fixture
async def sqlite_factory():
    """Shared in-memory SQLite (StaticPool) so a service's own session and the
    test's query session see the same rows."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def _tier1_verdict() -> ForecastVerdict:
    return ForecastVerdict(
        tier=TIER1_FLAG,
        effective_covers=100,
        confidence=0.4,
        baseline_used=False,
        reason=REASON_TIER1,
        detail="confidence below WARN threshold",
    )


async def _fetch_trip(factory):
    async with factory() as s:
        return (
            await s.execute(
                select(AgentActionLog).where(
                    AgentActionLog.tool_name == GUARDRAIL_TOOL
                )
            )
        ).scalars().first()


# ---------------------------------------------------------------------------
# Structural — the action log carries what a replay needs
# ---------------------------------------------------------------------------
def test_action_log_exposes_reconstruction_fields():
    cols = {c.name for c in AgentActionLog.__table__.columns}
    missing = _REPLAY_FIELDS - cols
    assert not missing, f"agent_action_log missing replay fields: {sorted(missing)}"


# ---------------------------------------------------------------------------
# Behavioural — a guardrail trip is persisted with a typed reason (NFR2)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_guardrail_trip_logged_with_typed_reason(sqlite_factory):
    with patch(
        "app.services.forecast_guardrail.AsyncSessionLocal", sqlite_factory
    ):
        await record_forecast_trip("hotel_x", _tier1_verdict())

    row = await _fetch_trip(sqlite_factory)
    assert row is not None, "trip was not persisted to agent_action_log"
    assert row.abstention_reason == REASON_TIER1        # typed reason (NFR2)
    assert row.abstention_layer == "forecast"
    assert row.error_code == REASON_TIER1
    assert row.status == "tool_error"
    assert (row.payload or {}).get("kind") == "trip"


# ---------------------------------------------------------------------------
# Traceability — the trip is joinable to the originating decision (HOS-293 fix)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_guardrail_trip_carries_request_id(sqlite_factory):
    token = request_id_var.set("req-trace-123")
    try:
        with patch(
            "app.services.forecast_guardrail.AsyncSessionLocal", sqlite_factory
        ):
            await record_forecast_trip("hotel_x", _tier1_verdict())
    finally:
        request_id_var.reset(token)

    row = await _fetch_trip(sqlite_factory)
    assert row is not None
    assert row.request_id == "req-trace-123", (
        "guardrail trip must carry the originating decision's request_id so the "
        "chain is joinable"
    )


# ---------------------------------------------------------------------------
# Known gap — model identity is not in the structured decision log (follow-up)
# ---------------------------------------------------------------------------
@pytest.mark.xfail(
    reason="model_id is not persisted in agent_action_log — decision→model link "
    "relies on unstructured app logs only. Tracked follow-up (HOS-293).",
    strict=False,
)
def test_action_log_records_model_identity():
    cols = {c.name for c in AgentActionLog.__table__.columns}
    assert "model_id" in cols
