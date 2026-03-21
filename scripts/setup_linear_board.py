#!/usr/bin/env python3
"""
scripts/setup_linear_board.py

One-time setup: creates Aetherix issue labels on the Linear team.

Usage:
    LINEAR_API_KEY=lin_api_... LINEAR_TEAM_ID=<uuid> python scripts/setup_linear_board.py

Labels created:
    AI Alert   — general AI/LLM errors
    Budget     — labor cost overruns
    Model      — forecast accuracy degradation
    PMS Sync   — PMS data pipeline issues
    WhatsApp   — inbound message / feedback events
"""

import asyncio
import os
import sys

import httpx

LABELS = [
    {"name": "AI Alert",  "color": "#ef4444"},  # red
    {"name": "Budget",    "color": "#f97316"},  # orange
    {"name": "Model",     "color": "#a855f7"},  # purple
    {"name": "PMS Sync",  "color": "#3b82f6"},  # blue
    {"name": "WhatsApp",  "color": "#22c55e"},  # green
]

CREATE_LABEL = """
mutation CreateLabel($teamId: String!, $name: String!, $color: String!) {
  issueLabelCreate(input: {teamId: $teamId, name: $name, color: $color}) {
    success
    issueLabel { id name color }
  }
}
"""


async def main() -> None:
    api_key = os.environ.get("LINEAR_API_KEY")
    team_id = os.environ.get("LINEAR_TEAM_ID")

    if not api_key or not team_id:
        print("ERROR: Set LINEAR_API_KEY and LINEAR_TEAM_ID environment variables.")
        sys.exit(1)

    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    created, skipped = 0, 0

    async with httpx.AsyncClient() as client:
        for label in LABELS:
            resp = await client.post(
                "https://api.linear.app/graphql",
                headers=headers,
                json={
                    "query": CREATE_LABEL,
                    "variables": {"teamId": team_id, **label},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            result = data.get("data", {}).get("issueLabelCreate", {})

            if result.get("success"):
                lbl = result["issueLabel"]
                print(f"  ✓  {lbl['name']}  {lbl['color']}  (id: {lbl['id']})")
                created += 1
            else:
                errors = data.get("errors", data)
                print(f"  ✗  {label['name']} — {errors}")
                skipped += 1

    print(f"\nDone: {created} created, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(main())
