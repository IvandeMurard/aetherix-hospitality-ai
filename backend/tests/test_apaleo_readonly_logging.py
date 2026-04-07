"""
Tests for HOS-107 — Apaleo read-only mode + agent action logging.

Coverage:
  - is_readonly_mode()  env var behaviour
  - is_write_tool()     known read/write tool classification
  - ApaleoAgentLogger   structured JSON output, mode labels, WARNING vs INFO
  - ApaleoMCPClient     write-guard blocks writes in readonly mode
  - ApaleoMCPClient     write-guard allows writes when APALEO_READONLY=false
  - ApaleoMCPClient     reads always pass through regardless of mode
  - ApaleoPMSAdapter    write-guard raises on update_staffing_in_pms (readonly)
  - ApaleoMCPAdapter    ApaleoWriteBlockedError is re-raised (not swallowed)
"""
from __future__ import annotations

import json
import logging
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.apaleo_logger import (
    WRITE_TOOLS,
    AgentActionRecord,
    ApaleoAgentLogger,
    ApaleoWriteBlockedError,
    is_readonly_mode,
    is_write_tool,
)
from app.integrations.apaleo_mcp_client import ApaleoMCPClient
from app.services.apaleo_adapter import ApaleoPMSAdapter
from app.services.apaleo_mcp_adapter import ApaleoMCPAdapter


# ===========================================================================
# is_readonly_mode
# ===========================================================================

class TestIsReadonlyMode:
    def test_readonly_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("APALEO_READONLY", raising=False)
        assert is_readonly_mode() is True

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes"])
    def test_readonly_for_truthy_values(
        self, value: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APALEO_READONLY", value)
        assert is_readonly_mode() is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no"])
    def test_writes_allowed_for_falsy_values(
        self, value: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APALEO_READONLY", value)
        assert is_readonly_mode() is False


# ===========================================================================
# is_write_tool
# ===========================================================================

class TestIsWriteTool:
    @pytest.mark.parametrize(
        "tool",
        [
            "APALEO_UPDATE_SCHEDULE",
            "APALEO_CREATES_A_PROPERTY",
            "APALEO_ARCHIVE_A_PROPERTY",
            "APALEO_CLONES_A_PROPERTY",
            "APALEO_MOVE_PROPERTY_TO_LIVE",
            "APALEO_RESET_PROPERTY_DATA",
            "APALEO_CREATE_A_UNIT",
            "APALEO_CREATE_MULTIPLE_UNITS",
            "APALEO_DELETE_A_UNIT",
            "APALEO_CREATE_A_UNIT_GROUP",
            "APALEO_REPLACE_A_UNIT_GROUP",
            "APALEO_DELETE_A_UNIT_GROUP",
            "REST_UPDATE_STAFFING",
        ],
    )
    def test_known_write_tools(self, tool: str) -> None:
        assert is_write_tool(tool) is True

    @pytest.mark.parametrize(
        "tool",
        [
            "APALEO_GET_A_PROPERTIES_LIST",
            "APALEO_GET_A_PROPERTY",
            "APALEO_GET_OCCUPANCY_METRICS",
            "APALEO_GET_REVENUE_METRICS",
            "APALEO_GET_RESERVATIONS",
            "APALEO_GET_A_UNITS_LIST",
            "REST_GET_OCCUPANCY",
            "REST_GET_REVENUE",
            "REST_GET_HISTORICAL_DATA",
        ],
    )
    def test_read_tools_are_not_write(self, tool: str) -> None:
        assert is_write_tool(tool) is False

    def test_write_tools_set_is_nonempty(self) -> None:
        assert len(WRITE_TOOLS) > 0


# ===========================================================================
# ApaleoAgentLogger
# ===========================================================================

class TestApaleoAgentLogger:
    def test_returns_agent_action_record(self) -> None:
        logger = ApaleoAgentLogger()
        record = logger.log("APALEO_GET_A_PROPERTIES_LIST", {})
        assert isinstance(record, AgentActionRecord)
        assert record.tool == "APALEO_GET_A_PROPERTIES_LIST"
        assert record.mode == "read"

    def test_read_logged_at_info(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="apaleo.agent_actions"):
            ApaleoAgentLogger().log("APALEO_GET_A_PROPERTIES_LIST", {}, mode="read")
        assert any("APALEO_AGENT_ACTION" in r.message for r in caplog.records)
        assert all(r.levelno == logging.INFO for r in caplog.records)

    def test_blocked_logged_at_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="apaleo.agent_actions"):
            ApaleoAgentLogger().log(
                "APALEO_UPDATE_SCHEDULE",
                {"propertyId": "MUC"},
                mode="blocked",
                error="read-only mode active",
            )
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_write_logged_at_info(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="apaleo.agent_actions"):
            ApaleoAgentLogger().log("APALEO_UPDATE_SCHEDULE", {}, mode="write")
        assert any(r.levelno == logging.INFO for r in caplog.records)

    def test_log_payload_is_valid_json(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="apaleo.agent_actions"):
            ApaleoAgentLogger().log(
                "APALEO_GET_OCCUPANCY_METRICS",
                {"propertyId": "MUC", "date": "2026-03-30"},
                user="aetherix-agent",
                mode="read",
                duration_ms=123.456,
                result_summary="85",
            )
        record = caplog.records[0]
        # Strip prefix "APALEO_AGENT_ACTION "
        json_part = record.message.split("APALEO_AGENT_ACTION ", 1)[1]
        data = json.loads(json_part)
        assert data["tool"] == "APALEO_GET_OCCUPANCY_METRICS"
        assert data["user"] == "aetherix-agent"
        assert data["mode"] == "read"
        assert data["duration_ms"] == 123.46
        assert data["result_summary"] == "85"

    def test_duration_rounded_to_2dp(self) -> None:
        record = ApaleoAgentLogger().log("T", {}, duration_ms=12.3456789)
        assert record.duration_ms == 12.35

    def test_none_duration_stays_none(self) -> None:
        record = ApaleoAgentLogger().log("T", {}, duration_ms=None)
        assert record.duration_ms is None

    def test_user_field_present_in_payload(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="apaleo.agent_actions"):
            ApaleoAgentLogger().log("T", {}, user="test-agent")
        json_part = caplog.records[0].message.split("APALEO_AGENT_ACTION ", 1)[1]
        assert json.loads(json_part)["user"] == "test-agent"

    def test_timestamp_is_iso8601(self) -> None:
        record = ApaleoAgentLogger().log("T", {})
        # Must be parseable as ISO-8601 with timezone
        from datetime import datetime
        dt = datetime.fromisoformat(record.timestamp)
        assert dt.tzinfo is not None


# ===========================================================================
# ApaleoMCPClient — write-guard
# ===========================================================================

class TestApaleoMCPClientWriteGuard:
    """
    Tests the write-guard before any MCP transport is opened.
    No network/MCP mocking needed — the guard fires before the session.
    """

    @pytest.fixture
    def configured_client(self) -> ApaleoMCPClient:
        return ApaleoMCPClient(
            server_url="https://mcp.example.com",
            auth_mode="bearer",
            client_id="id",
            client_secret="secret",
        )

    async def test_write_blocked_in_readonly_mode(
        self,
        configured_client: ApaleoMCPClient,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("APALEO_READONLY", "true")
        with pytest.raises(ApaleoWriteBlockedError, match="read-only mode"):
            await configured_client.call_tool("APALEO_UPDATE_SCHEDULE", {"propertyId": "MUC"})

    async def test_write_blocked_logs_warning(
        self,
        configured_client: ApaleoMCPClient,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("APALEO_READONLY", "true")
        with caplog.at_level(logging.WARNING, logger="apaleo.agent_actions"):
            with pytest.raises(ApaleoWriteBlockedError):
                await configured_client.call_tool("APALEO_UPDATE_SCHEDULE", {})
        assert any("blocked" in r.message for r in caplog.records)

    async def test_write_blocked_for_all_write_tools(
        self,
        configured_client: ApaleoMCPClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("APALEO_READONLY", "true")
        for tool in WRITE_TOOLS:
            if tool == "REST_UPDATE_STAFFING":
                continue  # REST sentinel — not an MCP tool name
            with pytest.raises(ApaleoWriteBlockedError):
                await configured_client.call_tool(tool, {})

    async def test_read_tool_not_blocked_in_readonly_mode(
        self,
        configured_client: ApaleoMCPClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Read tools must NOT raise — they should reach the transport layer."""
        monkeypatch.setenv("APALEO_READONLY", "true")
        # The guard should not fire for read tools; the error will come from
        # the transport (no real MCP server) — that's fine, it confirms the
        # guard was passed.
        with pytest.raises(Exception) as exc_info:
            await configured_client.call_tool("APALEO_GET_A_PROPERTIES_LIST", {})
        assert not isinstance(exc_info.value, ApaleoWriteBlockedError)

    async def test_write_allowed_when_readonly_false(
        self,
        configured_client: ApaleoMCPClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With APALEO_READONLY=false the guard must not fire."""
        monkeypatch.setenv("APALEO_READONLY", "false")
        # Guard passes; transport error expected (no real server)
        with pytest.raises(Exception) as exc_info:
            await configured_client.call_tool("APALEO_UPDATE_SCHEDULE", {})
        assert not isinstance(exc_info.value, ApaleoWriteBlockedError)

    async def test_unconfigured_client_raises_before_guard(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("APALEO_READONLY", "true")
        client = ApaleoMCPClient(server_url="", auth_mode="bearer")
        with pytest.raises(RuntimeError, match="not configured"):
            await client.call_tool("APALEO_UPDATE_SCHEDULE", {})

    async def test_user_param_forwarded_to_log(
        self,
        configured_client: ApaleoMCPClient,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("APALEO_READONLY", "true")
        with caplog.at_level(logging.WARNING, logger="apaleo.agent_actions"):
            with pytest.raises(ApaleoWriteBlockedError):
                await configured_client.call_tool(
                    "APALEO_UPDATE_SCHEDULE", {}, user="manager-42"
                )
        json_part = caplog.records[0].message.split("APALEO_AGENT_ACTION ", 1)[1]
        assert json.loads(json_part)["user"] == "manager-42"


# ===========================================================================
# ApaleoPMSAdapter — write-guard on REST update_staffing_in_pms
# ===========================================================================

class TestApaleoPMSAdapterWriteGuard:
    @pytest.fixture
    def adapter(self) -> ApaleoPMSAdapter:
        return ApaleoPMSAdapter(client_id="id", client_secret="secret")

    async def test_raises_write_blocked_in_readonly_mode(
        self,
        adapter: ApaleoPMSAdapter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("APALEO_READONLY", "true")
        with pytest.raises(ApaleoWriteBlockedError, match="read-only mode"):
            await adapter.update_staffing_in_pms(
                "MUC", date(2026, 3, 30), {"waiter": 2}
            )

    async def test_blocked_write_logs_warning(
        self,
        adapter: ApaleoPMSAdapter,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("APALEO_READONLY", "true")
        with caplog.at_level(logging.WARNING, logger="apaleo.agent_actions"):
            with pytest.raises(ApaleoWriteBlockedError):
                await adapter.update_staffing_in_pms("MUC", date(2026, 3, 30), {})
        assert any("blocked" in r.message for r in caplog.records)

    async def test_guard_fires_before_auth(
        self,
        adapter: ApaleoPMSAdapter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Write-guard must fire before any _authenticate() call."""
        monkeypatch.setenv("APALEO_READONLY", "true")
        adapter._authenticate = AsyncMock()  # type: ignore[method-assign]
        with pytest.raises(ApaleoWriteBlockedError):
            await adapter.update_staffing_in_pms("MUC", date(2026, 3, 30), {})
        adapter._authenticate.assert_not_awaited()

    async def test_write_proceeds_when_readonly_false(
        self,
        adapter: ApaleoPMSAdapter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When readonly=false the adapter must attempt the actual HTTP call."""
        monkeypatch.setenv("APALEO_READONLY", "false")
        adapter.access_token = "tok"
        adapter.token_expiry = float("inf")
        with patch("app.services.apaleo_adapter.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await adapter.update_staffing_in_pms(
                "MUC", date(2026, 3, 30), {"waiter": 1}
            )
        assert result is True


# ===========================================================================
# ApaleoMCPAdapter — ApaleoWriteBlockedError re-raised (not swallowed)
# ===========================================================================

class TestApaleoMCPAdapterWriteBlockedReraised:
    async def test_write_blocked_error_propagates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ApaleoMCPAdapter must not catch ApaleoWriteBlockedError — it must re-raise."""
        mock_client = MagicMock(spec=ApaleoMCPClient)
        mock_client.is_configured = True
        mock_client.call_tool = AsyncMock(
            side_effect=ApaleoWriteBlockedError("blocked")
        )
        adapter = ApaleoMCPAdapter(mcp_client=mock_client)
        with pytest.raises(ApaleoWriteBlockedError):
            await adapter.update_staffing_in_pms(
                "MUC", date(2026, 3, 30), {"waiter": 2}
            )

    async def test_generic_exception_returns_false(self) -> None:
        """Generic transport errors must still return False (existing contract)."""
        mock_client = MagicMock(spec=ApaleoMCPClient)
        mock_client.is_configured = True
        mock_client.call_tool = AsyncMock(side_effect=RuntimeError("network timeout"))
        adapter = ApaleoMCPAdapter(mcp_client=mock_client)
        result = await adapter.update_staffing_in_pms(
            "MUC", date(2026, 3, 30), {}
        )
        assert result is False
