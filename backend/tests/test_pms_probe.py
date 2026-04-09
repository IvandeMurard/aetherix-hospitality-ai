"""
Tests for GET /pms/mcp/probe — synchronous Apaleo MCP health-check.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.pms import router
from app.core.security import get_current_user


# ---------------------------------------------------------------------------
# Minimal app fixture (no DB, no auth)
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "email": "test@example.com"}
    return app


@pytest.fixture
def app() -> FastAPI:
    return _make_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_transport():
    """Return a wired async-context-manager fake for streamablehttp_client."""
    transport = MagicMock()
    transport.__aenter__ = AsyncMock(return_value=("r", "w", lambda: None))
    transport.__aexit__ = AsyncMock(return_value=False)
    return transport


def _mock_session(tool_names: list[str]):
    """Return a wired async-context-manager fake for ClientSession."""
    # MagicMock(name=...) sets the mock's repr name, NOT the .name attribute.
    tool_mocks = []
    for n in tool_names:
        t = MagicMock()
        t.name = n
        tool_mocks.append(t)
    list_result = MagicMock()
    list_result.tools = tool_mocks

    session = AsyncMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(return_value=list_result)

    wrapper = MagicMock()
    wrapper.__aenter__ = AsyncMock(return_value=session)
    wrapper.__aexit__ = AsyncMock(return_value=False)
    return wrapper


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestProbeMisconfigured:
    async def test_returns_503_when_env_vars_missing(self, client: AsyncClient) -> None:
        with patch("app.api.routes.pms.ApaleoMCPClient") as MockClient:
            instance = MockClient.return_value
            instance.is_configured = False

            resp = await client.get("/pms/mcp/probe")

        assert resp.status_code == 503
        assert resp.json()["detail"]["status"] == "misconfigured"


class TestProbeOk:
    async def test_returns_200_with_tool_list(self, client: AsyncClient) -> None:
        tool_names = ["APALEO_GET_OCCUPANCY_METRICS", "APALEO_GET_RESERVATIONS"]

        with (
            patch("app.api.routes.pms.ApaleoMCPClient") as MockClient,
            patch("app.api.routes.pms.streamablehttp_client", return_value=_mock_transport()),
            patch("app.api.routes.pms.ClientSession", return_value=_mock_session(tool_names)),
        ):
            instance = MockClient.return_value
            instance.is_configured = True
            instance.server_url = "https://mcp.apaleo.com/mcp/"
            instance._get_token = AsyncMock(return_value="tok")

            resp = await client.get("/pms/mcp/probe")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["tools_available"] == 2
        assert "APALEO_GET_OCCUPANCY_METRICS" in body["tools"]

    async def test_returns_503_on_transport_error(self, client: AsyncClient) -> None:
        broken_transport = MagicMock()
        broken_transport.__aenter__ = AsyncMock(side_effect=RuntimeError("connection refused"))
        broken_transport.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.api.routes.pms.ApaleoMCPClient") as MockClient,
            patch("app.api.routes.pms.streamablehttp_client", return_value=broken_transport),
        ):
            instance = MockClient.return_value
            instance.is_configured = True
            instance.server_url = "https://mcp.apaleo.com/mcp/"
            instance._get_token = AsyncMock(return_value="tok")

            resp = await client.get("/pms/mcp/probe")

        assert resp.status_code == 503
        body = resp.json()
        assert body["detail"]["status"] == "unreachable"
        assert "connection refused" in body["detail"]["error"]
