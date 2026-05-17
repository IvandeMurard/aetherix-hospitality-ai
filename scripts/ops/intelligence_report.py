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

# Charge .env si présent (local dev + Claude Code cloud)
sys.path.insert(0, str(Path(__file__).parent))
from _env_loader import load_env
load_env()

# ─── Configuration ────────────────────────────────────────────────────────────

REPO_ROOT  = Path(__file__).parent.parent.resolve()
VAULT_ROOT = Path(os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    r"C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality",
))

# Vault path: env var overrides hardcoded Windows path (enables Linux/CI usage)
_vault_env = os.environ.get("OBSIDIAN_VAULT_PATH", "")
VAULT_ROOT = Path(_vault_env) if _vault_env else Path(r"C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality")
# Vault path: use OBSIDIAN_VAULT_PATH env var (supports WSL, Linux, CI).
# Fallback to the Windows path for local native dev.
_vault_env = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    r"C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality",
)
VAULT_ROOT = Path(_vault_env)
VAULT_INTEL_DIR = VAULT_ROOT / "AI Reports" / "Intelligence"

# Fallback: if vault not accessible, stage notes locally in the repo
STAGING_DIR = REPO_ROOT / "docs" / "veille-staging"

LINEAR_API = "https://api.linear.app/graphql"

# Mots-clés qui déclenchent automatiquement un ticket Linear en mode hook
STRATEGIC_KEYWORDS = [
    "concurrent", "compétiteur", "marché", "opportunité", "menace",
    "stratégi", "veille", "tendance", "disruption", "pivot",
    "competitor", "market", "opportunity", "threat", "strategic",
]

PRIORITY_MAP = {"urgent": 1, "high": 2, "medium": 3, "low": 4}

# Score minimum pour pousser vers Linear/Obsidian en mode réactif (0-10)
RELEVANCE_THRESHOLD = 7

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

    if not VAULT_ROOT.exists():
        print(f"[–] Obsidian vault introuvable sur ce système ({VAULT_ROOT}) — écriture ignorée.", file=sys.stderr)
        return dest

    VAULT_INTEL_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    try:
        VAULT_INTEL_DIR.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    except OSError:
        # Vault inaccessible (e.g., Windows OneDrive path on Linux) → stage locally
        staging_dest = STAGING_DIR / filename
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        staging_dest.write_text(content, encoding="utf-8")
        print(f"[!] Vault inaccessible → note stagée : {staging_dest}")
        return staging_dest
    return dest


# ─── Relevance scoring ────────────────────────────────────────────────────────

PROJECT_CONTEXT = """
Projet Aetherix : IA agentique pour opérations F&B hôtelières.
- Prédiction de la demande F&B (restaurant d'hôtel)
- Intégrations PMS : Apaleo (prioritaire), Mews
- Alertes proactives WhatsApp
- Phase actuelle : architecture + intégrations de base
- Concurrents/références : Guac.com (YC), Mews Agents
"""


def score_content_relevance(title: str, body: str) -> tuple[int, str]:
    """
    Évalue la pertinence d'un contenu pour le projet Aetherix via Claude.
    Retourne (score 0-10, justification).
    Fallback par mots-clés si ANTHROPIC_API_KEY absente.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        import textwrap
        prompt = textwrap.dedent(f"""
            Tu évalues la pertinence d'un contenu pour une startup hospitality tech.

            {PROJECT_CONTEXT}

            Critères (score de 0 à 10) :
            - 8-10 : Directement actionnable (concurrent direct, technologie clé, opportunité marché immédiate)
            - 6-7 : Pertinent, apporte du contexte utile au projet
            - 4-5 : Informatif mais impact faible
            - 0-3 : Non pertinent

            Titre : {title}
            Contenu : {body[:1000]}

            Réponds UNIQUEMENT en JSON : {{"score": X, "raison": "..."}}
        """)
        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 256,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=20,
            )
            resp.raise_for_status()
            raw = resp.json()["content"][0]["text"].strip()
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
            data = json.loads(raw)
            return int(data.get("score", 0)), data.get("raison", "")
        except Exception as e:
            print(f"[!] Scoring ignoré : {e}", file=sys.stderr)

    # Fallback : mots-clés
    keywords = [
        "agentic", "agentique", "forecasting", "F&B", "food and beverage",
        "hotel", "PMS", "apaleo", "mews", "hospitality AI", "YC", "guac",
        "demand prediction", "revenue management", "concurrent", "startup",
    ]
    text = (title + " " + body).lower()
    score = sum(1 for kw in keywords if kw.lower() in text)
    return min(score * 2, 10), "scoring par mots-clés (ANTHROPIC_API_KEY absente)"


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
    parser.add_argument("--title",         help="Titre du rapport / ticket")
    parser.add_argument("--body",          help="Corps : chemin vers un .md OU texte direct OU '-' pour stdin")
    parser.add_argument("--linear",        action="store_true", help="Crée aussi un ticket Linear")
    parser.add_argument("--priority",      default="medium", choices=["urgent","high","medium","low"])
    parser.add_argument("--tags",          nargs="*", default=["intelligence","veille"])
    parser.add_argument("--dry-run",       action="store_true", help="Simulation sans écriture")
    parser.add_argument("--hook",          action="store_true", help="Mode hook Stop (lit stdin JSON)")
    parser.add_argument("--force",         action="store_true", help="Ignorer le gate de pertinence")
    parser.add_argument("--min-score",     type=int, default=RELEVANCE_THRESHOLD,
                        help=f"Score min pour pousser vers Linear/Obsidian (défaut: {RELEVANCE_THRESHOLD})")
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

    # 0. Gate de pertinence (mode réactif)
    if not args.force:
        score, raison = score_content_relevance(args.title, body)
        print(f"[i] Score de pertinence : {score}/10 — {raison}")
        if score < args.min_score:
            print(f"[–] Contenu non poussé (score {score} < seuil {args.min_score}).")
            print("    Utilisez --force pour ignorer ce seuil.")
            return
        print(f"[✓] Seuil atteint ({score} >= {args.min_score}) — publication en cours...")

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
