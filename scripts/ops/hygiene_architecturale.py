#!/usr/bin/env python3
"""Agent d'hygiène architecturale — HOS-320 (Story 16.18).

Detects drift between what the repo *says* and what the repo *is*, then emits a
Markdown report. It never edits code and never writes to the eval dataset: the
workflow turns its output into a documentation-only PR that a human merges.

Ten detectors. D1-D8 are static and deterministic — no network, no secrets, no
runtime access. That is deliberate: a hygiene agent that needs credentials is a
new attack surface, and Epic 16 NFR2 freezes new runtime surface.

D9 and D10 are the documented exceptions (HOS-324, HOS-325). Branch, PR and
workflow-run state exists only on the forge, so they shell out to `gh` with the
token CI already provides. They read and never write, stay out of the blocking
PR subset, and record a skip rather than reporting clean when `gh` is absent or
unauthenticated — a blind detector must say so.

  D1  harness drift   — CLAUDE.md vs AGENTS.md (same content, two harnesses)
  D2  doc → code      — backticked paths in docs resolve to files that exist
  D3  env sync        — vars documented in CLAUDE.md exist in backend/.env.example
  D4  eval gaps       — typed guardrail reasons (NFR2 / ADR-0009) that no
                        golden-dataset scenario exercises
  D5  doc size        — files that declare their own line ceiling stay under it
  D6  count coherence — hardcoded counts match the source they summarise
  D7  metric honesty  — the circular synthetic MAPE never appears unqualified
                        (HOS-318, taxonomie docs/context/status-taxonomy.md)
  D8  falsifiability  — a *property* asserted as fact (permanent, anonymised,
                        "by construction") carries what would make it false
                        (HOS-229, docs/context/dpia-anima-2026-08.md §10)
  D9  orphan work     — branches pushed with no PR, PRs left conflicting or
                        stale, branches surviving their merged PR (HOS-324).
                        Reads the forge; weekly report only, never blocking.
  D10 cron liveness   — the weekly agent proves it still runs (HOS-325). Run
                        from the PR CI, never from the cron it watches.

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
import shutil
import subprocess
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

# Paths no tree-walking detector may descend into. `.claude/worktrees/` holds up
# to sixteen full copies of this repo: without this, D7 scans every doc sixteen
# times and can fail on a stale copy that is no longer the repository at all.
# The rest are the usual non-source trees.
SCAN_EXCLUDED_PREFIXES = (
    ".git/",
    ".claude/",
    ".venv/",
    "node_modules/",
    "__pycache__/",
)


def _scan_excluded(rel: str) -> bool:
    """True when a repo-relative path belongs to a tree we never scan."""
    return any(
        rel.startswith(prefix) or f"/{prefix}" in rel
        for prefix in SCAN_EXCLUDED_PREFIXES
    )

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

# D6 (second family) — figures quoted from a machine-readable artefact. Counting
# entries works for "N décisions"; a benchmark result is not counted, it is read.
# The rule is the same either way: a number written in prose must match the thing
# it claims to summarise.
#
# Why: on 2026-08-02 the public README said the Recruit benchmark ran on 829
# restaurants. 829 is the *dataset*; the protocol selects 30. The conflation had
# reached four more surfaces, including the document that defines honest status
# labels and two prospect-facing docs — while `recruit_results.json`, published
# in the same public repo, said `n_stores: 30` throughout. The arithmetic gave it
# away: 1,193 scored points over 829 restaurants is 1.4 forecasts each.
#
# Scanned like D7 (every living .md, minus SCAN_EXCLUDED_PREFIXES) rather than a
# fixed list: the figure travels into new documents faster than a list is updated.
FIGURE_SOURCE = "eval/benchmarks/recruit_results.json"

# Two knobs, and the difference matters. `context` *scopes* the claim: without it
# the detector reads every "N restaurants" in the repo — scale scenarios, pricing
# tiers — and 17 false positives switch a detector off within a fortnight.
# `qualifier` *excuses* a mismatch: "829 restaurants" is correct when named as the
# dataset. Same escape valve as D7's caveats and D8's acknowledgements — state the
# role, keep the number.
FIGURE_CLAIMS = (
    {
        "label": "restaurants du benchmark",
        "pattern": re.compile(r"(\d[\d   ]*)\s+(?:real\s+)?(?:Japanese\s+)?restaurants", re.IGNORECASE),
        "path": ("protocol", "n_stores"),
        "context": re.compile(r"recruit|benchmark|mape|mdape", re.IGNORECASE),
        "qualifier": re.compile(
            r"dataset|jeu de donn[ée]es|au total|in total|en compte", re.IGNORECASE
        ),
        "window": 1,
        "hint": "Le dataset Recruit compte 829 restaurants ; le protocole en sélectionne "
        "`n_stores`. Citer la taille du dataset comme celle de l'échantillon gonfle la "
        "preuve d'un facteur 28. Nommer le rôle du nombre (« dataset de 829 ») ou écrire "
        "la taille réelle de l'échantillon.",
    },
    {
        "label": "points scorés",
        "pattern": re.compile(r"(\d[\d   ,]*)\s+(?:scored\s+(?:points|forecasts)|points scor[ée]s)", re.IGNORECASE),
        "path": ("protocol", "scored_points"),
        "context": re.compile(r"recruit|benchmark|mape|mdape|scor", re.IGNORECASE),
        # A floor is not a result: "≥ 300 points scorés" specifies what a future
        # run must reach (HOS-308), and comparing it to what HOS-307 produced is
        # a category error.
        "qualifier": re.compile(r"≥|>=|au moins|at least|minimum", re.IGNORECASE),
        "window": 0,
        "hint": "Le nombre de points scorés est produit par le run, pas choisi. "
        "S'il a changé, le benchmark a été rejoué : toutes les figures qui en dépendent "
        "sont à reprendre ensemble.",
    },
)


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

# D8 — property claims. D7 polices claims about *maturity* (does it run?); D8
# polices claims about *properties* (is it true?). The DPIA (HOS-229) found the
# same defect four times — "permanent", "anonymisé", "personal-data-free by
# construction", "aggregations anonymisées" — each a property written as an
# established fact, none carrying anything that could prove it wrong. Décision
# #33 fixed the maturity half; this is the other half.
#
# Scanned surfaces are *living* docs only, where a claim is load-bearing today.
# ADRs are excluded for the same reason D7 excludes them: a dated record is not
# rewritten, the qualification belongs in the docs that cite it. That is not a
# loophole — every claim that matters is restated on one of these surfaces
# (ADR-0011 D4's "personal-data-free by construction" is caught via
# decisions-architecturales.md §26).
PROPERTY_CLAIM_SOURCES = [
    "CLAUDE.md",
    "AGENTS.md",
    "docs/mesh-architecture.md",
    "docs/context/decisions-architecturales.md",
    "docs/context/open-decisions.md",
    "docs/context/memory-architecture.md",
    "docs/context/moat.md",
    "docs/context/perimetre-et-conformite-prospect.md",
]

# A claim is acknowledged — anywhere in the window — when the text says the work
# is not done. Naming a claim as unproven is the point; D8 asks for honesty, not
# for the proof itself.
PROPERTY_CLAIM_ACKNOWLEDGED = re.compile(
    r"à prouver|non prouv|pas prouv|contest|pseudonym|DPIA|à borner|non conforme|"
    r"reste ouvert|décision ouverte|à trancher|hypothèse",
    re.IGNORECASE,
)

# Each family: what asserts the property, what would make it falsifiable, and how
# far the qualifier may sit. `window: 0` means same line — a retention period
# belongs in the same table cell as the claim it bounds, otherwise the row above
# ("Séjour + 30j") silently vouches for the row below ("∞").
PROPERTY_CLAIMS = (
    {
        "code": "conservation",
        "label": "conservation illimitée",
        "pattern": re.compile(
            r"(?<![\w-])(permanent[es]?|illimit[ée]e?s?|ind[ée]finiment)(?![\w-])|∞",
            re.IGNORECASE,
        ),
        "qualifier": re.compile(
            r"\b\d+\s*(?:j\b|jours?|mois|ans?|ann[ée]es?|h\b|heures?)|born[ée]|"
            r"r[ée]tention|art\.?\s*5\(1\)\(e\)",
            re.IGNORECASE,
        ),
        "window": 0,
        # "Coexistence permanente pgvector + AGE" and "archive policy: garder
        # indéfiniment" are permanence claims about *architecture* and *repo
        # history* — no data subject, no art. 5(1)(e). D8 is about stored
        # personal data; firing on these would train the reader to skim.
        "exclude": re.compile(r"coexistence|migration path|archive|historique", re.IGNORECASE),
        "hint": "Une durée de conservation illimitée ne se justifie pas par une analyse de "
        "proportionnalité (art. 5(1)(e) RGPD). Nommer la durée dans la même phrase/cellule, "
        "ou marquer la claim comme non conforme / à borner. Réf. "
        "`docs/context/dpia-anima-2026-08.md` §6.",
    },
    {
        "code": "anonymat",
        "label": "anonymat affirmé",
        "pattern": re.compile(
            r"anonymis[ée]|anonymized|de-identified|d[ée]-identifi|personal-data-free|"
            r"sans donn[ée]es? personnelles",
            re.IGNORECASE,
        ),
        "qualifier": re.compile(
            r"k\s*[-≥>=]|k-anonym|plancher|seuil|WP29|consid[ée]rant 26|r[ée]-identif",
            re.IGNORECASE,
        ),
        "window": 3,
        "hint": "L'anonymat est une propriété empirique, pas un adjectif : l'absence "
        "d'identifiant direct ne suffit pas (considérant 26 + WP29 05/2014 — individualisation, "
        "corrélation, inférence). Nommer le plancher de k-anonymat, ou dire que la preuve "
        "n'existe pas encore. Réf. `docs/context/dpia-anima-2026-08.md` §10.2 et §10.3.",
    },
    {
        "code": "auto-justification",
        "label": "assertion auto-justifiée",
        # "by design" is deliberately absent: eval-by-design and privacy-by-design
        # are legitimate compounds here, and a detector that fires on Décision #22
        # gets switched off within a fortnight.
        "pattern": re.compile(r"(?<!-)by construction|par construction", re.IGNORECASE),
        "qualifier": re.compile(r"(?!)"),  # never matches — only an acknowledgement clears this
        "window": 3,
        "hint": "« by construction » présente une conclusion comme une prémisse : c'est "
        "exactement la forme d'affirmation que personne ne peut vérifier. Écrire ce qui la "
        "rendrait fausse, ou la marquer comme non prouvée.",
    },
)

# ─── D9 · Branches et PRs orphelines ──────────────────────────────────────────
# The first detector that leaves the working tree. D1-D8 read files; branch and
# PR state lives on the forge and nowhere else, so D9 shells out to `gh`.
#
# Why it exists: on 2026-08-01 two pieces of finished work were invisible for the
# same structural reason — nothing watched the gap between "the branch exists"
# and "it is merged and tracked". Story 16.20 sat pushed with no Linear issue and
# no PR; HOS-318's meta-repo PR sat open, superseded and conflicting, on the
# public front door while the story looked done. Both were found by hand.
#
# D9 is deliberately *not* in the blocking PR subset: an orphaned branch is not
# the current author's fault, and blocking them on it teaches people to bypass
# the gate. Its home is the weekly report.

# Watched repos, declared rather than inferred. The costly incident was
# cross-repo: watching only this one would have missed it entirely.
#
# The built-in GITHUB_TOKEN is scoped to this repository for writes but reads
# public siblings fine, which is what the other two are. Add a *private* repo
# here and D9 will record a skip for it rather than a false clean — the skip is
# the honest outcome, not a bug to work around with a broader token.
WATCHED_REPOS = [
    "IvandeMurard/aetherix-hospitality-ai",
    "IvandeMurard/hospitality-agentic-mesh",
    "IvandeMurard/tacet-app",
]

# An open PR untouched this long is forgotten or blocked. Either way it belongs
# in the report — PR #1 above rotted for fifteen hours; a fortnight is generous.
STALE_PR_DAYS = 14

# Branches that legitimately outlive their PR, as regex → justification.
# Symmetric with HARNESS_EXCEPTIONS and PLANNED_PATHS: a tolerated exception is
# written down and justified, or it is not tolerated.
BRANCH_EXCEPTIONS: dict[str, str] = {
    r"^(main|master|gh-pages)$": "branches permanentes",
    r"^dependabot/": "branches éphémères créées et supprimées par Dependabot",
}

_GH_TIMEOUT = 30

# ─── D10 · Cron d'hygiène en vie ──────────────────────────────────────────────
# The dead-man's switch the tooling was missing while imposing one on the
# product (Epic 12 G-1). The weekly workflow only speaks when it finds drift, so
# a failed run — or a cron GitHub silently disabled after 60 days of repo
# inactivity — is indistinguable from a clean week.
#
# It is deliberately *not* run by the workflow it watches: a detector hosted by
# the thing it observes never notices its own death. Its carrier is the PR CI,
# which runs whenever anyone works, as a warning rather than a failure.
CRON_WORKFLOW = "hygiene-architecturale.yml"
# Weekly cadence plus slack for a skipped Monday. Beyond this the silence is
# no longer plausibly normal.
CRON_MAX_AGE_DAYS = 10


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

    _check_figure_claims(result)


def _figure_value(data: object, path: tuple[str, ...]) -> int:
    cur = data
    for key in path:
        cur = cur[key]  # type: ignore[index]
    return int(cur)  # type: ignore[arg-type]


def _check_figure_claims(result: Result) -> None:
    """Second D6 family: prose figures against the artefact that produced them.

    A count is derived by counting; a benchmark figure is derived by reading.
    Both are the same promise — the number in the sentence is the number in the
    thing. This half exists because 829 (the dataset) was published as the
    sample size (30) on five surfaces at once, including the public README and
    the document defining honest status labels, while the JSON next to it said
    otherwise.

    Every living `.md` is scanned rather than a declared list: the figure
    reaches new documents faster than a list gets updated.
    """
    raw = _read(FIGURE_SOURCE)
    if raw is None:
        result.skipped.append(
            f"D6: `{FIGURE_SOURCE}` introuvable — chiffres du benchmark non vérifiés."
        )
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        result.skipped.append(f"D6: `{FIGURE_SOURCE}` illisible — chiffres non vérifiés.")
        return

    expected: list[tuple[dict, int]] = []
    for claim in FIGURE_CLAIMS:
        try:
            expected.append((claim, _figure_value(data, claim["path"])))
        except (KeyError, TypeError, ValueError):
            result.skipped.append(
                f"D6: `{'.'.join(claim['path'])}` absent de `{FIGURE_SOURCE}` — "
                f"« {claim['label']} » non vérifié."
            )

    for path in sorted(_ROOT.rglob("*.md")):
        rel = path.relative_to(_ROOT).as_posix()
        if _scan_excluded(rel) or rel.startswith(LOCAL_ONLY_PREFIXES):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for claim, value in expected:
            for i, line in enumerate(lines):
                for match in claim["pattern"].finditer(line):
                    digits = re.sub(r"\D", "", match.group(1))
                    if not digits or int(digits) == value:
                        continue
                    lo = max(0, i - claim["window"])
                    hi = min(len(lines), i + claim["window"] + 1)
                    window = "\n".join(lines[lo:hi])
                    # `context` scopes the claim to its subject; `qualifier`
                    # excuses a mismatch that is a different, legitimate reading.
                    if not claim["context"].search(window):
                        continue
                    if claim["qualifier"].search(window):
                        continue
                    result.findings.append(
                        Finding(
                            detector="D6",
                            title=f"`{rel}:{i + 1}` annonce {int(digits)} "
                            f"{claim['label']}, la source en donne {value}",
                            detail=f"Ligne : `{line.strip()[:160]}`\n\n"
                            f"Source de vérité : `{FIGURE_SOURCE}` "
                            f"(`{'.'.join(claim['path'])}` = {value}).\n\n"
                            + claim["hint"],
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
        if _scan_excluded(rel) or any(rel.startswith(p) for p in METRIC_CLAIM_EXCEPTIONS):
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


# ─── D8 · Propriétés falsifiables ─────────────────────────────────────────────


def detect_property_claims(result: Result) -> None:
    """A property written as an established fact must carry its falsifier.

    HOS-229: the DPIA found four such claims in the corpus, all load-bearing,
    none checkable — "Semantic: permanent", "aggregations anonymisées",
    "personal-data-free by construction". Each one silently decided a legal
    question (retention, GDPR scope) by choosing an adjective.

    The bar is deliberately low: naming the claim as unproven clears it. D8 asks
    for the falsifier, not the proof — demanding proof from a linter would make
    it unmergeable, and an unmergeable detector gets deleted.
    """
    scanned = 0
    for rel in PROPERTY_CLAIM_SOURCES:
        text = _read(rel)
        if text is None:
            result.skipped.append(f"D8: `{rel}` absent")
            continue

        scanned += 1
        lines = text.splitlines()
        # One finding per file and family: "anonymisé" written four times in
        # memory-architecture.md is one unproven claim, not four. Reporting it
        # four times buries the other seven families under repetition.
        hits: dict[str, list[tuple[int, str]]] = {}
        for i, line in enumerate(lines):
            for claim in PROPERTY_CLAIMS:
                if not claim["pattern"].search(line):
                    continue
                exclude = claim.get("exclude")
                if exclude is not None and exclude.search(line):
                    continue
                window = claim["window"]
                lo = max(0, i - window)
                around = "\n".join(lines[lo : i + window + 1])
                if claim["qualifier"].search(around) or PROPERTY_CLAIM_ACKNOWLEDGED.search(around):
                    continue
                hits.setdefault(claim["code"], []).append((i + 1, line.strip()))

        for claim in PROPERTY_CLAIMS:
            occurrences = hits.get(claim["code"])
            if not occurrences:
                continue
            first_line, first_text = occurrences[0]
            others = ", ".join(str(n) for n, _ in occurrences[1:])
            detail = f"Ligne : `{first_text[:160]}`\n\n"
            if others:
                detail += f"Même claim non qualifiée aux lignes : {others}.\n\n"
            result.findings.append(
                Finding(
                    detector="D8",
                    title=f"`{rel}:{first_line}` — {claim['label']} sans falsifieur"
                    + (f" ({len(occurrences)} occurrences)" if others else ""),
                    detail=detail + claim["hint"],
                    severity="info",
                )
            )

    if scanned == 0:
        result.skipped.append("D8: aucune source scannée")


# ─── D9 · Branches et PRs orphelines ──────────────────────────────────────────


def _gh(args: list[str]) -> object | None:
    """Run a `gh` command expecting JSON on stdout. None when gh is unusable.

    Every failure mode collapses to None on purpose: the caller turns that into
    a recorded skip. What must never happen is a silent empty result read as
    "no orphans" — that is the false negative D1's missing-harness finding was
    written to prevent.
    """
    if shutil.which("gh") is None:
        return None
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT,
            encoding="utf-8",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _branch_excepted(name: str) -> str | None:
    for pattern, why in BRANCH_EXCEPTIONS.items():
        if re.search(pattern, name):
            return why
    return None


def _age_days(iso: str) -> int | None:
    try:
        when = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    return (now - when).days


def detect_orphan_branches(result: Result) -> None:
    """Work that exists on the forge but is not on its way anywhere.

    Three shapes, learned from two incidents on the same day (2026-08-01):
      - a branch ahead of the default with no PR at all → pushed, never
        submitted (Story 16.20);
      - an open PR that conflicts or has gone quiet → rotting, often superseded
        (the meta-repo PR #1, open on the public README while its story read
        "done");
      - a branch whose PRs are all closed → cruft, one click to remove.

    Only the first two count as drift. Cruft is reported as info: a detector
    that fails a report over an undeleted branch stops being read.
    """
    if shutil.which("gh") is None:
        result.skipped.append(
            "D9: `gh` introuvable — l'état des branches et PRs vit sur la forge, "
            "pas dans l'arbre de travail. Aucun verdict rendu (ce n'est pas « clean »)."
        )
        return

    reached_any = False

    for repo in WATCHED_REPOS:
        info = _gh(["api", f"repos/{repo}", "--jq", '{default_branch: .default_branch}'])
        branches = _gh(["api", f"repos/{repo}/branches", "--paginate", "--jq", "[.[].name]"])
        prs = _gh([
            "pr", "list", "--repo", repo, "--state", "all", "--limit", "300",
            "--json", "number,state,headRefName,updatedAt,mergeable,title,isDraft",
        ])

        if info is None or branches is None or prs is None:
            result.skipped.append(
                f"D9: `{repo}` inaccessible (gh non authentifié, réseau, ou droits manquants) — "
                "aucun verdict rendu pour ce repo."
            )
            continue

        reached_any = True
        default_branch = info.get("default_branch", "main")
        prs_by_head: dict[str, list[dict]] = {}
        for pr in prs:
            prs_by_head.setdefault(pr["headRefName"], []).append(pr)

        # --- Branches ---------------------------------------------------------
        for branch in branches:
            if branch == default_branch or _branch_excepted(branch):
                continue

            related = prs_by_head.get(branch, [])
            if not related:
                result.findings.append(
                    Finding(
                        detector="D9",
                        title=f"`{repo}` — branche `{branch}` poussée sans aucune PR",
                        detail="Du travail est sur la forge et n'est en route nulle part : "
                        "ni PR, ni revue, ni trace dans Linear si la story a été oubliée. "
                        "C'est le cas de la Story 16.20, restée invisible jusqu'à une analyse "
                        "manuelle.\n\n"
                        "Ouvrir la PR, ou supprimer la branche si le travail est abandonné. "
                        f"Une branche légitimement durable se déclare dans `BRANCH_EXCEPTIONS` "
                        "avec sa justification.",
                    )
                )
                continue

            if all(pr["state"] in ("MERGED", "CLOSED") for pr in related):
                states = ", ".join(f"#{pr['number']} {pr['state'].lower()}" for pr in related)
                result.findings.append(
                    Finding(
                        detector="D9",
                        title=f"`{repo}` — branche `{branch}` survit à ses PRs ({states})",
                        detail="Reliquat sans conséquence, mais il encombre la liste des branches "
                        "et fait douter de ce qui est encore en cours. Supprimable en un clic "
                        "(`gh pr merge --delete-branch` le fait à la fermeture).",
                        severity="info",
                    )
                )

        # --- PRs ouvertes -----------------------------------------------------
        for pr in prs:
            if pr["state"] != "OPEN":
                continue

            reasons = []
            if pr.get("mergeable") == "CONFLICTING":
                reasons.append("elle est **en conflit** avec la branche par défaut")
            age = _age_days(pr.get("updatedAt", ""))
            if age is not None and age > STALE_PR_DAYS:
                reasons.append(f"elle n'a pas bougé depuis **{age} jours**")
            if not reasons:
                continue

            draft = " (draft)" if pr.get("isDraft") else ""
            result.findings.append(
                Finding(
                    detector="D9",
                    title=f"`{repo}` — PR #{pr['number']}{draft} stagne : {pr['title'][:70]}",
                    detail="Cette PR " + " et ".join(reasons) + ".\n\n"
                    "Une PR qui pourrit est rarement neutre : celle du méta-repo, le 01/08, était "
                    "supersédée par une autre et serait passée en régression si elle avait été "
                    "mergée par réflexe. Rebaser, fermer, ou merger — mais trancher.",
                )
            )

    if not reached_any:
        result.skipped.append(
            "D9: aucun repo surveillé n'a pu être interrogé — détecteur aveugle, pas clean."
        )


# ─── D10 · Cron d'hygiène en vie ──────────────────────────────────────────────


def detect_cron_liveness(result: Result) -> None:
    """The weekly agent must prove it still runs, not merely stay silent.

    Silence from a reporting job has two causes that look identical from the
    outside: nothing to report, or nothing running. This detector separates
    them by reading the last *successful* run of the workflow.

    Run it from the PR CI, never from the weekly workflow itself — a watchdog
    hosted by the process it watches dies with it.
    """
    repo = WATCHED_REPOS[0]
    runs = _gh([
        "api",
        f"repos/{repo}/actions/workflows/{CRON_WORKFLOW}/runs"
        "?status=success&per_page=1",
        "--jq",
        "[.workflow_runs[] | {created_at, html_url}]",
    ])

    if runs is None:
        result.skipped.append(
            f"D10: état du cron `{CRON_WORKFLOW}` illisible (gh absent, non authentifié, "
            "ou workflow inconnu) — aucun verdict rendu, ce n'est pas « clean »."
        )
        return

    if not runs:
        result.findings.append(
            Finding(
                detector="D10",
                title=f"`{CRON_WORKFLOW}` n'a aucun run réussi",
                detail="Le workflow existe mais n'a jamais abouti. Tant que c'est le cas, "
                "l'agent d'hygiène ne surveille rien : ses détecteurs ne s'exécutent que là.",
            )
        )
        return

    last = runs[0]
    age = _age_days(last.get("created_at", ""))
    if age is None:
        result.skipped.append(f"D10: date du dernier run illisible pour `{CRON_WORKFLOW}`")
        return

    if age <= CRON_MAX_AGE_DAYS:
        return

    result.findings.append(
        Finding(
            detector="D10",
            title=f"Cron d'hygiène muet depuis {age} jours (seuil : {CRON_MAX_AGE_DAYS})",
            detail=f"Dernier run réussi : {last.get('created_at', '?')[:10]} — "
            f"{last.get('html_url', '')}\n\n"
            "Le workflow hebdomadaire ne parle que lorsqu'il trouve du drift ; son silence "
            "ne prouve donc rien. Au-delà du seuil, l'hypothèse la plus probable n'est plus "
            "« aucun drift » mais « plus personne ne regarde ».\n\n"
            "Causes usuelles : GitHub désactive un cron après 60 jours sans activité du dépôt, "
            "le workflow échoue en amont des détecteurs, ou le fichier a été renommé sans "
            "mettre à jour `CRON_WORKFLOW`.",
        )
    )


DETECTORS = (
    ("D1", "Drift harness", detect_harness_drift),
    ("D2", "Doc → code", detect_doc_paths),
    ("D3", "Sync env", detect_env_sync),
    ("D4", "Lacunes eval", detect_eval_gaps),
    ("D5", "Plafond de lignes", detect_doc_size),
    ("D6", "Cohérence des comptes", detect_count_coherence),
    ("D7", "Honnêteté métriques", detect_metric_honesty),
    ("D8", "Propriétés falsifiables", detect_property_claims),
    ("D9", "Branches et PRs orphelines", detect_orphan_branches),
    ("D10", "Cron d'hygiène en vie", detect_cron_liveness),
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


def fix_harness() -> int:
    """Regenerate the derived harness files from the canonical one.

    `AGENTS.md` is not a document anyone maintains: it is `CLAUDE.md` with its
    self-references renamed. A derived artefact kept in sync by hand drifts —
    that is its definition, and it cost two cycles on 2026-08-01. D1 catches the
    drift; this closes it without anyone retyping a one-liner.

    Idempotent, and it only ever writes files already declared in HARNESS_FILES.
    """
    canonical, *derived = HARNESS_FILES
    base = _read(canonical)
    if base is None:
        print(f"❌ {canonical} introuvable — rien à propager.", file=sys.stderr)
        return 2

    changed = []
    for name in derived:
        target = _ROOT / name
        wanted = base.replace(canonical, name)
        if target.is_file() and target.read_text(encoding="utf-8") == wanted:
            continue
        target.write_text(wanted, encoding="utf-8")
        changed.append(name)

    if not changed:
        print("✅ Harnais déjà synchronisé — aucun fichier réécrit.")
    else:
        for name in changed:
            print(f"✏️  {name} régénéré depuis {canonical}")
        print("\nRelire le diff avant de committer : `git diff`.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent d'hygiène architecturale (HOS-320)")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Régénère les harnais dérivés (AGENTS.md) depuis le canonique (CLAUDE.md). "
        "Seule correction automatique de l'agent : elle ne touche qu'un artefact dérivé.",
    )
    parser.add_argument("--report", help="Chemin du rapport Markdown à écrire")
    parser.add_argument("--json", action="store_true", help="Émettre le résultat en JSON sur stdout")
    parser.add_argument(
        "--detectors",
        help="Codes séparés par des virgules (ex. D1). Par défaut : tous. "
        "Le contrôle PR bloquant n'exécute que D1 — voir .github/workflows/ci.yml.",
    )
    args = parser.parse_args()

    if args.fix:
        return fix_harness()

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
