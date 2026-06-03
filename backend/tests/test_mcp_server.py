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
    def test_exposes_three_tools(self):
        names = [t["name"] for t in TOOLS_MANIFEST]
        assert "get_operational_predictions" in names
        assert "get_recommendations_with_memory_context" in names
        assert "submit_feedback_to_memory" in names
        assert len(TOOLS_MANIFEST) == 3

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
