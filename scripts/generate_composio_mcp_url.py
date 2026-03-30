"""
Generate a Composio MCP URL for the Apaleo toolkit.

Usage:
    python scripts/generate_composio_mcp_url.py

Output:
    - Prints the MCP URL
    - Prints the ready-to-run `claude mcp add` command
    - Writes COMPOSIO_MCP_URL to .env (if present at project root)

Required env vars:
    COMPOSIO_API_KEY  — from https://app.composio.dev → Settings → API Keys
    COMPOSIO_USER_ID  — any stable identifier for this tenant
                        (e.g. Supabase tenant_id, or "aetherix-dev")

⚠️  Scope note (30/03/2026):
    The Composio Apaleo toolkit exposes the Inventory API only:
    properties, units, unit groups — NOT reservations, occupancy, or revenue.
    For F&B operational data, keep using ApaleoPMSAdapter (raw REST API)
    until Apaleo publishes its direct MCP server (alpha).

    MCP tools available via Composio:
      APALEO_GET_A_PROPERTIES_LIST, APALEO_CREATE_A_PROPERTY,
      APALEO_GET_A_PROPERTY, APALEO_ARCHIVE_A_PROPERTY,
      APALEO_GET_A_UNITS_LIST, APALEO_CREATE_A_UNIT,
      APALEO_GET_A_UNIT, APALEO_DELETE_A_UNIT,
      APALEO_LIST_UNIT_GROUPS, APALEO_CREATE_A_UNIT_GROUP,
      APALEO_GET_A_UNIT_GROUP, APALEO_REPLACE_A_UNIT_GROUP,
      APALEO_DELETE_A_UNIT_GROUP, APALEO_CLONES_A_PROPERTY,
      APALEO_CREATE_MULTIPLE_UNITS, APALEO_MOVE_PROPERTY_TO_LIVE,
      APALEO_RESET_PROPERTY_DATA + unit attribute variants
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
COMPOSIO_USER_ID = os.getenv("COMPOSIO_USER_ID", "aetherix-default")

if not COMPOSIO_API_KEY:
    sys.exit(
        "ERROR: COMPOSIO_API_KEY is not set.\n"
        "Add it to your .env file or export it:\n"
        "  export COMPOSIO_API_KEY=ak_..."
    )

try:
    from composio import Composio
except ImportError:
    sys.exit(
        "ERROR: composio-core not installed.\n"
        "Run: pip install composio-core python-dotenv"
    )

composio_client = Composio(api_key=COMPOSIO_API_KEY)

print("Creating Composio Tool Router session for Apaleo...")
session = composio_client.create(
    user_id=COMPOSIO_USER_ID,
    toolkits=["apaleo"],
)

mcp_url: str = session.mcp.url
print(f"\nMCP URL:\n  {mcp_url}")

cmd = (
    f'claude mcp add --transport http apaleo-composio "{mcp_url}" '
    f'--headers "X-API-Key:{COMPOSIO_API_KEY}"'
)
print(f"\nAdd to Claude Code:\n  {cmd}")

# Optionally persist to .env
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        content = f.read()

    updated = False
    lines = content.splitlines(keepends=True)
    new_lines = []
    for line in lines:
        if line.startswith("COMPOSIO_MCP_URL="):
            new_lines.append(f"COMPOSIO_MCP_URL={mcp_url}\n")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"\nCOMPOSIO_MCP_URL={mcp_url}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)
    print(f"\n.env updated: COMPOSIO_MCP_URL={mcp_url}")
else:
    print(f"\n(No .env found at project root — add manually:)")
    print(f"  COMPOSIO_MCP_URL={mcp_url}")

print("\nDone.")
