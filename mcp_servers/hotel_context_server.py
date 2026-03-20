"""
Hotel Context Layer — Unified MCP Server

This is the "context layer" described in the MCP hotel architecture.
Instead of each hotel system having a separate API integration hardcoded
into every AI agent, each system exposes its capabilities as MCP tools.
AI agents discover and use them through a single protocol.

Design: this server is a thin aggregation layer.
Each tool delegates to its canonical standalone server module so that
fixes and improvements in (e.g.) events_server.py propagate here
automatically — no code duplication.

In a production environment, each section here would be a separate MCP
server shipped by the vendor (Opera, PredictHQ, OpenWeatherMap, …).
"""

import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("HotelContextLayer")


# ═══════════════════════════════════════════════════════════════
# WEATHER SYSTEM
# Canonical implementation: mcp_servers/weather_server.py
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def get_weather(city: str = "Paris", country: str = "FR", date: Optional[str] = None) -> dict:
    """
    Get weather forecast for the hotel's location.
    Returns temperature, conditions, and humidity.
    Impacts outdoor seating demand and beverage preferences.

    Args:
        city: City name (e.g. "Paris")
        country: ISO country code (e.g. "FR")
        date: Date in YYYY-MM-DD format (optional, defaults to today)
    """
    from mcp_servers.weather_server import get_weather as _impl
    return _impl(city=city, country=country, date=date)


# ═══════════════════════════════════════════════════════════════
# EVENTS SYSTEM
# Canonical implementation: mcp_servers/events_server.py
# Geocoding: 50-city static table + OpenWeatherMap API fallback
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def get_local_events(date: str, location: str = "Paris, France", radius: str = "10km") -> list:
    """
    Get local events near the hotel for a specific date.
    Covers concerts, sports, festivals, and conferences.
    High-rank events significantly increase F&B demand.

    Args:
        date: Date in YYYY-MM-DD format
        location: City/location string (e.g. "Paris, France")
        radius: Search radius (e.g. "10km")
    """
    from mcp_servers.events_server import get_local_events as _impl
    return _impl(date=date, location=location, radius=radius)


# ═══════════════════════════════════════════════════════════════
# PMS SYSTEM (Property Management System)
# Canonical implementation: mcp_servers/pms_server.py
# Supports Apaleo OAuth2 with mock fallback
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def get_hotel_reservations(date: str) -> dict:
    """
    Get hotel reservation summary for a date from the PMS.
    Returns occupancy rate, expected guest count, group bookings,
    meal plans, and special requests relevant to F&B planning.

    Args:
        date: Date in YYYY-MM-DD format
    """
    from mcp_servers.pms_server import get_hotel_reservations as _impl
    return _impl(date=date)


@mcp.tool()
def parse_reservation_comments(date: str) -> dict:
    """
    Parse free-text reservation comments for a date and return structured
    F&B signals: dietary restrictions, celebrations, explicit F&B requests,
    and group context.

    This surfaces actionable guest intent buried in unstructured notes —
    dietary needs, anniversary dinners, champagne requests, etc. — without
    staff having to manually read every comment.

    Args:
        date: Date in YYYY-MM-DD format
    """
    from mcp_servers.pms_server import parse_reservation_comments as _impl
    return _impl(date=date)


@mcp.tool()
def create_service_request(guest_id: str, service_type: str, notes: str = "") -> dict:
    """
    Create a service request in the PMS for a guest.
    Used by AI to book spa treatments, room service, housekeeping,
    late checkout, or other services — without staff intervention.

    Args:
        guest_id: Guest identifier (e.g. "G-1042")
        service_type: Type of service ("spa", "room_service", "housekeeping",
                      "late_checkout", "restaurant_reservation", "luggage")
        notes: Additional notes or instructions
    """
    from mcp_servers.pms_server import create_service_request as _impl
    return _impl(guest_id=guest_id, service_type=service_type, notes=notes)


# ═══════════════════════════════════════════════════════════════
# PATTERN MEMORY (Historical F&B Data)
# Primary: Qdrant cloud (QDRANT_URL + MISTRAL_API_KEY)
# Fallback: in-memory keyword scoring on HISTORICAL_SCENARIOS
# ═══════════════════════════════════════════════════════════════

# Kept here as a fallback — used when Qdrant / Mistral are unavailable.
_HISTORICAL_SCENARIOS = [
    {
        "event_type": "concert", "event_name": "Coldplay concert nearby",
        "day": "Saturday", "magnitude": "large", "weather": "clear, 22°C",
        "actual_covers": 95, "usual_covers": 60, "variance": "+58%",
        "staffing": 6, "notes": "High demand from concert attendees, peak at 8pm"
    },
    {
        "event_type": "festival", "event_name": "Jazz festival downtown",
        "day": "Saturday", "magnitude": "medium", "weather": "sunny, 20°C",
        "actual_covers": 82, "usual_covers": 60, "variance": "+37%",
        "staffing": 5, "notes": "Steady flow throughout evening"
    },
    {
        "event_type": "sports", "event_name": "Football match nearby",
        "day": "Friday", "magnitude": "large", "weather": "cloudy, 18°C",
        "actual_covers": 88, "usual_covers": 55, "variance": "+60%",
        "staffing": 6, "notes": "Pre-match crowd, quick service needed"
    },
    {
        "event_type": "festival", "event_name": "Food festival",
        "day": "Sunday", "magnitude": "medium", "weather": "sunny, 24°C",
        "actual_covers": 70, "usual_covers": 45, "variance": "+56%",
        "staffing": 4, "notes": "Families, relaxed pace, outdoor seating busy"
    },
    {
        "event_type": "concert", "event_name": "Rock concert",
        "day": "Saturday", "magnitude": "large", "weather": "clear, 23°C",
        "actual_covers": 92, "usual_covers": 60, "variance": "+53%",
        "staffing": 6, "notes": "Young crowd, high energy, bar demand very high"
    },
    {
        "event_type": "wedding", "event_name": "In-house wedding",
        "day": "Saturday", "magnitude": "small", "weather": "sunny, 26°C",
        "actual_covers": 75, "usual_covers": 60, "variance": "+25%",
        "staffing": 5, "notes": "In-house wedding party, private dining room"
    },
    {
        "event_type": "corporate", "event_name": "Conference dinner",
        "day": "Friday", "magnitude": "medium", "weather": "clear, 25°C",
        "actual_covers": 78, "usual_covers": 55, "variance": "+42%",
        "staffing": 5, "notes": "Business crowd, wine focus, late seating"
    },
    {
        "event_type": "sports", "event_name": "Marathon event",
        "day": "Saturday", "magnitude": "large", "weather": "cool, 17°C",
        "actual_covers": 65, "usual_covers": 60, "variance": "+8%",
        "staffing": 4, "notes": "Post-race crowd arrives late, carb-heavy orders"
    },
    {
        "event_type": "holiday", "event_name": "Halloween weekend",
        "day": "Saturday", "magnitude": "medium", "weather": "rainy, 12°C",
        "actual_covers": 68, "usual_covers": 60, "variance": "+13%",
        "staffing": 4, "notes": "Theme-driven bookings, cocktail demand up"
    },
    {
        "event_type": "festival", "event_name": "Summer music festival",
        "day": "Saturday", "magnitude": "large", "weather": "hot, 30°C",
        "actual_covers": 85, "usual_covers": 60, "variance": "+42%",
        "staffing": 5, "notes": "Hot weather, drinks demand very high, light meals"
    },
    {
        "event_type": "holiday", "event_name": "Christmas Eve dinner",
        "day": "Wednesday", "magnitude": "large", "weather": "clear, 4°C",
        "actual_covers": 91, "usual_covers": 60, "variance": "+52%",
        "staffing": 6, "notes": "Full-board guests + VIP walk-ins, champagne upsell"
    },
    {
        "event_type": "holiday", "event_name": "Thanksgiving dinner",
        "day": "Thursday", "magnitude": "large", "weather": "cool, 10°C",
        "actual_covers": 87, "usual_covers": 60, "variance": "+45%",
        "staffing": 6, "notes": "Set menu, high wine demand, early service at 6pm"
    },
]


def _keyword_search(event_description: str, event_type: Optional[str], limit: int) -> list:
    """Fast keyword-based scoring — fallback when Qdrant is unavailable."""
    desc_lower = event_description.lower()
    keywords = [
        "concert", "festival", "sports", "football", "match", "wedding",
        "corporate", "conference", "marathon", "halloween", "music",
        "jazz", "rock", "summer", "holiday", "christmas", "thanksgiving",
    ]
    scored = []
    for scenario in _HISTORICAL_SCENARIOS:
        score = 0.0
        if event_type and scenario["event_type"] == event_type.lower():
            score += 0.5
        elif scenario["event_type"] in desc_lower:
            score += 0.35
        for kw in keywords:
            if kw in desc_lower and kw in scenario["event_name"].lower():
                score += 0.15
        if any(w in desc_lower for w in ["large", "major", "big", "massive"]):
            if scenario["magnitude"] == "large":
                score += 0.2
        if any(w in desc_lower for w in ["saturday", "friday"]):
            if scenario["day"] in ["Saturday", "Friday"]:
                score += 0.1
        scored.append((score, scenario))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"rank": i + 1, "similarity_score": round(score, 2), "scenario": s}
        for i, (score, s) in enumerate(scored[:limit])
    ]


def _qdrant_search(event_description: str, limit: int) -> list:
    """
    Vector search in Qdrant cloud.
    Requires QDRANT_URL and MISTRAL_API_KEY.
    Returns [] on any error so the caller falls back to keyword search.
    """
    qdrant_url  = os.getenv("QDRANT_URL")
    mistral_key = os.getenv("MISTRAL_API_KEY")

    if not qdrant_url or not mistral_key:
        return []

    try:
        from mistralai import Mistral
        from qdrant_client import QdrantClient

        mistral = Mistral(api_key=mistral_key)
        emb_resp = mistral.embeddings.create(
            model="mistral-embed",
            inputs=[event_description],
        )
        vector = emb_resp.data[0].embedding

        qdrant = QdrantClient(
            url=qdrant_url,
            api_key=os.getenv("QDRANT_API_KEY") or None,
        )
        results = qdrant.search(
            collection_name="hospitality_patterns",
            query_vector=vector,
            limit=limit,
        )
        if results:
            return [
                {
                    "rank":             i + 1,
                    "similarity_score": round(r.score, 2),
                    "scenario":         r.payload,
                }
                for i, r in enumerate(results)
            ]
    except Exception:
        pass

    return []


@mcp.tool()
def search_historical_patterns(
    event_description: str,
    event_type: Optional[str] = None,
    limit: int = 3,
) -> list:
    """
    Search historical F&B demand patterns similar to the described event.
    Returns past scenarios with actual covers, staffing numbers, and variance.
    Use this to ground predictions in real historical outcomes.

    Primary path: Qdrant vector search (QDRANT_URL + MISTRAL_API_KEY).
    Fallback: keyword scoring on built-in historical scenarios.

    Args:
        event_description: Natural language description of the event context
        event_type: Optional filter — concert, festival, sports, corporate,
                    wedding, holiday
        limit: Number of similar patterns to return (default 3)
    """
    results = _qdrant_search(event_description, limit)
    if results:
        return results
    return _keyword_search(event_description, event_type, limit)


if __name__ == "__main__":
    mcp.run()
