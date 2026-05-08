#!/usr/bin/env python3
"""Audit service-layer ID type comparisons (HOS-159-B / HOS-164).

Convention (docs/context/data-conventions.md):
  tenant_id   -> String slug ("demo_hotel")
  property_id -> UUID interne (uuid.UUID)
  hotel_id    -> alias tenant_id, String slug

Each MISMATCH_PATTERN is a (file_glob, regex, description) triple.
A match in the source file counts as one mismatch.

Exit code:
  0 -- no mismatches found in the checked files
  1 -- one or more mismatches remain
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Root of the backend services directory
_HERE = Path(__file__).parent
_SERVICE_DIR = _HERE.parent / "backend" / "app" / "services"

# (filename, regex_pattern, description)
# NOTE on "tenant_id": str(property_id) in anomaly_detection: the upsert dict
# uses property_id as surrogate for demand_anomalies.tenant_id (UUID column).
# _get_baseline_demand's SQL param {"tenant_id": str(tenant_id)} is CORRECT
# (captation_baselines.tenant_id is a String FK) and is explicitly exempted via
# the "# sql-param-correct" marker added to that line.
MISMATCH_PATTERNS: List[Tuple[str, str, str]] = [
    # -- alert_dispatcher.py ----------------------------------------------------
    (
        "alert_dispatcher.py",
        r"RestaurantProfile\.tenant_id\s*==\s*str\s*\(",
        "str(UUID) compared with tenant_id slug -- will never match in prod",
    ),
    # -- action_logger.py -------------------------------------------------------
    (
        "action_logger.py",
        r"StaffingRecommendation\.property_id\s*==\s*profile\.id\b",
        "UUID column compared with String profile.id (missing uuid.UUID cast)",
    ),
    # -- query_parser.py --------------------------------------------------------
    (
        "query_parser.py",
        r"StaffingRecommendation\.property_id\s*==\s*profile\.id\b",
        "UUID column compared with String profile.id (missing uuid.UUID cast)",
    ),
    (
        "query_parser.py",
        r"tenant_id\s*=\s*profile\.tenant_id\b",
        "ConversationalQuery.tenant_id set from slug -- _is_uuid guard always False for slugs",
    ),
    (
        "query_parser.py",
        r"property_id\s*=\s*profile\.id\b(?!\s*\))",
        "ConversationalQuery.property_id set from String profile.id without uuid.UUID cast",
    ),
    # -- anomaly_detection.py ---------------------------------------------------
    (
        "anomaly_detection.py",
        r"tenant_id\s*:\s*uuid\.UUID",
        "tenant_id typed as uuid.UUID -- convention requires str slug",
    ),
    (
        "anomaly_detection.py",
        # Match the upsert dict form: `"tenant_id": str(tenant_id),` on its own line.
        # Exempt _get_baseline_demand's SQL param (marked # sql-param-correct).
        r'"tenant_id":\s*str\(tenant_id\)(?!.*#\s*sql-param-correct)',
        "Slug string stored in demand_anomalies.tenant_id (UUID column) -- use str(property_id)",
    ),
    (
        "anomaly_detection.py",
        r"property_id=row\[0\]",
        "Raw String DB row[0] passed to uuid.UUID property_id without uuid.UUID(str(...)) cast",
    ),
    (
        "anomaly_detection.py",
        r"tenant_id=row\[1\](?!\s*#)",
        "Raw DB row[1] passed to tenant_id parameter without explicit str() cast annotation",
    ),
    # -- roi_calculator.py -------------------------------------------------------
    (
        "roi_calculator.py",
        r"self\.run_for_property\(db\s*,\s*property_id\s*=\s*pid\b",
        "String pid from restaurant_profiles.id passed to run_for_property(property_id: uuid.UUID)",
    ),
]


def audit() -> int:
    total_mismatches = 0
    file_counts: dict[str, int] = {}

    for filename, pattern, description in MISMATCH_PATTERNS:
        path = _SERVICE_DIR / filename
        if not path.exists():
            print(f"[SKIP]  {filename} -- file not found at {path}")
            continue

        source = path.read_text(encoding="utf-8")
        hits = list(re.finditer(pattern, source, re.MULTILINE))

        if not hits:
            continue

        for match in hits:
            lineno = source[: match.start()].count("\n") + 1
            print(f"[MISMATCH]  {filename}:{lineno}  {description}")
            print(f"            found: {match.group()!r}")
            total_mismatches += 1
            file_counts[filename] = file_counts.get(filename, 0) + 1

    print()
    if total_mismatches == 0:
        print("OK  0 mismatches -- all service-layer ID comparisons conform to convention.")
        return 0

    print(f"FAIL  {total_mismatches} mismatch(es) found across {len(file_counts)} file(s):")
    for fname, count in sorted(file_counts.items()):
        print(f"    {fname}: {count}")
    return 1


if __name__ == "__main__":
    sys.exit(audit())
