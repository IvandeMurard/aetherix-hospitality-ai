"""
Diagnostic Composio — vérifie les connexions Apaleo disponibles
et affiche l'URL MCP correcte à utiliser.

Usage:
    python scripts/diagnose_composio.py
"""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for candidate in [os.path.join(_root, "backend", ".env"), os.path.join(_root, ".env")]:
    if os.path.exists(candidate):
        load_dotenv(candidate)
        break

API_KEY = os.getenv("COMPOSIO_API_KEY", "")
if not API_KEY:
    sys.exit("ERROR: COMPOSIO_API_KEY absent du .env")

HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}
BASE = "https://backend.composio.dev/api/v1"


def get(path: str) -> dict:
    r = requests.get(f"{BASE}{path}", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


# 1. Lister les connexions actives
print("\n=== Connexions Composio (connectedAccounts) ===")
try:
    data = get("/connectedAccounts")
    accounts = data.get("items", [])
    if not accounts:
        print("[WARN] Aucune connexion trouvée — as-tu bien connecté Apaleo dans le dashboard ?")
    for acc in accounts:
        print(f"  - app={acc.get('appName')} | entity={acc.get('entityId')} | status={acc.get('status')} | id={acc.get('id')}")
except Exception as e:
    print(f"[ERR] {e}")

# 2. Lister les entités
print("\n=== Entités disponibles ===")
try:
    data = get("/toolset/entities")
    entities = data.get("items", data) if isinstance(data, dict) else data
    for ent in (entities if isinstance(entities, list) else []):
        print(f"  - id={ent.get('id')} | email={ent.get('email', 'n/a')}")
except Exception as e:
    print(f"[ERR] {e}")

# 3. Trouver les connexions Apaleo
print("\n=== Connexions Apaleo ===")
try:
    data = get("/connectedAccounts?appName=apaleo")
    apaleo_accounts = data.get("items", [])
    if not apaleo_accounts:
        print("[WARN] Aucune connexion Apaleo trouvée")
    else:
        for acc in apaleo_accounts:
            entity_id = acc.get("entityId", "default")
            from urllib.parse import urlencode
            params = urlencode({"api_key": API_KEY, "user_id": entity_id})
            url = f"https://mcp.composio.dev/apaleo?{params}"
            print(f"\n[OK] Connexion Apaleo trouvée !")
            print(f"     entity_id : {entity_id}")
            print(f"     status    : {acc.get('status')}")
            print(f"\n[URL MCP CORRECTE]")
            print(f"     {url}")
            print(f"\n[COMMANDE CLAUDE CODE]")
            print(f'     claude mcp remove apaleo-composio')
            print(f'     claude mcp add --transport http apaleo-composio "{url}"')
except Exception as e:
    print(f"[ERR] {e}")
