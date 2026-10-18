"""
Tests for ApaleoMCPAdapter and ApaleoMCPClient.

These tests mock the MCP transport layer so no live server is required.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.apaleo_mcp_client import ApaleoMCPClient
from app.providers.pms.base import PMSDataStatus
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
# ApaleoMCPAdapter — occupancy and F&B revenue (HOS-352: true or absent)
# ---------------------------------------------------------------------------

PERFORMANCE = {"data": {
    "houseCount": 100, "soldCount": 75, "outOfOrderCount": 0,
    "netFoodAndBeveragesRevenue": {"amount": 5200.0, "currency": "EUR"},
    "netAccommodationRevenue": {"amount": 12000.0, "currency": "EUR"},
}}


class TestFetchOccupancy:
    async def test_returns_rooms_from_mcp(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = PERFORMANCE
        occ = await adapter.fetch_occupancy("MUC", date(2026, 3, 29))
        assert (occ.status, occ.rooms_sold, occ.rooms_available, occ.rate) == (PMSDataStatus.OK, 75, 100, 0.75)
        mock_mcp_client.call_tool.assert_awaited_once_with(
            "ListPropertyPerformanceReport",
            {"property_id": "MUC", "from_": "2026-03-29", "to": "2026-03-29"},
        )

    async def test_mcp_error_is_absent_not_80(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.side_effect = RuntimeError("MCP unreachable")
        occ = await adapter.fetch_occupancy("MUC", date(2026, 3, 29))
        assert occ.status == PMSDataStatus.PMS_ERROR and occ.rooms_sold is None

    async def test_http_error_payload_is_a_pms_error(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        """The MCP server returns Apaleo's HTTP errors as a payload (seen: 422)."""
        mock_mcp_client.call_tool.return_value = {"message": "To must be greater than From", "status_code": 422}
        occ = await adapter.fetch_occupancy("MUC", date(2026, 3, 29))
        assert occ.status == PMSDataStatus.PMS_ERROR and "422" in occ.detail

    async def test_not_configured_is_absent(
        self, unconfigured_adapter: ApaleoMCPAdapter
    ) -> None:
        occ = await unconfigured_adapter.fetch_occupancy("MUC", date(2026, 3, 29))
        assert occ.status == PMSDataStatus.NOT_CONFIGURED and occ.rooms_sold is None

    async def test_empty_house_is_no_data(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = {"data": {"houseCount": 0, "soldCount": 0}}
        occ = await adapter.fetch_occupancy("MUC", date(2026, 3, 29))
        assert occ.status == PMSDataStatus.NO_DATA


class TestFetchFbRevenue:
    async def test_returns_net_fb_revenue(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = PERFORMANCE
        rev = await adapter.fetch_fb_revenue("MUC", date(2026, 3, 29))
        assert (rev.status, rev.amount, rev.currency) == (PMSDataStatus.OK, 5200.0, "EUR")

    async def test_never_falls_back_to_another_revenue_line(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.return_value = {"data": {
            "houseCount": 100, "soldCount": 75,
            "netAccommodationRevenue": {"amount": 12000.0, "currency": "EUR"},
            "grossAmount": {"amount": 20000.0, "currency": "EUR"},
        }}
        rev = await adapter.fetch_fb_revenue("MUC", date(2026, 3, 29))
        assert rev.status == PMSDataStatus.NO_DATA and rev.amount is None

    async def test_error_is_absent_not_zero(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        mock_mcp_client.call_tool.side_effect = Exception("timeout")
        rev = await adapter.fetch_fb_revenue("MUC", date(2026, 3, 29))
        assert rev.status == PMSDataStatus.PMS_ERROR and rev.amount is None

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
    async def test_always_returns_false(
        self, adapter: ApaleoMCPAdapter, mock_mcp_client: MagicMock
    ) -> None:
        # Apaleo MCP has no staffing/schedule update tool — always returns False.
        result = await adapter.update_staffing_in_pms(
            "MUC", date(2026, 3, 29), {"waiter": 2, "chef": 1}
        )
        assert result is False
        mock_mcp_client.call_tool.assert_not_awaited()

    async def test_returns_false_when_not_configured(
        self, unconfigured_adapter: ApaleoMCPAdapter
    ) -> None:
        result = await unconfigured_adapter.update_staffing_in_pms(
            "MUC", date(2026, 3, 29), {}
        )
        assert result is False
