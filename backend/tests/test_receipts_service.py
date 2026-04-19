"""Tier-1 tests for ReceiptsService.daily_receipt (P2-1).

Pure-mock tests — no DB, no asyncpg, run anywhere. Verifies grouping,
counters, and date-range semantics. Integration with real Postgres is
covered separately when asyncpg is available.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.receipts import ReceiptsService, ReceiptPayload


@dataclass
class _FakeRow:
    """Mimics the subset of AgentActionLog columns ReceiptsService reads."""
    created_at: datetime
    tool_name: str
    status: str
    request_id: str = ""
    latency_ms: int | None = None
    error_code: str | None = None
    dedup_hit: bool | None = None
    top_similarity: float | None = None


def _mock_db(rows: list[_FakeRow]) -> Any:
    """Build an AsyncMock AsyncSession whose execute().scalars().all() returns rows."""
    scalars_obj = MagicMock()
    scalars_obj.all = MagicMock(return_value=rows)
    result_obj = MagicMock()
    result_obj.scalars = MagicMock(return_value=scalars_obj)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_obj)
    return db


HOTEL = "hotel_demo"
TODAY = date(2026, 4, 19)


class TestEmptyLog:
    @pytest.mark.asyncio
    async def test_no_rows_returns_zero_total(self):
        db = _mock_db([])
        svc = ReceiptsService(db)
        payload = await svc.daily_receipt(HOTEL, TODAY)
        assert isinstance(payload, ReceiptPayload)
        assert payload.total_actions == 0
        assert payload.lines == []
        assert payload.counts_by_status == {}
        assert payload.counts_by_tool == {}

    @pytest.mark.asyncio
    async def test_no_rows_keeps_hotel_id_and_date(self):
        db = _mock_db([])
        svc = ReceiptsService(db)
        payload = await svc.daily_receipt(HOTEL, TODAY)
        assert payload.hotel_id == HOTEL
        assert payload.receipt_date == TODAY


class TestCounters:
    @pytest.mark.asyncio
    async def test_groups_by_status(self):
        rows = [
            _FakeRow(datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc),
                     "get_operational_predictions", "ok", "rid-1", 120),
            _FakeRow(datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
                     "get_operational_predictions", "ok", "rid-2", 110),
            _FakeRow(datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
                     "submit_feedback_to_memory", "auth_error", "rid-3"),
            _FakeRow(datetime(2026, 4, 19, 11, 0, tzinfo=timezone.utc),
                     "submit_feedback_to_memory", "rate_limited", "rid-4"),
        ]
        payload = await ReceiptsService(_mock_db(rows)).daily_receipt(HOTEL, TODAY)
        assert payload.total_actions == 4
        assert payload.counts_by_status == {
            "ok": 2, "auth_error": 1, "rate_limited": 1,
        }

    @pytest.mark.asyncio
    async def test_groups_by_tool(self):
        rows = [
            _FakeRow(datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc),
                     "get_operational_predictions", "ok", "rid-1"),
            _FakeRow(datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
                     "get_operational_predictions", "ok", "rid-2"),
            _FakeRow(datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
                     "submit_feedback_to_memory", "ok", "rid-3"),
        ]
        payload = await ReceiptsService(_mock_db(rows)).daily_receipt(HOTEL, TODAY)
        assert payload.counts_by_tool == {
            "get_operational_predictions": 2,
            "submit_feedback_to_memory": 1,
        }


class TestLineMapping:
    @pytest.mark.asyncio
    async def test_line_fields_copied_from_row(self):
        ts = datetime(2026, 4, 19, 14, 30, tzinfo=timezone.utc)
        row = _FakeRow(
            created_at=ts,
            tool_name="submit_feedback_to_memory",
            status="ok",
            request_id="abc-123",
            latency_ms=87,
            error_code=None,
            dedup_hit=True,
            top_similarity=0.93,
        )
        payload = await ReceiptsService(_mock_db([row])).daily_receipt(HOTEL, TODAY)
        assert len(payload.lines) == 1
        line = payload.lines[0]
        assert line.timestamp == ts
        assert line.tool_name == "submit_feedback_to_memory"
        assert line.status == "ok"
        assert line.request_id == "abc-123"
        assert line.latency_ms == 87
        assert line.dedup_hit is True
        assert line.top_similarity == 0.93

    @pytest.mark.asyncio
    async def test_null_request_id_becomes_empty_string(self):
        row = _FakeRow(
            created_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
            tool_name="get_operational_predictions",
            status="ok",
            request_id="",  # NOT NULL DEFAULT '' per schema
        )
        payload = await ReceiptsService(_mock_db([row])).daily_receipt(HOTEL, TODAY)
        assert payload.lines[0].request_id == ""


class TestDateBoundaries:
    @pytest.mark.asyncio
    async def test_query_uses_utc_day_window(self):
        """Verify the WHERE clause covers the full UTC day for target_date."""
        db = _mock_db([])
        await ReceiptsService(db).daily_receipt(HOTEL, TODAY)
        # Inspect the executed SELECT — the .where() clauses are compiled
        # against AgentActionLog.created_at >= 2026-04-19T00:00:00+00:00 and
        # <= 2026-04-19T23:59:59.999999+00:00.
        assert db.execute.await_count == 1
        stmt = db.execute.await_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "agent_action_log" in compiled
        assert "hotel_id" in compiled
        assert "2026-04-19 00:00:00" in compiled
        assert "2026-04-19 23:59:59" in compiled
