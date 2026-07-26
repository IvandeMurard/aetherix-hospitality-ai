#!/usr/bin/env python3
"""Agent d'hygiène architecturale — HOS-320 (Story 16.18).

Detects drift between what the repo *says* and what the repo *is*, then emits a
Markdown report. It never edits code and never writes to the eval dataset: the
workflow turns its output into a documentation-only PR that a human merges.

Four detectors, all static and deterministic — no network, no secrets, no
runtime access. That is deliberate: a hygiene agent that needs credentials is a
new attack surface, and Epic 16 NFR2 freezes new runtime surface.

  D1  harness drift   — CLAUDE.md vs AGENTS.md (same content, two harnesses)
  D2  doc → code      — backticked paths in docs resolve to files that exist
  D3  env sync        — vars documented in CLAUDE.md exist in backend/.env.example
  D4  eval gaps       — typed guardrail reasons (NFR2 / ADR-0009) that no
                        golden-dataset scenario exercises

Usage:
  python scripts/ops/hygiene_architecturale.py
  python scripts/ops/hygiene_architecturale.py --report docs/testing/evidence/hygiene/report.md
  python scripts/ops/hygiene_architecturale.py --json

Exit codes:
  0  clean — no drift
  1  drift found (the workflow opens a PR)
  2  error — a configured input is missing
"""
from __future__ import annotations

import argparse
import datetime
import difflib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/ops/ -> repo root

# Console output carries emoji; a Windows terminal defaults to cp1252 and would
# raise UnicodeEncodeError on them. CI is UTF-8, local dev is not (Points
# d'attention #2), and the script must behave the same on both.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ─── Config — the only node-specific block ───────────────────────────────────
# Porting this agent to another Mesh node (Tacet, Anima, Orchestrateur) means
# editing this block and nothing below it. Extract to a shared reusable workflow
# only once a *second* repo actually runs it (see HOS-320 §Out of scope).

# D1 — harness files expected to hold identical content. The first is canonical.
HARNESS_FILES = ["CLAUDE.md", "AGENTS.md"]

# D1 — lines allowed to differ between harnesses, as regex → justification.
# Symmetric with PLANNED_PATHS: a divergence is acceptable only if it is written
# down and justified. Without this, the first legitimate harness-specific
# instruction (Claude Code skills vs Codex conventions) would make D1 shout with
# no way to acknowledge it — and a linter nobody can silence gets deleted.
# An entry matching nothing is reported in turn: a stale exception is an
# unkept promise, same rule as PLANNED_PATHS.
HARNESS_EXCEPTIONS: dict[str, str] = {}

# D2 — docs scanned for backticked repo paths, and the prefixes that mark a
# token as a repo path (anything else is prose, a URL, or an absolute path).
DOC_SOURCES = [
    "CLAUDE.md",
    "docs/context/decisions-architecturales.md",
    "docs/context/open-decisions.md",
]
PATH_PREFIXES = ("backend/", "scripts/", "docs/", "eval/", ".github/", "tools/")

# D2 — paths the docs cite on purpose for code that is not built yet. Keeping
# this register explicit is the point: it separates "the doc is stale" (a bug)
# from "the doc describes unbuilt code" (a known, dated intention). An entry
# here is a promise — when the code lands, the entry goes.
PLANNED_PATHS = {
    "backend/app/models/graph/": "Graphe de contexte — Décision #24 / ADR-0008, Phase 4",
    "backend/app/services/context_graph_service.py": "Graphe de contexte — Décision #24 / ADR-0008, Phase 4",
    "backend/app/services/context_graph_queries/": "Graphe de contexte — Décision #24 / ADR-0008, Phase 4",
    "backend/app/providers/pos/": "POS ingestion — Décision #23 / ADR-0006, Phase 4",
    "backend/app/providers/pms/base.py": "PMS canonical schema — Décision #28 / ADR-0006 amendé, Phase 4",
}

# D3 — env var declarations.
ENV_EXAMPLE = "backend/.env.example"
ENV_DOC = "CLAUDE.md"
ENV_DOC_HEADING = "## Variables d'environnement"

# D4 — where typed guardrail reasons are declared, and the dataset that must
# exercise them.
GUARDRAIL_GLOB = "backend/app/**/*.py"
GOLDEN_DATASET = "eval/golden_dataset.jsonl"

# ─── Detector plumbing ────────────────────────────────────────────────────────


@dataclass
class Finding:
    detector: str
    title: str
    detail: str
    severity: str = "drift"  # "drift" counts toward the exit code; "info" does not


@dataclass
class Result:
    findings: list[Finding] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def drift(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "drift"]

    @property
    def info(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "info"]


def _read(rel: str) -> str | None:
    path = _ROOT / rel
    return path.read_text(encoding="utf-8") if path.is_file() else None


# ─── D1 · Harness drift ───────────────────────────────────────────────────────


def _missing_harness(name: str) -> Finding:
    """A declared harness file that is not on disk.

    This is drift, never a skip. `AGENTS.md` untracked meant CI checked out a
    repo without it, D1 bailed silently, and the report printed "✅ clean" for a
    detector that never ran — a false negative on the detector that justifies
    this story. A detector that loses its target must shout, not go quiet.
    """
    return Finding(
        detector="D1",
        title=f"Fichier harness déclaré mais introuvable : `{name}`",
        detail=f"`{name}` figure dans `HARNESS_FILES` mais n'est pas sur le disque — "
        "typiquement un fichier untracked que `actions/checkout` ne récupère pas. "
        "Le détecteur n'a donc rien pu comparer : ce résultat n'est pas « clean », il est aveugle. "
        "Soit committer le fichier, soit le retirer de `HARNESS_FILES`.",
    )


def _apply_exceptions(text: str, used: set[str]) -> list[str]:
    """Drop lines covered by HARNESS_EXCEPTIONS, recording which ones matched."""
    lines = text.splitlines()
    if not HARNESS_EXCEPTIONS:
        return lines

    kept = []
    for line in lines:
        for pattern in HARNESS_EXCEPTIONS:
            if re.search(pattern, line):
                used.add(pattern)
                break
        else:
            kept.append(line)
    return kept


def detect_harness_drift(result: Result) -> None:
    """CLAUDE.md and AGENTS.md must carry identical content.

    Self-references are normalised away — AGENTS.md legitimately calls itself
    AGENTS.md — so what remains is real divergence. This is the detector that
    catches a find-replace gone wrong (e.g. `claude-sonnet-4-6` rewritten to a
    model ID that does not exist).
    """
    canonical, *others = HARNESS_FILES
    base = _read(canonical)
    if base is None:
        result.findings.append(_missing_harness(canonical))
        return

    used_exceptions: set[str] = set()

    for other in others:
        text = _read(other)
        if text is None:
            result.findings.append(_missing_harness(other))
            continue

        # Normalise the one difference that is by design: the file's own name.
        normalised = text.replace(other, canonical)
        if normalised == base:
            continue

        left, right = _apply_exceptions(base, used_exceptions), _apply_exceptions(normalised, used_exceptions)
        if left == right:
            continue

        diff = list(
            difflib.unified_diff(
                left,
                right,
                fromfile=canonical,
                tofile=other,
                lineterm="",
                n=0,
            )
        )
        changed = sum(1 for line in diff if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))
        result.findings.append(
            Finding(
                detector="D1",
                title=f"{other} diverge de {canonical} ({changed} lignes)",
                detail="```diff\n" + "\n".join(diff) + "\n```",
            )
        )

    for pattern in sorted(set(HARNESS_EXCEPTIONS) - used_exceptions):
        result.findings.append(
            Finding(
                detector="D1",
                title=f"Exception harness périmée : `{pattern}`",
                detail=f"Justifiée par « {HARNESS_EXCEPTIONS[pattern]} », mais ne correspond plus à aucune ligne. "
                "La divergence a disparu — retirer l'entrée de `HARNESS_EXCEPTIONS`.",
                severity="info",
            )
        )


# ─── D2 · Doc → code ──────────────────────────────────────────────────────────

_BACKTICKED = re.compile(r"`([^`\s]+)`")


def detect_doc_paths(result: Result) -> None:
    """Every repo path cited in the docs must resolve to a real file or dir."""
    broken: dict[str, set[str]] = {}

    for source in DOC_SOURCES:
        text = _read(source)
        if text is None:
            result.skipped.append(f"D2: {source} introuvable")
            continue

        for token in _BACKTICKED.findall(text):
            if not token.startswith(PATH_PREFIXES):
                continue
            # Globs are illustrative patterns (`docs/adr/000X-*.md`), not claims
            # that a specific file exists.
            if "*" in token:
                continue
            # Strip trailing punctuation the prose may have glued on.
            candidate = token.rstrip(".,;:)")
            target = _ROOT / candidate
            if target.exists():
                continue
            broken.setdefault(candidate, set()).add(source)

    for candidate in sorted(broken):
        cited = ", ".join(f"`{s}`" for s in sorted(broken[candidate]))
        planned = PLANNED_PATHS.get(candidate)
        if planned:
            result.findings.append(
                Finding(
                    detector="D2",
                    title=f"Doc décrit du code non écrit : `{candidate}`",
                    detail=f"Cité dans {cited}. Intention connue et datée — {planned}. "
                    "Retirer de `PLANNED_PATHS` quand le code atterrit.",
                    severity="info",
                )
            )
            continue
        result.findings.append(
            Finding(
                detector="D2",
                title=f"Chemin cité mais inexistant : `{candidate}`",
                detail=f"Cité dans {cited}. Le fichier a été déplacé ou supprimé — corriger la référence. "
                "S'il s'agit de code non écrit assumé, l'inscrire dans `PLANNED_PATHS` avec sa justification.",
            )
        )


# ─── D3 · Env sync ────────────────────────────────────────────────────────────

_ENV_ASSIGN = re.compile(r"^([A-Z][A-Z0-9_]*)=", re.MULTILINE)
_ENV_DOCLINE = re.compile(r"^([A-Z][A-Z0-9_]*)\s+—", re.MULTILINE)


def detect_env_sync(result: Result) -> None:
    """Vars documented in CLAUDE.md must exist in backend/.env.example.

    Only this direction is drift. The reverse is expected: `.env.example` is the
    exhaustive source of truth (Points d'attention #1) while CLAUDE.md documents
    a curated subset, so undocumented vars are reported as info, not drift.
    """
    example = _read(ENV_EXAMPLE)
    doc = _read(ENV_DOC)
    if example is None or doc is None:
        result.skipped.append(f"D3: {ENV_EXAMPLE} ou {ENV_DOC} introuvable")
        return

    declared = set(_ENV_ASSIGN.findall(example))

    # Restrict to the env section so unrelated ALL-CAPS prose is not parsed.
    _, _, tail = doc.partition(ENV_DOC_HEADING)
    if not tail:
        result.skipped.append(f"D3: section « {ENV_DOC_HEADING} » absente de {ENV_DOC}")
        return
    section = tail.split("\n---", 1)[0]
    documented = set(_ENV_DOCLINE.findall(section))

    for name in sorted(documented - declared):
        result.findings.append(
            Finding(
                detector="D3",
                title=f"`{name}` documenté dans {ENV_DOC} mais absent de {ENV_EXAMPLE}",
                detail="La source de vérité config est `backend/.env.example` (Points d'attention #1) — "
                "un déploiement suivant CLAUDE.md ne trouverait pas cette variable.",
            )
        )

    undocumented = sorted(declared - documented)
    if undocumented:
        result.findings.append(
            Finding(
                detector="D3",
                title=f"{len(undocumented)} variables déclarées mais non documentées dans {ENV_DOC}",
                detail="Attendu (CLAUDE.md documente un sous-ensemble curé) — listé pour revue, non bloquant :\n"
                + ", ".join(f"`{n}`" for n in undocumented),
                severity="info",
            )
        )


# ─── D4 · Eval gaps ───────────────────────────────────────────────────────────

_REASON_CONST = re.compile(r'^REASON_[A-Z0-9_]+\s*=\s*"([a-z0-9_]+)"', re.MULTILINE)


def detect_eval_gaps(result: Result) -> None:
    """Typed guardrail reasons with no scenario in the golden dataset.

    NFR2 (ADR-0009) requires every guardrail trip to log a typed reason. A reason
    that no eval scenario exercises is an untested failure path. Reported as a
    proposal only — writing to the dataset would corrupt the merge gate it feeds
    (Décision #29), so a human authors the scenario.
    """
    dataset = _read(GOLDEN_DATASET)
    if dataset is None:
        result.skipped.append(f"D4: {GOLDEN_DATASET} introuvable")
        return

    reasons: dict[str, str] = {}
    for path in sorted(_ROOT.glob(GUARDRAIL_GLOB)):
        if "__pycache__" in path.parts:
            continue
        for literal in _REASON_CONST.findall(path.read_text(encoding="utf-8")):
            reasons.setdefault(literal, str(path.relative_to(_ROOT)).replace("\\", "/"))

    if not reasons:
        result.skipped.append("D4: aucune constante REASON_* trouvée")
        return

    for literal in sorted(reasons):
        if literal in dataset:
            continue
        result.findings.append(
            Finding(
                detector="D4",
                title=f"Raison typée sans scénario eval : `{literal}`",
                detail=f"Déclarée dans `{reasons[literal]}`, absente de `{GOLDEN_DATASET}`. "
                "Chemin d'échec non couvert — proposer un scénario (rédaction humaine, "
                "l'agent n'écrit jamais dans le dataset qui garde le merge).",
            )
        )


DETECTORS = (
    ("D1", "Drift harness", detect_harness_drift),
    ("D2", "Doc → code", detect_doc_paths),
    ("D3", "Sync env", detect_env_sync),
    ("D4", "Lacunes eval", detect_eval_gaps),
)


# ─── Report ───────────────────────────────────────────────────────────────────


def render_report(result: Result, today: str) -> str:
    lines = [
        "---",
        "type: hygiene-architecturale",
        f"date: {today}",
        "story: HOS-320",
        f"drift_count: {len(result.drift)}",
        "---",
        "",
        f"# Rapport d'hygiène architecturale — {today}",
        "",
        "> Généré par `scripts/ops/hygiene_architecturale.py` (HOS-320, Story 16.18).",
        "> Détection statique du drift entre ce que le repo **dit** et ce qu'il **est**.",
        "> Aucune écriture de code ni de dataset : cette PR est documentaire, la décision reste humaine.",
        "",
    ]

    if not result.drift:
        lines += ["✅ **Aucun drift détecté.**", ""]
    else:
        lines += [f"⚠️ **{len(result.drift)} drift(s) détecté(s).**", ""]

    for code, label, _ in DETECTORS:
        findings = [f for f in result.findings if f.detector == code]
        drift_n = sum(1 for f in findings if f.severity == "drift")
        status = "✅ clean" if drift_n == 0 else f"⚠️ {drift_n}"
        lines += [f"## {code} · {label} — {status}", ""]
        if not findings:
            lines += ["Rien à signaler.", ""]
            continue
        for finding in findings:
            marker = "ℹ️" if finding.severity == "info" else "⚠️"
            lines += [f"### {marker} {finding.title}", "", finding.detail, ""]

    if result.skipped:
        lines += ["## Détecteurs ignorés", ""]
        lines += [f"- {s}" for s in result.skipped]
        lines += [""]

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent d'hygiène architecturale (HOS-320)")
    parser.add_argument("--report", help="Chemin du rapport Markdown à écrire")
    parser.add_argument("--json", action="store_true", help="Émettre le résultat en JSON sur stdout")
    args = parser.parse_args()

    result = Result()
    for _, _, detector in DETECTORS:
        detector(result)

    today = datetime.date.today().isoformat()

    if args.json:
        print(
            json.dumps(
                {
                    "date": today,
                    "drift_count": len(result.drift),
                    "findings": [
                        {"detector": f.detector, "title": f.title, "severity": f.severity}
                        for f in result.findings
                    ],
                    "skipped": result.skipped,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        report = render_report(result, today)
        if args.report:
            out = _ROOT / args.report
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(report, encoding="utf-8")
            print(f"📄 Rapport écrit : {args.report}")
        else:
            print(report)

    for finding in result.drift:
        print(f"⚠️  [{finding.detector}] {finding.title}", file=sys.stderr)
    print(
        f"\n{'⚠️' if result.drift else '✅'} {len(result.drift)} drift(s), "
        f"{len(result.info)} info, {len(result.skipped)} détecteur(s) ignoré(s).",
        file=sys.stderr,
    )

    return 1 if result.drift else 0


if __name__ == "__main__":
    sys.exit(main())
