"""
scripts/intelligence_report.py
Rapport d'intelligence : écrit simultanément dans Obsidian et Linear.

Modes d'utilisation :
─────────────────────────────────────────────────────────────────
1. Manuel (après une session de veille) :
     python scripts/intelligence_report.py \
       --title "Veille concurrentielle — Mars 2026" \
       --body  notes/veille-mars.md \
       --linear                          # crée aussi un ticket Linear
       --priority high                   # urgent, medium, low (défaut: medium)

2. Pipe depuis Claude / n'importe quelle commande :
     echo "Insight clé..." | python scripts/intelligence_report.py \
       --title "Analyse rapide" --linear

3. Hook Claude Code Stop (automatique) :
     Appelé via settings.json, lit le JSON de contexte sur stdin.
     Écrit une note de session dans Obsidian.
     Si le transcript contient des mots-clés stratégiques → crée aussi un ticket Linear.

Sortie :
  - Obsidian : Vault/AI Reports/Intelligence/YYYY-MM-DD-<slug>.md
  - Linear   : ticket avec label "Strategic Intelligence", lien vers la note
─────────────────────────────────────────────────────────────────
Prérequis (variables d'environnement) :
  LINEAR_API_KEY    — lin_api_...
  LINEAR_TEAM_ID    — UUID de l'équipe Linear

  Optionnel pour le hook Stop (résumé auto via Claude) :
  ANTHROPIC_API_KEY — sk-ant-...
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import httpx

# ─── Configuration ────────────────────────────────────────────────────────────

REPO_ROOT  = Path(__file__).parent.parent.resolve()
VAULT_ROOT = Path(r"C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality")
VAULT_INTEL_DIR = VAULT_ROOT / "AI Reports" / "Intelligence"

LINEAR_API = "https://api.linear.app/graphql"

# Mots-clés qui déclenchent automatiquement un ticket Linear en mode hook
STRATEGIC_KEYWORDS = [
    "concurrent", "compétiteur", "marché", "opportunité", "menace",
    "stratégi", "veille", "tendance", "disruption", "pivot",
    "competitor", "market", "opportunity", "threat", "strategic",
]

PRIORITY_MAP = {"urgent": 1, "high": 2, "medium": 3, "low": 4}

# ─── Linear ───────────────────────────────────────────────────────────────────

CREATE_ISSUE_GQL = """
mutation CreateIssue(
  $teamId: String!
  $title: String!
  $description: String!
  $labelIds: [String!]
  $priority: Int
) {
  issueCreate(input: {
    teamId: $teamId
    title: $title
    description: $description
    labelIds: $labelIds
    priority: $priority
  }) {
    success
    issue { id identifier url title }
  }
}
"""

GET_LABEL_ID_GQL = """
query Labels($teamId: String!) {
  team(id: $teamId) {
    labels { nodes { id name } }
  }
}
"""


def _linear_headers() -> dict:
    key = os.environ.get("LINEAR_API_KEY", "")
    if not key:
        raise EnvironmentError("LINEAR_API_KEY non définie")
    return {"Authorization": key, "Content-Type": "application/json"}


def get_label_id(team_id: str, label_name: str) -> str | None:
    """Retourne l'ID du label Linear dont le nom correspond (insensible à la casse)."""
    resp = httpx.post(
        LINEAR_API,
        headers=_linear_headers(),
        json={"query": GET_LABEL_ID_GQL, "variables": {"teamId": team_id}},
        timeout=15,
    )
    resp.raise_for_status()
    nodes = resp.json()["data"]["team"]["labels"]["nodes"]
    for n in nodes:
        if n["name"].lower() == label_name.lower():
            return n["id"]
    return None


def create_linear_issue(
    title: str,
    description: str,
    priority: str = "medium",
    label: str = "Strategic Intelligence",
) -> dict:
    """Crée un ticket Linear. Retourne {"identifier": "HOS-XX", "url": "..."}."""
    team_id = os.environ.get("LINEAR_TEAM_ID", "")
    if not team_id:
        raise EnvironmentError("LINEAR_TEAM_ID non définie")

    label_id = get_label_id(team_id, label)
    label_ids = [label_id] if label_id else []

    resp = httpx.post(
        LINEAR_API,
        headers=_linear_headers(),
        json={
            "query": CREATE_ISSUE_GQL,
            "variables": {
                "teamId": team_id,
                "title": title,
                "description": description,
                "labelIds": label_ids,
                "priority": PRIORITY_MAP.get(priority.lower(), 3),
            },
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    issue = data.get("data", {}).get("issueCreate", {}).get("issue", {})
    if not issue:
        raise RuntimeError(f"Linear API error: {data.get('errors', data)}")
    return issue


# ─── Obsidian ─────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:60]


def write_obsidian_note(
    title: str,
    body: str,
    tags: list[str] | None = None,
    linear_url: str | None = None,
    dry_run: bool = False,
) -> Path:
    """Écrit la note Markdown dans le vault. Retourne le chemin de la note."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    slug = _slugify(title)
    filename = f"{date_str}-{slug}.md"
    dest = VAULT_INTEL_DIR / filename

    tag_list = tags or ["intelligence", "veille"]
    front_matter = textwrap.dedent(f"""\
        ---
        title: "{title}"
        date: {date_str}
        time: {time_str}
        tags: [{", ".join(tag_list)}]
        source: claude-code
        ---
    """)

    linear_section = ""
    if linear_url:
        linear_section = f"\n\n---\n\n**Linear :** [{linear_url}]({linear_url})\n"

    content = f"{front_matter}\n# {title}\n\n{body.strip()}{linear_section}\n"

    if dry_run:
        print(f"[dry-run] Écrirait : {dest}")
        print(content[:300] + ("..." if len(content) > 300 else ""))
        return dest

    VAULT_INTEL_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


# ─── Hook mode ────────────────────────────────────────────────────────────────

def handle_stop_hook(raw_json: str, dry_run: bool) -> None:
    """
    Appelé automatiquement par le hook Claude Code Stop.
    stdin contient un JSON avec : session_id, transcript_path (optionnel), stop_hook_active.
    """
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        # Si stdin n'est pas du JSON, traiter comme du texte brut
        payload = {"session_id": "unknown", "raw_text": raw_json}

    session_id = payload.get("session_id", "unknown")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"Session Claude Code — {now}"

    # Lire le transcript si disponible
    transcript_path = payload.get("transcript_path")
    if transcript_path and Path(transcript_path).exists():
        body_lines = Path(transcript_path).read_text(encoding="utf-8", errors="replace")
        # Tronquer si trop long
        if len(body_lines) > 4000:
            body_lines = body_lines[:4000] + "\n\n*[transcript tronqué]*"
    else:
        body_lines = payload.get("raw_text", f"Session `{session_id}` terminée.")

    # Détecter si le contenu est stratégique
    body_lower = body_lines.lower()
    is_strategic = any(kw in body_lower for kw in STRATEGIC_KEYWORDS)

    linear_url = None
    if is_strategic and not dry_run:
        team_id = os.environ.get("LINEAR_TEAM_ID")
        api_key = os.environ.get("LINEAR_API_KEY")
        if team_id and api_key:
            try:
                issue = create_linear_issue(
                    title=f"[Veille] {title}",
                    description=f"Session automatiquement détectée comme stratégique.\n\n```\n{body_lines[:2000]}\n```",
                    priority="medium",
                )
                linear_url = issue.get("url")
                print(f"[✓] Linear : {issue.get('identifier')} — {issue.get('url')}")
            except Exception as e:
                print(f"[!] Linear ignoré : {e}", file=sys.stderr)

    note_path = write_obsidian_note(
        title=title,
        body=body_lines,
        tags=["session", "claude-code"] + (["veille", "intelligence"] if is_strategic else []),
        linear_url=linear_url,
        dry_run=dry_run,
    )
    print(f"[✓] Obsidian : {note_path.name}" + (" [strategic]" if is_strategic else ""))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rapport d'intelligence → Obsidian + Linear",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--title",    help="Titre du rapport / ticket")
    parser.add_argument("--body",     help="Corps : chemin vers un .md OU texte direct OU '-' pour stdin")
    parser.add_argument("--linear",   action="store_true", help="Crée aussi un ticket Linear")
    parser.add_argument("--priority", default="medium", choices=["urgent","high","medium","low"])
    parser.add_argument("--tags",     nargs="*", default=["intelligence","veille"])
    parser.add_argument("--dry-run",  action="store_true", help="Simulation sans écriture")
    parser.add_argument("--hook",     action="store_true", help="Mode hook Stop (lit stdin JSON)")
    args = parser.parse_args()

    print(f"\n{'─'*55}")
    print(f"  Intelligence Report  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'─'*55}\n")

    # ── Mode hook (Claude Code Stop) ──
    if args.hook or (not args.title and not sys.stdin.isatty()):
        raw = sys.stdin.read()
        handle_stop_hook(raw, args.dry_run)
        return

    # ── Mode manuel ──
    if not args.title:
        parser.error("--title requis en mode manuel")

    # Lire le corps
    if not args.body or args.body == "-":
        body = sys.stdin.read() if not args.body else ""
    elif Path(args.body).exists():
        body = Path(args.body).read_text(encoding="utf-8")
    else:
        body = args.body  # texte direct

    if not body.strip():
        parser.error("Corps vide — fournir --body ou piper du texte")

    # 1. Créer le ticket Linear si demandé
    linear_url = None
    if args.linear:
        team_id = os.environ.get("LINEAR_TEAM_ID")
        api_key = os.environ.get("LINEAR_API_KEY")
        if not team_id or not api_key:
            print("[!] LINEAR_API_KEY ou LINEAR_TEAM_ID manquant — Linear ignoré", file=sys.stderr)
        elif args.dry_run:
            print(f"[dry-run] Créerait Linear : '{args.title}' (priority={args.priority})")
        else:
            issue = create_linear_issue(args.title, body, args.priority)
            linear_url = issue.get("url")
            print(f"[✓] Linear : {issue.get('identifier')} — {linear_url}")

    # 2. Écrire la note Obsidian
    note_path = write_obsidian_note(
        title=args.title,
        body=body,
        tags=args.tags,
        linear_url=linear_url,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print(f"[✓] Obsidian : {note_path}")

    print(f"\n{'─'*55}\n")


if __name__ == "__main__":
    main()
