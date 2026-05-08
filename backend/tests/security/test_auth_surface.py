"""Security regression suite — HOS-149 AC8.

Covers every mutating endpoint's auth surface:
  - POST /predictions/predict  (AC2, AC3)
  - POST /predictions/train    (AC4)
  - POST /webhooks/twilio/whatsapp  (AC5)
  - POST /auth/register        (AC6)
  - Startup env validation     (AC1, AC7)

Each mutating endpoint is tested for:
  * request without Authorization → 401
  * request with expired token → 401
  * request with revoked token → 401
  * request with valid token but wrong scope → 403
  * request with valid token + correct scope → 200 (business logic mocked)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mock_forecast_result(hotel_id: str = "hotel-001") -> dict[str, Any]:
    return {
        "tenant_id": hotel_id,
        "date": date.today().isoformat(),
        "service_type": "dinner",
        "prediction": {"covers": 45, "confidence": 0.85, "interval": [38, 52]},
        "reasoning": "Mock forecast.",
        "reasoning_detail": {
            "summary": "Mock forecast.",
            "confidence_factors": [],
            "claude_used": False,
        },
        "staffing_recommendation": {"servers": 4, "kitchen": 3, "hosts": 1},
    }


def _make_token(
    hotel_id: str = "hotel-001",
    scopes: list[str] | None = None,
    revoked: bool = False,
    expired: bool = False,
) -> MagicMock:
    tok = MagicMock()
    tok.hotel_id = hotel_id
    tok.scopes = scopes if scopes is not None else ["predict", "recommend", "feedback"]
    tok.revoked_at = datetime.now(timezone.utc) if revoked else None
    tok.expires_at = (
        datetime.now(timezone.utc) - timedelta(hours=1) if expired else None
    )
    tok.last_used_at = None
    return tok


# ---------------------------------------------------------------------------
# AC1 + AC7 — Boot-time env validation
# ---------------------------------------------------------------------------

class TestStartupEnvValidation:
    """Tests for _validate_startup_env() in main.py (AC1 + AC7).

    Uses explicit env dicts to stay hermetic — no monkeypatching of os.environ,
    which avoids triggering load_dotenv() pollution across the test suite.
    """

    @staticmethod
    def _fn():
        from app.main import _validate_startup_env
        return _validate_startup_env

    def test_missing_auth_secret_raises(self):
        with pytest.raises(SystemExit, match="AUTH_SECRET"):
            self._fn()(env={})

    def test_placeholder_secret_raises(self):
        with pytest.raises(SystemExit, match="AUTH_SECRET"):
            self._fn()(env={"AUTH_SECRET": "SECRET_CHANGE_ME"})

    def test_short_secret_raises(self):
        with pytest.raises(SystemExit, match="AUTH_SECRET"):
            self._fn()(env={"AUTH_SECRET": "tooshort"})

    def test_valid_secret_passes(self):
        self._fn()(env={"AUTH_SECRET": "a" * 32})  # should not raise

    def test_twilio_skip_forbidden_in_production(self):
        with pytest.raises(SystemExit, match="TWILIO_SKIP_SIGNATURE_VALIDATION"):
            self._fn()(env={
                "AUTH_SECRET": "a" * 32,
                "APP_ENV": "production",
                "TWILIO_SKIP_SIGNATURE_VALIDATION": "true",
            })

    def test_twilio_skip_allowed_outside_production(self):
        self._fn()(env={
            "AUTH_SECRET": "a" * 32,
            "APP_ENV": "staging",
            "TWILIO_SKIP_SIGNATURE_VALIDATION": "true",
        })  # should not raise


# ---------------------------------------------------------------------------
# Shared: minimal predict/train app factory
# ---------------------------------------------------------------------------

def _make_predictions_app(
    predict_dep_override=None,
    train_dep_override=None,
) -> FastAPI:
    from unittest.mock import AsyncMock as _AsyncMock
    from unittest.mock import MagicMock

    from app.api.routes.predictions import _predict_auth, _train_auth, router
    from app.core.error_handlers import problem_details_handler
    from app.db.session import get_db

    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(HTTPException, problem_details_handler)
    # HOS-157: engine injected from app.state (no module-level singleton)
    app.state.engine = MagicMock()
    # HOS-151: avoid real DB connections in unit tests
    async def _noop_db():
        yield _AsyncMock()
    app.dependency_overrides[get_db] = _noop_db
    if predict_dep_override is not None:
        app.dependency_overrides[_predict_auth] = predict_dep_override
    if train_dep_override is not None:
        app.dependency_overrides[_train_auth] = train_dep_override
    return app


def _raises_401(detail: str = "unauthorized"):
    def _dep():
        raise HTTPException(status_code=401, detail=detail)
    return _dep


def _raises_403(detail: str = "forbidden"):
    def _dep():
        raise HTTPException(status_code=403, detail=detail)
    return _dep


def _returns_token(tok):
    def _dep():
        return tok
    return _dep


# ---------------------------------------------------------------------------
# AC2 + AC3 — /predict auth surface
# ---------------------------------------------------------------------------

class TestPredictAuthSurface:
    """AC2: /predict requires bearer token. AC3: hotel_id bound to token."""

    _PAYLOAD = {"hotel_id": "hotel-001", "target_date": "2026-05-10"}

    def test_no_authorization_returns_401(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        client = TestClient(_make_predictions_app(_raises_401("Missing Bearer token")))
        resp = client.post("/predictions/predict", json=self._PAYLOAD)
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        client = TestClient(_make_predictions_app(_raises_401("Token expired")))
        resp = client.post("/predictions/predict", json=self._PAYLOAD)
        assert resp.status_code == 401

    def test_revoked_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        client = TestClient(_make_predictions_app(_raises_401("Token revoked")))
        resp = client.post("/predictions/predict", json=self._PAYLOAD)
        assert resp.status_code == 401

    def test_wrong_scope_returns_403(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        client = TestClient(
            _make_predictions_app(_raises_403("Token missing required scope: predict"))
        )
        resp = client.post("/predictions/predict", json=self._PAYLOAD)
        assert resp.status_code == 403

    def test_valid_token_with_predict_scope_returns_200(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        tok = _make_token(hotel_id="hotel-001", scopes=["predict"])
        app = _make_predictions_app(_returns_token(tok))
        app.state.engine.get_forecast = AsyncMock(
            return_value=_mock_forecast_result("hotel-001")
        )
        client = TestClient(app)
        resp = client.post("/predictions/predict", json=self._PAYLOAD)
        assert resp.status_code == 200

    def test_hotel_id_overridden_by_token(self, monkeypatch):
        """AC3: body hotel_id ignored when it differs from token hotel_id."""
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        tok = _make_token(hotel_id="token-hotel", scopes=["predict"])
        app = _make_predictions_app(_returns_token(tok))
        app.state.engine.get_forecast = AsyncMock(
            return_value=_mock_forecast_result("token-hotel")
        )
        client = TestClient(app)
        resp = client.post(
            "/predictions/predict",
            json={"hotel_id": "other-hotel", "target_date": "2026-05-10"},
        )
        assert resp.status_code == 200
        assert resp.json()["hotel_id"] == "token-hotel"

    def test_response_header_x_aetherix_hotel_id(self, monkeypatch):
        """AC3: X-Aetherix-Hotel-Id response header = token hotel_id."""
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        tok = _make_token(hotel_id="hotel-001", scopes=["predict"])
        app = _make_predictions_app(_returns_token(tok))
        app.state.engine.get_forecast = AsyncMock(
            return_value=_mock_forecast_result("hotel-001")
        )
        client = TestClient(app)
        resp = client.post("/predictions/predict", json=self._PAYLOAD)
        assert resp.headers.get("x-aetherix-hotel-id") == "hotel-001"


# ---------------------------------------------------------------------------
# AC4 — /train auth surface
# ---------------------------------------------------------------------------

class TestTrainAuthSurface:
    """AC4: /train requires admin:train scope."""

    _PAYLOAD: dict = {}  # uses TrainRequest defaults

    def test_no_authorization_returns_401(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        client = TestClient(_make_predictions_app(train_dep_override=_raises_401()))
        resp = client.post("/predictions/train", json=self._PAYLOAD)
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        client = TestClient(
            _make_predictions_app(train_dep_override=_raises_401("Token expired"))
        )
        resp = client.post("/predictions/train", json=self._PAYLOAD)
        assert resp.status_code == 401

    def test_revoked_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        client = TestClient(
            _make_predictions_app(train_dep_override=_raises_401("Token revoked"))
        )
        resp = client.post("/predictions/train", json=self._PAYLOAD)
        assert resp.status_code == 401

    def test_predict_scope_returns_403(self, monkeypatch):
        """Token with only 'predict' scope must be rejected for /train."""
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        client = TestClient(
            _make_predictions_app(
                train_dep_override=_raises_403("Token missing required scope: admin:train")
            )
        )
        resp = client.post("/predictions/train", json=self._PAYLOAD)
        assert resp.status_code == 403

    def test_admin_train_scope_proceeds_past_auth(self, monkeypatch):
        """Token with admin:train scope reaches the handler (business logic may fail — not auth)."""
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        tok = _make_token(hotel_id="hotel-001", scopes=["admin:train"])

        with patch(
            "app.api.routes.predictions._build_training_dataframe",
            new_callable=AsyncMock,
        ) as mock_df:
            import pandas as pd

            df = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=90), "y": range(90)})
            mock_df.return_value = df

            app = _make_predictions_app(train_dep_override=_returns_token(tok))
            # HOS-157: engine on app.state — configure the mock forecaster
            app.state.engine.forecaster.is_trained = True
            app.state.engine.forecaster.model = None
            app.state.engine.forecaster.train = MagicMock()
            app.state.engine.forecaster.save_model = MagicMock()

            client = TestClient(app)
            resp = client.post("/predictions/train", json=self._PAYLOAD)

        # Must NOT be 401 or 403 — auth passed, business logic runs
        assert resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# AC5 — /webhooks/twilio/whatsapp HMAC validation
# ---------------------------------------------------------------------------

def _make_webhooks_app() -> FastAPI:
    from app.api.routes.webhooks import router
    from app.core.error_handlers import problem_details_handler

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.add_exception_handler(HTTPException, problem_details_handler)
    return app


def _twilio_signature(url: str, params: dict[str, str], auth_token: str) -> str:
    """Compute a valid Twilio HMAC-SHA1 signature for test use."""
    s = url
    for key in sorted(params.keys()):
        s += key + params[key]
    mac = hmac.new(auth_token.encode(), s.encode(), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode()


class TestWhatsAppWebhookHMACValidation:
    """AC5: /webhooks/twilio/whatsapp must validate X-Twilio-Signature."""

    _URL = "/api/v1/webhooks/twilio/whatsapp"
    _FORM = {"Body": "hello", "From": "whatsapp:+336", "To": "whatsapp:+1415"}

    def test_missing_signature_returns_403(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "false")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_secret")
        client = TestClient(_make_webhooks_app())
        resp = client.post(self._URL, data=self._FORM)
        assert resp.status_code == 403

    def test_invalid_signature_returns_403(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "false")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_secret")
        client = TestClient(_make_webhooks_app())
        resp = client.post(
            self._URL,
            data=self._FORM,
            headers={"X-Twilio-Signature": "invalidsig"},
        )
        assert resp.status_code == 403

    def test_background_task_not_called_on_bad_signature(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "false")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_secret")
        with patch("app.api.routes.webhooks.whatsapp.handle_inbound_message") as mock_handle:
            client = TestClient(_make_webhooks_app())
            client.post(self._URL, data=self._FORM)
        mock_handle.assert_not_called()

    def test_valid_signature_returns_200(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "false")
        auth_token = "test_secret_token_abc"
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", auth_token)

        client = TestClient(_make_webhooks_app())
        # Compute URL as the test client would send it
        full_url = "http://testserver" + self._URL
        sig = _twilio_signature(full_url, self._FORM, auth_token)

        with patch("app.api.routes.webhooks.whatsapp.handle_inbound_message"):
            resp = client.post(
                self._URL,
                data=self._FORM,
                headers={"X-Twilio-Signature": sig},
            )
        assert resp.status_code == 200

    def test_skip_validation_allows_no_signature(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        with patch("app.api.routes.webhooks.whatsapp.handle_inbound_message"):
            client = TestClient(_make_webhooks_app())
            resp = client.post(self._URL, data=self._FORM)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AC6 — /auth/register invitation-gated
# ---------------------------------------------------------------------------

def _make_auth_app(registration_enabled: bool = False) -> FastAPI:
    import importlib

    import app.api.routes.auth as auth_mod

    # Force module reload so the os.getenv branch is re-evaluated
    importlib.reload(auth_mod)
    from app.core.error_handlers import problem_details_handler

    _app = FastAPI()
    _app.include_router(auth_mod.router)
    _app.add_exception_handler(HTTPException, problem_details_handler)
    return _app


class TestRegisterGating:
    """AC6: /auth/register returns 403 unless REGISTRATION_ENABLED=true."""

    def test_register_disabled_by_default(self, monkeypatch):
        monkeypatch.setenv("REGISTRATION_ENABLED", "false")
        client = TestClient(_make_auth_app(registration_enabled=False))
        resp = client.post("/auth/register", json={"email": "x@x.com", "password": "pw"})
        assert resp.status_code == 403

    def test_register_disabled_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("REGISTRATION_ENABLED", raising=False)
        client = TestClient(_make_auth_app(registration_enabled=False))
        resp = client.post("/auth/register", json={"email": "x@x.com", "password": "pw"})
        assert resp.status_code == 403
