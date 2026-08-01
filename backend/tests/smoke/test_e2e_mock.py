"""HOS-161 — CI-safe pytest mirror of scripts/ci/smoke_test_e2e.py.

All HTTP traffic is mocked. Steps 1, 3, 4, 5 are exercised; steps 2 and 6
require a live staging environment and are skipped in CI.

The pytest invocation `python -m pytest tests/smoke/ -x` (from backend/) must
pass with no credentials and no network access.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the smoke script as a module without executing main().
# Located at <repo>/scripts/ci/smoke_test_e2e.py.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "smoke_test_e2e.py"


@pytest.fixture(scope="module")
def smoke():
    spec = importlib.util.spec_from_file_location("smoke_test_e2e", _SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["smoke_test_e2e"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Mock httpx.Client builder
# ---------------------------------------------------------------------------

def _resp(status: int, json_body: Any | None = None, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = text if text else (json.dumps(json_body) if json_body is not None else "")
    r.headers = {"content-type": "application/json"} if json_body is not None else {}
    r.json.return_value = json_body or {}
    r.raise_for_status = MagicMock()
    if status >= 400:
        import httpx
        r.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=r
        )
    return r


def _build_client(handlers: dict[tuple[str, str], MagicMock]) -> MagicMock:
    """Build a fake httpx.Client. handlers maps (METHOD, path-suffix) -> response."""
    client = MagicMock()

    def _match(method: str, url: str) -> MagicMock:
        for (m, suffix), resp in handlers.items():
            if m == method and url.endswith(suffix):
                return resp
        # Default: 404 — surfaces unexpected calls during the test.
        return _resp(404, {"detail": f"no handler for {method} {url}"})

    client.get = lambda url, **kw: _match("GET", url)
    client.post = lambda url, **kw: _match("POST", url)

    def _request(method, url, **kw):
        return _match(method, url)

    client.request = _request
    return client


# ===========================================================================
# Step 1 — Boot validation
# ===========================================================================

def test_step1_boot_happy_path(smoke, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    handlers = {
        ("GET", "/health"): _resp(200, {"status": "ok"}),
        ("GET", "/health/workers"): _resp(200, {"anomaly_scan": "ok", "dispatch": "never_ran"}),
    }
    client = _build_client(handlers)
    result = smoke.step1_boot(client, "http://localhost:8000")
    assert result["status"] == "ok", result


def test_step1_boot_fails_when_health_returns_500(smoke, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    handlers = {
        ("GET", "/health"): _resp(500),
        ("GET", "/health/workers"): _resp(404),
    }
    client = _build_client(handlers)
    result = smoke.step1_boot(client, "http://localhost:8000")
    assert result["status"] == "fail"
    assert "/health" in result["details"]


def test_step1_boot_tolerates_missing_workers_endpoint(smoke, monkeypatch):
    """404 on /health/workers must not fail step 1 — endpoint is optional."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    handlers = {
        ("GET", "/health"): _resp(200, {"status": "ok"}),
        ("GET", "/health/workers"): _resp(404),
    }
    client = _build_client(handlers)
    result = smoke.step1_boot(client, "http://localhost:8000")
    assert result["status"] == "ok", result


def test_step1_boot_fails_when_worker_status_is_bad(smoke, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    handlers = {
        ("GET", "/health"): _resp(200, {"status": "ok"}),
        ("GET", "/health/workers"): _resp(200, {"anomaly_scan": "ok", "dispatch": "failed"}),
    }
    client = _build_client(handlers)
    result = smoke.step1_boot(client, "http://localhost:8000")
    assert result["status"] == "fail"
    assert "dispatch" in result["details"]


# ===========================================================================
# Step 2 — only smoke-checked here; real probe is staging-only
# ===========================================================================

@pytest.mark.skip(reason="requires staging — see scripts/ci/smoke_test_e2e.py step 2")
def test_step2_apaleo_probe_staging_only():
    pass


# ===========================================================================
# Step 3 — Prophet predict via MCP
# ===========================================================================

def _mcp_response_payload(tool_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": "test",
        "result": {
            "content": [{"type": "text", "text": json.dumps(tool_result)}],
            "isError": False,
        },
    }


def test_step3_predict_ok(smoke):
    handlers = {
        ("POST", "/mcp/v1/"): _resp(
            200,
            _mcp_response_payload({
                "prediction": {"covers": 45, "confidence": 0.85},
                "recommendation_id": str(uuid.uuid4()),
            }),
        ),
    }
    client = _build_client(handlers)
    result = smoke.step3_predict(client, "http://localhost:8000", "tok", "demo_hotel")
    assert result["status"] == "ok", result
    assert "covers=45" in result["details"]


def test_step3_predict_fails_when_covers_zero(smoke):
    handlers = {
        ("POST", "/mcp/v1/"): _resp(
            200,
            _mcp_response_payload({"prediction": {"covers": 0, "confidence": 0.1}}),
        ),
    }
    client = _build_client(handlers)
    result = smoke.step3_predict(client, "http://localhost:8000", "tok", "demo_hotel")
    assert result["status"] == "fail"


def test_step3_predict_fails_on_mcp_error(smoke):
    handlers = {
        ("POST", "/mcp/v1/"): _resp(
            200,
            {"jsonrpc": "2.0", "id": "test", "error": {"code": -1, "message": "boom"}},
        ),
    }
    client = _build_client(handlers)
    result = smoke.step3_predict(client, "http://localhost:8000", "tok", "demo_hotel")
    assert result["status"] == "fail"
    assert "MCP error" in result["details"]


# ===========================================================================
# Step 4 — Memory feedback round-trip
# ===========================================================================

def test_step4_memory_roundtrip_ok(smoke):
    rec_id = str(uuid.uuid4())
    # Each MCP call hits the same URL; queue responses in call order.
    payloads = [
        _mcp_response_payload({
            "prediction": {"covers": 50, "confidence": 0.9},
            "recommendation_id": rec_id,
        }),
        _mcp_response_payload({"status": "stored"}),
        _mcp_response_payload({"recommendations": [], "memory_hits": 3}),
    ]
    responses = [_resp(200, p) for p in payloads]
    client = MagicMock()
    client.post = MagicMock(side_effect=responses)
    client.get = MagicMock(side_effect=AssertionError("step4 should not GET"))
    result = smoke.step4_memory(client, "http://localhost:8000", "tok", "demo_hotel")
    assert result["status"] == "ok", result
    assert rec_id in result["details"]
    assert client.post.call_count == 3


def test_step4_memory_fails_when_recall_returns_non_dict(smoke):
    payloads = [
        _mcp_response_payload({"prediction": {"covers": 50}, "recommendation_id": str(uuid.uuid4())}),
        _mcp_response_payload({"status": "stored"}),
        # MCP tool result must be a dict per contract; a string surfaces a regression.
        {"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": json.dumps("not a dict")}], "isError": False}},
    ]
    responses = [_resp(200, p) for p in payloads]
    client = MagicMock()
    client.post = MagicMock(side_effect=responses)
    result = smoke.step4_memory(client, "http://localhost:8000", "tok", "demo_hotel")
    assert result["status"] == "fail"


# ===========================================================================
# Step 5 — Auth surface
# ===========================================================================

def test_step5_auth_surface_all_endpoints_reject_anonymous(smoke):
    handlers = {
        ("POST", "/api/v1/predictions/predict"): _resp(401, {"detail": "Missing Bearer token"}),
        ("POST", "/api/v1/predictions/train"): _resp(401, {"detail": "Missing Bearer token"}),
        ("POST", "/webhooks/twilio/inbound"): _resp(403, {"detail": "invalid signature"}),
        ("POST", "/api/v1/auth/register"): _resp(403, {"detail": "Registration disabled"}),
    }
    client = _build_client(handlers)
    result = smoke.step5_auth_surface(client, "http://localhost:8000")
    assert result["status"] == "ok", result
    assert "checked=4" in result["details"]


def test_step5_auth_surface_fails_when_predict_returns_200(smoke):
    handlers = {
        ("POST", "/api/v1/predictions/predict"): _resp(200, {"covers": 10}),
        ("POST", "/api/v1/predictions/train"): _resp(401),
        ("POST", "/webhooks/twilio/inbound"): _resp(403),
        ("POST", "/api/v1/auth/register"): _resp(403),
    }
    client = _build_client(handlers)
    result = smoke.step5_auth_surface(client, "http://localhost:8000")
    assert result["status"] == "fail"
    assert "/predictions/predict" in result["details"]


def test_step5_auth_surface_fails_when_endpoint_500s(smoke):
    handlers = {
        ("POST", "/api/v1/predictions/predict"): _resp(401),
        ("POST", "/api/v1/predictions/train"): _resp(500),
        ("POST", "/webhooks/twilio/inbound"): _resp(403),
        ("POST", "/api/v1/auth/register"): _resp(403),
    }
    client = _build_client(handlers)
    result = smoke.step5_auth_surface(client, "http://localhost:8000")
    assert result["status"] == "fail"
    assert "/predictions/train" in result["details"]


# ===========================================================================
# Step 6 — staging only
# ===========================================================================

@pytest.mark.skip(reason="requires staging — needs DB write access + Twilio sandbox")
def test_step6_anomaly_dispatch_staging_only():
    pass


# ===========================================================================
# Driver — main() exits 0 when every step passes
# ===========================================================================

def test_main_returns_zero_when_all_steps_pass(smoke, monkeypatch, capsys):
    """Run main() with every step skipped — sanity check on the driver."""
    monkeypatch.setenv("SMOKE_SKIP_STEPS", "1,2,3,4,5,6")
    monkeypatch.delenv("APP_BASE_URL", raising=False)

    # httpx.Client is still constructed even when all steps are skipped.
    with patch.object(smoke.httpx, "Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__ = lambda s: MagicMock()
        mock_client_cls.return_value.__exit__ = lambda *a: None
        rc = smoke.main([])

    assert rc == 0
    out = capsys.readouterr().out.strip().splitlines()
    summary = json.loads(out[-1])
    assert summary["total"] == 6
    assert summary["skipped"] == 6
    assert summary["failed"] == 0
    assert summary["exit_code"] == 0
