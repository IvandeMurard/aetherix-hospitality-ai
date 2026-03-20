"""
Events MCP Server

Standalone server showing what an event intelligence vendor (e.g. PredictHQ)
would ship as their MCP server. Exposes local event data for AI agents to
understand demand drivers without any custom integration code.

Run standalone: python mcp_servers/events_server.py
"""

import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("EventsServer")


# ── Geocoding helper ──────────────────────────────────────────────────────────
# Static table covers 50+ hotel markets (instant lookup, no API call).
# Falls back to OpenWeatherMap Geocoding API for unlisted cities.

_CITY_COORDS: dict = {
    "paris":          (48.8566,   2.3522),
    "london":         (51.5074,  -0.1278),
    "new york":       (40.7128,  -74.0060),
    "berlin":         (52.5200,  13.4050),
    "amsterdam":      (52.3676,   4.9041),
    "madrid":         (40.4168,  -3.7038),
    "rome":           (41.9028,  12.4964),
    "barcelona":      (41.3851,   2.1734),
    "lisbon":         (38.7223,  -9.1393),
    "dubai":          (25.2048,  55.2708),
    "tokyo":          (35.6762, 139.6503),
    "singapore":      ( 1.3521, 103.8198),
    "hong kong":      (22.3193, 114.1694),
    "sydney":         (-33.8688, 151.2093),
    "los angeles":    (34.0522, -118.2437),
    "chicago":        (41.8781,  -87.6298),
    "miami":          (25.7617,  -80.1918),
    "toronto":        (43.6532,  -79.3832),
    "montreal":       (45.5017,  -73.5673),
    "zurich":         (47.3769,   8.5417),
    "geneva":         (46.2044,   6.1432),
    "vienna":         (48.2082,  16.3738),
    "prague":         (50.0755,  14.4378),
    "warsaw":         (52.2297,  21.0122),
    "budapest":       (47.4979,  19.0402),
    "stockholm":      (59.3293,  18.0686),
    "copenhagen":     (55.6761,  12.5683),
    "oslo":           (59.9139,  10.7522),
    "helsinki":       (60.1699,  24.9384),
    "brussels":       (50.8503,   4.3517),
    "milan":          (45.4654,   9.1859),
    "munich":         (48.1351,  11.5820),
    "frankfurt":      (50.1109,   8.6821),
    "hamburg":        (53.5753,  10.0153),
    "istanbul":       (41.0082,  28.9784),
    "athens":         (37.9838,  23.7275),
    "cairo":          (30.0444,  31.2357),
    "cape town":      (-33.9249,  18.4241),
    "nairobi":        (-1.2921,  36.8219),
    "bangkok":        (13.7563, 100.5018),
    "kuala lumpur":   ( 3.1390, 101.6869),
    "jakarta":        (-6.2088, 106.8456),
    "mumbai":         (19.0760,  72.8777),
    "delhi":          (28.7041,  77.1025),
    "seoul":          (37.5665, 126.9780),
    "beijing":        (39.9042, 116.4074),
    "shanghai":       (31.2304, 121.4737),
    "mexico city":    (19.4326,  -99.1332),
    "buenos aires":   (-34.6037,  -58.3816),
    "sao paulo":      (-23.5505,  -46.6333),
    "rio de janeiro": (-22.9068, -43.1729),
}


def _location_to_coords(location: str) -> tuple:
    """
    Convert a location string to (lat, lon).

    Priority:
      1. Static lookup  — instant, no API call, 50+ cities
      2. OpenWeatherMap Geocoding API — for unlisted cities (needs OPENWEATHER_API_KEY)
      3. Paris fallback with stderr warning
    """
    loc_lower = location.lower()

    for city, coords in _CITY_COORDS.items():
        if city in loc_lower:
            return coords

    api_key = os.getenv("OPENWEATHER_API_KEY") or os.getenv("WEATHER_API_KEY")
    if api_key:
        try:
            resp = requests.get(
                "http://api.openweathermap.org/geo/1.0/direct",
                params={"q": location, "limit": 1, "appid": api_key},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception:
            pass

    print(
        f"[events_server] WARNING: could not geocode '{location}' — "
        "defaulting to Paris coords. Set OPENWEATHER_API_KEY for auto-geocoding.",
        file=sys.stderr,
    )
    return 48.8566, 2.3522


def _mock_events(date: str) -> list:
    """Day-of-week based mock — used when no API key is set or on API failure."""
    day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
    if day in ["Friday", "Saturday"]:
        return [
            {"title": "Weekend concert at local venue", "category": "concerts",  "rank": 75},
            {"title": "Sports event at stadium",        "category": "sports",    "rank": 60},
        ]
    if day == "Sunday":
        return [{"title": "Sunday market and community fair", "category": "community", "rank": 40}]
    return [{"title": "Business conference at convention center", "category": "conferences", "rank": 45}]


@mcp.tool()
def get_local_events(date: str, location: str = "Paris, France", radius: str = "10km") -> list:
    """
    Get local events near a location for a specific date.
    Covers concerts, sports, festivals, and conferences.

    Args:
        date: Date in YYYY-MM-DD format
        location: City/location string (e.g. "Paris, France")
        radius: Search radius (e.g. "10km")
    """
    api_key = os.getenv("PREDICTHQ_API_KEY") or os.getenv("PREDICTHQ_ACCESS_TOKEN")

    if not api_key:
        return _mock_events(date)

    lat, lon = _location_to_coords(location)

    try:
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        params = {
            "start": f"{date}T00:00:00",
            "end":   f"{date}T23:59:59",
            "location_around.origin": f"{lat},{lon}",
            "location_around.radius": radius,
            "limit": 10,
            "category": "concerts,sports,festivals,conferences,performing-arts",
        }
        response = requests.get(
            "https://api.predicthq.com/v1/events/",
            headers=headers,
            params=params,
            timeout=10,
        )
        if response.status_code == 200:
            results = [
                {
                    "title":    e.get("title",    "Unknown"),
                    "category": e.get("category", "unknown"),
                    "rank":     e.get("rank",     0),
                }
                for e in response.json().get("results", [])
            ]
            return results if results else _mock_events(date)
    except Exception:
        pass

    # API call failed — degrade gracefully to mock instead of returning []
    return _mock_events(date)


if __name__ == "__main__":
    mcp.run()
