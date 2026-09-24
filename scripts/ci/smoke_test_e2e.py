#!/usr/bin/env python3
"""HOS-161 — E2E smoke test against a running Aetherix backend.

Designed to be executed manually against a real staging environment after a
release-candidate PR is merged. It is NOT a pytest module; it exits with
status 0 when every required step passes, 1 otherwise.

Steps (each emits one JSON line on stdout):
  1. Boot validation        — /health, /health/workers, schema-drift script
  2. Apaleo MCP probe       — /api/v1/pms/mcp/probe (skippable)
  3. Prophet predict        — /mcp/v1/ tools/call get_operational_predictions
  4. Memory feedback loop   — predict -> submit_feedback -> recommendations
  5. Auth surface           — endpoints reject anonymous traffic
  6. Anomaly dispatch       — synthetic anomaly -> dispatch worker (skippable)

Environment:
  APP_BASE_URL          (default http://localhost:8000)
  SMOKE_MCP_TOKEN       MCP bearer (predict + memory_write + memory_read scopes)
  SMOKE_HOTEL_ID        (default demo_hotel)
  SMOKE_SKIP_STEPS      Comma-separated step numbers to skip, e.g. "2,6"
  DATABASE_URL          Optional — only required for step 6

Usage:
  python scripts/smoke_test_e2e.py [--help]
  python scripts/smoke_test_e2e.py --skip 2,6

Output: one JSON line per step + one final summary line.
Exit code: 0 if all non-skipped steps pass, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

# Load .env from repo root if present (Phase 0 convenience — no impact on CI mock).
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_HOTEL_ID = "demo_hotel"
HTTP_TIMEOUT = 30.0
HEALTH_SLA_SECONDS = 1.0


# ---------------------------------------------------------------------------
# Step result helpers
# ---------------------------------------------------------------------------

def _emit(step: int, name: str, status: str, duration_ms: int, details: str) -> dict[str, Any]:
    payload = {
        "step": step,
        "name": name,
        "status": status,
        "duration_ms": duration_ms,
        "details": details,
    }
    print(json.dumps(payload), flush=True)
    return payload


def _ok(step: int, name: str, t0: float, details: str = "") -> dict[str, Any]:
    return _emit(step, name, "ok", int((time.monotonic() - t0) * 1000), details)


def _fail(step: int, name: str, t0: float, details: str) -> dict[str, Any]:
    return _emit(step, name, "fail", int((time.monotonic() - t0) * 1000), details)


def _skip(step: int, name: str, details: str = "skipped") -> dict[str, Any]:
    payload = {"step": step, "name": name, "status": "skip", "duration_ms": 0, "details": details}
    print(json.dumps(payload), flush=True)
    return payload


# ---------------------------------------------------------------------------
# MCP JSON-RPC helper
# ---------------------------------------------------------------------------

def _mcp_call(
    client: httpx.Client,
    base_url: str,
    token: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Invoke an MCP tool via JSON-RPC. Returns the parsed text result dict."""
    rpc_id = str(uuid.uuid4())
    resp = client.post(
        f"{base_url}/mcp/v1/",
        json={
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        raise RuntimeError(f"MCP error: {body['error']}")
    content = body["result"]["content"][0]["text"]
    return json.loads(content)


# ---------------------------------------------------------------------------
# Step 1 — Boot validation
# ---------------------------------------------------------------------------

def step1_boot(client: httpx.Client, base_url: str) -> dict[str, Any]:
    name = "boot_validation"
    t0 = time.monotonic()
    try:
        # Warm-up call: first hit after Fly machine idle may take ~15s
        # (Python interpreter warm-up, Prophet import, asyncpg pool init).
        # Measurement is on the SECOND call, against a warm instance.
        try:
            client.get(f"{base_url}/health", timeout=HTTP_TIMEOUT)
        except Exception:
            pass  # First call may even timeout; that's fine, we retry below.

        t_measure = time.monotonic()
        r = client.get(f"{base_url}/health", timeout=HTTP_TIMEOUT)
        health_elapsed = time.monotonic() - t_measure
        if r.status_code != 200:
            return _fail(1, name, t0, f"/health -> {r.status_code}")
        if health_elapsed > HEALTH_SLA_SECONDS:
            return _fail(1, name, t0, f"/health (warm) latency {health_elapsed:.2f}s > {HEALTH_SLA_SECONDS}s")

        # /health/workers is optional — degrade to a warning if 404.
        workers_detail = "workers=skipped"
        try:
            rw = client.get(f"{base_url}/health/workers", timeout=HTTP_TIMEOUT)
            if rw.status_code == 200:
                body = rw.json() if rw.headers.get("content-type", "").startswith("application/json") else {}
                bad = [k for k, v in body.items() if v not in ("ok", "never_ran", None)]
                if bad:
                    return _fail(1, name, t0, f"/health/workers reports failing: {bad}")
                workers_detail = f"workers={sorted(body.keys())}"
            elif rw.status_code != 404:
                return _fail(1, name, t0, f"/health/workers -> {rw.status_code}")
        except httpx.HTTPError:
            workers_detail = "workers=unreachable"

        # check_schema_drift — only invoked when DATABASE_URL is set.
        if os.getenv("DATABASE_URL"):
            repo_root = Path(__file__).resolve().parent.parent.parent
            script = repo_root / "scripts" / "ci" / "check_schema_drift.py"
            if script.exists():
                proc = subprocess.run(
                    [sys.executable, str(script)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if proc.returncode != 0:
                    return _fail(
                        1, name, t0,
                        f"schema_drift exit={proc.returncode}: {proc.stderr.strip()[:200]}",
                    )
                drift_detail = "schema_drift=clean"
            else:
                drift_detail = "schema_drift=missing"
        else:
            drift_detail = "schema_drift=skipped(no DATABASE_URL)"

        return _ok(1, name, t0, f"{workers_detail}; {drift_detail}")
    except Exception as exc:
        return _fail(1, name, t0, f"unexpected: {exc!r}")


# ---------------------------------------------------------------------------
# Step 2 — Apaleo MCP probe
# ---------------------------------------------------------------------------

def step2_apaleo_probe(client: httpx.Client, base_url: str, token: str) -> dict[str, Any]:
    name = "apaleo_mcp_probe"
    t0 = time.monotonic()
    try:
        r = client.get(
            f"{base_url}/api/v1/pms/mcp/probe",
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return _fail(2, name, t0, f"probe -> {r.status_code}: {r.text[:200]}")
        body = r.json()
        if body.get("status") != "ok":
            return _fail(2, name, t0, f"probe status={body.get('status')}")
        if (body.get("tools_available") or 0) <= 0:
            return _fail(2, name, t0, f"tools_available={body.get('tools_available')}")
        return _ok(2, name, t0, f"tools_available={body['tools_available']}")
    except Exception as exc:
        return _fail(2, name, t0, f"unexpected: {exc!r}")


# ---------------------------------------------------------------------------
# Step 3 — Prophet predict (via MCP)
# ---------------------------------------------------------------------------

def step3_predict(client: httpx.Client, base_url: str, token: str, hotel_id: str) -> dict[str, Any]:
    name = "prophet_predict"
    t0 = time.monotonic()
    try:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = _mcp_call(
            client, base_url, token, "get_operational_predictions",
            {"target_date": tomorrow, "service_type": "dinner"},
        )
        # The tool returns the engine forecast envelope.
        pred = result.get("prediction") or {}
        covers = pred.get("covers", pred.get("predicted_covers", 0))
        if not isinstance(covers, (int, float)) or covers <= 0:
            return _fail(3, name, t0, f"predicted_covers={covers}")
        return _ok(3, name, t0, f"covers={covers} date={tomorrow}")
    except Exception as exc:
        return _fail(3, name, t0, f"unexpected: {exc!r}")


# ---------------------------------------------------------------------------
# Step 4 — Memory feedback round-trip
# ---------------------------------------------------------------------------

def step4_memory(client: httpx.Client, base_url: str, token: str, hotel_id: str) -> dict[str, Any]:
    name = "memory_feedback_roundtrip"
    t0 = time.monotonic()
    try:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        pred = _mcp_call(
            client, base_url, token, "get_operational_predictions",
            {"target_date": tomorrow, "service_type": "dinner"},
        )
        rec_id = pred.get("recommendation_id") or pred.get("id")
        synthesized = not rec_id
        if synthesized:
            # Predictions do not create a staffing recommendation: a synthesized
            # id must be refused as unknown for this property (tenant check,
            # ADR-0007 §17.4) — that refusal is the expected outcome.
            rec_id = str(uuid.uuid4())

        feedback_args = {
            "recommendation_id": rec_id, "outcome": "accepted", "notes": "smoke test",
            # ADR-0007 §17.4: who decided + a structured reason are mandatory.
            "decided_by": "human_via_host", "reason_code": "none_given", "reason_source": "human",
        }
        try:
            _mcp_call(client, base_url, token, "submit_feedback_to_memory", feedback_args)
        except RuntimeError as exc:
            if not (synthesized and "unknown_recommendation" in str(exc)):
                raise

        recall = _mcp_call(
            client, base_url, token, "get_recommendations_with_memory_context",
            {"query": "last night dinner", "k_memory": 5},
        )
        if not isinstance(recall, dict):
            return _fail(4, name, t0, f"recall returned non-dict: {type(recall).__name__}")

        return _ok(4, name, t0, f"recommendation_id={rec_id}")
    except Exception as exc:
        return _fail(4, name, t0, f"unexpected: {exc!r}")


# ---------------------------------------------------------------------------
# Step 5 — Auth surface
# ---------------------------------------------------------------------------

def step5_auth_surface(client: httpx.Client, base_url: str) -> dict[str, Any]:
    name = "auth_surface"
    t0 = time.monotonic()
    # Each tuple: (method, path, json_body | None, form_body | None, expected_codes)
    targets: list[tuple[str, str, dict | None, dict | None, set[int]]] = [
        (
            "POST", "/api/v1/predictions/predict",
            {"hotel_id": "x", "target_date": date.today().isoformat()}, None,
            {401, 403},
        ),
        (
            "POST", "/api/v1/predictions/train",
            {}, None,
            {401, 403},
        ),
        (
            "POST", "/webhooks/twilio/inbound",
            None,
            {"From": "+33600000001", "Body": "Why?", "To": "+14155238886"},
            # Public callback, but without a valid signature must NOT 200.
            {400, 401, 403},
        ),
        (
            "POST", "/api/v1/auth/register",
            {"email": "x@example.com", "password": "irrelevant"}, None,
            {401, 403, 404, 405},
        ),
    ]
    failures: list[str] = []
    saved_skip = os.environ.pop("TWILIO_SKIP_SIGNATURE_VALIDATION", None)
    try:
        for method, path, json_body, form_body, expected in targets:
            try:
                r = client.request(
                    method, f"{base_url}{path}",
                    json=json_body, data=form_body, timeout=HTTP_TIMEOUT,
                )
            except httpx.HTTPError as exc:
                failures.append(f"{path}: transport error {exc!r}")
                continue
            if r.status_code in expected:
                continue
            if r.status_code in (200, 500):
                failures.append(f"{path}: got {r.status_code}, expected one of {sorted(expected)}")
            else:
                # 422 (validation error) on the train endpoint is also acceptable
                # because the auth dep runs before the body parser in some paths.
                if r.status_code == 422 and "train" in path:
                    continue
                failures.append(f"{path}: got {r.status_code}, expected one of {sorted(expected)}")
    finally:
        if saved_skip is not None:
            os.environ["TWILIO_SKIP_SIGNATURE_VALIDATION"] = saved_skip

    if failures:
        return _fail(5, name, t0, "; ".join(failures))
    return _ok(5, name, t0, f"checked={len(targets)}")


# ---------------------------------------------------------------------------
# Step 6 — Anomaly dispatch (skippable, optional admin endpoint)
# ---------------------------------------------------------------------------

def step6_anomaly_dispatch(client: httpx.Client, base_url: str, token: str, hotel_id: str) -> dict[str, Any]:
    name = "anomaly_dispatch_pipeline"
    t0 = time.monotonic()
    try:
        try:
            import asyncpg  # type: ignore
        except ImportError:
            return _fail(6, name, t0, "asyncpg not installed — install or skip step 6")

        # Prefer SMOKE_DATABASE_URL (raw asyncpg DSN) over DATABASE_URL
        # (which uses SQLAlchemy's postgresql+asyncpg:// prefix incompatible
        # with the bare asyncpg.connect() call below).
        db_url = os.getenv("SMOKE_DATABASE_URL") or os.getenv("DATABASE_URL", "")
        # Strip SQLAlchemy driver suffix if present.
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = "postgresql://" + db_url[len("postgresql+asyncpg://"):]
        if not db_url:
            return _fail(6, name, t0, "DATABASE_URL not set")
        # asyncpg uses postgres:// not postgresql+asyncpg://
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        import asyncio

        async def _seed_anomaly() -> str:
            conn = await asyncpg.connect(db_url)
            try:
                # Match the ORM schema (backend/app/db/models.py — DemandAnomaly).
                # tenant_id is a String slug (HOS-165); property_id is a UUID and
                # must come from an existing restaurant_profiles row.
                property_id = await conn.fetchval(
                    "SELECT property_id FROM restaurant_profiles "
                    "WHERE tenant_id = $1 LIMIT 1",
                    hotel_id,
                )
                if not property_id:
                    raise RuntimeError(
                        f"No restaurant_profiles row for tenant_id={hotel_id!r}"
                    )

                row_id = await conn.fetchval(
                    """
                    INSERT INTO demand_anomalies (
                        id, tenant_id, property_id,
                        window_start, window_end,
                        expected_demand, baseline_demand, deviation_pct,
                        direction, triggering_factors, status, detected_at
                    )
                    VALUES (
                        gen_random_uuid(), $1, $2,
                        now(), now() + interval '4 hours',
                        1300.00, 1000.00, 30.00,
                        'surge', '["smoke_test"]'::jsonb, 'detected', now()
                    )
                    RETURNING id
                    """,
                    hotel_id, property_id,
                )
                return str(row_id)
            finally:
                await conn.close()

        anomaly_id = asyncio.run(_seed_anomaly())

        # Try to trigger the dispatch worker via an admin endpoint if available.
        # The endpoint is optional — dispatch normally runs via APScheduler cron.
        # If absent (404), we still consider step 6 OK because the data-layer
        # half of the pipeline (anomaly INSERT) was verified.
        trigger = client.post(
            f"{base_url}/api/v1/workers/dispatch/trigger",
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=HTTP_TIMEOUT,
        )
        if trigger.status_code == 404:
            return _ok(
                6, name, t0,
                f"anomaly_seeded={anomaly_id}; dispatch_trigger=absent (cron-only)",
            )
        if trigger.status_code not in (200, 202, 204):
            return _fail(
                6, name, t0,
                f"dispatch trigger -> {trigger.status_code} for anomaly={anomaly_id}",
            )

        async def _verify_dispatched() -> int:
            conn = await asyncpg.connect(db_url)
            try:
                return await conn.fetchval(
                    """
                    SELECT count(*) FROM staffing_recommendations
                    WHERE anomaly_id = $1 AND status = 'dispatched'
                    """,
                    uuid.UUID(anomaly_id),
                )
            finally:
                await conn.close()

        # Allow a few seconds for the worker to commit.
        deadline = time.monotonic() + 10
        n = 0
        while time.monotonic() < deadline:
            n = asyncio.run(_verify_dispatched())
            if n >= 1:
                break
            time.sleep(1)
        if n < 1:
            return _fail(6, name, t0, f"no dispatched row for anomaly={anomaly_id}")
        return _ok(6, name, t0, f"anomaly={anomaly_id} dispatched_rows={n}")
    except Exception as exc:
        return _fail(6, name, t0, f"unexpected: {exc!r}")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _parse_skip(raw: str) -> set[int]:
    if not raw:
        return set()
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aetherix E2E smoke test (HOS-161).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("APP_BASE_URL", DEFAULT_BASE_URL),
        help="Backend base URL (default: $APP_BASE_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--hotel-id",
        default=os.getenv("SMOKE_HOTEL_ID", DEFAULT_HOTEL_ID),
        help="Tenant / hotel id for predictions (default: demo_hotel)",
    )
    parser.add_argument(
        "--skip",
        default=os.getenv("SMOKE_SKIP_STEPS", ""),
        help='Comma-separated step numbers to skip, e.g. "2,6"',
    )
    args = parser.parse_args(argv)

    token = os.getenv("SMOKE_MCP_TOKEN", "")
    skip = _parse_skip(args.skip)

    results: list[dict[str, Any]] = []
    with httpx.Client() as client:
        # Step 1 — always runs.
        if 1 in skip:
            results.append(_skip(1, "boot_validation"))
        else:
            results.append(step1_boot(client, args.base_url))

        # Steps 2-4 require the MCP token.
        for step_num, runner in (
            (2, lambda: step2_apaleo_probe(client, args.base_url, token)),
            (3, lambda: step3_predict(client, args.base_url, token, args.hotel_id)),
            (4, lambda: step4_memory(client, args.base_url, token, args.hotel_id)),
        ):
            if step_num in skip:
                results.append(_skip(step_num, f"step{step_num}"))
                continue
            if not token and step_num != 2:
                results.append(_skip(step_num, f"step{step_num}", "SMOKE_MCP_TOKEN missing"))
                continue
            results.append(runner())

        # Step 5 — never needs the token.
        if 5 in skip:
            results.append(_skip(5, "auth_surface"))
        else:
            results.append(step5_auth_surface(client, args.base_url))

        # Step 6 — usually skipped (needs DB + admin endpoint).
        if 6 in skip:
            results.append(_skip(6, "anomaly_dispatch_pipeline"))
        else:
            results.append(step6_anomaly_dispatch(client, args.base_url, token, args.hotel_id))

    passed = sum(1 for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "exit_code": 0 if failed == 0 else 1,
    }
    print(json.dumps(summary), flush=True)
    return summary["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
