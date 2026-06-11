"""
Ad-hoc Apaleo sandbox test — exercises ApaleoMCPClient directly against the
live sandbox (no backend/DB required). Mirrors /pms/mcp/probe but also tests
APALEO_LIST_RESERVATIONS over a real date range.

Run: python scripts/test_apaleo_sandbox_run.py
"""

import asyncio
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / "backend" / ".env")
sys.path.insert(0, str(_root / "backend"))

from app.integrations.apaleo_mcp_client import ApaleoMCPClient  # noqa: E402


async def main() -> int:
    client = ApaleoMCPClient()
    print(f"== Apaleo Sandbox test @ {date.today().isoformat()} ==")
    print(f"   client_id={client.client_id}  property_id={client.property_id or '(none)'}")

    # 1 — credentials
    if not client.has_credentials:
        print("[FAIL] credentials missing in backend/.env")
        return 1
    print("[OK]  credentials present")

    # 2 — OAuth2
    try:
        ms = await client.authenticate()
    except Exception as exc:
        print(f"[FAIL] OAuth2: {exc}")
        return 2
    print(f"[OK]  OAuth2 token acquired in {ms:.0f}ms")

    # 3 — list_tools
    tools = client.list_tools()
    print(f"[OK]  list_tools -> {len(tools)} tool(s): {[t['name'] for t in tools]}")

    # 4 — occupancy metrics (today)
    try:
        t0 = time.monotonic()
        occ = await client.call_tool("APALEO_GET_OCCUPANCY_METRICS")
        dt = (time.monotonic() - t0) * 1000
        print(f"[OK]  APALEO_GET_OCCUPANCY_METRICS ({dt:.0f}ms) -> {occ}")
    except Exception as exc:
        print(f"[FAIL] APALEO_GET_OCCUPANCY_METRICS: {exc}")
        return 5

    # 5 — list reservations (today .. +14d)
    frm = date.today().isoformat()
    to = (date.today() + timedelta(days=14)).isoformat()
    try:
        t0 = time.monotonic()
        res = await client.call_tool(
            "APALEO_LIST_RESERVATIONS", {"from_date": frm, "to_date": to}
        )
        dt = (time.monotonic() - t0) * 1000
        count = res.get("count", len(res.get("reservations", [])))
        print(f"[OK]  APALEO_LIST_RESERVATIONS {frm}..{to} ({dt:.0f}ms) -> count={count}")
    except Exception as exc:
        print(f"[FAIL] APALEO_LIST_RESERVATIONS: {exc}")
        return 6

    print("\n=== Apaleo sandbox: GREEN — full pipeline OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
