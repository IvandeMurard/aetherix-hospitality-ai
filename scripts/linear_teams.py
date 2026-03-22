"""
scripts/linear_teams.py
Liste toutes les équipes Linear et leurs UUIDs.

Usage :
    LINEAR_API_KEY=lin_api_... python scripts/linear_teams.py

Copier l'UUID de l'équipe HOS dans LINEAR_TEAM_ID (.env + GitHub Secrets).
"""

import os
import sys
import httpx

LINEAR_API = "https://api.linear.app/graphql"

QUERY = """
query {
  teams {
    nodes {
      id
      name
      key
    }
  }
}
"""


def main() -> None:
    api_key = os.environ.get("LINEAR_API_KEY", "")
    if not api_key:
        print("Erreur : LINEAR_API_KEY non définie", file=sys.stderr)
        sys.exit(1)

    resp = httpx.post(
        LINEAR_API,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        json={"query": QUERY},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    teams = data.get("data", {}).get("teams", {}).get("nodes", [])
    if not teams:
        print("Aucune équipe trouvée.")
        return

    print(f"\n{'Clé':<8} {'Nom':<30} {'UUID'}")
    print("─" * 75)
    for t in teams:
        marker = " ◄ utiliser cet UUID" if t["key"] == "HOS" else ""
        print(f"{t['key']:<8} {t['name']:<30} {t['id']}{marker}")

    print()
    hos = next((t for t in teams if t["key"] == "HOS"), None)
    if hos:
        print(f"LINEAR_TEAM_ID={hos['id']}")
        print("\nMettre à jour :")
        print("  1. .env local")
        print("  2. GitHub → Settings → Secrets → LINEAR_TEAM_ID")
    else:
        print("Équipe HOS non trouvée. Vérifier le nom de l'équipe dans Linear.")


if __name__ == "__main__":
    main()
