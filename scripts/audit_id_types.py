#!/usr/bin/env python3
"""Static analysis for tenant_id / property_id / hotel_id type mismatches.

Scans backend/app/services/ for three categories of drift:

  A. tenant_id (String) == str(UUID_expr)      — UUID cast to str for WHERE comparison
  B. property_id (UUID) == .id (String)         — String PK compared to UUID FK
  C. str(uuid...) used in raw SQL bind-param    — UUID column receives str instead of UUID

Usage:
    python scripts/audit_id_types.py

Exit code: always 0 (findings are expected, not errors).
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
# Each tuple: (compiled_regex, description_template)
# ---------------------------------------------------------------------------
PATTERNS: List[Tuple[re.Pattern, str]] = [
    # A — tenant_id (String) == str(UUID) in WHERE clause
    (
        re.compile(r"\.tenant_id\s*==\s*str\("),
        "tenant_id (String) == str(UUID) in WHERE",
    ),
    # B — property_id (UUID) == .id (String) in WHERE clause
    (
        re.compile(r"\.property_id\s*==\s*(?:\w+\.)+id\b"),
        "property_id (UUID) == .id (String) in WHERE",
    ),
    # C1 — "tenant_id": str(...) in raw SQL bind-param dict
    (
        re.compile(r'"tenant_id"\s*:\s*str\('),
        'str(UUID) -> UUID column "tenant_id" in INSERT params',
    ),
    # C2 — "property_id": str(...) in raw SQL bind-param dict
    (
        re.compile(r'"property_id"\s*:\s*str\('),
        'str(UUID) -> UUID column "property_id" in INSERT params',
    ),
    # C3 — "anomaly_id": str(...) in raw SQL bind-param dict
    (
        re.compile(r'"anomaly_id"\s*:\s*str\('),
        'str(UUID) -> UUID column "anomaly_id" in INSERT params',
    ),
    # C4 — "id": str(uuid...) in raw SQL bind-param dict (primary key)
    (
        re.compile(r'"id"\s*:\s*str\(uuid'),
        'str(uuid.uuid4()) -> UUID primary key "id" in INSERT params',
    ),
    # C5 — variable assignment: *id = str(uuid.uuid4()) used later as UUID PK
    (
        re.compile(r"\brec_id\s*=\s*str\(uuid"),
        "str(uuid.uuid4()) assigned to rec_id (UUID PK placeholder)",
    ),
]


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
        # Skip pure comment lines — they describe intent, not runtime behaviour
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
        # Normalise to forward slashes for consistent output cross-platform
        rel_fwd = rel.replace("\\", "/")
        print(f"[MISMATCH] {rel_fwd}:{m.line_no} -- {m.description}")

    count = len(all_mismatches)
    print(f"\n{count} mismatch(es) found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
