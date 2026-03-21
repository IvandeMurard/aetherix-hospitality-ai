"""
scripts/veille_proactive.py
Veille hebdomadaire automatisée — hotel tech, agentique IA, Apaleo/Mews, YC, hospitalitynet.

Modes :
  python scripts/veille_proactive.py              # rapport complet → Linear + repo
  python scripts/veille_proactive.py --dry-run    # simulation, pas d'écriture
  python scripts/veille_proactive.py --no-linear  # rapport sans ticket Linear

Sources surveillées :
  - hospitalitynet.org (RSS)
  - Apaleo blog / changelog
  - Mews blog
  - Y Combinator (W/S batches — filtre hospitality/F&B/forecasting)
  - Hacker News / recherche web hotel tech + agentique

Prérequis :
  ANTHROPIC_API_KEY  — pour l'analyse et la synthèse
  LINEAR_API_KEY     — lin_api_...
  LINEAR_TEAM_ID     — UUID équipe
"""

from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import httpx

# ─── Config ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
VEILLE_OUTPUT_DIR = REPO_ROOT / "docs" / "veille"
MAX_AGE_DAYS = 7

LINEAR_API = "https://api.linear.app/graphql"

# Sources RSS/Atom
RSS_SOURCES = [
    {
        "name": "Hospitalitynet",
        "url": "https://www.hospitalitynet.org/rss/all.xml",
        "tags": ["hospitalitynet", "hotel-industrie"],
    },
    {
        "name": "Apaleo Blog",
        "url": "https://apaleo.com/blog/feed",
        "tags": ["apaleo", "pms"],
    },
    {
        "name": "Mews Blog",
        "url": "https://www.mews.com/en/blog/rss.xml",
        "tags": ["mews", "pms"],
    },
]

# Requêtes de recherche web (fallback si RSS indisponible)
SEARCH_QUERIES = [
    "hotel tech AI agentic 2025 2026",
    "agentic AI hospitality operations",
    "Apaleo news 2026",
    "Mews hospitality news 2026",
    "Y Combinator hotel restaurant food forecasting startup",
    "hospitality F&B AI forecasting SaaS",
]

# Mots-clés de pertinence projet
RELEVANCE_KEYWORDS = [
    "agentic", "agentique", "forecasting", "F&B", "food and beverage",
    "hotel operations", "PMS", "apaleo", "mews", "hospitality AI",
    "revenue management", "demand prediction", "restaurant AI",
    "Y Combinator", "YC", "guac", "hotel tech", "proptech hospitality",
    "whatsapp hotel", "chatbot hotel",
]


# ─── Types ────────────────────────────────────────────────────────────────────

class Article(TypedDict):
    title: str
    url: str
    summary: str
    source: str
    published: str  # ISO date string
    tags: list[str]
    relevance_score: int  # 0-10


# ─── Fetchers ─────────────────────────────────────────────────────────────────

def _parse_rss_date(date_str: str) -> datetime | None:
    """Parse RSS date formats."""
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch_rss(source: dict, cutoff: datetime, client: httpx.Client) -> list[Article]:
    """Fetch and parse RSS feed, return articles newer than cutoff."""
    articles: list[Article] = []
    try:
        resp = client.get(source["url"], timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [!] RSS {source['name']} inaccessible : {e}", file=sys.stderr)
        return articles

    content = resp.text

    # Simple XML parsing without external deps
    items = re.findall(r"<item>(.*?)</item>", content, re.DOTALL)
    if not items:
        # Try <entry> for Atom feeds
        items = re.findall(r"<entry>(.*?)</entry>", content, re.DOTALL)

    for item in items:
        title_m = re.search(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.DOTALL)
        link_m = re.search(r"<link[^>]*>(?:<!\[CDATA\[)?(https?://[^<]+?)(?:\]\]>)?</link>", item, re.DOTALL)
        if not link_m:
            link_m = re.search(r'<link[^>]+href=["\']([^"\']+)["\']', item)
        desc_m = re.search(r"<description[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", item, re.DOTALL)
        if not desc_m:
            desc_m = re.search(r"<summary[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</summary>", item, re.DOTALL)
        date_m = re.search(r"<pubDate[^>]*>(.*?)</pubDate>", item, re.DOTALL)
        if not date_m:
            date_m = re.search(r"<published[^>]*>(.*?)</published>", item, re.DOTALL)
        if not date_m:
            date_m = re.search(r"<updated[^>]*>(.*?)</updated>", item, re.DOTALL)

        if not title_m or not link_m:
            continue

        title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
        url = link_m.group(1).strip()
        summary = re.sub(r"<[^>]+>", "", desc_m.group(1) if desc_m else "").strip()[:500]

        pub_date = None
        if date_m:
            pub_date = _parse_rss_date(date_m.group(1))

        # Filter by age
        if pub_date:
            pub_aware = pub_date if pub_date.tzinfo else pub_date.replace(tzinfo=timezone.utc)
            if pub_aware < cutoff:
                continue
            pub_str = pub_aware.strftime("%Y-%m-%d")
        else:
            pub_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        articles.append({
            "title": title,
            "url": url,
            "summary": summary,
            "source": source["name"],
            "published": pub_str,
            "tags": source["tags"].copy(),
            "relevance_score": 0,  # scored later by Claude
        })

    return articles


def score_articles_with_claude(articles: list[Article], api_key: str) -> list[Article]:
    """
    Use Claude API to score each article's relevance (0-10) for the Aetherix project.
    Articles with score >= 5 are kept; others are filtered out.
    """
    if not articles:
        return articles

    # Build batch prompt
    articles_text = "\n\n".join(
        f"[{i+1}] Source: {a['source']}\nTitre: {a['title']}\nRésumé: {a['summary'][:300]}"
        for i, a in enumerate(articles)
    )

    project_context = textwrap.dedent("""
        Projet : Aetherix — IA agentique pour opérations F&B hôtelières.
        - Prédiction de la demande F&B (restaurant d'hôtel)
        - Intégrations PMS : Apaleo (prioritaire), Mews
        - Alertes proactives via WhatsApp
        - Stack : FastAPI, Claude AI, pgvector
        - Concurrents/références : Guac.com (YC), Mews Agents
        - Phase actuelle : construction architecture + intégrations de base
    """)

    prompt = textwrap.dedent(f"""
        Tu es un analyste de veille stratégique pour une startup hospitality tech.

        {project_context}

        Pour chaque article ci-dessous, attribue un score de pertinence de 0 à 10 :
        - 8-10 : Directement actionnable pour le projet (nouveau concurrent, technologie clé, opportunité marché)
        - 6-7 : Pertinent, apporte du contexte utile
        - 3-5 : Informatif mais peu d'impact direct
        - 0-2 : Non pertinent

        Articles :
        {articles_text}

        Réponds UNIQUEMENT en JSON valide, tableau de {len(articles)} objets :
        [{{"index": 1, "score": X, "raison": "..."}}]
        Pas de markdown, pas d'explication hors JSON.
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
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        # Strip markdown fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
        scores = json.loads(raw)
        for item in scores:
            idx = item["index"] - 1
            if 0 <= idx < len(articles):
                articles[idx]["relevance_score"] = item["score"]
                if item.get("raison"):
                    articles[idx]["summary"] += f"\n\n_Pertinence : {item['raison']}_"
    except Exception as e:
        print(f"  [!] Scoring Claude échoué : {e}", file=sys.stderr)
        # Fallback : keyword scoring
        for article in articles:
            text = (article["title"] + " " + article["summary"]).lower()
            score = sum(1 for kw in RELEVANCE_KEYWORDS if kw.lower() in text)
            article["relevance_score"] = min(score * 2, 10)

    return articles


def synthesize_report(articles: list[Article], api_key: str) -> str:
    """Use Claude to generate a structured weekly intelligence brief."""
    if not articles:
        return "_Aucun contenu pertinent trouvé cette semaine._"

    articles_text = "\n\n".join(
        f"**[{a['relevance_score']}/10]** {a['source']} — {a['published']}\n"
        f"**{a['title']}**\n{a['summary'][:400]}\n{a['url']}"
        for a in sorted(articles, key=lambda x: x["relevance_score"], reverse=True)
    )

    prompt = textwrap.dedent(f"""
        Tu es un analyste de veille stratégique pour Aetherix (IA agentique F&B hôtelier).

        Synthétise ces articles en un rapport hebdomadaire structuré en français.
        Format souhaité :

        ## Faits marquants
        (2-3 insights les plus importants, avec implication pour Aetherix)

        ## Articles sélectionnés
        (Liste structurée, triée par pertinence décroissante)

        ## Signaux à surveiller
        (Tendances émergentes, concurrents, technologies)

        ## Actions recommandées
        (1-3 actions concrètes pour l'équipe Aetherix)

        Articles cette semaine :
        {articles_text}

        Sois concis et orienté action. Si un article justifie une story Linear, indique-le explicitement.
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
                "model": "claude-sonnet-4-6",
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"  [!] Synthèse Claude échouée : {e}", file=sys.stderr)
        # Fallback : liste brute
        lines = [f"- [{a['relevance_score']}/10] **{a['title']}** ({a['source']})\n  {a['url']}" for a in articles]
        return "\n".join(lines)


# ─── Linear ───────────────────────────────────────────────────────────────────

def create_linear_issue(title: str, description: str, api_key: str, team_id: str) -> dict:
    """Crée un ticket Linear et retourne {identifier, url}."""
    # Get Strategic Intelligence label
    label_resp = httpx.post(
        LINEAR_API,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        json={
            "query": "query Labels($t: String!) { team(id: $t) { labels { nodes { id name } } } }",
            "variables": {"t": team_id},
        },
        timeout=15,
    )
    label_resp.raise_for_status()
    nodes = label_resp.json().get("data", {}).get("team", {}).get("labels", {}).get("nodes", [])
    label_id = next((n["id"] for n in nodes if "intelligence" in n["name"].lower()), None)

    create_resp = httpx.post(
        LINEAR_API,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        json={
            "query": """
                mutation CI($t: String!, $ti: String!, $d: String!, $l: [String!], $p: Int) {
                  issueCreate(input: {teamId: $t, title: $ti, description: $d, labelIds: $l, priority: $p}) {
                    success
                    issue { id identifier url title }
                  }
                }
            """,
            "variables": {
                "t": team_id,
                "ti": title,
                "d": description,
                "l": [label_id] if label_id else [],
                "p": 3,  # medium
            },
        },
        timeout=15,
    )
    create_resp.raise_for_status()
    issue = create_resp.json().get("data", {}).get("issueCreate", {}).get("issue", {})
    if not issue:
        raise RuntimeError(f"Linear error: {create_resp.json()}")
    return issue


# ─── Output ───────────────────────────────────────────────────────────────────

def save_report_to_repo(title: str, body: str, dry_run: bool) -> Path:
    """Sauvegarde le rapport dans docs/veille/ pour sync Obsidian via git."""
    VEILLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^\w]+", "-", title.lower())[:50]
    dest = VEILLE_OUTPUT_DIR / f"{date_str}-{slug}.md"

    front_matter = textwrap.dedent(f"""\
        ---
        title: "{title}"
        date: {date_str}
        type: veille-hebdomadaire
        tags: [veille, intelligence, hotel-tech, automatique]
        source: github-actions
        ---
    """)
    content = f"{front_matter}\n# {title}\n\n{body}\n"

    if dry_run:
        print(f"[dry-run] Écrirait : {dest}")
        print(content[:400] + "...")
        return dest

    dest.write_text(content, encoding="utf-8")
    return dest


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Veille hebdomadaire automatisée — Aetherix")
    parser.add_argument("--dry-run",   action="store_true", help="Simulation sans écriture ni Linear")
    parser.add_argument("--no-linear", action="store_true", help="Rapport sans ticket Linear")
    parser.add_argument("--min-score", type=int, default=5, help="Score min pour inclure un article (défaut: 5)")
    args = parser.parse_args()

    print(f"\n{'─'*60}")
    print(f"  Veille Hebdomadaire Aetherix  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'─'*60}\n")

    api_key     = os.environ.get("ANTHROPIC_API_KEY", "")
    linear_key  = os.environ.get("LINEAR_API_KEY", "")
    linear_team = os.environ.get("LINEAR_TEAM_ID", "")

    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    print(f"Période couverte : {cutoff.strftime('%Y-%m-%d')} → aujourd'hui\n")

    # 1. Collecter les articles RSS
    all_articles: list[Article] = []
    with httpx.Client(headers={"User-Agent": "Aetherix-Veille/1.0"}) as client:
        for source in RSS_SOURCES:
            print(f"[+] Fetching {source['name']}...")
            arts = fetch_rss(source, cutoff, client)
            print(f"    → {len(arts)} articles récents")
            all_articles.extend(arts)

    if not all_articles:
        print("[!] Aucun article collecté (sources RSS indisponibles ?)")
        print("    Pour un rapport manuel, utiliser intelligence_report.py")
        return

    print(f"\n{len(all_articles)} articles collectés au total\n")

    # 2. Scorer avec Claude
    if api_key:
        print("[+] Scoring avec Claude...")
        all_articles = score_articles_with_claude(all_articles, api_key)
    else:
        print("[!] ANTHROPIC_API_KEY absente — scoring par mots-clés uniquement")
        for article in all_articles:
            text = (article["title"] + " " + article["summary"]).lower()
            score = sum(1 for kw in RELEVANCE_KEYWORDS if kw.lower() in text)
            article["relevance_score"] = min(score * 2, 10)

    # 3. Filtrer par score minimum
    relevant = [a for a in all_articles if a["relevance_score"] >= args.min_score]
    print(f"→ {len(relevant)}/{len(all_articles)} articles retenus (score >= {args.min_score})\n")

    if not relevant:
        print("[i] Aucun article suffisamment pertinent cette semaine.")
        title = f"Veille Hebdomadaire — {datetime.now().strftime('%d %B %Y')} (rien de notable)"
        body = "_Aucun article pertinent cette semaine pour Aetherix._"
    else:
        # 4. Synthèse Claude
        print("[+] Synthèse du rapport...")
        if api_key:
            body = synthesize_report(relevant, api_key)
        else:
            lines = [
                f"- [{a['relevance_score']}/10] **{a['title']}** ({a['source']} — {a['published']})\n  {a['url']}"
                for a in sorted(relevant, key=lambda x: x["relevance_score"], reverse=True)
            ]
            body = "\n".join(lines)
        title = f"Veille Hebdomadaire — {datetime.now().strftime('%d %B %Y')}"

    # 5. Sauvegarder dans le repo (pour sync Obsidian via git pull)
    report_path = save_report_to_repo(title, body, dry_run=args.dry_run)
    if not args.dry_run:
        print(f"[✓] Rapport sauvegardé : {report_path.relative_to(REPO_ROOT)}")

    # 6. Créer ticket Linear (si articles pertinents et clés disponibles)
    if relevant and not args.no_linear and not args.dry_run:
        if linear_key and linear_team:
            try:
                linear_desc = f"{body}\n\n---\n\n_Rapport généré automatiquement par GitHub Actions._\n_Fichier : `{report_path.relative_to(REPO_ROOT)}`_"
                issue = create_linear_issue(
                    title=f"[Veille] {title}",
                    description=linear_desc[:10000],
                    api_key=linear_key,
                    team_id=linear_team,
                )
                print(f"[✓] Linear : {issue.get('identifier')} — {issue.get('url')}")
            except Exception as e:
                print(f"[!] Linear ignoré : {e}", file=sys.stderr)
        else:
            print("[!] LINEAR_API_KEY ou LINEAR_TEAM_ID absentes — Linear ignoré")
    elif args.dry_run:
        print(f"[dry-run] Créerait Linear : '{title}'")

    print(f"\n{'─'*60}\n")


if __name__ == "__main__":
    main()
