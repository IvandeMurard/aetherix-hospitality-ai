"""Linear integration — create and query issues via GraphQL API."""
import os
import httpx

LINEAR_API_URL = "https://api.linear.app/graphql"


def _headers() -> dict:
    key = os.environ.get("LINEAR_API_KEY", "")
    return {"Authorization": key, "Content-Type": "application/json"}


def _team_id() -> str:
    return os.environ.get("LINEAR_TEAM_ID", "")


async def create_issue(
    title: str,
    description: str = "",
    priority: int = 0,
    team_id: str | None = None,
) -> dict:
    """Create a Linear issue. Priority: 0=No, 1=Urgent, 2=High, 3=Medium, 4=Low."""
    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue {
          id
          identifier
          title
          url
          priority
        }
      }
    }
    """
    variables = {
        "input": {
            "teamId": team_id or _team_id(),
            "title": title,
            "description": description,
            "priority": priority,
        }
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            LINEAR_API_URL,
            json={"query": mutation, "variables": variables},
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(data["errors"])
        return data["data"]["issueCreate"]


async def list_issues(limit: int = 10, team_id: str | None = None) -> list[dict]:
    """Return the most recent issues for the team."""
    query = """
    query ListIssues($teamId: String!, $first: Int!) {
      team(id: $teamId) {
        issues(first: $first, orderBy: createdAt) {
          nodes {
            id
            identifier
            title
            state { name }
            priority
            url
          }
        }
      }
    }
    """
    variables = {"teamId": team_id or _team_id(), "first": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            LINEAR_API_URL,
            json={"query": query, "variables": variables},
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(data["errors"])
        return data["data"]["team"]["issues"]["nodes"]
