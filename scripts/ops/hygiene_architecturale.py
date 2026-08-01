#!/usr/bin/env python3
"""Agent d'hygiène architecturale — HOS-320 (Story 16.18).

Detects drift between what the repo *says* and what the repo *is*, then emits a
Markdown report. It never edits code and never writes to the eval dataset: the
workflow turns its output into a documentation-only PR that a human merges.

Seven detectors, all static and deterministic — no network, no secrets, no
runtime access. That is deliberate: a hygiene agent that needs credentials is a
new attack surface, and Epic 16 NFR2 freezes new runtime surface.

  D1  harness drift   — CLAUDE.md vs AGENTS.md (same content, two harnesses)
  D2  doc → code      — backticked paths in docs resolve to files that exist
  D3  env sync        — vars documented in CLAUDE.md exist in backend/.env.example
  D4  eval gaps       — typed guardrail reasons (NFR2 / ADR-0009) that no
                        golden-dataset scenario exercises
  D5  doc size        — files that declare their own line ceiling stay under it
  D6  count coherence — hardcoded counts match the source they summarise
  D7  metric honesty  — the circular synthetic MAPE never appears unqualified
                        (HOS-318, taxonomie docs/context/status-taxonomy.md)

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

# D2 — paths the docs cite on purpose for something not written yet, code or
# document. Keeping this register explicit is the point: it separates "the doc
# is stale" (a bug) from "the doc describes an unbuilt thing" (a known, dated
# intention). An entry here is a promise — when it lands, the entry goes.
PLANNED_PATHS = {
    "backend/app/models/graph/": "Graphe de contexte — Décision #24 / ADR-0008 DIFFÉRÉ 31/07/2026, reprise conditionnée ADR-0006 §10.4",
    "backend/app/services/context_graph_service.py": "Graphe de contexte — Décision #24 / ADR-0008 DIFFÉRÉ 31/07/2026, reprise conditionnée ADR-0006 §10.4",
    "backend/app/services/context_graph_queries/": "Graphe de contexte — Décision #24 / ADR-0008 DIFFÉRÉ 31/07/2026, reprise conditionnée ADR-0006 §10.4",
    "backend/app/providers/pos/": "POS ingestion — Décision #23 / ADR-0006, Phase 4",
    "backend/app/providers/pms/base.py": "PMS canonical schema — Décision #28 / ADR-0006 amendé, Phase 4",
    "eval/judge_calibration_set.jsonl": "LLM-as-judge EVAL-6 — ADR-0007 §14, critère bloquant Phase 4",
}

# D2 — paths that exist on disk but are deliberately out of the repo (élagage
# 30/07/2026, cf. docs/INDEX.md §Convention local-only). Citing them is correct:
# the reader has them locally, a fresh clone does not. Without this, CI reports
# every such citation as broken — ~13 false positives on the first run, and a
# detector that cries wolf gets switched off within a fortnight.
LOCAL_ONLY_PREFIXES = ("docs/veille/", "docs/_archive/", "tools/bmad/_bmad/")

# D3 — env var declarations. The doc side moved out of CLAUDE.md on 30/07 (it is
# neither a session fact nor an index); pointing D3 at the old heading would let
# it read an empty section and report "clean" for a detector that no longer sees
# anything — the same false negative D1 guards against.
ENV_EXAMPLE = "backend/.env.example"
ENV_DOC = "docs/ops/environment-variables.md"
ENV_DOC_HEADING = None  # None → scan the whole file

# D5 — files that declare their own line ceiling. The limit is read *from the
# file*, never hardcoded here: a threshold duplicated in the doc and in this
# script is exactly the divergence D6 exists to catch.
DOC_SIZE_LIMITS = ["CLAUDE.md", "AGENTS.md"]
_SIZE_DECL = re.compile(r"plafond dur (\d+) lignes")

# D6 — hardcoded counts that must match a countable source of truth. Three
# different figures for the same set (24 / 29 / 31) were in circulation on
# 31/07/2026, including one in the source file itself.
COUNT_CLAIMS = [
    {
        "label": "décisions architecturales",
        "claim": re.compile(r"(\d+)\s+décisions"),
        "scanned": ["CLAUDE.md", "AGENTS.md", "docs/INDEX.md", "docs/context/decisions-architecturales.md"],
        "source": "docs/context/decisions-architecturales.md",
        "entry": re.compile(r"^### \d+ — ", re.MULTILINE),
    },
]

# D4 — where typed guardrail reasons are declared, and the dataset that must
# exercise them.
GUARDRAIL_GLOB = "backend/app/**/*.py"
GOLDEN_DATASET = "eval/golden_dataset.jsonl"

# D7 — the synthetic MAPE is circular (generate_demo_data.py builds covers from
# the regressors Prophet consumes). It stays in the repo as the Décision #14
# non-regression gate; what is forbidden is citing it as evidence. Prose only:
# this detector polices *claims*, not code comments naming the gate constant.
METRIC_CLAIM_PATTERN = re.compile(r"15[.,]09")
METRIC_CLAIM_QUALIFIERS = re.compile(
    r"circulaire|circular|synth[ée]tique|synthetic|non-r[ée]gression|non-regression",
    re.IGNORECASE,
)
# How many lines around the hit may carry the qualifier. A table row cannot hold
# a caveat, so the surrounding block counts — but only just.
METRIC_CLAIM_WINDOW = 2
# Symmetric with PLANNED_PATHS and the D1 exceptions: an unqualified occurrence
# is tolerable only where it is written down *why*.
METRIC_CLAIM_EXCEPTIONS = {
    "docs/context/mape-benchmark.md": "Foyer canonique du chiffre — le fichier porte "
    "un bandeau de qualification en tête, qui couvre le bloc de résultats.",
    "docs/adr/": "Un ADR est un enregistrement daté. On n'y réécrit pas l'histoire ; "
    "la qualification vit dans les docs vivants qui le citent.",
    "tools/bmad/": "Sorties BMad archivées — packs de story figés, pas une surface de claim.",
    "docs/testing/evidence/": "Rapports d'exécution horodatés, y compris ceux de cet agent.",
}

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
_LINE_ANCHOR = re.compile(r":\d+(?:[,-]\d+)*$")


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
            # Deliberately out of the repo but present locally — see
            # LOCAL_ONLY_PREFIXES. Not a broken reference.
            if token.startswith(LOCAL_ONLY_PREFIXES):
                continue
            # Globs are illustrative patterns (`docs/adr/000X-*.md`), not claims
            # that a specific file exists.
            if "*" in token:
                continue
            # Strip trailing punctuation the prose may have glued on.
            candidate = token.rstrip(".,;:)")
            # `file.py:128` and `file.py:128,141` are ordinary citation forms —
            # resolve the file, ignore the line anchors.
            candidate = _LINE_ANCHOR.sub("", candidate)
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
# Two documentation shapes are accepted: the original `VAR — description` code
# block, and the Markdown table (`| `VAR` | description |`) the extracted doc
# uses. Supporting both keeps the detector working across the move.
_ENV_DOCLINE = re.compile(r"^\|?\s*`?([A-Z][A-Z0-9_]{2,})`?\s*(?:\||—)", re.MULTILINE)


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

    if ENV_DOC_HEADING is None:
        section = doc
    else:
        # Restrict to the env section so unrelated ALL-CAPS prose is not parsed.
        _, _, tail = doc.partition(ENV_DOC_HEADING)
        if not tail:
            result.skipped.append(f"D3: section « {ENV_DOC_HEADING} » absente de {ENV_DOC}")
            return
        section = tail.split("\n---", 1)[0]

    documented = set(_ENV_DOCLINE.findall(section))
    if not documented:
        # The doc parsed to zero variables: either it moved again or the shape
        # changed. Reporting "all undocumented" as info would read as clean.
        result.findings.append(
            Finding(
                detector="D3",
                title=f"Aucune variable lisible dans {ENV_DOC}",
                detail="Le détecteur n'a extrait aucun nom de variable — le fichier a bougé ou son format a changé. "
                "Ce résultat n'est pas « clean », il est aveugle. Vérifier `ENV_DOC` et `_ENV_DOCLINE`.",
            )
        )
        return

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


# ─── D5 · Plafond de lignes ───────────────────────────────────────────────────


def detect_doc_size(result: Result) -> None:
    """Files that declare a line ceiling must respect it.

    The ceiling is parsed out of the file itself. That is the whole point: on
    31/07/2026 `CLAUDE.md` declared "cible ≤ 150 lignes" and sat at 196 — 30%
    over, unnoticed, and the session that found it began by adding to the file.
    A rule nobody measures is not a rule.
    """
    for rel in DOC_SIZE_LIMITS:
        text = _read(rel)
        if text is None:
            result.skipped.append(f"D5: {rel} introuvable")
            continue

        match = _SIZE_DECL.search(text)
        if not match:
            result.findings.append(
                Finding(
                    detector="D5",
                    title=f"{rel} ne déclare plus son plafond",
                    detail="Le détecteur lit le plafond dans le fichier (motif « plafond dur N lignes »). "
                    "Sans déclaration, il ne peut rien vérifier — restaurer la ligne de règle, "
                    "ou retirer le fichier de `DOC_SIZE_LIMITS`.",
                )
            )
            continue

        limit = int(match.group(1))
        actual = len(text.splitlines())
        if actual <= limit:
            continue

        result.findings.append(
            Finding(
                detector="D5",
                title=f"{rel} dépasse son plafond : {actual} lignes pour {limit}",
                detail=f"Écart : **+{actual - limit} lignes**. Ce fichier est chargé à chaque session — "
                "tout ce qu'on y laisse est payé à chaque fois. "
                "Soit extraire une section vers un sous-fichier et ne garder qu'un pointeur, "
                "soit relever le plafond explicitement dans la ligne de règle si la croissance est assumée.",
            )
        )


# ─── D6 · Cohérence des comptes ───────────────────────────────────────────────


def detect_count_coherence(result: Result) -> None:
    """Hardcoded counts must match the source they claim to summarise.

    A number written in two files diverges on the next addition, silently. On
    31/07/2026 three figures for the same set were live — 24 in `AGENTS.md` *and
    in the source file itself*, 31 in `docs/INDEX.md`, 29 actually present.
    """
    for claim in COUNT_CLAIMS:
        source = _read(claim["source"])
        if source is None:
            result.skipped.append(f"D6: {claim['source']} introuvable")
            continue

        actual = len(claim["entry"].findall(source))
        if actual == 0:
            result.findings.append(
                Finding(
                    detector="D6",
                    title=f"Aucune entrée « {claim['label']} » comptée dans `{claim['source']}`",
                    detail="Le motif d'entrée ne correspond plus à rien — le format du fichier a changé. "
                    "Résultat aveugle, pas clean : vérifier `COUNT_CLAIMS[...]['entry']`.",
                )
            )
            continue

        for rel in claim["scanned"]:
            text = _read(rel)
            if text is None:
                continue
            for stated in {int(n) for n in claim["claim"].findall(text)}:
                if stated == actual:
                    continue
                result.findings.append(
                    Finding(
                        detector="D6",
                        title=f"`{rel}` annonce {stated} {claim['label']}, il y en a {actual}",
                        detail=f"Source de vérité : `{claim['source']}` ({actual} entrées). "
                        f"Écart de {abs(stated - actual)}. "
                        "Corriger le nombre, ou mieux : retirer le compte codé en dur — "
                        "un chiffre dupliqué dérive à chaque ajout.",
                    )
                )


# ─── D7 · Honnêteté métriques ─────────────────────────────────────────────────


def detect_metric_honesty(result: Result) -> None:
    """The circular synthetic MAPE must never be readable as evidence.

    HOS-318: `generate_demo_data.py` builds covers from the very regressors
    Prophet consumes, so 15.09% measures the generator, not forecast skill. The
    figure is not deleted — it remains the Décision #14 non-regression gate —
    but every occurrence must carry its own caveat within `METRIC_CLAIM_WINDOW`
    lines, because a number screenshotted out of a table travels alone.
    """
    scanned = 0
    for path in sorted(_ROOT.rglob("*.md")):
        rel = path.relative_to(_ROOT).as_posix()
        if rel.startswith(".git/") or any(rel.startswith(p) for p in METRIC_CLAIM_EXCEPTIONS):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            result.skipped.append(f"D7: `{rel}` illisible")
            continue

        scanned += 1
        for i, line in enumerate(lines):
            if not METRIC_CLAIM_PATTERN.search(line):
                continue
            lo = max(0, i - METRIC_CLAIM_WINDOW)
            window = "\n".join(lines[lo : i + METRIC_CLAIM_WINDOW + 1])
            if METRIC_CLAIM_QUALIFIERS.search(window):
                continue
            result.findings.append(
                Finding(
                    detector="D7",
                    title=f"`{rel}:{i + 1}` cite le MAPE synthétique sans qualificatif",
                    detail=f"Ligne : `{line.strip()[:160]}`\n\n"
                    "Ce chiffre est **circulaire** (les couverts de test sont fabriqués à partir "
                    "des régresseurs que Prophet consomme) : il ne prouve rien sur données réelles. "
                    "Ajouter « synthétique et circulaire — gate interne de non-régression » dans la "
                    "même phrase, ou citer le benchmark Recruit à la place "
                    "(`docs/context/mape-benchmark.md`). Convention : "
                    "`docs/context/status-taxonomy.md`.",
                )
            )

    if scanned == 0:
        result.skipped.append("D7: aucun fichier .md scanné")


DETECTORS = (
    ("D1", "Drift harness", detect_harness_drift),
    ("D2", "Doc → code", detect_doc_paths),
    ("D3", "Sync env", detect_env_sync),
    ("D4", "Lacunes eval", detect_eval_gaps),
    ("D5", "Plafond de lignes", detect_doc_size),
    ("D6", "Cohérence des comptes", detect_count_coherence),
    ("D7", "Honnêteté métriques", detect_metric_honesty),
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
    parser.add_argument(
        "--detectors",
        help="Codes séparés par des virgules (ex. D1). Par défaut : tous. "
        "Le contrôle PR bloquant n'exécute que D1 — voir .github/workflows/ci.yml.",
    )
    args = parser.parse_args()

    selected = None
    if args.detectors:
        selected = {c.strip().upper() for c in args.detectors.split(",") if c.strip()}
        known = {code for code, _, _ in DETECTORS}
        unknown = selected - known
        if unknown:
            print(f"❌ Détecteur(s) inconnu(s) : {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2

    result = Result()
    for code, _, detector in DETECTORS:
        if selected is None or code in selected:
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
