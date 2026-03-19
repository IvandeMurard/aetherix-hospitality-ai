"""
Web Search MCP Server

Standalone server exposing Google Search via Serper API.
Any MCP-compatible AI agent can connect to this to retrieve
real-time web search results — no custom integration needed per agent.

Run standalone: python mcp_servers/search_server.py
"""

import os
from typing import Optional

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("SearchServer")


@mcp.tool()
def web_search(query: str, num_results: int = 5, country: Optional[str] = None) -> dict:
    """
    Search the web using Google (via Serper API).

    Args:
        query: Search query string
        num_results: Number of results to return (default 5, max 10)
        country: Optional ISO country code to localise results (e.g. "fr", "de")
    """
    api_key = os.getenv("SERPER_API_KEY")

    if not api_key:
        return {
            "results": [
                {
                    "title": "Mock result — SERPER_API_KEY not configured",
                    "link": "https://serper.dev",
                    "snippet": "Add SERPER_API_KEY to your .env to enable live web search.",
                }
            ],
            "source": "mock",
        }

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    payload: dict = {"q": query, "num": min(num_results, 10)}
    if country:
        payload["gl"] = country.lower()

    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            organic = data.get("organic", [])
            return {
                "results": [
                    {
                        "title": r.get("title", ""),
                        "link": r.get("link", ""),
                        "snippet": r.get("snippet", ""),
                    }
                    for r in organic[:num_results]
                ],
                "source": "serper",
            }
        return {
            "results": [],
            "source": "error",
            "error": f"Serper API returned {response.status_code}",
        }
    except Exception as exc:
        return {"results": [], "source": "error", "error": str(exc)}


if __name__ == "__main__":
    mcp.run()
