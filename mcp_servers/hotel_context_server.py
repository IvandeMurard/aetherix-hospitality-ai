"""
Hotel Context Layer — Unified MCP Server

This is the "context layer" described in the MCP hotel architecture.
Instead of each hotel system having a separate API integration hardcoded
into every AI agent, each system exposes its capabilities as MCP tools.
AI agents discover and use them through a single protocol.

In a production environment, each tool here would be a separate MCP server
shipped by the vendor (e.g., Opera ships pms_server, PredictHQ ships
events_server). This file shows what the unified context layer looks like
when aggregated — what the AI agent actually sees.
"""

import os
import json
import random
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("HotelContextLayer")


# ═══════════════════════════════════════════════════════════════
# WEATHER SYSTEM
# In production: OpenWeatherMap or similar ships this MCP server
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
    api_key = os.getenv("OPENWEATHER_API_KEY") or os.getenv("WEATHER_API_KEY")

    if not api_key:
        conditions = ["Sunny", "Partly cloudy", "Overcast", "Light rain", "Clear"]
        temps = [8, 12, 15, 18, 22, 25]
        condition = random.choice(conditions)
        temp = random.choice(temps)
        return {
            "description": f"{condition}, {temp}°C",
            "temperature": temp,
            "feels_like": temp - 2,
            "humidity": random.randint(50, 80),
            "city": city,
            "source": "mock"
        }

    base_url = "https://api.openweathermap.org/data/2.5"
    try:
        if not date or date == datetime.now().strftime("%Y-%m-%d"):
            url = f"{base_url}/weather"
        else:
            url = f"{base_url}/forecast"

        params = {
            "q": f"{city},{country}",
            "appid": api_key,
            "units": "metric",
            "lang": "en"
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            weather_data = data.get("list", [data])[0]
            temp = weather_data["main"]["temp"]
            desc = weather_data["weather"][0]["description"]
            return {
                "description": f"{desc.capitalize()}, {int(temp)}°C",
                "temperature": int(temp),
                "feels_like": int(weather_data["main"]["feels_like"]),
                "humidity": weather_data["main"]["humidity"],
                "city": city,
                "source": "openweathermap"
            }
    except Exception:
        pass

    return {
        "description": "Partly cloudy, 18°C",
        "temperature": 18,
        "humidity": 65,
        "city": city,
        "source": "mock_fallback"
    }


# ═══════════════════════════════════════════════════════════════
# EVENTS SYSTEM
# In production: PredictHQ ships this MCP server
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
    api_key = os.getenv("PREDICTHQ_API_KEY") or os.getenv("PREDICTHQ_ACCESS_TOKEN")

    if not api_key:
        day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        if day in ["Friday", "Saturday"]:
            return [
                {"title": "Weekend concert at local venue", "category": "concerts", "rank": 75},
                {"title": "Sports event at stadium", "category": "sports", "rank": 60}
            ]
        if day == "Sunday":
            return [
                {"title": "Sunday market and community fair", "category": "community", "rank": 40}
            ]
        return [
            {"title": "Business conference at convention center", "category": "conferences", "rank": 45}
        ]

    try:
        origin = "48.8566,2.3522"  # Paris default
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        params = {
            "start": f"{date}T00:00:00",
            "end": f"{date}T23:59:59",
            "location_around.origin": origin,
            "location_around.radius": radius,
            "limit": 10,
            "category": "concerts,sports,festivals,conferences,performing-arts"
        }
        response = requests.get(
            "https://api.predicthq.com/v1/events/",
            headers=headers,
            params=params,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return [
                {
                    "title": e.get("title", "Unknown"),
                    "category": e.get("category", "unknown"),
                    "rank": e.get("rank", 0)
                }
                for e in data.get("results", [])
            ]
    except Exception:
        pass

    return []


# ═══════════════════════════════════════════════════════════════
# PMS SYSTEM (Property Management System)
# In production: Opera / Mews / Apaleo / Cloudbeds ships this MCP server
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
    day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
    base_occupancy = 0.85 if day in ["Friday", "Saturday"] else 0.70 if day == "Sunday" else 0.62
    occupancy = min(1.0, max(0.0, base_occupancy + random.uniform(-0.08, 0.08)))
    total_rooms = 120
    occupied = int(total_rooms * occupancy)

    groups = []
    if day not in ["Saturday", "Sunday"]:
        groups = [{"name": "Tech conference group", "size": 28, "meal_plan": "half-board"}]
    elif day == "Saturday":
        groups = [{"name": "Wedding party", "size": 45, "meal_plan": "full-board"}]

    return {
        "date": date,
        "day_of_week": day,
        "total_rooms": total_rooms,
        "occupied_rooms": occupied,
        "occupancy_rate": round(occupancy * 100, 1),
        "expected_guests": occupied + int(occupied * 0.15),
        "groups": groups,
        "special_requests": {
            "dietary_restrictions": random.randint(5, 20),
            "late_checkout": random.randint(3, 12),
            "early_checkin": random.randint(2, 8)
        },
        "source": "mock_pms"
    }


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
    import uuid
    ticket_id = f"SR-{uuid.uuid4().hex[:8].upper()}"
    routing = {
        "spa": "spa_desk",
        "room_service": "kitchen",
        "housekeeping": "housekeeping",
        "late_checkout": "front_desk",
        "restaurant_reservation": "restaurant_host",
        "luggage": "concierge"
    }
    return {
        "ticket_id": ticket_id,
        "guest_id": guest_id,
        "service_type": service_type,
        "notes": notes,
        "status": "created",
        "assigned_to": routing.get(service_type, "front_desk"),
        "created_at": datetime.now().isoformat(),
        "estimated_response_minutes": 5,
        "source": "mock_pms"
    }


# ═══════════════════════════════════════════════════════════════
# PATTERN MEMORY (Historical F&B Data)
# In production: your data warehouse or CDP ships this MCP server
# ═══════════════════════════════════════════════════════════════

HISTORICAL_SCENARIOS = [
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
]


@mcp.tool()
def search_historical_patterns(
    event_description: str,
    event_type: Optional[str] = None,
    limit: int = 3
) -> list:
    """
    Search historical F&B demand patterns similar to the described event.
    Returns past scenarios with actual covers, staffing numbers, and variance.
    Use this to ground predictions in real historical outcomes.

    Args:
        event_description: Natural language description of the event context
        event_type: Optional filter — concert, festival, sports, corporate,
                    wedding, holiday
        limit: Number of similar patterns to return (default 3)
    """
    desc_lower = event_description.lower()
    scored = []

    for scenario in HISTORICAL_SCENARIOS:
        score = 0.0

        if event_type and scenario["event_type"] == event_type.lower():
            score += 0.5
        elif scenario["event_type"] in desc_lower:
            score += 0.35

        keywords = [
            "concert", "festival", "sports", "football", "match", "wedding",
            "corporate", "conference", "marathon", "halloween", "music",
            "jazz", "rock", "summer", "holiday"
        ]
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


if __name__ == "__main__":
    mcp.run()
