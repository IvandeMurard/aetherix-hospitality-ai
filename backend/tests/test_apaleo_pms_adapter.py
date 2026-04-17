"""Tests for ApaleoPMSAdapter — HOS-131 acceptance criteria.

Coverage (REST adapter, not MCP adapter):
- AC2: get_historical_data() pagination — fetches all pages
- AC3: get_occupancy() raises ApaleoSyncError on non-200
- AC3: get_revenue() raises ApaleoSyncError on non-200
- AC3: get_historical_data() raises ApaleoSyncError on non-200
- AC5: _authenticate() retry on HTTPStatusError (tenacity)
- Data quality: null occupancy in 200 response returns 0, not 85
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.apaleo_adapter import ApaleoSyncError, ApaleoPMSAdapter


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


# ---------------------------------------------------------------------------
# AC3 — get_occupancy raises ApaleoSyncError on non-200
# ---------------------------------------------------------------------------

class TestGetOccupancyErrors:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [429, 500, 503])
    async def test_raises_apaleo_sync_error_on_non_200(self, status: int):
        adapter = _adapter()
        with _patch_http([_mock_response(status, {})]):
            with pytest.raises(ApaleoSyncError, match=str(status)):
                await adapter.get_occupancy("MUC", date(2026, 4, 1))

    @pytest.mark.asyncio
    async def test_returns_occupancy_on_200(self):
        adapter = _adapter()
        with _patch_http([_mock_response(200, {"occupancy": 42})]):
            result = await adapter.get_occupancy("MUC", date(2026, 4, 1))
        assert result == 42

    @pytest.mark.asyncio
    async def test_null_occupancy_returns_zero_not_85(self):
        """Null occupancy field in 200 response must return 0, never the old sentinel 85."""
        adapter = _adapter()
        with _patch_http([_mock_response(200, {"occupancy": None})]):
            result = await adapter.get_occupancy("MUC", date(2026, 4, 1))
        assert result == 0
        assert result != 85


# ---------------------------------------------------------------------------
# AC3 — get_revenue raises ApaleoSyncError on non-200
# ---------------------------------------------------------------------------

class TestGetRevenueErrors:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [429, 500, 503])
    async def test_raises_apaleo_sync_error_on_non_200(self, status: int):
        adapter = _adapter()
        with _patch_http([_mock_response(status, {})]):
            with pytest.raises(ApaleoSyncError, match=str(status)):
                await adapter.get_revenue("MUC", date(2026, 4, 1))

    @pytest.mark.asyncio
    async def test_returns_revenue_on_200(self):
        adapter = _adapter()
        body = {"revenue": [{"amount": 1200.0, "category": "F&B"}]}
        with _patch_http([_mock_response(200, body)]):
            result = await adapter.get_revenue("MUC", date(2026, 4, 1), "F&B")
        assert result == 1200.0


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
