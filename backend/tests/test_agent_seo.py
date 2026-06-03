"""Unit tests for P1-5 Agent SEO — discovery manifest + tracking middleware (HOS-72).

Tier 1: pure-logic tests on the agent detection functions — always run,
        no HTTP client or full stack required.
Tier 2: integration tests that exercise the actual FastAPI app — skipped when
        the full stack (DB, providers) is unavailable.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers — try importing without raising
# ---------------------------------------------------------------------------

def _try_import_middleware():
    try:
        from app.middleware.agent_tracking import extract_agent_id, is_agent_request
        return is_agent_request, extract_agent_id
    except (ImportError, ModuleNotFoundError):
        return None, None


def _try_import_wellknown():
    try:
        from app.api.routes.wellknown import _AGENT_MANIFEST
        return _AGENT_MANIFEST
    except (ImportError, ModuleNotFoundError):
        return None


_is_agent, _extract_id = _try_import_middleware()
_manifest = _try_import_wellknown()

_skip_mw = pytest.mark.skipif(
    _is_agent is None, reason="agent_tracking middleware unavailable"
)
_skip_manifest = pytest.mark.skipif(
    _manifest is None, reason="wellknown route unavailable"
)


def _make_request(user_agent: str = "", headers: dict | None = None) -> MagicMock:
    """Build a minimal mock Starlette Request."""
    req = MagicMock()
    all_headers = {}
    if user_agent:
        all_headers["user-agent"] = user_agent
    if headers:
        all_headers.update(headers)

    def _get(key, default=""):
        return all_headers.get(key.lower(), default)

    req.headers.get.side_effect = _get
    req.url.path = "/api/v1/predictions/predict"
    return req


# ---------------------------------------------------------------------------
# Tier 1 — agent detection pure logic
# ---------------------------------------------------------------------------

class TestIsAgentRequest:
    @_skip_mw
    def test_mcp_client_ua_detected(self):
        req = _make_request(user_agent="mcp-client/1.0")
        assert _is_agent(req) is True

    @_skip_mw
    def test_claude_ua_detected(self):
        req = _make_request(user_agent="Claude/3.5")
        assert _is_agent(req) is True

    @_skip_mw
    def test_agent_ua_detected(self):
        req = _make_request(user_agent="my-custom-agent/2.0")
        assert _is_agent(req) is True

    @_skip_mw
    def test_ua_case_insensitive(self):
        req = _make_request(user_agent="MCP-CLIENT/0.9")
        assert _is_agent(req) is True

    @_skip_mw
    def test_plain_browser_not_detected(self):
        req = _make_request(user_agent="Mozilla/5.0 (Windows NT 10.0) Chrome/120")
        assert _is_agent(req) is False

    @_skip_mw
    def test_x_agent_id_header_detected(self):
        req = _make_request(headers={"x-agent-id": "agent-abc"})
        assert _is_agent(req) is True

    @_skip_mw
    def test_x_aetherix_mcp_version_header_detected(self):
        req = _make_request(headers={"x-aetherix-mcp-version": "0"})
        assert _is_agent(req) is True

    @_skip_mw
    def test_no_headers_not_detected(self):
        req = _make_request()
        assert _is_agent(req) is False

    @_skip_mw
    def test_curl_not_detected(self):
        req = _make_request(user_agent="curl/7.88.1")
        assert _is_agent(req) is False


class TestExtractAgentId:
    @_skip_mw
    def test_prefers_x_agent_id(self):
        req = _make_request(
            user_agent="claude/3.5",
            headers={"x-agent-id": "my-agent-123"},
        )
        assert _extract_id(req) == "my-agent-123"

    @_skip_mw
    def test_falls_back_to_mcp_version(self):
        req = _make_request(headers={"x-aetherix-mcp-version": "0"})
        assert _extract_id(req) == "mcp-v0"

    @_skip_mw
    def test_falls_back_to_ua(self):
        req = _make_request(user_agent="mcp-client/1.0")
        result = _extract_id(req)
        assert "mcp-client" in result

    @_skip_mw
    def test_returns_unknown_when_nothing(self):
        req = _make_request()
        assert _extract_id(req) == "unknown"

    @_skip_mw
    def test_ua_truncated_at_80_chars(self):
        long_ua = "mcp-client-" + "x" * 200
        req = _make_request(user_agent=long_ua)
        result = _extract_id(req)
        assert len(result) <= 80

    @_skip_mw
    def test_x_agent_id_truncated_at_80_chars(self):
        long_id = "agent-" + "y" * 200
        req = _make_request(headers={"x-agent-id": long_id})
        result = _extract_id(req)
        assert len(result) <= 80

    @_skip_mw
    def test_x_agent_id_control_chars_stripped(self):
        """Log-forging / PII hardening: CR/LF/NUL and C0 range stripped."""
        malicious = "agent-1\r\nFAKE LOG LINE\x00\x1b[31m"
        req = _make_request(headers={"x-agent-id": malicious})
        result = _extract_id(req)
        assert "\n" not in result
        assert "\r" not in result
        assert "\x00" not in result
        assert "\x1b" not in result


# ---------------------------------------------------------------------------
# Tier 1 — agent.json manifest shape
# ---------------------------------------------------------------------------

class TestAgentManifest:
    @_skip_manifest
    def test_has_required_top_level_keys(self):
        required = {"schema_version", "name", "version", "mcp_endpoint", "tools",
                    "auth_schemes", "rate_limits", "contact"}
        assert required.issubset(_manifest.keys())

    @_skip_manifest
    def test_exactly_three_tools(self):
        assert len(_manifest["tools"]) == 3

    @_skip_manifest
    def test_tool_names_match_mcp_core(self):
        names = {t["name"] for t in _manifest["tools"]}
        assert "get_operational_predictions" in names
        assert "get_recommendations_with_memory_context" in names
        assert "submit_feedback_to_memory" in names

    @_skip_manifest
    def test_mcp_endpoint_path(self):
        assert _manifest["mcp_endpoint"] == "/mcp/v0/"

    @_skip_manifest
    def test_agent_callable_endpoints_present(self):
        paths = {e["path"] for e in _manifest.get("agent_callable_endpoints", [])}
        assert "/api/v1/predictions/predict" in paths
        assert "/api/v1/roi/simulate" in paths
        assert "/mcp/v0/" in paths

    @_skip_manifest
    def test_agent_callable_flags(self):
        for ep in _manifest.get("agent_callable_endpoints", []):
            assert ep.get("x-agent-callable") is True
            assert ep.get("x-mcp-compatible") is True

    @_skip_manifest
    def test_rate_limits_cover_three_tools(self):
        rl = _manifest["rate_limits"]
        assert "get_operational_predictions" in rl
        assert "get_recommendations_with_memory_context" in rl
        assert "submit_feedback_to_memory" in rl

    @_skip_manifest
    def test_contact_has_email(self):
        assert "email" in _manifest["contact"]


# ---------------------------------------------------------------------------
# Tier 2 — HTTP integration (skipped when full stack unavailable)
# ---------------------------------------------------------------------------

def _try_import_test_client():
    try:
        from fastapi.testclient import TestClient

        from app.main import app
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        return None


_client = _try_import_test_client()
_skip_http = pytest.mark.skipif(_client is None, reason="full app stack unavailable")


class TestWellKnownHTTP:
    @_skip_http
    def test_agent_json_returns_200(self):
        resp = _client.get("/.well-known/agent.json")
        assert resp.status_code == 200

    @_skip_http
    def test_agent_json_content_type(self):
        resp = _client.get("/.well-known/agent.json")
        assert "application/json" in resp.headers.get("content-type", "")

    @_skip_http
    def test_agent_json_has_tools(self):
        resp = _client.get("/.well-known/agent.json")
        body = resp.json()
        assert len(body["tools"]) == 3
