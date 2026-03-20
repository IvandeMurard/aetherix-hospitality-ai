"""
End-to-end scenario runner — F&B Operations Agent

Exercises the full data pipeline without requiring any API keys:
  1. PMS           → reservation summary + comment signals
  2. Events        → local events near hotel
  3. Weather       → forecast
  4. Patterns      → historical similarity search
  5. Prediction    → structured output (LLM-formatted if ANTHROPIC_API_KEY set,
                     rule-based heuristic otherwise)

Usage:
    python run_scenario.py
    python run_scenario.py --date 2026-04-11 --location "Paris, France"
    python run_scenario.py --date 2026-12-24 --city Paris
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATE_FMT = "%Y-%m-%d"


# ---------------------------------------------------------------------------
# Step functions (each calls one MCP tool via its Python function directly)
# ---------------------------------------------------------------------------

def step_reservations(date: str) -> dict:
    from mcp_servers.pms_server import get_hotel_reservations
    return get_hotel_reservations(date=date)


def step_fb_context(date: str) -> dict:
    from mcp_servers.pms_server import get_fb_forecast_context
    return get_fb_forecast_context(date=date)


def step_comment_signals(date: str) -> dict:
    from mcp_servers.pms_server import parse_reservation_comments
    return parse_reservation_comments(date=date)


def step_events(date: str, location: str) -> list:
    from mcp_servers.events_server import get_local_events
    return get_local_events(date=date, location=location)


def step_weather(city: str) -> dict:
    from mcp_servers.weather_server import get_weather
    return get_weather(city=city)


def step_patterns(event_description: str) -> list:
    from mcp_servers.hotel_context_server import search_historical_patterns
    return search_historical_patterns(event_description=event_description, limit=3)


# ---------------------------------------------------------------------------
# Heuristic prediction (runs when no ANTHROPIC_API_KEY is available)
# ---------------------------------------------------------------------------

def _heuristic_predict(
    date: str,
    reservations: dict,
    fb_context: dict,
    events: list,
    weather: dict,
    patterns: list,
    comment_signals: dict,
) -> dict:
    """Rule-based F&B prediction — deterministic, no LLM required."""
    base_covers = int(reservations.get("expected_guests", 60) * 0.65)

    # Event uplift
    event_boost = 0
    for ev in events:
        rank = ev.get("rank", 0)
        if rank >= 70:
            event_boost += 35
        elif rank >= 50:
            event_boost += 20
        else:
            event_boost += 8

    # Weather adjustment
    temp = weather.get("temperature", 18)
    desc = weather.get("description", "").lower()
    weather_mod = 0
    if "rain" in desc or "storm" in desc:
        weather_mod = -5
    elif temp >= 22 and "sun" in desc:
        weather_mod = 10

    # Pattern anchor
    anchor_covers = base_covers
    if patterns:
        best = patterns[0]["scenario"]
        anchor_covers = int(best["actual_covers"] * 0.95 + base_covers * 0.05)

    # Group meal commitments
    group_boost = 0
    for g in fb_context.get("group_meal_commitments", []):
        group_boost += int(g.get("size", 0) * 0.8)

    # Celebration / upsell signals from comments
    celebration_count = sum(comment_signals.get("celebration_summary", {}).values())
    upsell_count = sum(
        v for k, v in comment_signals.get("fb_request_summary", {}).items()
        if k in ("champagne", "cake", "restaurant_reservation")
    )

    expected_covers = max(
        30,
        int((anchor_covers + event_boost + weather_mod + group_boost) * 1.0)
    )

    # Staff: roughly 1 per 15 covers, min 3, max 10
    staff = max(3, min(10, round(expected_covers / 15)))

    # Confidence
    conf_base = 70
    if patterns and patterns[0]["similarity_score"] >= 0.4:
        conf_base += 10
    if events:
        conf_base += 5
    if weather.get("source") != "mock":
        conf_base += 5
    confidence = min(95, conf_base)

    key_factors = []
    day = datetime.strptime(date, DATE_FMT).strftime("%A")
    occupancy = reservations.get("occupancy_rate", 0)
    key_factors.append(f"{day} — hotel occupancy {occupancy:.0f}%")

    if events:
        ev_titles = ", ".join(e["title"] for e in events[:2])
        key_factors.append(f"Local events: {ev_titles}")

    key_factors.append(f"Weather: {weather.get('description', 'n/a')}")

    if group_boost:
        groups = fb_context.get("group_meal_commitments", [])
        for g in groups[:2]:
            key_factors.append(
                f"Group commitment: {g['group']} ({g['size']} guests, {g['meal']})"
            )

    if patterns:
        p = patterns[0]["scenario"]
        key_factors.append(
            f"Closest pattern: \"{p['event_name']}\" — {p['actual_covers']} covers, "
            f"{p['staffing']} staff (similarity {patterns[0]['similarity_score']:.2f})"
        )

    if celebration_count:
        key_factors.append(
            f"{celebration_count} celebration reservation(s) — champagne / cake upsell opportunity"
        )

    dietary = fb_context.get("dietary_restrictions", {})
    dietary_total = sum(dietary.values())
    if dietary_total:
        key_factors.append(f"Dietary requirements for {dietary_total} guests — prep special menus")

    actions = []
    if expected_covers > 80:
        actions.append("Open private dining room or extend restaurant floor plan")
    if group_boost:
        actions.append("Confirm set-menu quantities with kitchen by 14:00")
    if upsell_count:
        actions.append(f"Brief front-desk on {upsell_count} champagne/cake requests — room delivery coordination")
    if dietary_total:
        actions.append(f"Prepare {dietary_total} special dietary covers (check allergen log)")
    actions.append(f"Target mise en place for {expected_covers + 10} covers as buffer")

    return {
        "expected_covers": expected_covers,
        "recommended_staff": staff,
        "confidence": confidence,
        "key_factors": key_factors[:5],
        "operational_recommendations": actions,
        "method": "heuristic (set ANTHROPIC_API_KEY for Claude-powered prediction)",
    }


# ---------------------------------------------------------------------------
# Claude-powered prediction (when ANTHROPIC_API_KEY is available)
# ---------------------------------------------------------------------------

async def _claude_predict(date: str, location: str, city: str) -> str:
    """Run the full MCP agent with Claude."""
    from mcp_agent import run_hotel_mcp_agent
    return await run_hotel_mcp_agent(date, location, city)


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def _header(title: str) -> None:
    print(f"\n  {'─' * 56}")
    print(f"  {title}")
    print(f"  {'─' * 56}")


def _print_result(result: dict, date: str) -> None:
    print(f"\n{'═' * 60}")
    print("  F&B DEMAND FORECAST")
    print(f"{'═' * 60}")
    print(f"  Date       : {datetime.strptime(date, DATE_FMT).strftime('%A, %d %B %Y')}")
    print()
    print(f"  Expected covers     : {result['expected_covers']}")
    print(f"  Recommended staff   : {result['recommended_staff']}")
    print(f"  Confidence          : {result['confidence']}%")
    print()
    print("  Key factors:")
    for f in result.get("key_factors", []):
        print(f"    · {f}")
    print()
    print("  Operational recommendations:")
    for a in result.get("operational_recommendations", []):
        print(f"    → {a}")
    print()
    print(f"  Method: {result.get('method', 'unknown')}")
    print(f"{'═' * 60}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="F&B Operations Agent — end-to-end scenario runner"
    )
    parser.add_argument("--date", default=None,
                        help="Date (YYYY-MM-DD). Defaults to tomorrow.")
    parser.add_argument("--location", default="Paris, France",
                        help="Hotel location (default: 'Paris, France')")
    parser.add_argument("--city", default="Paris",
                        help="City for weather lookup (default: Paris)")
    args = parser.parse_args()

    from datetime import timedelta
    date = args.date or (datetime.now() + timedelta(days=1)).strftime(DATE_FMT)
    location = args.location
    city = args.city

    has_claude = bool(os.getenv("ANTHROPIC_API_KEY"))

    print(f"\n{'═' * 60}")
    print("  F&B OPERATIONS AGENT  —  End-to-End Scenario")
    print(f"{'═' * 60}")
    print(f"  Date     : {date}")
    print(f"  Location : {location}")
    print(f"  Mode     : {'Claude MCP (ANTHROPIC_API_KEY set)' if has_claude else 'Heuristic (mock data, no keys needed)'}")

    if has_claude:
        asyncio.run(_claude_predict(date, location, city))
        return

    # ── Heuristic path ────────────────────────────────────────────
    print()

    _header("1 / 5  PMS — Reservations")
    reservations = step_reservations(date)
    print(f"    Occupancy  : {reservations.get('occupancy_rate', 'n/a')}%")
    print(f"    Guests     : {reservations.get('expected_guests', 'n/a')}")
    print(f"    Groups     : {len(reservations.get('groups', []))}")
    print(f"    Source     : {reservations.get('source', 'n/a')}")

    fb_context = step_fb_context(date)
    comment_signals = step_comment_signals(date)
    if comment_signals.get("reservations_with_signals", 0):
        print(f"    Comments   : {comment_signals['reservations_with_signals']} reservations with F&B signals")
        if comment_signals.get("celebration_summary"):
            print(f"    Celebrations: {comment_signals['celebration_summary']}")
        if comment_signals.get("dietary_summary"):
            print(f"    Dietary req : {comment_signals['dietary_summary']}")

    _header("2 / 5  Events — Local demand drivers")
    events = step_events(date, location)
    if events:
        for ev in events[:3]:
            print(f"    · [{ev.get('rank', '?'):>3}] {ev['title']} ({ev.get('category', '?')})")
    else:
        print("    (none found)")

    _header("3 / 5  Weather forecast")
    weather = step_weather(city)
    print(f"    {weather.get('description', 'n/a')}  |  humidity {weather.get('humidity', 'n/a')}%  |  source: {weather.get('source', 'n/a')}")

    _header("4 / 5  Historical patterns (nearest match)")
    event_desc = (
        f"{'weekend' if datetime.strptime(date, DATE_FMT).weekday() >= 4 else 'weekday'} "
        + (events[0]["title"] if events else "business day")
    )
    patterns = step_patterns(event_desc)
    if patterns:
        p = patterns[0]["scenario"]
        print(f"    Closest: \"{p['event_name']}\"")
        print(f"    Result : {p['actual_covers']} covers, {p['staffing']} staff, variance {p['variance']}")
        print(f"    Score  : {patterns[0]['similarity_score']:.2f}")

    _header("5 / 5  Prediction")
    result = _heuristic_predict(
        date=date,
        reservations=reservations,
        fb_context=fb_context,
        events=events,
        weather=weather,
        patterns=patterns,
        comment_signals=comment_signals,
    )
    _print_result(result, date)


if __name__ == "__main__":
    main()
