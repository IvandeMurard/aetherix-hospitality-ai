"""Génère un jeton MCP et le SQL qui l'enregistre — sans jamais afficher le jeton.

Le jeton brut (atx_<env>_<aléatoire>) est écrit dans le fichier .env indiqué, sous
SMOKE_MCP_TOKEN. Seule son empreinte SHA-256 (hash_token, backend/app/mcp_core.py)
va dans le SQL, à exécuter dans l'éditeur SQL Supabase. Le jeton ne transite donc
ni par un terminal partagé, ni par un chat.

Usage (depuis la racine du dépôt) :
    backend/.venv/Scripts/python.exe -I scripts/ops/mint_mcp_token.py \
        --env backend/.env --sql mcp_token_insert.sql
    # puis coller mcp_token_insert.sql dans l'éditeur SQL Supabase et l'exécuter.

Scopes par défaut = ceux qu'exigent les étapes 3 et 4 du smoke test
(scripts/ci/smoke_test_e2e.py) : predict, recommend, feedback, + lecture mémoire/recap.
La correspondance outil → scope est `_TOOL_SCOPE` dans backend/app/mcp_core.py.
"""
from __future__ import annotations

import argparse
import hashlib
import secrets
from pathlib import Path

DEFAULT_SCOPES = "predict,recommend,feedback,memory:read,receipts:read"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env", required=True, help="fichier .env où écrire SMOKE_MCP_TOKEN")
    ap.add_argument("--sql", required=True, help="fichier SQL de sortie (empreinte seule)")
    ap.add_argument("--hotel-id", default="demo_hotel")
    ap.add_argument("--scopes", default=DEFAULT_SCOPES)
    ap.add_argument("--label", default="smoke-test")
    args = ap.parse_args()

    scopes = [s.strip() for s in args.scopes.split(",") if s.strip()]
    raw = "atx_demo_" + secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    env_path = Path(args.env)
    kept = [
        ln for ln in (env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else [])
        if not ln.startswith("SMOKE_MCP_TOKEN=")
    ]
    kept.append("SMOKE_MCP_TOKEN=" + raw)
    env_path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    arr = ", ".join("'" + s + "'" for s in scopes)
    Path(args.sql).write_text(
        "-- Jeton MCP (empreinte SHA-256 seule ; le jeton est dans " + env_path.name + ")\n"
        "INSERT INTO mcp_api_tokens (id, hotel_id, token_hash, token_prefix, scopes, label)\n"
        "VALUES (gen_random_uuid(), '" + args.hotel_id + "', '" + digest + "', 'atx_demo_',\n"
        "        ARRAY[" + arr + "], '" + args.label + "');\n\n"
        "-- Révocation :\n"
        "-- UPDATE mcp_api_tokens SET revoked_at = now() WHERE token_hash = '" + digest + "';\n",
        encoding="utf-8",
    )
    print("ok : " + env_path.name + " mis à jour (" + str(len(raw)) + " car.), SQL -> " + args.sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
