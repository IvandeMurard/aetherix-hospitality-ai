#!/usr/bin/env python
"""Linear audit — dumps the Hospitalityagent team state as a markdown report.

Read-only. No writes, no mutations. Reads LINEAR_API_KEY + LINEAR_TEAM_ID from
environment (or uses the known team ID from CLAUDE.md as fallback).

Usage:
    python scripts/linear_audit.py > linear_state.md

Output:
    Markdown report with:
    - Summary counts by state
    - Epic → Story hierarchy table
    - Duplicate candidates (same title prefix)
    - Stale issues (In Progress > 14 days)
    - Issues missing Acceptance Criteria
    - Full issue table (identifier, title, state, estimate, labels, parent)

Requires: Python 3.8+, stdlib only (urllib). No pip install needed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

API = "https://api.linear.app/graphql"
KEY = os.environ.get("LINEAR_API_KEY", "").strip()
TEAM_ID = os.environ.get("LINEAR_TEAM_ID", "2f6bb5e2-d735-4769-9377-11fe186aa0ad").strip()

if not KEY:
    sys.stderr.write("ERROR: LINEAR_API_KEY not set in environment.\n")
    sys.stderr.write("On Windows PowerShell:  $env:LINEAR_API_KEY = 'lin_api_...'\n")
    sys.exit(1)


def gql(query: str, variables: dict) -> dict:
    """POST a GraphQL query to Linear. Raises on HTTP or GraphQL error."""
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        API, data=body, method="POST",
        headers={"Authorization": KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


ISSUES_QUERY = """
query Issues($teamId: String!, $cursor: String) {
  team(id: $teamId) {
    name
    key
    issues(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id
        identifier
        title
        description
        state { name type }
        priority
        estimate
        createdAt
        updatedAt
        startedAt
        completedAt
        canceledAt
        dueDate
        assignee { name }
        labels { nodes { name } }
        parent { identifier title }
        children { nodes { identifier } }
        url
      }
    }
  }
}
"""


def fetch_all_issues() -> tuple[str, list[dict]]:
    """Paginate through every issue in the team."""
    cursor = None
    all_issues: list[dict] = []
    team_name = ""
    page = 1
    while True:
        sys.stderr.write(f"  fetching page {page}...\n")
        data = gql(ISSUES_QUERY, {"teamId": TEAM_ID, "cursor": cursor})
        team = data["team"]
        team_name = f"{team['name']} ({team['key']})"
        issues = team["issues"]
        all_issues.extend(issues["nodes"])
        if not issues["pageInfo"]["hasNextPage"]:
            break
        cursor = issues["pageInfo"]["endCursor"]
        page += 1
    return team_name, all_issues


def days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - t).days


def has_acceptance_criteria(desc: str | None) -> bool:
    if not desc:
        return False
    d = desc.lower()
    return any(marker in d for marker in (
        "acceptance criteria", "critères d'acceptation",
        "- [ ]", "- [x]", "ac1", "ac 1",
    ))


def priority_label(p: int | None) -> str:
    return {0: "—", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}.get(p or 0, "—")


def md_escape(s: str | None) -> str:
    if not s:
        return ""
    return s.replace("|", "\\|").replace("\n", " ").strip()


def main() -> int:
    sys.stderr.write(f"Linear audit — team {TEAM_ID}\n")
    try:
        team_name, issues = fetch_all_issues()
    except Exception as exc:
        sys.stderr.write(f"FATAL: {exc}\n")
        return 1

    sys.stderr.write(f"Fetched {len(issues)} issues from {team_name}\n")

    # -------- Summary by state --------
    by_state: dict[str, int] = {}
    for i in issues:
        s = i["state"]["name"]
        by_state[s] = by_state.get(s, 0) + 1

    # -------- Epics (issues with children) and orphan stories --------
    epics = [i for i in issues if i["children"]["nodes"]]
    stories_by_parent: dict[str, list[dict]] = {}
    orphans: list[dict] = []
    for i in issues:
        if i["parent"]:
            stories_by_parent.setdefault(i["parent"]["identifier"], []).append(i)
        elif not i["children"]["nodes"]:
            orphans.append(i)

    # -------- Stale (In Progress > 14 days) --------
    stale = []
    for i in issues:
        if i["state"]["type"] == "started":
            age = days_since(i["startedAt"] or i["updatedAt"])
            if age and age > 14:
                stale.append((i, age))

    # -------- Duplicate candidates (identical title, case-insensitive) --------
    title_map: dict[str, list[dict]] = {}
    for i in issues:
        key = i["title"].lower().strip()
        title_map.setdefault(key, []).append(i)
    dup_groups = [v for v in title_map.values() if len(v) > 1]

    # -------- Issues missing AC --------
    unfinished = [i for i in issues if i["state"]["type"] not in ("completed", "canceled")]
    missing_ac = [i for i in unfinished if not has_acceptance_criteria(i["description"])]

    # ============================================================
    # Markdown output
    # ============================================================
    out = sys.stdout.write

    out(f"# Linear audit — {team_name}\n\n")
    out(f"> Generated {datetime.now(timezone.utc).isoformat()} · "
        f"{len(issues)} issues\n\n")

    out("## 1. Summary by state\n\n")
    out("| State | Count |\n|---|---:|\n")
    for state, count in sorted(by_state.items(), key=lambda x: -x[1]):
        out(f"| {state} | {count} |\n")
    out("\n")

    out(f"## 2. Stale In-Progress (> 14 days) — {len(stale)} issues\n\n")
    if stale:
        out("| Issue | Title | Days since started | Assignee |\n"
            "|---|---|---:|---|\n")
        for i, age in sorted(stale, key=lambda x: -x[1]):
            assignee = (i["assignee"] or {}).get("name", "—")
            out(f"| {i['identifier']} | {md_escape(i['title'])} | {age} | {assignee} |\n")
    else:
        out("*None.*\n")
    out("\n")

    out(f"## 3. Duplicate title candidates — {len(dup_groups)} groups\n\n")
    if dup_groups:
        for group in dup_groups:
            ids = ", ".join(i["identifier"] for i in group)
            out(f"- **{md_escape(group[0]['title'])}** → {ids}\n")
    else:
        out("*No exact-title duplicates detected.*\n")
    out("\n")

    out(f"## 4. Unfinished issues missing Acceptance Criteria "
        f"— {len(missing_ac)} / {len(unfinished)}\n\n")
    out("Heuristic: no `- [ ]`, `- [x]`, `acceptance criteria`, or `AC1` markers "
        "in description.\n\n")
    if missing_ac:
        out("| Issue | State | Title |\n|---|---|---|\n")
        for i in missing_ac[:50]:
            out(f"| {i['identifier']} | {i['state']['name']} | "
                f"{md_escape(i['title'])} |\n")
        if len(missing_ac) > 50:
            out(f"\n*...and {len(missing_ac) - 50} more.*\n")
    else:
        out("*All unfinished issues have AC.*\n")
    out("\n")

    out(f"## 5. Epics and their stories — {len(epics)} epics\n\n")
    for epic in sorted(epics, key=lambda x: x["identifier"]):
        state = epic["state"]["name"]
        children = stories_by_parent.get(epic["identifier"], [])
        out(f"### {epic['identifier']} · {md_escape(epic['title'])} "
            f"*[{state}]*\n\n")
        if epic["description"]:
            snippet = md_escape(epic["description"][:120])
            out(f"> {snippet}\n\n")
        if children:
            out("| Story | State | Estimate | Title |\n"
                "|---|---|---:|---|\n")
            for c in sorted(children, key=lambda x: x["identifier"]):
                est = c["estimate"] if c["estimate"] is not None else "—"
                out(f"| {c['identifier']} | {c['state']['name']} | {est} | "
                    f"{md_escape(c['title'])} |\n")
        else:
            out("*No sub-issues.*\n")
        out("\n")

    out(f"## 6. Orphan issues (no parent, no children) — {len(orphans)}\n\n")
    if orphans:
        out("| Issue | State | Priority | Estimate | Title |\n"
            "|---|---|---|---:|---|\n")
        for i in sorted(orphans, key=lambda x: x["identifier"]):
            est = i["estimate"] if i["estimate"] is not None else "—"
            out(f"| {i['identifier']} | {i['state']['name']} | "
                f"{priority_label(i['priority'])} | {est} | "
                f"{md_escape(i['title'])} |\n")
    out("\n")

    out("## 7. Full issue table\n\n")
    out("| Issue | State | Priority | Estimate | Labels | Parent | Title |\n"
        "|---|---|---|---:|---|---|---|\n")
    for i in sorted(issues, key=lambda x: x["identifier"]):
        est = i["estimate"] if i["estimate"] is not None else "—"
        labels = ", ".join(l["name"] for l in i["labels"]["nodes"]) or "—"
        parent = i["parent"]["identifier"] if i["parent"] else "—"
        out(f"| [{i['identifier']}]({i['url']}) | {i['state']['name']} | "
            f"{priority_label(i['priority'])} | {est} | {labels} | {parent} | "
            f"{md_escape(i['title'])} |\n")

    sys.stderr.write("Done.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
