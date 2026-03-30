#!/usr/bin/env python3
"""
Veille proactive Aetherix
━━━━━━━━━━━━━━━━━━━━━━━━
Scrape → Score (Claude Haiku) → Draft → [human approval] → Push Linear

Usage:
  python scripts/veille_proactive.py [--min-score N] [--dry-run]
  python scripts/veille_proactive.py --push-linear docs/veille/draft-YYYY-MM-DD.json
"""

import argparse
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# Charge .env si présent (local dev + Claude Code cloud)
sys.path.insert(0, str(Path(__file__).parent))
from _env_loader import load_env
load_env()

# ─── Config ───────────────────────────────────────────────────────────────────

# ─── Sources ─────────────────────────────────────────────────────────────────

SOURCES = [
    {
        "name": "Hospitalitynet",
        "type": "rss",
        "url": "https://www.hospitalitynet.org/rss/rss.xml",
        "category": "hotel-tech",
    },
    {
        "name": "Mews Blog",
        "type": "rss",
        "url": "https://www.mews.com/en/blog/rss.xml",
        "category": "pms",
    },
    {
        "name": "Apaleo Blog",
        "type": "rss",
        "url": "https://apaleo.com/blog/feed",
        "category": "pms",
    },
    {
        "name": "Hacker News — hotel AI",
        "type": "hn",
        "query": "hotel restaurant AI forecast",
        "category": "tech",
    },
    {
        "name": "Hacker News — MCP agents",
        "type": "hn",
        "query": "MCP agent tool calling hospitality",
        "category": "agent-first",
    },
]

# ─── Scoring prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un analyste stratégique pour Aetherix, une plateforme IA agentique B2B pour les opérations F&B hôtelières.

Contexte projet Aetherix :
- Mission : anticiper, alerter et recommander sur les opérations F&B (couverts, staffing, inventaire)
- Stack : FastAPI + Python + Supabase (PostgreSQL) + Qdrant (vecteurs) + Next.js + Claude (Anthropic)
- Intégrations PMS : Apaleo (prioritaire, OAuth2), Mews (secondaire, webhooks)
- Delivery : WhatsApp (Twilio), dashboard manager
- Pivot stratégique actuel : exposer Aetherix comme primitive agent-callable via MCP Server
- Phase en cours : Phase 0 (architecture + intégrations base), bientôt Phase 1 (forecasting F&B Prophet + LLM)

Critères de pertinence (score sur 10) :
  +3 : Impacte directement la roadmap ou une décision technique (MCP, PMS, forecasting, IA agentique)
  +3 : Révèle un concurrent direct ou une opportunité de marché hôtelier
  +2 : Information actionnable → justifie une nouvelle story Linear
  +1 : Contenu récent (moins de 7 jours)
  +1 : Source fiable (hospitalitynet.org, YC, Apaleo/Mews officiel, a16z, arXiv)

Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ni après."""

USER_PROMPT_TEMPLATE = """Analyse cet article pour Aetherix :

Titre : {title}
Source : {source}
Date : {date}
Résumé : {content}

Réponds en JSON strict :
{{
  "score": <entier 0-10>,
  "pourquoi": "<1 phrase : pourquoi ce score>",
  "lien_projet": "<1 phrase : lien concret avec Aetherix>",
  "action": "<titre de story Linear proposée, ou null si aucune action>",
  "tags": ["<tag1>", "<tag2>"]
}}"""


# ─── HTTP helper ──────────────────────────────────────────────────────────────

def http_get(url: str, timeout: int = 15) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Aetherix-Veille/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠️  HTTP error [{url[:70]}]: {e}", file=sys.stderr)
        return None


# ─── Fetchers ─────────────────────────────────────────────────────────────────

def fetch_rss(url: str) -> list[dict]:
    raw = http_get(url)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
        items = []
        for item in root.findall(".//item")[:10]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()[:600]
            pub = (item.findtext("pubDate") or "").strip()
            if title and link:
                items.append({"title": title, "url": link, "content": desc, "date": pub})
        return items
    except ET.ParseError as e:
        print(f"  ⚠️  RSS parse error: {e}", file=sys.stderr)
        return []


def fetch_hn(query: str) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={encoded}&tags=story&hitsPerPage=10"
    raw = http_get(url)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        items = []
        for hit in data.get("hits", []):
            title = hit.get("title", "").strip()
            link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            created = hit.get("created_at", "")
            if title:
                items.append({
                    "title": title,
                    "url": link,
                    "content": f"HN — {hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments",
                    "date": created,
                })
        return items
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  ⚠️  HN parse error: {e}", file=sys.stderr)
        return []


# ─── Scoring ──────────────────────────────────────────────────────────────────

def score_article(article: dict, source_name: str, api_key: str) -> dict:
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 350,
        "system": SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(
                title=article["title"],
                source=source_name,
                date=article["date"][:30],
                content=article["content"][:500],
            ),
        }],
    }).encode()

    try:
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=20) as resp:
            body = json.loads(resp.read())

        text = body["content"][0]["text"].strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        return json.loads(text)

    except Exception as e:
        print(f"  ⚠️  Scoring error '{article['title'][:50]}': {e}", file=sys.stderr)
        return {"score": 0, "pourquoi": f"Erreur: {e}", "lien_projet": "", "action": None, "tags": []}


# ─── Report generation ────────────────────────────────────────────────────────

def build_report(date_str: str, results: list[dict], min_score: int) -> str:
    actionable = [r for r in results if r["analysis"].get("action")]
    informational = [r for r in results if not r["analysis"].get("action")]

    lines = [
        "---",
        f"date: {date_str}",
        "type: draft-veille",
        f"articles_retenus: {len(results)}",
        f"min_score: {min_score}",
        "---",
        "",
        f"# Veille Aetherix — {date_str}",
        "",
        f"**{len(results)} articles retenus** (seuil : {min_score}/10) · "
        f"{len(actionable)} actions Linear · {len(informational)} informationnels",
        "",
        "---",
        "",
    ]

    if actionable:
        lines += ["## ✅ Actions recommandées (→ Linear)", ""]
        for i, item in enumerate(actionable, 1):
            a = item["analysis"]
            lines += [
                f"### {i}. {item['article']['title']}",
                f"**Source :** {item['source_name']} | **Score :** {a['score']}/10 | **Date :** {item['article']['date'][:25]}",
                f"**URL :** {item['article']['url']}",
                "",
                f"**Pourquoi :** {a['pourquoi']}",
                f"**Lien projet :** {a['lien_projet']}",
                f"**Action Linear :** `{a['action']}`",
                f"**Tags :** {' '.join(f'`{t}`' for t in a.get('tags', []))}",
                "",
            ]

    if informational:
        lines += ["## 📰 Articles retenus (informationnels)", ""]
        for i, item in enumerate(informational, 1):
            a = item["analysis"]
            lines += [
                f"### {i}. {item['article']['title']}",
                f"**Source :** {item['source_name']} | **Score :** {a['score']}/10 | **Date :** {item['article']['date'][:25]}",
                f"**URL :** {item['article']['url']}",
                "",
                f"**Pourquoi :** {a['pourquoi']}",
                f"**Lien projet :** {a['lien_projet']}",
                f"**Tags :** {' '.join(f'`{t}`' for t in a.get('tags', []))}",
                "",
            ]

    return "\n".join(lines)


# ─── Linear push ──────────────────────────────────────────────────────────────

def push_to_linear(api_key: str, team_id: str, item: dict) -> str | None:
    a = item["analysis"]
    title = f"[Veille] {a['action']}"
    description = (
        f"# Veille Aetherix — {item.get('date_str', '')}\n\n"
        f"**Source :** {item['source_name']}\n"
        f"**Article :** [{item['article']['title']}]({item['article']['url']})\n"
        f"**Score de pertinence :** {a['score']}/10\n\n"
        f"## Pourquoi c'est important\n{a['pourquoi']}\n\n"
        f"## Lien avec Aetherix\n{a['lien_projet']}\n\n"
        f"**Tags :** {' '.join(f'`{t}`' for t in a.get('tags', []))}\n"
    )

    mutation = (
        "mutation CreateIssue($title: String!, $description: String!, "
        "$teamId: String!, $priority: Int!) {"
        "  issueCreate(input: {title: $title, description: $description, "
        "teamId: $teamId, priority: $priority}) {"
        "    success issue { id identifier url } } }"
    )

    payload = json.dumps({
        "query": mutation,
        "variables": {"title": title, "description": description, "teamId": team_id, "priority": 3},
    }).encode()

    try:
        request = urllib.request.Request(
            "https://api.linear.app/graphql",
            data=payload,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as resp:
            data = json.loads(resp.read())
        issue = data.get("data", {}).get("issueCreate", {}).get("issue")
        if issue:
            return issue["url"]
        if errors := data.get("errors"):
            print(f"  ⚠️  Linear API: {errors}", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠️  Linear push error: {e}", file=sys.stderr)
    return None


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_generate(args):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY manquant", file=sys.stderr)
        sys.exit(1)

    date_str = datetime.date.today().isoformat()
    output_dir = Path("docs/veille")
    output_dir.mkdir(parents=True, exist_ok=True)
    draft_md = output_dir / f"draft-{date_str}.md"
    draft_json = output_dir / f"draft-{date_str}.json"

    print(f"🔍 Veille Aetherix — {date_str}")
    print(f"   Seuil : {args.min_score}/10 | Mode : {'dry-run' if args.dry_run else 'live'}\n")

    seen_urls: set = set()
    all_results = []

    for source in SOURCES:
        print(f"📡 {source['name']}...")
        articles = (
            fetch_rss(source["url"]) if source["type"] == "rss"
            else fetch_hn(source.get("query", ""))
        )
        print(f"   {len(articles)} articles récupérés")

        for article in articles:
            url = article["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)

            analysis = score_article(article, source["name"], api_key)
            score = analysis.get("score", 0)

            if score >= args.min_score:
                print(f"   ✅ {score}/10 — {article['title'][:65]}")
                all_results.append({
                    "source_name": source["name"],
                    "source_category": source["category"],
                    "article": article,
                    "analysis": analysis,
                    "date_str": date_str,
                })
            else:
                print(f"   ⬜ {score}/10 — {article['title'][:65]}")

    print(f"\n📊 {len(all_results)} articles retenus (score ≥ {args.min_score})")

    if not all_results:
        msg = f"Aucun article pertinent cette semaine (seuil : {args.min_score}/10).\n"
        if not args.dry_run:
            draft_md.write_text(
                f"---\ndate: {date_str}\ntype: draft-veille\narticles_retenus: 0\n---\n\n"
                f"# Veille {date_str}\n\n{msg}", encoding="utf-8"
            )
            draft_json.write_text("[]", encoding="utf-8")
        else:
            print(f"📝 [DRY-RUN] {msg}")
        return

    report_md = build_report(date_str, all_results, args.min_score)

    if args.dry_run:
        print("\n📝 [DRY-RUN] Rapport :\n")
        print(report_md)
        return

    draft_md.write_text(report_md, encoding="utf-8")
    draft_json.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n📝 Brouillons sauvegardés :")
    print(f"   Markdown : {draft_md}  ← lisible pour validation")
    print(f"   JSON     : {draft_json}  ← utilisé par --push-linear")
    print("\n✅ Phase 1 terminée. En attente de validation humaine.")


def cmd_push_linear(args):
    api_key = os.environ.get("LINEAR_API_KEY")
    team_id = os.environ.get("LINEAR_TEAM_ID")

    if not api_key or not team_id:
        print("❌ LINEAR_API_KEY ou LINEAR_TEAM_ID manquant", file=sys.stderr)
        sys.exit(1)

    # Accept .md or .json — always load the .json sibling
    draft_path = Path(args.push_linear)
    json_path = draft_path.with_suffix(".json")
    if not json_path.exists():
        print(f"❌ Fichier JSON introuvable : {json_path}", file=sys.stderr)
        sys.exit(1)

    results = json.loads(json_path.read_text(encoding="utf-8"))
    actionable = [r for r in results if r["analysis"].get("action")]

    print(f"📤 Push Linear depuis : {json_path}")
    print(f"   {len(actionable)} actions à pousser\n")

    pushed = 0
    for item in actionable:
        url = push_to_linear(api_key, team_id, item)
        if url:
            print(f"   ✅ {item['analysis']['action'][:60]} → {url}")
            pushed += 1
        else:
            print(f"   ❌ Échec : {item['analysis']['action']}")

    print(f"\n✅ {pushed}/{len(actionable)} issues Linear créées.")


def main():
    parser = argparse.ArgumentParser(description="Veille proactive Aetherix")
    parser.add_argument("--min-score", type=int, default=7, metavar="N",
                        help="Score minimum de pertinence (défaut : 7)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulation sans écriture ni push")
    parser.add_argument("--push-linear", metavar="PATH",
                        help="Chemin vers draft-YYYY-MM-DD.json — pousse vers Linear sans re-scraper")
    args = parser.parse_args()

    if args.push_linear:
        cmd_push_linear(args)
    else:
        cmd_generate(args)


if __name__ == "__main__":
    main()
