"""
Test du serveur MCP Apaleo distant (https://mcp.apaleo.com/mcp/) — le chemin
réellement utilisé par le client de `main`. Standalone, sans le package app.

Etapes : OAuth2 -> connexion streamable-HTTP -> initialize -> list_tools -> call_tool (read).
"""
import asyncio
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv(Path("backend/.env"))
CID = os.getenv("APALEO_CLIENT_ID", "")
SEC = os.getenv("APALEO_CLIENT_SECRET", "")
SERVER = os.getenv("APALEO_MCP_SERVER_URL", "https://mcp.apaleo.com/mcp/")
TOKEN_URL = "https://identity.apaleo.com/connect/token"


async def get_token() -> str:
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.post(TOKEN_URL, data={
            "grant_type": "client_credentials", "client_id": CID, "client_secret": SEC})
        r.raise_for_status()
        return r.json()["access_token"]


async def main() -> int:
    print(f"== Test serveur MCP Apaleo : {SERVER} ==")
    token = await get_token()
    print(f"[OK]  OAuth2 token acquis (len={len(token)})")

    try:
        t0 = time.monotonic()
        async with streamablehttp_client(SERVER, headers={"Authorization": f"Bearer {token}"}) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                ms = (time.monotonic() - t0) * 1000
                print(f"[OK]  Handshake MCP initialize en {ms:.0f}ms")

                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                print(f"[OK]  list_tools -> {len(names)} outils")
                for n in names[:25]:
                    print(f"        - {n}")

                # tente un outil de lecture sur les propriétés (read-only, safe)
                read_candidates = [n for n in names if "GET" in n.upper() and ("PROPERT" in n.upper() or "RESERVATION" in n.upper())]
                if read_candidates:
                    tool = read_candidates[0]
                    print(f"\n[..] call_tool {tool} ...")
                    res = await session.call_tool(tool, {})
                    txt = res.content[0].text if res.content and res.content[0].type == "text" else str(res)
                    print(f"[OK]  {tool} -> {txt[:400]}")
        return 0
    except Exception as exc:
        print(f"[FAIL] MCP: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
