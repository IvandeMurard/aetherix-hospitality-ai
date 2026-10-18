"""Tests for ApaleoPMSAdapter — HOS-131 acceptance criteria, HOS-352 contract.

Coverage (REST adapter, not MCP adapter):
- AC2: get_historical_data() pagination — fetches all pages
- HOS-352: occupancy and F&B revenue come from the property-performance
  report; a non-200 is an absent figure with status ``pms_error``, never a
  raised error that leaves no row, nor a default
- AC3: get_historical_data() raises ApaleoSyncError on non-200
- AC5: _authenticate() retry on HTTPStatusError (tenacity)
- Data quality: a missing count is absent, never 0 nor the old sentinel 85
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.providers.pms.base import PMSDataStatus
from app.services.apaleo_adapter import ApaleoPMSAdapter, ApaleoSyncError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _adapter() -> ApaleoPMSAdapter:
    a = ApaleoPMSAdapter(client_id="id", client_secret="secret")
    a.access_token = "tok"
    a.token_expiry = float("inf")
    return a


def _mock_response(status: int, body) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=body)
    return r


def _patch_http(responses: list):
    """Patch httpx.AsyncClient.get to return responses in order."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return patch("app.services.apaleo_adapter.httpx.AsyncClient", return_value=ctx)


# Shape of the sandbox payload, probed on 18/10/2026 (values changed).
PERFORMANCE = {
    "houseCount": 103, "soldCount": 71, "outOfOrderCount": 3, "occupancyPercentage": 71.0,
    "netFoodAndBeveragesRevenue": {"amount": 1840.5, "currency": "EUR"},
    "grossFoodAndBeveragesRevenue": {"amount": 2024.55, "currency": "EUR"},
    "netAccommodationRevenue": {"amount": 9100.0, "currency": "EUR"},
}


# ---------------------------------------------------------------------------
# HOS-352 — occupancy and F&B revenue: true or absent
# ---------------------------------------------------------------------------

class TestPerformanceFigures:
    @pytest.mark.asyncio
    async def test_reads_the_property_performance_report(self):
        adapter = _adapter()
        with _patch_http([_mock_response(200, PERFORMANCE)]) as client_cls:
            occ = await adapter.fetch_occupancy("MUC", date(2026, 4, 1))
        url = client_cls.return_value.__aenter__.return_value.get.await_args.args[0]
        assert url.endswith("/reports/v1/reports/property-performance")
        assert (occ.status, occ.rooms_sold, occ.rooms_available) == (PMSDataStatus.OK, 71, 100)

    @pytest.mark.asyncio
    async def test_fb_revenue_is_net_fb_only(self):
        adapter = _adapter()
        with _patch_http([_mock_response(200, PERFORMANCE)]):
            rev = await adapter.fetch_fb_revenue("MUC", date(2026, 4, 1))
        assert (rev.status, rev.amount, rev.currency) == (PMSDataStatus.OK, 1840.5, "EUR")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [429, 500, 503])
    async def test_non_200_is_an_absent_figure_not_an_exception(self, status: int):
        adapter = _adapter()
        with _patch_http([_mock_response(status, {}), _mock_response(status, {})]):
            occ = await adapter.fetch_occupancy("MUC", date(2026, 4, 1))
            rev = await adapter.fetch_fb_revenue("MUC", date(2026, 4, 1))
        assert occ.status == rev.status == PMSDataStatus.PMS_ERROR
        assert occ.rooms_sold is None and rev.amount is None
        assert str(status) in occ.detail

    @pytest.mark.asyncio
    async def test_missing_counts_are_absent_never_zero_nor_85(self):
        adapter = _adapter()
        with _patch_http([_mock_response(200, {"occupancyPercentage": 85.0})]):
            occ = await adapter.fetch_occupancy("MUC", date(2026, 4, 1))
        assert occ.status == PMSDataStatus.NO_DATA
        assert occ.rooms_sold is None and occ.rate is None

    @pytest.mark.asyncio
    async def test_unconfigured_is_absent_without_a_call(self):
        adapter = ApaleoPMSAdapter(client_id="", client_secret="")
        adapter.client_id = adapter.client_secret = None
        with _patch_http([]) as client_cls:
            occ = await adapter.fetch_occupancy("MUC", date(2026, 4, 1))
        assert occ.status == PMSDataStatus.NOT_CONFIGURED
        client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_token_request_sends_no_rejected_custom_scope(self):
        """Apaleo identity answered 400 to the old custom scopes (sandbox, 18/10/2026)."""
        adapter = ApaleoPMSAdapter(client_id="id", client_secret="secret")
        token = MagicMock(status_code=200)
        token.json.return_value = {"access_token": "t", "expires_in": 3600}
        token.raise_for_status = MagicMock()
        client = AsyncMock()
        client.post = AsyncMock(return_value=token)
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("app.services.apaleo_adapter.httpx.AsyncClient", return_value=ctx):
            await adapter._authenticate()
        assert "scope" not in client.post.await_args.kwargs["data"]


# ---------------------------------------------------------------------------
# AC2 — get_historical_data pagination
# ---------------------------------------------------------------------------

class TestGetHistoricalDataPagination:
    @pytest.mark.asyncio
    async def test_fetches_single_page_when_no_next(self):
        adapter = _adapter()
        body = {
            "stayRecords": [{"id": "r1"}, {"id": "r2"}],
            "pageInfo": {"hasNext": False},
        }
        with _patch_http([_mock_response(200, body)]):
            result = await adapter.get_historical_data("MUC", date(2026, 1, 1), date(2026, 3, 31))
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_fetches_all_pages(self):
        adapter = _adapter()
        page1 = {
            "stayRecords": [{"id": "r1"}],
            "pageInfo": {"hasNext": True, "nextPageToken": "tok2"},
        }
        page2 = {
            "stayRecords": [{"id": "r2"}, {"id": "r3"}],
            "pageInfo": {"hasNext": False},
        }
        with _patch_http([_mock_response(200, page1), _mock_response(200, page2)]):
            result = await adapter.get_historical_data("MUC", date(2026, 1, 1), date(2026, 3, 31))
        assert len(result) == 3
        assert result[0]["id"] == "r1"
        assert result[2]["id"] == "r3"

    @pytest.mark.asyncio
    async def test_handles_bare_list_response(self):
        """Legacy Apaleo response: bare list (no pageInfo)."""
        adapter = _adapter()
        with _patch_http([_mock_response(200, [{"id": "r1"}, {"id": "r2"}])]):
            result = await adapter.get_historical_data("MUC", date(2026, 1, 1), date(2026, 3, 31))
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_raises_on_non_200(self):
        adapter = _adapter()
        with _patch_http([_mock_response(500, {})]):
            with pytest.raises(ApaleoSyncError, match="500"):
                await adapter.get_historical_data("MUC", date(2026, 1, 1), date(2026, 3, 31))

    @pytest.mark.asyncio
    async def test_stops_when_no_next_token(self):
        """If hasNext=True but nextPageToken is absent, stop to avoid infinite loop."""
        adapter = _adapter()
        body = {
            "stayRecords": [{"id": "r1"}],
            "pageInfo": {"hasNext": True},  # hasNext but no token
        }
        with _patch_http([_mock_response(200, body)]):
            result = await adapter.get_historical_data("MUC", date(2026, 1, 1), date(2026, 3, 31))
        assert len(result) == 1


# ---------------------------------------------------------------------------
# AC5 — _authenticate() retry on HTTPStatusError
# ---------------------------------------------------------------------------

class TestAuthenticateRetry:
    @pytest.mark.asyncio
    async def test_retries_on_http_status_error(self):
        """_authenticate() must retry up to 3x on HTTPStatusError."""
        adapter = ApaleoPMSAdapter(client_id="id", client_secret="secret")
        adapter.access_token = None

        call_count = 0
        ok_response = MagicMock()
        ok_response.raise_for_status = MagicMock()
        ok_response.json = MagicMock(return_value={"access_token": "t", "expires_in": 3600})

        fail_response = MagicMock()
        fail_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=MagicMock())
        )

        async def fake_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return fail_response
            return ok_response

        mock_client = AsyncMock()
        mock_client.post = fake_post
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_client)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.apaleo_adapter.httpx.AsyncClient", return_value=ctx):
            await adapter._authenticate()

        assert call_count == 3
        assert adapter.access_token == "t"
