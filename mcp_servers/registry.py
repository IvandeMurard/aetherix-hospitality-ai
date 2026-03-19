"""
MCP Service Registry

Declares which hotel systems have MCP servers available.
The agent_router uses this to decide between:
  - MCP path   : mcp_agent.py  (Claude + tool discovery)
  - Direct path: autonomous_agent.py  (Mistral, hardcoded integrations)

To add a new system:
  1. Create mcp_servers/<system>_server.py
  2. Register it here with enabled=True
  3. The router picks it up automatically

To temporarily force fallback for a system (e.g. server is down):
  Set "enabled": False in its entry.
"""

import os

_BASE = os.path.dirname(os.path.abspath(__file__))


def _server(filename: str) -> str:
    return os.path.join(_BASE, filename)


# Registry: system_name → metadata
REGISTRY = {
    "weather": {
        "server_path": _server("weather_server.py"),
        "tools": ["get_weather"],
        "enabled": True,
        "description": "Weather data — OpenWeatherMap API with mock fallback",
        "vendor_example": "OpenWeatherMap, Tomorrow.io, Meteomatics",
    },
    "events": {
        "server_path": _server("events_server.py"),
        "tools": ["get_local_events"],
        "enabled": True,
        "description": "Local events — PredictHQ API with mock fallback",
        "vendor_example": "PredictHQ, Ticketmaster, SeatGeek",
    },
    "pms": {
        "server_path": _server("pms_server.py"),
        "tools": [
            "get_hotel_reservations",
            "get_fb_forecast_context",
            "create_service_request",
            "get_guest_profile",
        ],
        "enabled": True,
        "description": "Property Management System — reservation and guest data",
        "vendor_example": "Opera Cloud, Mews, Apaleo, Cloudbeds",
    },
    "patterns": {
        "server_path": _server("hotel_context_server.py"),
        "tools": ["search_historical_patterns"],
        "enabled": True,
        "description": "Historical F&B pattern memory — data warehouse / CDP",
        "vendor_example": "Snowflake, BigQuery, internal data warehouse",
    },
}

# All of these must be available for the MCP path to be selected.
# If any are missing/disabled, the router falls back to autonomous_agent.py.
REQUIRED_SYSTEMS = ["weather", "events", "pms", "patterns"]


def get_available_systems() -> dict:
    """
    Returns {system_name: bool} — True if the system is enabled
    and its server file exists on disk.
    """
    return {
        name: meta["enabled"] and os.path.isfile(meta["server_path"])
        for name, meta in REGISTRY.items()
    }


def all_required_available() -> bool:
    """True only when every required system is enabled and its file exists."""
    available = get_available_systems()
    return all(available.get(s, False) for s in REQUIRED_SYSTEMS)
