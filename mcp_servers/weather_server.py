"""
Weather MCP Server

Standalone server showing what a weather data vendor (e.g. OpenWeatherMap)
would ship as their MCP server. Any MCP-compatible AI agent can connect to
this and get weather data — no custom integration code needed per agent.

Run standalone: python mcp_servers/weather_server.py
"""

import os
import random
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("WeatherServer")


@mcp.tool()
def get_weather(city: str = "Paris", country: str = "FR", date: Optional[str] = None) -> dict:
    """
    Get weather forecast for a location.

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
        url = f"{base_url}/weather" if not date or date == datetime.now().strftime("%Y-%m-%d") else f"{base_url}/forecast"
        params = {"q": f"{city},{country}", "appid": api_key, "units": "metric", "lang": "en"}
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

    return {"description": "Partly cloudy, 18°C", "temperature": 18, "humidity": 65, "city": city, "source": "mock_fallback"}


if __name__ == "__main__":
    mcp.run()
