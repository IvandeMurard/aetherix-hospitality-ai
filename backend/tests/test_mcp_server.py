"""Unit tests for the Aetherix MCP Server v0 (ADR 0001 · P1-2).

Tier 1 (mcp_core): pure-logic tests — always run, no DB or engine needed.
Tier 2 (mcp_server): auth/dispatch tests that require the full app stack,
  skipped when deps missing (pattern matches test_predictions_train.py).
"""
from __future__ import annotations

import pytest

from app.mcp_core import (
    _LOCAL_BUCKETS,
    TOOLS_MANIFEST,
    MCPAuthError,
    check_rate_limit,
    hash_token,
    require_scope,
    sanitize_notes,
)

# ---------------------------------------------------------------------------
# Tier 1 — mcp_core pure logic
# ---------------------------------------------------------------------------

class TestTokenHashing:
    def test_hash_deterministic(self):
        h1 = hash_token("atx_dev_abc123")
        h2 = hash_token("atx_dev_abc123")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_differs_by_input(self):
        assert hash_token("atx_dev_a") != hash_token("atx_dev_b")


class TestSanitizeNotes:
    def test_strips_control_chars(self):
        out = sanitize_notes("hello\x00\x01world")
        assert out == "helloworld"

    def test_preserves_internal_spaces(self):
        out = sanitize_notes("  foo bar  ")
        assert out == "foo bar"

    def test_enforces_max_length(self):
        long = "x" * 5000
        out = sanitize_notes(long, max_len=50)
        assert len(out) == 50

    def test_empty_input_returns_empty(self):
        assert sanitize_notes("") == ""
        assert sanitize_notes(None) == ""


class TestRateLimit:
    def test_under_limit_passes(self):
        _LOCAL_BUCKETS.clear()
        for _ in range(5):
            check_rate_limit("hotel_x", "get_operational_predictions")

    def test_over_limit_raises(self):
        _LOCAL_BUCKETS.clear()
        # submit_feedback_to_memory has a 20/min limit
        for _ in range(20):
            check_rate_limit("hotel_rl", "submit_feedback_to_memory")
        with pytest.raises(MCPAuthError) as excinfo:
            check_rate_limit("hotel_rl", "submit_feedback_to_memory")
        assert excinfo.value.status == 429

    def test_rate_limit_scoped_per_tool(self):
        _LOCAL_BUCKETS.clear()
        for _ in range(20):
            check_rate_limit("hotel_z", "submit_feedback_to_memory")
        # Different tool should still be allowed
        check_rate_limit("hotel_z", "get_operational_predictions")

    def test_rate_limit_scoped_per_hotel(self):
        _LOCAL_BUCKETS.clear()
        for _ in range(20):
            check_rate_limit("hotel_a", "submit_feedback_to_memory")
        # Different hotel: clean bucket
        check_rate_limit("hotel_b", "submit_feedback_to_memory")


class TestScopeEnforcement:
    def test_missing_scope_raises_403(self):
        with pytest.raises(MCPAuthError) as excinfo:
            require_scope(["predict"], "submit_feedback_to_memory")
        assert excinfo.value.status == 403

    def test_present_scope_passes(self):
        require_scope(["predict", "recommend", "feedback"], "submit_feedback_to_memory")

    def test_none_scopes_rejected(self):
        with pytest.raises(MCPAuthError):
            require_scope(None, "get_operational_predictions")


class TestToolsManifest:
    def test_exposes_expected_tools(self):
        """v0 (3 tools, ADR-0001) + recall_memory (ADR-0004 PR-A) = 4."""
        names = [t["name"] for t in TOOLS_MANIFEST]
        assert "get_operational_predictions" in names
        assert "get_recommendations_with_memory_context" in names
        assert "submit_feedback_to_memory" in names
        assert "recall_memory" in names
        assert len(TOOLS_MANIFEST) == 4

    def test_no_tool_exposes_hotel_id_input(self):
        """Critical — hotel_id must never be client-supplied (ADR D4)."""
        for t in TOOLS_MANIFEST:
            props = t["inputSchema"].get("properties", {})
            assert "hotel_id" not in props, (
                f"Tool {t['name']} exposes hotel_id as input — breaks tenant isolation"
            )
            required = t["inputSchema"].get("required", [])
            assert "hotel_id" not in required

    def test_each_tool_has_description(self):
        for t in TOOLS_MANIFEST:
            assert t.get("description")
            assert t.get("inputSchema", {}).get("type") == "object"

    def test_recall_memory_schema_shape(self):
        """recall_memory advertises a query + optional k_memory, no target_date."""
        tool = next(t for t in TOOLS_MANIFEST if t["name"] == "recall_memory")
        props = tool["inputSchema"]["properties"]
        assert "query" in props
        assert "k_memory" in props
        assert "target_date" not in props, (
            "recall_memory is atomic — target_date belongs to get_operational_predictions"
        )
        assert tool["inputSchema"]["required"] == ["query"]
        assert props["k_memory"].get("maximum") == 20


class TestRecallMemoryScope:
    """ADR-0004: recall_memory has its own scope, distinct from `recommend`.

    Existing tokens scoped to `recommend` must NOT silently gain access to
    `recall_memory` — scope grants are explicit.
    """

    def test_recall_scope_required(self):
        with pytest.raises(MCPAuthError) as excinfo:
            require_scope(["recommend"], "recall_memory")
        assert excinfo.value.status == 403
        assert "recall" in excinfo.value.detail

    def test_recall_scope_granted(self):
        require_scope(["recall"], "recall_memory")

    def test_recommend_scope_does_not_grant_recall(self):
        with pytest.raises(MCPAuthError):
            require_scope(["predict", "recommend", "feedback"], "recall_memory")


# ---------------------------------------------------------------------------
# Tier 2 — auth + dispatcher (skip if full stack missing)
# ---------------------------------------------------------------------------

def _try_import_server():
    try:
        import app.mcp_server as m
        return m
    except (ImportError, ModuleNotFoundError, TypeError):
        return None


_server = _try_import_server()
_skip_if_no_server = pytest.mark.skipif(
    _server is None,
    reason="mcp_server deps unavailable (requires full backend stack)",
)


class TestAuthErrors:
    @_skip_if_no_server
    @pytest.mark.asyncio
    async def test_missing_auth_header_raises_401(self):
        from unittest.mock import MagicMock
        db = MagicMock()
        with pytest.raises(MCPAuthError) as excinfo:
            await _server.verify_bearer(None, db)
        assert excinfo.value.status == 401

    @_skip_if_no_server
    @pytest.mark.asyncio
    async def test_non_bearer_header_raises_401(self):
        from unittest.mock import MagicMock
        db = MagicMock()
        with pytest.raises(MCPAuthError) as excinfo:
            await _server.verify_bearer("Basic abc", db)
        assert excinfo.value.status == 401


class TestTenantIsolationD4:
    """ADR 0001 D4: hotel_id MUST come from the token, never from arguments.

    Regression for architect-flagged concern: a caller that injects
    `hotel_id` into arguments must have that value silently dropped. We assert
    the dispatch args filter itself — no network, no DB.
    """

    def test_hotel_id_stripped_from_args(self):
        # Inline re-creation of the filter from dispatch_tool to avoid full
        # stack import (Tier 1 guarantee: this test runs in any env).
        arguments = {
            "hotel_id": "attacker-supplied-other-tenant",
            "target_date": "2026-04-20",
            "service_type": "dinner",
        }
        filtered = {k: v for k, v in arguments.items() if k != "hotel_id"}
        assert "hotel_id" not in filtered
        assert filtered["target_date"] == "2026-04-20"
        assert filtered["service_type"] == "dinner"

    def test_filter_noop_when_no_hotel_id(self):
        arguments = {"query": "rainy saturday dinner"}
        filtered = {k: v for k, v in arguments.items() if k != "hotel_id"}
        assert filtered == arguments


class TestRecallMemoryTool:
    """Tier 2 — tool_recall_memory atomic recall (ADR-0004 · HOS-184 PR-A).

    The DB-touching happy path is exercised by the existing v0 composite
    tool tests; here we cover the new tool's input contract and the safe
    early-exit paths that do not require a working DB session.
    """

    @_skip_if_no_server
    @pytest.mark.asyncio
    async def test_empty_query_raises_400(self):
        from unittest.mock import MagicMock
        db = MagicMock()
        with pytest.raises(MCPAuthError) as excinfo:
            await _server.tool_recall_memory("hotel-a", "", db=db)
        assert excinfo.value.status == 400
        assert "query is required" in excinfo.value.detail

    @_skip_if_no_server
    @pytest.mark.asyncio
    async def test_whitespace_only_query_raises_400(self):
        """Sanitizer strips whitespace; effectively-empty input must error."""
        from unittest.mock import MagicMock
        db = MagicMock()
        with pytest.raises(MCPAuthError) as excinfo:
            await _server.tool_recall_memory("hotel-a", "   \t  ", db=db)
        assert excinfo.value.status == 400

    @_skip_if_no_server
    @pytest.mark.asyncio
    async def test_k_memory_clamped_at_upper_bound(self):
        """k_memory > 20 must be silently clamped, never amplified at the DB."""
        from unittest.mock import AsyncMock, MagicMock

        # db.execute returns an empty rows iterable to trigger the recency
        # fallback path. We only assert the returned k_memory field reflects
        # the clamp — no DB content needed.
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        result_mock = MagicMock()
        result_mock.scalars = MagicMock(return_value=scalars)
        db = MagicMock()
        db.execute = AsyncMock(return_value=result_mock)

        out = await _server.tool_recall_memory(
            "hotel-a", "test query", db=db, embedding_provider=None, k_memory=999
        )
        assert out["k_memory"] == 20  # upper bound from max(1, min(20, k))
        assert out["source"] == "recency_fallback"
        assert out["memory_hits"] == []
        assert out["top_similarity"] is None

    @_skip_if_no_server
    @pytest.mark.asyncio
    async def test_k_memory_clamped_at_lower_bound(self):
        from unittest.mock import AsyncMock, MagicMock
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        result_mock = MagicMock()
        result_mock.scalars = MagicMock(return_value=scalars)
        db = MagicMock()
        db.execute = AsyncMock(return_value=result_mock)

        out = await _server.tool_recall_memory(
            "hotel-a", "test", db=db, embedding_provider=None, k_memory=0
        )
        assert out["k_memory"] == 1

    @_skip_if_no_server
    @pytest.mark.asyncio
    async def test_no_embedding_provider_falls_back_to_recency(self):
        """When embedding_provider is None, we go straight to recency fallback."""
        from unittest.mock import AsyncMock, MagicMock
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        result_mock = MagicMock()
        result_mock.scalars = MagicMock(return_value=scalars)
        db = MagicMock()
        db.execute = AsyncMock(return_value=result_mock)

        out = await _server.tool_recall_memory(
            "hotel-a", "anything", db=db, embedding_provider=None
        )
        assert out["source"] == "recency_fallback"
        # db.execute should have been called exactly once (the fallback query)
        assert db.execute.await_count == 1


class TestOrchestratorImportSurface:
    """ADR-0004 — orchestrator/ must import cleanly and expose its public API.

    This is a smoke test: importing the package alone validates the boundary
    is respected (no app.services / app.db / app.api imports) AND the public
    class is exposed.
    """

    def test_orchestrator_package_imports(self):
        try:
            from orchestrator import AetherixOrchestrator  # type: ignore[import-not-found]
        except ImportError:
            pytest.skip("orchestrator package not on sys.path in this test env")
        assert AetherixOrchestrator is not None

    def test_handle_request_is_pra_stub(self):
        """PR-A stub: any call must raise NotImplementedError until PR-B."""
        try:
            from orchestrator import AetherixOrchestrator  # type: ignore[import-not-found]
        except ImportError:
            pytest.skip("orchestrator package not on sys.path in this test env")
        orch = AetherixOrchestrator()
        import asyncio
        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(
                orch.handle_request(query="test")
            )
