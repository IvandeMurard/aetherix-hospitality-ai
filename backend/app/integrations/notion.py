"""
Notion integration — knowledge base, runbooks, and SOPs for Aetherix.

Env vars required:
  NOTION_API_KEY   — Integration token from https://www.notion.so/my-integrations
  NOTION_DB_ID     — Target database ID for operational notes / runbooks
"""

import os
from typing import Any

import httpx

NOTION_API_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


def _headers() -> dict[str, str]:
    token = os.environ["NOTION_API_KEY"]
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


async def query_database(database_id: str | None = None) -> list[dict[str, Any]]:
    """Return all pages in the configured (or specified) Notion database."""
    db_id = database_id or os.environ["NOTION_DB_ID"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/databases/{db_id}/query",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("results", [])


async def create_page(title: str, content: str, database_id: str | None = None) -> dict[str, Any]:
    """Create a new page in the Notion database (e.g. an operational report or alert log)."""
    db_id = database_id or os.environ["NOTION_DB_ID"]
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                },
            }
        ],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/pages", headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()
