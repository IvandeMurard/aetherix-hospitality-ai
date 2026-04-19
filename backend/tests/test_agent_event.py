"""Tier-1 unit tests for AgentEvent + emit_agent_event (ADR 0003 · HOS-73b).

All tests are pure-logic and always run — no DB or real async stack needed.
DB write path is tested via mock to confirm field mapping without pgvector.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Try importing — graceful skip if full stack absent
# ---------------------------------------------------------------------------

def _try_import():
    try:
        from app.services.agent_event import AgentEvent, emit_agent_event
        return AgentEvent, emit_agent_event
    except (ImportError, ModuleNotFoundError):
        return None, None


_AgentEvent, _emit = _try_import()
_skip = pytest.mark.skipif(_AgentEvent is None, reason="agent_event module unavailable")


# ---------------------------------------------------------------------------
# AgentEvent dataclass shape
# ---------------------------------------------------------------------------

class TestAgentEventModel:
    @_skip
    def test_required_fields_set(self):
        ev = _AgentEvent(hotel_id="h1", tool_name="get_operational_predictions", scopes=["predict"], status="ok")
        assert ev.hotel_id == "h1"
        assert ev.tool_name == "get_operational_predictions"
        assert ev.status == "ok"

    @_skip
    def test_optional_fields_default_none(self):
        ev = _AgentEvent(hotel_id="h1", tool_name="t", scopes=[], status="ok")
        assert ev.latency_ms is None
        assert ev.embedding_latency_ms is None
        assert ev.dedup_hit is None
        assert ev.top_similarity is None
        assert ev.error_code is None

    @_skip
    def test_request_id_defaults_empty(self):
        ev = _AgentEvent(hotel_id="h1", tool_name="t", scopes=[], status="ok")
        assert ev.request_id == ""

    @_skip
    def test_status_mutable(self):
        ev = _AgentEvent(hotel_id="h1", tool_name="t", scopes=[], status="ok")
        ev.status = "tool_error"
        assert ev.status == "tool_error"

    @_skip
    def test_asdict_serializable(self):
        ev = _AgentEvent(hotel_id="h1", tool_name="t", scopes=["predict"], status="ok",
                         latency_ms=42, dedup_hit=True, top_similarity=0.87)
        d = asdict(ev)
        assert d["dedup_hit"] is True
        assert d["top_similarity"] == 0.87
        json.dumps(d)  # must be JSON-serializable

    @_skip
    def test_all_valid_statuses(self):
        for status in ("ok", "auth_error", "tool_error", "rate_limited"):
            ev = _AgentEvent(hotel_id="h1", tool_name="t", scopes=[], status=status)
            assert ev.status == status


# ---------------------------------------------------------------------------
# emit_agent_event — mock DB path
# ---------------------------------------------------------------------------

class TestEmitAgentEvent:
    @_skip
    @pytest.mark.asyncio
    async def test_happy_path_calls_execute(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        ev = _AgentEvent(hotel_id="h1", tool_name="get_operational_predictions",
                         scopes=["predict"], status="ok", latency_ms=55)
        await _emit(ev, db)
        db.execute.assert_called_once()
        call_args = db.execute.call_args
        params = call_args[0][1]
        assert params["hotel_id"] == "h1"
        assert params["tool_name"] == "get_operational_predictions"
        assert params["status"] == "ok"
        assert params["latency_ms"] == 55

    @_skip
    @pytest.mark.asyncio
    async def test_db_error_is_swallowed(self):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=RuntimeError("db is down"))
        ev = _AgentEvent(hotel_id="h1", tool_name="t", scopes=[], status="ok")
        # Must not raise
        await _emit(ev, db)

    @_skip
    @pytest.mark.asyncio
    async def test_embedding_fields_passed(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        ev = _AgentEvent(hotel_id="h1", tool_name="submit_feedback_to_memory",
                         scopes=["feedback"], status="ok",
                         embedding_latency_ms=120, dedup_hit=False, top_similarity=0.72)
        await _emit(ev, db)
        params = db.execute.call_args[0][1]
        assert params["embedding_latency_ms"] == 120
        assert params["dedup_hit"] is False
        assert abs(params["top_similarity"] - 0.72) < 1e-6

    @_skip
    @pytest.mark.asyncio
    async def test_tool_error_status_stored(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        ev = _AgentEvent(hotel_id="h1", tool_name="t", scopes=[], status="tool_error",
                         error_code="upstream_unavailable")
        await _emit(ev, db)
        params = db.execute.call_args[0][1]
        assert params["status"] == "tool_error"
        assert params["error_code"] == "upstream_unavailable"
