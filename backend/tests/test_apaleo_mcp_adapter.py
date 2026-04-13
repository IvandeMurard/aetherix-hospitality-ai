"""
Tests for ApaleoMCPAdapter and ApaleoMCPClient.

These tests mock the MCP transport layer so no live server is required.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.apaleo_mcp_client import ApaleoMCPClient
from app.services.apaleo_mcp_adapter import ApaleoMCPAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_mcp_client() -> MagicMock:
    """Return a fully-mocked ApaleoMCPClient with is_configured=True."""
    client = MagicMock(spec=ApaleoMCPClient)
    client.is_configured = True
    client.call_tool = AsyncMock()
    return client


@pytest.fixture
def adapter(mock_mcp_client: MagicMock) -> ApaleoMCPAdapter:
    return ApaleoMCPAdapter(mcp_client=mock_mcp_client)


@pytest.fixture
def unconfigured_adapter() -> ApaleoMCPAdapter:
    client = MagicMock(spec=ApaleoMCPClient)
    client.is_configured = False
    return ApaleoMCPAdapter(mcp_client=client)


# ---------------------------------------------------------------------------
# ApaleoMCPClient unit tests
# ---------------------------------------------------------------------------

class TestApaleoMCPClientIsConfigured:
    def test_true_when_all_set(self) -> None:
        c = ApaleoMCPClient("id", "secret", "https://mcp.example.com")
        assert c.is_configured is True

    def test_false_when_missing_secret(self) -> None:
        c = ApaleoMCPClient("id", "", "https://mcp.example.com")
        assert c.is_configured is False

    def test_false_when_missing_url(self) -> None:
        c = ApaleoMCPClient("id", "secret", "")
        assert c.is_configured is False


class TestApaleoMCPClientCallTool:
    async def test_raises_when_not_configured(self) -> None:
        client = ApaleoMCPClient("", "", "")
        with pytest.raises(RuntimeError, match="not configured"):
            await client.call_tool("some_tool", {})

    async def test_json_response_is_parsed(self) -> None:
        """call_tool should decode JSON text blocks automatically."""
        client = ApaleoMCPClient("id", "secret", "https://mcp.example.com")

        # Fake MCP result with a JSON text block
        fake_content = MagicMock()
        fake_content.type = "text"
        fake_content.text = '{"occupancy": 85}'
        fake_result = MagicMock()
        fake_result.content = [fake_content]

        with (
            patch("app.integrations.apaleo_mcp_client.ApaleoMCPClient._get_token",
                  new_callable=AsyncMock, return_value="tok"),
            patch("app.integrations.apaleo_mcp_client.streamablehttp_client") as mock_transport,
            patch("app.integrations.apaleo_mcp_client.ClientSession") as mock_session_cls,
        ):
            # Wire the context-manager chain
            mock_session = AsyncMock()
            mock_session.initialize = AsyncMock()
            mock_session.call_tool = AsyncMock(return_value=fake_result)
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_transport.return_value.__aenter__ = AsyncMock(
                return_value=("r", "w", lambda: None)
            )
            mock_transport.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.call_tool("apaleo_get_occupancy_metrics",
                                            {"propertyId": "MUC", "date": "2026-03-29"})

        assert result == {"occupancy": 85}


# ---------------------------------------------------------------------------
# ApaleoMCPAdapter — get_occupancy
# ---------------------------------------------------------------------------

class TestGetOccupancy:
    async def test_returns_value_from_mcp(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = {"occupancyPercent": 75}
        result = await adapter.get_occupancy("MUC", date(2026, 3, 29))
        assert result == 75
        mock_mcp_client.call_tool.assert_awaited_once_with(
            "APALEO_GET_OCCUPANCY_METRICS",
            {"propertyId": "MUC", "date": "2026-03-29"},
        )

    async def test_falls_back_on_mcp_error(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.side_effect = RuntimeError("MCP unreachable")
        result = await adapter.get_occupancy("MUC", date(2026, 3, 29))
        assert result == 80  # safe default

    async def test_returns_mock_when_not_configured(
        self, unconfigured_adapter: ApaleoMCPAdapter
    ) -> None:
        result = await unconfigured_adapter.get_occupancy("MUC", date(2026, 3, 29))
        assert result == 80


# ---------------------------------------------------------------------------
# ApaleoMCPAdapter — get_revenue
# ---------------------------------------------------------------------------

class TestGetRevenue:
    async def test_returns_matching_category_sum(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = {
            "revenue": [
                {"category": "F&B", "amount": 1200.0},
                {"category": "Rooms", "amount": 4000.0},
            ]
        }
        result = await adapter.get_revenue("MUC", date(2026, 3, 29), "F&B")
        assert result == 1200.0

    async def test_sums_all_when_no_category_match(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = {
            "revenue": [
                {"category": "Rooms", "amount": 3000.0},
                {"category": "Spa", "amount": 500.0},
            ]
        }
        result = await adapter.get_revenue("MUC", date(2026, 3, 29), "F&B")
        assert result == 3500.0  # no F&B match → sum all

    async def test_uses_totalRevenue_fallback(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = {"totalRevenue": 9999.0}
        result = await adapter.get_revenue("MUC", date(2026, 3, 29))
        assert result == 9999.0

    async def test_returns_zero_on_error(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.side_effect = Exception("timeout")
        result = await adapter.get_revenue("MUC", date(2026, 3, 29))
        assert result == 0.0


# ---------------------------------------------------------------------------
# ApaleoMCPAdapter — get_historical_data
# ---------------------------------------------------------------------------

class TestGetHistoricalData:
    async def test_returns_reservations_list(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = {
            "reservations": [{"id": "R1"}, {"id": "R2"}]
        }
        result = await adapter.get_historical_data(
            "MUC", date(2026, 1, 1), date(2026, 1, 31)
        )
        assert len(result) == 2
        assert result[0]["id"] == "R1"

    async def test_handles_bare_list_response(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = [{"id": "R1"}]
        result = await adapter.get_historical_data(
            "MUC", date(2026, 1, 1), date(2026, 1, 31)
        )
        assert result == [{"id": "R1"}]

    async def test_returns_empty_on_error(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.side_effect = Exception("network error")
        result = await adapter.get_historical_data(
            "MUC", date(2026, 1, 1), date(2026, 1, 31)
        )
        assert result == []


# ---------------------------------------------------------------------------
# ApaleoMCPAdapter — update_staffing_in_pms
# ---------------------------------------------------------------------------

class TestUpdateStaffingInPms:
    async def test_returns_true_on_success(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = {"success": True}
        result = await adapter.update_staffing_in_pms(
            "MUC", date(2026, 3, 29), {"waiter": 2, "chef": 1}
        )
        assert result is True
        mock_mcp_client.call_tool.assert_awaited_once_with(
            "APALEO_UPDATE_SCHEDULE",
            {
                "propertyId": "MUC",
                "date": "2026-03-29",
                "deltas": {"waiter": 2, "chef": 1},
                "source": "Aetherix-AI",
            },
        )

    async def test_accepts_status_ok(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = {"status": "ok"}
        assert await adapter.update_staffing_in_pms("MUC", date(2026, 3, 29), {}) is True

    async def test_returns_false_on_error(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.side_effect = Exception("network error")
        result = await adapter.update_staffing_in_pms("MUC", date(2026, 3, 29), {})
        assert result is False

    async def test_skips_when_not_configured(
        self, unconfigured_adapter: ApaleoMCPAdapter
    ) -> None:
        result = await unconfigured_adapter.update_staffing_in_pms(
            "MUC", date(2026, 3, 29), {}
        )
        assert result is False
