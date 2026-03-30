"""
Generate (or reconstruct) a Composio MCP URL for the Apaleo toolkit.

URL format confirmed (30/03/2026):
    https://mcp.composio.dev/apaleo?api_key=<KEY>&user_id=<USER_ID>

Auth is embedded in the URL query params — no X-API-Key header needed.

Usage:
    python scripts/generate_composio_mcp_url.py

Output:
    - Prints the MCP URL
    - Prints the ready-to-run `claude mcp add` command
    - Writes COMPOSIO_MCP_URL to backend/.env (or root .env as fallback)

Required env vars:
    COMPOSIO_API_KEY  — from https://app.composio.dev → Settings → API Keys
    COMPOSIO_USER_ID  — stable identifier for this session
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
from urllib.parse import urlencode

from dotenv import load_dotenv

# Try backend/.env first (primary), then project-root .env as fallback
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend_env = os.path.join(_root, "backend", ".env")
_root_env = os.path.join(_root, ".env")
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)
elif os.path.exists(_root_env):
    load_dotenv(_root_env)
else:
    load_dotenv()  # fallback: search from CWD

COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
COMPOSIO_USER_ID = os.getenv("COMPOSIO_USER_ID", "aetherix-default")

if not COMPOSIO_API_KEY:
    sys.exit(
        "ERROR: COMPOSIO_API_KEY is not set.\n"
        "Add it to backend/.env:\n"
        "  COMPOSIO_API_KEY=ak_..."
    )

print(f"[INFO] API Key  : {COMPOSIO_API_KEY[:10]}...")
print(f"[INFO] User ID  : {COMPOSIO_USER_ID}")

# ------------------------------------------------------------------
# Build the MCP URL.
# Composio's standard URL format: auth is in query params.
# Try the Tool Router API first; fall back to static URL construction.
# ------------------------------------------------------------------

mcp_url: str = ""

try:
    from composio import Composio  # noqa: PLC0415

    composio_client = Composio(api_key=COMPOSIO_API_KEY)
    session = composio_client.create(
        user_id=COMPOSIO_USER_ID,
        toolkits=["apaleo"],
    )
    mcp_url = session.mcp.url
    print(f"[OK] Tool Router session created")

except Exception as exc:
    print(f"[WARN] Tool Router API unavailable ({exc}), building static URL")
    # Confirmed URL pattern from Composio (30/03/2026)
    params = urlencode({"api_key": COMPOSIO_API_KEY, "user_id": COMPOSIO_USER_ID})
    mcp_url = f"https://mcp.composio.dev/apaleo?{params}"

print(f"\n[OK] COMPOSIO_MCP_URL:\n     {mcp_url}")

# Auth is embedded in URL query params — no header needed
cmd = f'claude mcp add --transport http apaleo-composio "{mcp_url}"'
print(f"\n[NEXT] Add to Claude Code:\n  {cmd}")

# ------------------------------------------------------------------
# Persist to .env
# ------------------------------------------------------------------

env_path = _backend_env if os.path.exists(_backend_env) else _root_env
if os.path.exists(env_path):
    with open(env_path) as f:
        content = f.read()

    lines = content.splitlines(keepends=True)
    new_lines = []
    updated_mcp = False
    updated_apaleo = False

    for line in lines:
        if line.startswith("COMPOSIO_MCP_URL="):
            new_lines.append(f"COMPOSIO_MCP_URL={mcp_url}\n")
            updated_mcp = True
        elif line.startswith("APALEO_MCP_SERVER_URL="):
            new_lines.append(f"APALEO_MCP_SERVER_URL={mcp_url}\n")
            updated_apaleo = True
        else:
            new_lines.append(line)

    if not updated_mcp:
        new_lines.append(f"\nCOMPOSIO_MCP_URL={mcp_url}\n")
    if not updated_apaleo:
        new_lines.append(f"APALEO_MCP_SERVER_URL={mcp_url}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)
    print(f"\n[INFO] COMPOSIO_MCP_URL and APALEO_MCP_SERVER_URL updated in {os.path.basename(env_path)}")
else:
    print(f"\n[INFO] No .env found — add manually:")
    print(f"  COMPOSIO_MCP_URL={mcp_url}")
    print(f"  APALEO_MCP_SERVER_URL={mcp_url}")
