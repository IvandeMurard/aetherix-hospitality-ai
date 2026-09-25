#!/usr/bin/env python3
"""Validate `public-status.yml` — the only source of the public status block.

The file is synced to the public meta-repo README (ADR-0010). Everything in
`name`, `description` and `status` is published verbatim, so this gate checks
two things: that the status is honest (taxonomy, evidence on main, freshness)
and that nothing private leaks (ADR-0012 / Signal Contract never migrate,
ticket IDs, decision numbers, internal paths, private repo name, secrets,
e-mail addresses).

`evidence` paths are internal by design: they are checked for existence and
never rendered, so they are exempt from the leak denylist.

Exit codes:
  0  valid (warnings allowed — e.g. a stale `verified_on`)
  1  validation error(s)
  2  file missing or not parseable

Usage:
  python scripts/ci/check_public_status.py
  python scripts/ci/check_public_status.py --file public-status.yml --max-age-days 30
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/ci/ -> repo root
DEFAULT_FILE = "public-status.yml"
DEFAULT_MAX_AGE_DAYS = 60

# Status taxonomy (docs/context/status-taxonomy.md) + "In progress" (partly merged,
# not usable yet). "Built (PoC)" is forbidden by the taxonomy and not listed.
ALLOWED_STATUSES = ("Built", "Shadow-mode", "Synthetic PoC", "In progress", "Design", "Research")
ALLOWED_DEPLOYED = (True, False, "unknown", "n/a")
# "Live" is only meaningful for something that runs.
LIVE_CAPABLE_STATUSES = ("Built", "Shadow-mode")

TOP_LEVEL_KEYS = {"schema_version", "max_age_days", "entries"}
ENTRY_KEYS = {"id", "name", "status", "deployed", "description", "verified_on", "evidence"}
PUBLIC_FIELDS = ("id", "name", "status", "description")

NAME_MAX = 60
DESCRIPTION_MAX = 220
_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# (label, pattern). Case-insensitive. Each pattern names what it protects so a
# failure message says why, not just what.
LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(rx, re.IGNORECASE))
    for label, rx in (
        ("private ADR (ADR-0012 never migrates)", r"\bADR[\s_-]*0*12\b"),
        ("Signal Contract (never migrates)", r"\bsignal[\s_-]*contract\b"),
        ("ticket ID", r"\b(?:HOS|EVAL|QA)-\d+\b"),
        ("decision number", r"\bd[ée]cisions?\s*(?:#|n°|no\.)\s*\d+"),
        ("private section reference", r"§\s*\d"),
        ("private repo name", r"aetherix-hospitality-ai"),
        ("internal path", r"(?<![\w.-])(?:backend|supabase|docs/context|docs/adr|scripts/(?:ci|ops|eval)|app/(?:services|api|core|db|workers))/"),
        ("env file", r"(?<![\w-])\.env\b"),
        ("staging hostname", r"\b[\w-]+\.fly\.dev\b"),
        ("e-mail address", r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
        ("secret-looking string", r"\b(?:sk-(?:ant-)?[A-Za-z0-9_-]{16,}|gh[opsur]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[abprs]-[A-Za-z0-9-]{10,}|AC[0-9a-f]{32}|SK[0-9a-f]{32})\b"),
        ("secret-looking string", r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        ("secret-looking string", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        ("secret-looking string", r"\b(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*\S+"),
        ("secret-looking string", r"\b[A-Za-z0-9+/_-]{40,}\b"),
    )
)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def find_leaks(text: str) -> list[str]:
    """Return the labels of every denylist pattern that matches `text`."""
    return [f"{label}: {m.group(0)!r}" for label, rx in LEAK_PATTERNS for m in [rx.search(text)] if m]


def _as_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _check_evidence(where: str, entry: dict, exists: Callable[[str], bool], report: Report) -> None:
    evidence = entry.get("evidence", [])
    status = entry.get("status")
    if evidence is None:
        evidence = []
    if not isinstance(evidence, list) or not all(isinstance(p, str) and p.strip() for p in evidence):
        report.errors.append(f"{where}: `evidence` must be a list of non-empty paths")
        return
    if status == "Built" and not evidence:
        report.errors.append(f"{where}: status Built requires at least one evidence path")
    for path in evidence:
        if path.startswith("/") or "\\" in path or ".." in Path(path).parts:
            report.errors.append(f"{where}: evidence {path!r} must be a repo-relative path")
            continue
        if not exists(path):
            msg = f"{where}: evidence {path!r} does not exist on this branch"
            if status == "Built":
                report.errors.append(msg + " (Built requires every evidence path)")
            else:
                report.warnings.append(msg)


def _check_entry(where: str, entry: object, exists: Callable[[str], bool], today: date,
                 max_age_days: int, report: Report) -> None:
    if not isinstance(entry, dict):
        report.errors.append(f"{where}: must be a mapping")
        return
    unknown = set(entry) - ENTRY_KEYS
    if unknown:
        report.errors.append(f"{where}: unknown key(s) {sorted(unknown)} — only {sorted(ENTRY_KEYS)} are allowed")
    missing = (ENTRY_KEYS - {"evidence"}) - set(entry)
    if missing:
        report.errors.append(f"{where}: missing key(s) {sorted(missing)}")

    for key in PUBLIC_FIELDS:
        value = entry.get(key)
        if key in entry and (not isinstance(value, str) or not value.strip()):
            report.errors.append(f"{where}: `{key}` must be a non-empty string")

    entry_id = entry.get("id")
    if isinstance(entry_id, str) and not _ID_RE.match(entry_id):
        report.errors.append(f"{where}: id {entry_id!r} must be kebab-case")

    name = entry.get("name")
    if isinstance(name, str) and len(name) > NAME_MAX:
        report.errors.append(f"{where}: name longer than {NAME_MAX} characters")

    description = entry.get("description")
    if isinstance(description, str):
        if len(description) > DESCRIPTION_MAX:
            report.errors.append(f"{where}: description longer than {DESCRIPTION_MAX} characters")
        if "\n" in description.strip():
            report.errors.append(f"{where}: description must be one line (use `>-` folding in YAML)")

    status = entry.get("status")
    if "status" in entry and status not in ALLOWED_STATUSES:
        report.errors.append(f"{where}: status {status!r} not in {list(ALLOWED_STATUSES)}")

    deployed = entry.get("deployed")
    if "deployed" in entry:
        if deployed not in ALLOWED_DEPLOYED or isinstance(deployed, int) and not isinstance(deployed, bool):
            report.errors.append(f"{where}: deployed must be true, false, unknown or n/a (got {deployed!r})")
        elif deployed is True and status not in LIVE_CAPABLE_STATUSES:
            report.errors.append(f"{where}: deployed: true is only possible for {list(LIVE_CAPABLE_STATUSES)} (status is {status!r})")

    if "verified_on" in entry:
        verified = _as_date(entry.get("verified_on"))
        if verified is None:
            report.errors.append(f"{where}: verified_on must be an ISO date (YYYY-MM-DD)")
        elif verified > today:
            report.errors.append(f"{where}: verified_on {verified} is in the future")
        elif (today - verified).days > max_age_days:
            report.warnings.append(
                f"{where}: verified_on {verified} is {(today - verified).days} days old (> {max_age_days}) — re-check it against main"
            )

    for key in PUBLIC_FIELDS:
        value = entry.get(key)
        if isinstance(value, str):
            for leak in find_leaks(value):
                report.errors.append(f"{where}: `{key}` would leak a {leak}")

    _check_evidence(where, entry, exists, report)


def validate(data: object, exists: Callable[[str], bool], today: date,
             max_age_days: int | None = None) -> Report:
    """Pure validation. `exists(path)` answers whether a repo-relative path exists."""
    report = Report()
    if not isinstance(data, dict):
        report.errors.append("top level must be a mapping")
        return report
    unknown = set(data) - TOP_LEVEL_KEYS
    if unknown:
        report.errors.append(f"unknown top-level key(s) {sorted(unknown)}")
    if data.get("schema_version") != 1:
        report.errors.append("schema_version must be 1")

    file_age = data.get("max_age_days", DEFAULT_MAX_AGE_DAYS)
    if not isinstance(file_age, int) or isinstance(file_age, bool) or file_age <= 0:
        report.errors.append("max_age_days must be a positive integer")
        file_age = DEFAULT_MAX_AGE_DAYS
    age = max_age_days if max_age_days is not None else file_age

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        report.errors.append("entries must be a non-empty list")
        return report

    seen: set[str] = set()
    for i, entry in enumerate(entries):
        entry_id = entry.get("id") if isinstance(entry, dict) else None
        where = f"entries[{i}]" + (f" ({entry_id})" if isinstance(entry_id, str) else "")
        if isinstance(entry_id, str):
            if entry_id in seen:
                report.errors.append(f"{where}: duplicate id")
            seen.add(entry_id)
        _check_entry(where, entry, exists, today, age, report)
    return report


def load(path: Path) -> object:
    """Parse the YAML file. Raises OSError / ValueError on unreadable or invalid input."""
    import yaml  # local import: the pure functions above do not need PyYAML

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", default=str(_ROOT / DEFAULT_FILE))
    parser.add_argument("--root", default=str(_ROOT), help="repo root that evidence paths resolve against")
    parser.add_argument("--max-age-days", type=int, default=None,
                        help="override the file's max_age_days for the staleness warning")
    parser.add_argument("--today", default=None, help="ISO date, for reproducible runs")
    args = parser.parse_args(argv)

    path = Path(args.file)
    try:
        data = load(path)
    except (OSError, ValueError) as exc:
        print(f"❌ cannot read {path}: {exc}", file=sys.stderr)
        return 2

    root = Path(args.root)
    today = date.fromisoformat(args.today) if args.today else date.today()
    report = validate(data, lambda p: (root / p).exists(), today, args.max_age_days)

    for warning in report.warnings:
        print(f"::warning title=public-status::{warning}")
    for error in report.errors:
        print(f"::error title=public-status::{error}")
    if report.ok:
        count = len(data["entries"]) if isinstance(data, dict) else 0
        print(f"✅ {path.name}: {count} entries valid ({len(report.warnings)} warning(s))")
        return 0
    print(f"❌ {path.name}: {len(report.errors)} error(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
