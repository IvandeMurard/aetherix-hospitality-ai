"""
Setup Linear board for Aetherix Hospitality AI project.
Creates domain labels, an 'In Review' state, and seed issues per module.

Usage:
  LINEAR_API_KEY=lin_api_... LINEAR_TEAM_ID=... python scripts/setup_linear_board.py
"""
import os
import sys
import httpx

API_URL = "https://api.linear.app/graphql"
API_KEY = os.environ.get("LINEAR_API_KEY", "")
TEAM_ID = os.environ.get("LINEAR_TEAM_ID", "")

if not API_KEY or not TEAM_ID:
    print("ERROR: LINEAR_API_KEY and LINEAR_TEAM_ID must be set.")
    sys.exit(1)

HEADERS = {"Authorization": API_KEY, "Content-Type": "application/json"}


def gql(query: str, variables: dict = {}) -> dict:
    r = httpx.post(API_URL, json={"query": query, "variables": variables}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


# ── 1. Labels métier à créer ──────────────────────────────────────────────────

LABELS = [
    {"name": "Backend",      "color": "#0EA5E9"},
    {"name": "Frontend",     "color": "#8B5CF6"},
    {"name": "AI/ML",        "color": "#F59E0B"},
    {"name": "Integration",  "color": "#10B981"},
    {"name": "Infra",        "color": "#6B7280"},
    {"name": "WhatsApp",     "color": "#25D366"},
    {"name": "Obsidian",     "color": "#7C3AED"},
    {"name": "Linear",       "color": "#5E6AD2"},
    {"name": "Apaleo",       "color": "#F97316"},
    {"name": "Voice",        "color": "#EC4899"},
]

CREATE_LABEL = """
mutation CreateLabel($name: String!, $color: String!, $teamId: String!) {
  issueLabelCreate(input: { name: $name, color: $color, teamId: $teamId }) {
    success
    issueLabel { id name }
  }
}
"""

def create_labels(existing_names: set):
    created = []
    for label in LABELS:
        if label["name"] in existing_names:
            print(f"  ⏭  Label '{label['name']}' déjà existant")
            continue
        result = gql(CREATE_LABEL, {**label, "teamId": TEAM_ID})
        if result["issueLabelCreate"]["success"]:
            print(f"  ✅ Label '{label['name']}' créé")
            created.append(result["issueLabelCreate"]["issueLabel"])
        else:
            print(f"  ❌ Échec label '{label['name']}'")
    return created


# ── 2. État 'In Review' ────────────────────────────────────────────────────────

CREATE_STATE = """
mutation CreateState($name: String!, $color: String!, $type: String!, $teamId: String!) {
  workflowStateCreate(input: { name: $name, color: $color, type: $type, teamId: $teamId }) {
    success
    workflowState { id name }
  }
}
"""

def create_in_review_state(existing_names: set):
    if "In Review" in existing_names:
        print("  ⏭  État 'In Review' déjà existant")
        return None
    result = gql(CREATE_STATE, {
        "name": "In Review",
        "color": "#F2994A",
        "type": "started",
        "teamId": TEAM_ID,
    })
    if result["workflowStateCreate"]["success"]:
        print("  ✅ État 'In Review' créé")
        return result["workflowStateCreate"]["workflowState"]
    print("  ❌ Échec création état 'In Review'")
    return None


# ── 3. Issues initiales ────────────────────────────────────────────────────────

SEED_ISSUES = [
    {
        "title": "[Infra] Déploiement Docker local (Obsidian + Linear)",
        "description": "Vérifier que le stack Docker démarre correctement avec les volumes Obsidian montés et les intégrations Linear actives.",
        "priority": 2,
    },
    {
        "title": "[Integration] Module Obsidian — write_note / list_notes",
        "description": "Intégration lecture/écriture dans le vault Obsidian. Tester avec le vault 'Agentic AI Hospitality'.",
        "priority": 2,
    },
    {
        "title": "[Integration] Module Linear — create_issue / list_issues",
        "description": "Intégration GraphQL Linear. Résolution automatique UUID depuis clé équipe.",
        "priority": 2,
    },
    {
        "title": "[AI/ML] Pipeline Claude MCP — POST /predict",
        "description": "Activer le chemin Claude MCP via ANTHROPIC_API_KEY. Fallback heuristique si clé absente.",
        "priority": 1,
    },
    {
        "title": "[Backend] API FastAPI — health check + Swagger",
        "description": "Endpoint GET /health retourne statut de toutes les clés. Swagger disponible sur /docs.",
        "priority": 3,
    },
    {
        "title": "[WhatsApp] Agent ambiant Twilio",
        "description": "Réception et envoi de messages WhatsApp via Twilio. Tester le webhook entrant.",
        "priority": 3,
    },
    {
        "title": "[Frontend] Interface Next.js — http://localhost:3000",
        "description": "Vérifier que le frontend démarre, se connecte au backend et affiche les données correctement.",
        "priority": 3,
    },
    {
        "title": "[Apaleo] Connexion PMS — récupération des réservations",
        "description": "Authentification OAuth Apaleo. Récupérer les réservations du property PAR.",
        "priority": 2,
    },
]

CREATE_ISSUE = """
mutation CreateIssue($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue { id identifier title url }
  }
}
"""

def create_seed_issues(todo_state_id: str, existing_titles: set):
    for issue in SEED_ISSUES:
        if issue["title"] in existing_titles:
            print(f"  ⏭  Issue '{issue['title'][:50]}...' déjà existante")
            continue
        result = gql(CREATE_ISSUE, {"input": {
            "teamId": TEAM_ID,
            "title": issue["title"],
            "description": issue["description"],
            "priority": issue["priority"],
            "stateId": todo_state_id,
        }})
        if result["issueCreate"]["success"]:
            i = result["issueCreate"]["issue"]
            print(f"  ✅ {i['identifier']} — {i['title'][:60]}")
        else:
            print(f"  ❌ Échec issue '{issue['title'][:50]}'")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n🔍 Récupération de l'état actuel du board...")
    data = gql("""
    query($teamId: String!) {
      team(id: $teamId) {
        states { nodes { id name type } }
        labels { nodes { name } }
        issues { nodes { title } }
      }
    }
    """, {"teamId": TEAM_ID})

    team = data["team"]
    existing_states = {s["name"]: s for s in team["states"]["nodes"]}
    existing_labels = {l["name"] for l in team["labels"]["nodes"]}
    existing_titles = {i["title"] for i in team["issues"]["nodes"]}
    todo_state_id = next(
        (s["id"] for s in team["states"]["nodes"] if s["type"] == "unstarted"),
        None
    )

    print(f"\n📌 Labels ({len(existing_labels)} existants) :")
    create_labels(existing_labels)

    print(f"\n📋 États ({len(existing_states)} existants) :")
    create_in_review_state(set(existing_states.keys()))

    print(f"\n🗂  Issues de départ ({len(existing_titles)} existantes) :")
    if todo_state_id:
        create_seed_issues(todo_state_id, existing_titles)
    else:
        print("  ❌ Impossible de trouver l'état 'Todo'")

    print("\n🎉 Setup terminé — board disponible sur https://linear.app/hospitalityagent\n")


if __name__ == "__main__":
    main()
