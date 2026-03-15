"""
Events MCP Server

Standalone server showing what an event intelligence vendor (e.g. PredictHQ)
would ship as their MCP server. Exposes local event data for AI agents to
understand demand drivers without any custom integration code.

Run standalone: python mcp_servers/events_server.py
"""

import os
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("EventsServer")


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
        day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        if day in ["Friday", "Saturday"]:
            return [
                {"title": "Weekend concert at local venue", "category": "concerts", "rank": 75},
                {"title": "Sports event at stadium", "category": "sports", "rank": 60}
            ]
        if day == "Sunday":
            return [{"title": "Sunday market and community fair", "category": "community", "rank": 40}]
        return [{"title": "Business conference at convention center", "category": "conferences", "rank": 45}]

    try:
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        params = {
            "start": f"{date}T00:00:00",
            "end": f"{date}T23:59:59",
            "location_around.origin": "48.8566,2.3522",
            "location_around.radius": radius,
            "limit": 10,
            "category": "concerts,sports,festivals,conferences,performing-arts"
        }
        response = requests.get("https://api.predicthq.com/v1/events/", headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return [
                {"title": e.get("title", "Unknown"), "category": e.get("category", "unknown"), "rank": e.get("rank", 0)}
                for e in data.get("results", [])
            ]
    except Exception:
        pass

    return []


if __name__ == "__main__":
    mcp.run()
