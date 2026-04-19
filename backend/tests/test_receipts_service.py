"""Tier-1 tests for ReceiptsService.daily_receipt (P2-1 + P2-2).

Pure-mock tests — no DB, no asyncpg, run anywhere.
P2-1: grouping, counters, date-range semantics.
P2-2: memory_hits enrichment via request_id backlink (batch query).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.receipts import ReceiptsService, ReceiptPayload


# ---------------------------------------------------------------------------
# Fake ORM rows (no DB, no SQLAlchemy)
# ---------------------------------------------------------------------------

@dataclass
class _FakeLogRow:
    """Mimics AgentActionLog columns used by ReceiptsService."""
    created_at: datetime
    tool_name: str
    status: str
    request_id: str = ""
    latency_ms: int | None = None
    error_code: str | None = None
    dedup_hit: bool | None = None
    top_similarity: float | None = None


@dataclass
class _FakeMemRow:
    """Mimics OperationalMemory columns used by ReceiptsService._attach_memory_hits."""
    id: Any = field(default_factory=uuid.uuid4)
    request_id: str = ""
    reflection: str = ""
    manager_feedback: str | None = None
    memory_type: str = "feedback"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Mock DB factory — two sequential execute results (log rows + memory rows)
# ---------------------------------------------------------------------------

def _make_result(rows):
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=rows)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    return result


def _mock_db(log_rows: list, mem_rows: list | None = None) -> Any:
    """Return an AsyncSession mock.

    First execute() → log_rows (AgentActionLog query).
    Second execute() → mem_rows (OperationalMemory enrichment query, P2-2).
    """
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        _make_result(log_rows),
        _make_result(mem_rows or []),
    ])
    return db


HOTEL = "hotel_demo"
TODAY = date(2026, 4, 19)
TS = lambda h: datetime(2026, 4, 19, h, 0, tzinfo=timezone.utc)  # noqa: E731


# ---------------------------------------------------------------------------
# P2-1: empty log
# ---------------------------------------------------------------------------

class TestEmptyLog:
    @pytest.mark.asyncio
    async def test_no_rows_returns_zero_total(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_make_result([]))
        payload = await ReceiptsService(db).daily_receipt(HOTEL, TODAY)
        assert isinstance(payload, ReceiptPayload)
        assert payload.total_actions == 0
        assert payload.lines == []
        assert payload.counts_by_status == {}
        assert payload.counts_by_tool == {}

    @pytest.mark.asyncio
    async def test_no_rows_keeps_hotel_id_and_date(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_make_result([]))
        payload = await ReceiptsService(db).daily_receipt(HOTEL, TODAY)
        assert payload.hotel_id == HOTEL
        assert payload.receipt_date == TODAY


# ---------------------------------------------------------------------------
# P2-1: counters
# ---------------------------------------------------------------------------

class TestCounters:
    @pytest.mark.asyncio
    async def test_groups_by_status(self):
        log_rows = [
            _FakeLogRow(TS(8), "get_operational_predictions", "ok", "rid-1", 120),
            _FakeLogRow(TS(9), "get_operational_predictions", "ok", "rid-2", 110),
            _FakeLogRow(TS(10), "submit_feedback_to_memory", "auth_error", "rid-3"),
            _FakeLogRow(TS(11), "submit_feedback_to_memory", "rate_limited", "rid-4"),
        ]
        payload = await ReceiptsService(_mock_db(log_rows)).daily_receipt(HOTEL, TODAY)
        assert payload.total_actions == 4
        assert payload.counts_by_status == {
            "ok": 2, "auth_error": 1, "rate_limited": 1,
        }

    @pytest.mark.asyncio
    async def test_groups_by_tool(self):
        log_rows = [
            _FakeLogRow(TS(8), "get_operational_predictions", "ok", "rid-1"),
            _FakeLogRow(TS(9), "get_operational_predictions", "ok", "rid-2"),
            _FakeLogRow(TS(10), "submit_feedback_to_memory", "ok", "rid-3"),
        ]
        payload = await ReceiptsService(_mock_db(log_rows)).daily_receipt(HOTEL, TODAY)
        assert payload.counts_by_tool == {
            "get_operational_predictions": 2,
            "submit_feedback_to_memory": 1,
        }


# ---------------------------------------------------------------------------
# P2-1: line-field mapping
# ---------------------------------------------------------------------------

class TestLineMapping:
    @pytest.mark.asyncio
    async def test_line_fields_copied_from_row(self):
        ts = datetime(2026, 4, 19, 14, 30, tzinfo=timezone.utc)
        row = _FakeLogRow(
            created_at=ts, tool_name="submit_feedback_to_memory",
            status="ok", request_id="abc-123", latency_ms=87,
            dedup_hit=True, top_similarity=0.93,
        )
        payload = await ReceiptsService(_mock_db([row])).daily_receipt(HOTEL, TODAY)
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
        row = _FakeLogRow(TS(10), "get_operational_predictions", "ok", request_id="")
        payload = await ReceiptsService(_mock_db([row])).daily_receipt(HOTEL, TODAY)
        assert payload.lines[0].request_id == ""


# ---------------------------------------------------------------------------
# P2-2: memory_hits enrichment
# ---------------------------------------------------------------------------

class TestMemoryHitsEnrichment:
    @pytest.mark.asyncio
    async def test_memory_hit_attached_to_matching_line(self):
        rid = "req-abc"
        mem_id = uuid.uuid4()
        log_rows = [_FakeLogRow(TS(10), "submit_feedback_to_memory", "ok", rid)]
        mem_rows = [
            _FakeMemRow(
                id=mem_id, request_id=rid,
                reflection="[rec=xxx] outcome=accepted notes=great",
                manager_feedback="followed", memory_type="feedback",
                created_at=TS(10),
            )
        ]
        payload = await ReceiptsService(_mock_db(log_rows, mem_rows)).daily_receipt(HOTEL, TODAY)
        line = payload.lines[0]
        assert len(line.memory_hits) == 1
        hit = line.memory_hits[0]
        assert hit.memory_id == str(mem_id)
        assert hit.manager_feedback == "followed"
        assert hit.memory_type == "feedback"
        assert "accepted" in hit.reflection_snippet

    @pytest.mark.asyncio
    async def test_no_memory_hit_when_request_id_empty(self):
        log_rows = [_FakeLogRow(TS(8), "get_operational_predictions", "ok", request_id="")]
        # Second execute never called (no request_ids to batch)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_make_result(log_rows))
        payload = await ReceiptsService(db).daily_receipt(HOTEL, TODAY)
        assert payload.lines[0].memory_hits == []
        # Only one execute call (log query); no memory query issued
        assert db.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_multiple_hits_on_same_line(self):
        rid = "req-multi"
        log_rows = [_FakeLogRow(TS(9), "submit_feedback_to_memory", "ok", rid)]
        mem_rows = [
            _FakeMemRow(id=uuid.uuid4(), request_id=rid, reflection="first"),
            _FakeMemRow(id=uuid.uuid4(), request_id=rid, reflection="second"),
        ]
        payload = await ReceiptsService(_mock_db(log_rows, mem_rows)).daily_receipt(HOTEL, TODAY)
        assert len(payload.lines[0].memory_hits) == 2

    @pytest.mark.asyncio
    async def test_hits_routed_to_correct_line(self):
        rid_a, rid_b = "req-A", "req-B"
        log_rows = [
            _FakeLogRow(TS(8), "submit_feedback_to_memory", "ok", rid_a),
            _FakeLogRow(TS(9), "submit_feedback_to_memory", "ok", rid_b),
        ]
        mem_a_id = uuid.uuid4()
        mem_b_id = uuid.uuid4()
        mem_rows = [
            _FakeMemRow(id=mem_a_id, request_id=rid_a, reflection="for A"),
            _FakeMemRow(id=mem_b_id, request_id=rid_b, reflection="for B"),
        ]
        payload = await ReceiptsService(_mock_db(log_rows, mem_rows)).daily_receipt(HOTEL, TODAY)
        hits_a = payload.lines[0].memory_hits
        hits_b = payload.lines[1].memory_hits
        assert len(hits_a) == 1 and hits_a[0].memory_id == str(mem_a_id)
        assert len(hits_b) == 1 and hits_b[0].memory_id == str(mem_b_id)

    @pytest.mark.asyncio
    async def test_reflection_snippet_capped_at_200(self):
        rid = "req-long"
        long_reflection = "x" * 300
        log_rows = [_FakeLogRow(TS(10), "submit_feedback_to_memory", "ok", rid)]
        mem_rows = [_FakeMemRow(id=uuid.uuid4(), request_id=rid, reflection=long_reflection)]
        payload = await ReceiptsService(_mock_db(log_rows, mem_rows)).daily_receipt(HOTEL, TODAY)
        assert len(payload.lines[0].memory_hits[0].reflection_snippet) == 200

    @pytest.mark.asyncio
    async def test_non_matching_memory_rows_not_attached(self):
        rid_log = "req-used"
        rid_other = "req-other"
        log_rows = [_FakeLogRow(TS(10), "submit_feedback_to_memory", "ok", rid_log)]
        # memory row has a DIFFERENT request_id — should not be attached
        mem_rows = [_FakeMemRow(id=uuid.uuid4(), request_id=rid_other, reflection="orphan")]
        payload = await ReceiptsService(_mock_db(log_rows, mem_rows)).daily_receipt(HOTEL, TODAY)
        assert payload.lines[0].memory_hits == []


# ---------------------------------------------------------------------------
# P2-1: date boundaries
# ---------------------------------------------------------------------------

class TestDateBoundaries:
    @pytest.mark.asyncio
    async def test_query_uses_utc_day_window(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_make_result([]))
        await ReceiptsService(db).daily_receipt(HOTEL, TODAY)
        stmt = db.execute.await_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "agent_action_log" in compiled
        assert "hotel_id" in compiled
        assert "2026-04-19 00:00:00" in compiled
        assert "2026-04-19 23:59:59" in compiled
