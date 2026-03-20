"""
Smoke Test — F&B Operations Agent

Validates the entire stack using mock fallbacks (no real API keys needed).
Each check is independent; failures are reported at the end.

Usage:
    python smoke_test.py
"""

import os
import sys
import traceback
from datetime import datetime, timedelta

# Ensure we run from repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── helpers ──────────────────────────────────────────────────────────────────

PASS = "  [OK]"
FAIL = "  [FAIL]"
SKIP = "  [SKIP]"

results: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    """Run fn(); record pass/fail."""
    try:
        fn()
        results.append((name, True, ""))
        print(f"{PASS}  {name}")
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        results.append((name, False, msg))
        print(f"{FAIL}  {name}")
        print(f"         {msg}")


# ── 1. Registry ───────────────────────────────────────────────────────────────

def test_registry_imports():
    from mcp_servers.registry import REGISTRY, get_available_systems, all_required_available, REQUIRED_SYSTEMS
    assert REGISTRY, "REGISTRY is empty"
    assert REQUIRED_SYSTEMS, "REQUIRED_SYSTEMS is empty"
    avail = get_available_systems()
    for name in REQUIRED_SYSTEMS:
        assert avail.get(name), f"Required system '{name}' not available (file missing or disabled)"


# ── 2. Weather mock ───────────────────────────────────────────────────────────

def test_weather_mock():
    # Ensure no real key so we exercise mock path
    os.environ.pop("OPENWEATHER_API_KEY", None)
    os.environ.pop("WEATHER_API_KEY", None)
    from mcp_servers.weather_server import get_weather
    result = get_weather(city="Paris", country="FR")
    assert "temperature" in result, f"Missing 'temperature': {result}"
    assert result["source"] == "mock", f"Expected mock source, got: {result['source']}"


# ── 3. Events mock ────────────────────────────────────────────────────────────

def test_events_mock():
    os.environ.pop("PREDICTHQ_API_KEY", None)
    os.environ.pop("PREDICTHQ_ACCESS_TOKEN", None)
    from mcp_servers.events_server import get_local_events
    # Use a Saturday for richer mock data
    saturday = "2025-12-27"
    events = get_local_events(date=saturday, location="Paris, France")
    assert isinstance(events, list) and len(events) > 0, f"Expected events list, got: {events}"
    assert "title" in events[0], f"Missing 'title' in event: {events[0]}"


# ── 4. PMS mock ───────────────────────────────────────────────────────────────

def test_pms_mock():
    os.environ.pop("APALEO_CLIENT_ID", None)
    os.environ.pop("APALEO_CLIENT_SECRET", None)
    from mcp_servers.pms_server import get_hotel_reservations
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    result = get_hotel_reservations(date=tomorrow)
    assert isinstance(result, dict), f"Expected dict, got: {type(result)}"
    assert any(k in result for k in ("total_reservations", "reservations", "occupied_rooms", "expected_guests")), \
        f"Unexpected shape: {result}"


# ── 5. PMS F&B context mock ───────────────────────────────────────────────────

def test_pms_fb_context():
    os.environ.pop("APALEO_CLIENT_ID", None)
    os.environ.pop("APALEO_CLIENT_SECRET", None)
    from mcp_servers.pms_server import get_fb_forecast_context
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    result = get_fb_forecast_context(date=tomorrow)
    assert isinstance(result, dict), f"Expected dict, got: {type(result)}"


# ── 5b. Reservation comment parsing ──────────────────────────────────────────

def test_comment_parsing_direct():
    from mcp_servers.pms_server import _parse_comment_signals
    signals = _parse_comment_signals(
        "Anniversary dinner — champagne please. Vegan menu required."
    )
    assert "vegan" in signals["dietary"], f"vegan not found: {signals['dietary']}"
    assert "anniversary" in signals["celebrations"], f"anniversary not found: {signals['celebrations']}"
    assert "champagne" in signals["fb_requests"], f"champagne not found: {signals['fb_requests']}"


def test_parse_reservation_comments_mock():
    os.environ.pop("APALEO_CLIENT_ID", None)
    os.environ.pop("APALEO_CLIENT_SECRET", None)
    from mcp_servers.pms_server import parse_reservation_comments
    # Saturday — richer mock
    result = parse_reservation_comments(date="2026-04-11")
    assert "dietary_summary" in result, f"Missing dietary_summary: {result}"
    assert "celebration_summary" in result, f"Missing celebration_summary: {result}"
    assert "details" in result and len(result["details"]) > 0, "No details returned"


# ── 6. Hotel context server imports ──────────────────────────────────────────

def test_hotel_context_server_importable():
    import mcp_servers.hotel_context_server as hcs
    # Verify at least the mcp object exists
    assert hasattr(hcs, "mcp"), "hotel_context_server.mcp not found"


# ── 7. Search server importable ───────────────────────────────────────────────

def test_search_server_importable():
    import mcp_servers.search_server as ss
    assert hasattr(ss, "mcp"), "search_server.mcp not found"


# ── 8. Agent router imports ───────────────────────────────────────────────────

def test_agent_router_imports():
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("agent_router", "agent_router.py")
    mod = importlib.util.module_from_spec(spec)
    # Don't execute (it calls main), just load module-level code
    # We just need the file to be syntactically valid
    import ast
    with open("agent_router.py") as f:
        ast.parse(f.read())


# ── 9. Seed data imports ──────────────────────────────────────────────────────

def test_seed_data_importable():
    import ast
    with open("seed_data.py") as f:
        ast.parse(f.read())


# ── 10. API imports ───────────────────────────────────────────────────────────

def test_api_importable():
    import ast
    with open("api.py") as f:
        ast.parse(f.read())


# ── 11. Demo app importable ───────────────────────────────────────────────────

def test_demo_app_importable():
    import ast
    with open("demo_app.py") as f:
        ast.parse(f.read())


# ── 12. Credential summary ────────────────────────────────────────────────────

def print_credential_summary():
    keys = {
        "ANTHROPIC_API_KEY": "Claude MCP agent (primary path)",
        "MISTRAL_API_KEY":   "Direct agent (fallback)",
        "QDRANT_URL":        "Qdrant vector memory",
        "APALEO_CLIENT_ID":  "Apaleo PMS (real reservations)",
        "PREDICTHQ_API_KEY": "PredictHQ events (real events)",
        "OPENWEATHER_API_KEY": "OpenWeatherMap (real weather)",
        "SERPER_API_KEY":    "Serper web search",
        "ELEVENLABS_API_KEY": "ElevenLabs voice",
    }
    from dotenv import dotenv_values
    env_file = dotenv_values(".env")
    print()
    print("  Credential status (.env + environment):")
    print(f"  {'Key':<26}  {'Status':<12}  Note")
    print(f"  {'-'*26}  {'-'*12}  {'-'*36}")
    for key, note in keys.items():
        value = os.getenv(key) or env_file.get(key, "")
        is_set = bool(value and value not in ("", "your-client-id", "your-client-secret"))
        tag = "set" if is_set else "NOT SET"
        print(f"  {key:<26}  {tag:<12}  {note}")
    print()


# ── run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("=" * 64)
    print("  SMOKE TEST — F&B Operations Agent")
    print("=" * 64)
    print()

    check("Registry: all required servers present",     test_registry_imports)
    check("Weather: mock fallback returns valid data",  test_weather_mock)
    check("Events: mock fallback returns valid data",   test_events_mock)
    check("PMS: mock reservations return valid data",   test_pms_mock)
    check("PMS: F&B forecast context returns dict",     test_pms_fb_context)
    check("Comment parser: signals extracted correctly", test_comment_parsing_direct)
    check("Comment parser: mock tool returns structure", test_parse_reservation_comments_mock)
    check("Hotel context server: importable",           test_hotel_context_server_importable)
    check("Search server: importable",                  test_search_server_importable)
    check("Agent router: valid syntax",                 test_agent_router_imports)
    check("seed_data.py: valid syntax",                 test_seed_data_importable)
    check("api.py: valid syntax",                       test_api_importable)
    check("demo_app.py: valid syntax",                  test_demo_app_importable)

    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)

    print()
    print("=" * 64)
    print(f"  {passed}/{total} checks passed")
    print("=" * 64)

    print_credential_summary()

    sys.exit(0 if passed == total else 1)
