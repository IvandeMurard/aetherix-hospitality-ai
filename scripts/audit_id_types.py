#!/usr/bin/env python3
"""Static analysis for tenant_id / property_id / hotel_id type mismatches.

Convention (docs/context/data-conventions.md):
  tenant_id   -> String slug ("demo_hotel")
  property_id -> UUID interne (uuid.UUID)
  hotel_id    -> alias tenant_id, String slug

Scans backend/app/services/ for known drift patterns.  Lines that contain
the marker comment ``# sql-param-correct`` are exempted — they represent
correct String FK bindings (e.g. captation_baselines.tenant_id) that would
otherwise match the UUID-column pattern.

Usage:
    python scripts/audit_id_types.py

Exit code:
  0 -- no mismatches found
  1 -- one or more mismatches remain
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
SERVICES_DIR = ROOT / "backend" / "app" / "services"

# ---------------------------------------------------------------------------
# Detection patterns
# Each tuple: (compiled_regex, description)
# Lines containing "# sql-param-correct" are always skipped.
# ---------------------------------------------------------------------------
PATTERNS: List[Tuple[re.Pattern, str]] = [
    # A1 — tenant_id (String slug) == str(UUID expression) in WHERE clause
    (
        re.compile(r"\.tenant_id\s*==\s*str\("),
        "tenant_id (String slug) == str(UUID) in WHERE -- UUID string never matches slug",
    ),
    # B1 — property_id (UUID column) compared with .id (String column) without cast
    (
        re.compile(r"\.property_id\s*==\s*(?:\w+\.)+id\b(?!\s*\))"),
        "property_id (UUID col) == .id (String col) without uuid.UUID cast",
    ),
    # B2 — ConversationalQuery / ORM constructor: property_id = profile.id (String, no cast)
    (
        re.compile(r"\bproperty_id\s*=\s*profile\.id\b(?!\s*\))"),
        "ORM constructor: property_id set from String profile.id without uuid.UUID cast",
    ),
    # B3 — ORM constructor: tenant_id = profile.tenant_id (slug assigned to UUID column)
    #      Lines with "# convention-ok" are exempt (e.g. calls to str-typed parameters).
    (
        re.compile(r"\btenant_id\s*=\s*profile\.tenant_id\b(?!.*#\s*convention-ok)"),
        "ORM constructor: tenant_id (UUID col) set from String slug profile.tenant_id",
    ),
    # C1 — tenant_id type-hint annotated as uuid.UUID (should be str per convention)
    (
        re.compile(r"\btenant_id\s*:\s*uuid\.UUID\b"),
        "tenant_id parameter typed as uuid.UUID -- convention requires str slug",
    ),
    # C2 — upsert dict: "tenant_id": str(tenant_id) storing slug in UUID column
    #      (exempted when # sql-param-correct is present on the same line)
    (
        re.compile(r'"tenant_id"\s*:\s*str\(tenant_id\)(?!.*#\s*sql-param-correct)'),
        '"tenant_id": str(tenant_id) -- slug stored in UUID column; use str(property_id)',
    ),
    # D1 — run_full_scan: raw String DB row[0] passed directly to uuid.UUID parameter
    (
        re.compile(r"\bproperty_id\s*=\s*row\[0\]\s*[,)]"),
        "run_full_scan: raw String row[0] passed to uuid.UUID property_id (missing cast)",
    ),
    # D2 — run_full_scan: raw DB row[1] (slug) passed to uuid.UUID parameter unannotated
    (
        re.compile(r"\btenant_id\s*=\s*row\[1\]\s*[,)]"),
        "run_full_scan: raw row[1] passed to tenant_id uuid.UUID param (missing str() cast)",
    ),
    # D3 — run_full_scan: String pid passed directly to uuid.UUID parameter
    (
        re.compile(r"run_for_property\(db\s*,\s*property_id\s*=\s*pid\b"),
        "run_full_scan: String pid passed to run_for_property(property_id: uuid.UUID)",
    ),
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Mismatch:
    path: Path
    line_no: int
    description: str

    def relative(self, root: Path) -> str:
        try:
            return str(self.path.relative_to(root))
        except ValueError:
            return str(self.path)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------
def scan_file(path: Path) -> List[Mismatch]:
    mismatches: List[Mismatch] = []
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[WARN] Cannot read {path}: {exc}", file=sys.stderr)
        return mismatches

    for line_no, line in enumerate(source.splitlines(), start=1):
        stripped = line.lstrip()
        # Skip pure comment lines -- they describe intent, not runtime behaviour
        if stripped.startswith("#"):
            continue
        for pattern, description in PATTERNS:
            if pattern.search(line):
                mismatches.append(Mismatch(path, line_no, description))
                break  # one mismatch report per line

    return mismatches


def collect_py_files(directory: Path) -> List[Path]:
    if not directory.exists():
        print(f"[ERROR] Directory not found: {directory}", file=sys.stderr)
        sys.exit(1)
    return sorted(directory.glob("**/*.py"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    files = collect_py_files(SERVICES_DIR)
    all_mismatches: List[Mismatch] = []

    for path in files:
        all_mismatches.extend(scan_file(path))

    for m in all_mismatches:
        rel = m.relative(ROOT)
        rel_fwd = rel.replace("\\", "/")
        print(f"[MISMATCH] {rel_fwd}:{m.line_no} -- {m.description}")

    count = len(all_mismatches)
    print(f"\n{count} mismatch(es) found.")
    return 1 if count else 0


if __name__ == "__main__":
    sys.exit(main())
