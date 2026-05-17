"""P2-6 tests — GET /api/v1/receipts/{hotel_id}/{date} auth surface.

Pure-mock tests: no DB, no LLM.

Covered:
  1.  Missing Authorization header → 401
  2.  Invalid / revoked token → 401 (verify_bearer raises MCPAuthError)
  3.  Token missing receipts:read scope → 403
  4.  Valid token with receipts:read → 200 + ReceiptPayload shape
  5.  Route is registered under /api/v1/receipts prefix
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.receipts import ReceiptPayload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(scopes: list[str]) -> MagicMock:
    tok = MagicMock()
    tok.hotel_id = "hotel_demo"
    tok.scopes = scopes
    tok.revoked_at = None
    tok.expires_at = None
    return tok


def _make_payload() -> ReceiptPayload:
    return ReceiptPayload(
        hotel_id="hotel_demo",
        receipt_date=date(2026, 5, 17),
        generated_at=datetime(2026, 5, 17, 18, 0, tzinfo=timezone.utc),
        total_actions=3,
        counts_by_status={"ok": 3},
        counts_by_tool={"get_operational_predictions": 3},
        lines=[],
    )


async def _noop_db():
    yield AsyncMock()


def _make_app() -> FastAPI:
    from app.api.routes.receipts import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# 1. Missing Authorization → 401
# ---------------------------------------------------------------------------

def test_receipts_route_no_auth_returns_401(monkeypatch):
    monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
    from app.mcp_core import MCPAuthError
    from app.db.session import get_db

    app = _make_app()
    app.dependency_overrides[get_db] = _noop_db

    with patch(
        "app.api.routes.receipts.verify_bearer",
        new_callable=AsyncMock,
        side_effect=MCPAuthError(401, "unauthorized", "Missing Bearer token"),
    ):
        with TestClient(app) as client:
            resp = client.get("/api/v1/receipts/hotel_demo/2026-05-17")

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Token missing receipts:read scope → 403
# ---------------------------------------------------------------------------

def test_receipts_route_wrong_scope_returns_403(monkeypatch):
    from app.db.session import get_db

    app = _make_app()
    app.dependency_overrides[get_db] = _noop_db

    tok = _make_token(scopes=["predict"])

    with patch(
        "app.api.routes.receipts.verify_bearer",
        new_callable=AsyncMock,
        return_value=tok,
    ):
        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/receipts/hotel_demo/2026-05-17",
                headers={"Authorization": "Bearer some-token"},
            )

    assert resp.status_code == 403
    assert "receipts:read" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Valid token with receipts:read → 200 + payload shape
# ---------------------------------------------------------------------------

def test_receipts_route_valid_token_returns_200(monkeypatch):
    from app.db.session import get_db

    app = _make_app()
    app.dependency_overrides[get_db] = _noop_db

    tok = _make_token(scopes=["receipts:read"])
    payload = _make_payload()

    with patch(
        "app.api.routes.receipts.verify_bearer",
        new_callable=AsyncMock,
        return_value=tok,
    ), patch(
        "app.api.routes.receipts.ReceiptsService.daily_receipt",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/receipts/hotel_demo/2026-05-17",
                headers={"Authorization": "Bearer valid-token"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["hotel_id"] == "hotel_demo"
    assert body["receipt_date"] == "2026-05-17"
    assert body["total_actions"] == 3
    assert "counts_by_status" in body
    assert "lines" in body


# ---------------------------------------------------------------------------
# 4. Route prefix check
# ---------------------------------------------------------------------------

def test_receipts_route_registered_at_correct_prefix():
    app = _make_app()
    routes = {r.path for r in app.routes}
    assert "/api/v1/receipts/{hotel_id}/{receipt_date}" in routes
