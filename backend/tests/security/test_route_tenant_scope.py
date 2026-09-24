"""Tenant isolation on HTTP routes that take a tenant id from the caller
(ADR-0007 §17.7, 24/09/2026).

Before this change, an authenticated caller could read or act on any tenant:
  * GET /kpi/{hotel_id}/recommendation_acceptance — any receipts:read token
  * GET /receipts/{hotel_id}/{date}              — any receipts:read token
  * GET /reports/weekly?tenant_id=               — no auth at all
  * GET|POST /baselines/{tenant_id}[...]          — any dashboard user
  * POST /events/sync, /weather/sync (tenant_id)  — any dashboard user
  * POST /notifications/test, /dispatch           — no auth at all
Each case below pins the refusal and the allowed path.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.tenant_scope import require_token_hotel
from app.db.session import get_db

OWN = "hotel_a"
OTHER = "hotel_b"


def _token(hotel_id: str | None = OWN) -> MagicMock:
    tok = MagicMock()
    tok.hotel_id = hotel_id
    tok.scopes = ["receipts:read"]
    return tok


def _db_returning(profile=None, rows=None):
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = profile
    result.scalars.return_value.all.return_value = rows or []
    result.fetchall.return_value = rows or []
    db.execute = AsyncMock(return_value=result)
    return db


def _app(router_module: str, db=None) -> FastAPI:
    import importlib

    mod = importlib.import_module(router_module)
    app = FastAPI()
    app.include_router(mod.router, prefix="/api/v1")
    database = db or _db_returning()

    async def _db():
        yield database

    app.dependency_overrides[get_db] = _db
    return app


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def test_require_token_hotel_refuses_other_and_unbound():
    from fastapi import HTTPException

    require_token_hotel(_token(OWN), OWN)
    for tok in (_token(OTHER), _token(None), object()):
        with pytest.raises(HTTPException) as exc:
            require_token_hotel(tok, OWN)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# MCP-token routes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    f"/api/v1/kpi/{OTHER}/recommendation_acceptance",
    f"/api/v1/kpi/{OTHER}/decision_capture",
])
def test_kpi_routes_refuse_another_hotel(path):
    from app.api.routes import kpi

    app = _app("app.api.routes.kpi")
    app.dependency_overrides[kpi._kpi_auth] = lambda: _token(OWN)
    with TestClient(app) as client:
        assert client.get(path).status_code == 403


def test_kpi_acceptance_serves_own_hotel():
    from app.api.routes import kpi

    app = _app("app.api.routes.kpi")
    app.dependency_overrides[kpi._kpi_auth] = lambda: _token(OWN)
    with TestClient(app) as client:
        resp = client.get(f"/api/v1/kpi/{OWN}/recommendation_acceptance")
    assert resp.status_code == 200


def test_receipts_route_refuses_another_hotel():
    from app.api.routes import receipts

    app = _app("app.api.routes.receipts")
    app.dependency_overrides[receipts._receipts_auth] = lambda: _token(OWN)
    with patch("app.api.routes.receipts.ReceiptsService") as svc:
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/receipts/{OTHER}/2026-05-17")
    assert resp.status_code == 403
    svc.assert_not_called()


def test_weekly_report_requires_a_token():
    app = _app("app.api.routes.reports")
    with TestClient(app) as client:
        resp = client.get(f"/api/v1/reports/weekly?tenant_id={OWN}")
    assert resp.status_code == 401


def test_weekly_report_refuses_another_hotel():
    from app.api.routes import reports

    app = _app("app.api.routes.reports")
    app.dependency_overrides[reports._reports_auth] = lambda: _token(OWN)
    with TestClient(app) as client:
        resp = client.get(f"/api/v1/reports/weekly?tenant_id={OTHER}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Dashboard-user routes
# ---------------------------------------------------------------------------

def _user(uid="user-1", superuser=False):
    return {"id": uid, "email": "u@x", "is_active": True, "is_superuser": superuser}


def _profile(owner="user-1"):
    p = MagicMock()
    p.owner_id = owner
    p.tenant_id = OTHER
    p.latitude = 48.85
    p.longitude = 2.35
    return p


@pytest.mark.parametrize("method,path,module,body", [
    ("get", f"/api/v1/baselines/{OTHER}", "app.api.routes.baselines", None),
    ("post", f"/api/v1/baselines/{OTHER}/recalculate", "app.api.routes.baselines", None),
    ("post", "/api/v1/events/sync", "app.api.routes.events", {"tenant_id": OTHER}),
    ("post", "/api/v1/weather/sync", "app.api.routes.weather", {"tenant_id": OTHER}),
])
@pytest.mark.parametrize("profile", [None, "not_owner"])
def test_user_routes_refuse_a_tenant_the_user_does_not_own(method, path, module, body, profile):
    from app.core.security import get_current_user

    prof = None if profile is None else _profile(owner="someone-else")
    app = _app(module, db=_db_returning(profile=prof))
    app.dependency_overrides[get_current_user] = lambda: _user()
    with TestClient(app) as client:
        resp = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
    assert resp.status_code == 403


def test_owner_passes_the_tenant_check():
    from app.core.security import get_current_user

    app = _app("app.api.routes.weather", db=_db_returning(profile=_profile(owner="user-1")))
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("app.api.routes.weather._run_sync", new_callable=AsyncMock):
        with TestClient(app) as client:
            resp = client.post("/api/v1/weather/sync", json={"tenant_id": OTHER})
    assert resp.status_code == 202


@pytest.mark.parametrize("path,body", [
    ("/api/v1/notifications/dispatch", None),
    ("/api/v1/notifications/test", {"channel": "sms", "to": "+33600000000", "message": "x"}),
])
def test_notification_routes_are_ops_only(path, body):
    from app.core.security import get_current_user

    app = _app("app.api.routes.notifications")
    app.dependency_overrides[get_current_user] = lambda: _user(superuser=False)
    with patch("app.services.alert_dispatcher.AlertDispatcherService.run_pending",
               new_callable=AsyncMock) as run:
        with TestClient(app) as client:
            resp = client.post(path, json=body) if body else client.post(path)
    assert resp.status_code == 403
    run.assert_not_called()

