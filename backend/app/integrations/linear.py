"""
Linear integration — issue and project tracking for Aetherix ops workflows.

Env vars required:
  LINEAR_API_KEY   — Personal API key from https://linear.app/settings/api
  LINEAR_TEAM_ID   — Target team ID for created issues
"""

import os
from typing import Any

import httpx

GRAPHQL_URL = "https://api.linear.app/graphql"


def _headers() -> dict[str, str]:
    return {
        "Authorization": os.environ["LINEAR_API_KEY"],
        "Content-Type": "application/json",
    }


async def _run(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GRAPHQL_URL,
            headers=_headers(),
            json={"query": query, "variables": variables or {}},
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise ValueError(data["errors"])
        return data["data"]


async def create_issue(title: str, description: str, priority: int = 2, team_id: str | None = None) -> dict[str, Any]:
    """
    Create a Linear issue — e.g. a maintenance request or ops alert.
    Priority: 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low.
    """
    tid = team_id or os.environ["LINEAR_TEAM_ID"]
    query = """
    mutation CreateIssue($title: String!, $description: String!, $teamId: String!, $priority: Int) {
      issueCreate(input: {
        title: $title
        description: $description
        teamId: $teamId
        priority: $priority
      }) {
        success
        issue { id identifier title url }
      }
    }
    """
    result = await _run(query, {"title": title, "description": description, "teamId": tid, "priority": priority})
    return result["issueCreate"]["issue"]


async def list_issues(team_id: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
    """Fetch the most recent open issues for the team."""
    tid = team_id or os.environ["LINEAR_TEAM_ID"]
    query = """
    query ListIssues($teamId: ID!, $first: Int) {
      team(id: $teamId) {
        issues(first: $first, filter: { state: { type: { nin: ["completed", "cancelled"] } } }) {
          nodes { id identifier title priority state { name } assignee { name } }
        }
      }
    }
    """
    result = await _run(query, {"teamId": tid, "first": limit})
    return result["team"]["issues"]["nodes"]
