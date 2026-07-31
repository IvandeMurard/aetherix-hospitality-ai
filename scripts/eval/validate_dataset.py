#!/usr/bin/env python3
"""Golden-dataset validator — EVAL-0 (HOS-204), ADR-0007 §D1/§3.

Validates `eval/golden_dataset.jsonl`:
  - every line parses as JSON
  - required top-level fields present
  - `id` unique + kebab-case, prefixed by a known layer prefix
  - `category` in the 11-category taxonomy (+ pos_anomaly placeholder)
  - `layer` in the known layer set
  - per-category minimum counts for the EVAL-0 "unblocking minimum" (AC0.1)

Exit codes:
  0  valid
  1  validation error(s)
  2  dataset file missing / unreadable

Usage:
  python scripts/eval/validate_dataset.py
  python scripts/eval/validate_dataset.py --dataset path/to.jsonl --strict-full
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/eval/ -> repo root
_DEFAULT_DATASET = _ROOT / "eval" / "golden_dataset.jsonl"

REQUIRED_FIELDS = (
    "schema_version",
    "id",
    "category",
    "layer",
    "created_at",
    "author",
    "input",
    "expected",
    "failure_trigger",
    "notes",
)

# Taxonomy — ADR-0007 §D1 (11 active + pos_anomaly forward-compat).
CATEGORIES = {
    "normal_day",
    "event_day",
    "weather_anomaly",
    "ota_cancellation_wave",
    "weekend_weekday_split",
    "service_stratification",
    "closure_day",
    "holiday_eve",
    "breakfast_dinner_mix_shift",
    "ood_edge",
    "parser_intent",
    "pos_anomaly",
    # HOS-321 — runtime-guardrail trip scenarios. Distinct from the forecast
    # categories above: these assert that the right *typed reason* fires (NFR2 /
    # ADR-0009), not a business value. Does not reopen ADR-0007 §D2.g, which
    # exempts runtime guardrails from EVAL-1 *metric* coverage — a different
    # object.
    "guardrail_trip",
}

LAYERS = {"forecast", "recommendation", "receipt", "parser", "drift", "latency", "guardrail"}

# EVAL-0 AC0.1 "unblocking minimum" — unblocks EVAL-1 / EVAL-2 / EVAL-4.
EVAL0_MIN_COUNTS = {
    "normal_day": 10,
    "event_day": 6,
    "weather_anomaly": 3,
    "ood_edge": 3,
    "parser_intent": 12,
}

# AC0.2 full-coverage milestone (Sprint N+2) — checked only with --strict-full.
FULL_MIN_COUNTS = {
    "normal_day": 15,
    "event_day": 8,
    "weather_anomaly": 5,
    "ota_cancellation_wave": 3,
    "weekend_weekday_split": 5,
    "service_stratification": 5,
    "closure_day": 3,
    "holiday_eve": 4,
    "breakfast_dinner_mix_shift": 3,
    "ood_edge": 5,
    "parser_intent": 15,
}

_KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate(dataset: Path, strict_full: bool = False) -> list[str]:
    """Return a list of error strings (empty = valid)."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    counts: Counter[str] = Counter()

    lines = dataset.read_text(encoding="utf-8").splitlines()
    non_empty = [(i, ln) for i, ln in enumerate(lines, 1) if ln.strip()]

    for lineno, raw in non_empty:
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"line {lineno}: invalid JSON — {exc}")
            continue

        missing = [f for f in REQUIRED_FIELDS if f not in row]
        if missing:
            errors.append(f"line {lineno}: missing fields {missing}")

        sid = row.get("id", "")
        if sid in seen_ids:
            errors.append(f"line {lineno}: duplicate id {sid!r}")
        elif sid:
            seen_ids.add(sid)
        if sid and not _KEBAB_RE.match(sid):
            errors.append(f"line {lineno}: id {sid!r} is not kebab-case")

        category = row.get("category")
        if category not in CATEGORIES:
            errors.append(f"line {lineno}: unknown category {category!r}")
        else:
            counts[category] += 1

        if row.get("layer") not in LAYERS:
            errors.append(f"line {lineno}: unknown layer {row.get('layer')!r}")

        if not isinstance(row.get("input"), dict):
            errors.append(f"line {lineno}: 'input' must be an object")
        if not isinstance(row.get("expected"), dict):
            errors.append(f"line {lineno}: 'expected' must be an object")

    required = FULL_MIN_COUNTS if strict_full else EVAL0_MIN_COUNTS
    milestone = "AC0.2 full coverage" if strict_full else "AC0.1 unblocking minimum"
    for cat, minimum in required.items():
        if counts[cat] < minimum:
            errors.append(
                f"category '{cat}': {counts[cat]} scenario(s), "
                f"{milestone} requires >= {minimum}"
            )

    if not non_empty:
        errors.append("dataset is empty")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate eval/golden_dataset.jsonl")
    parser.add_argument("--dataset", type=Path, default=_DEFAULT_DATASET)
    parser.add_argument(
        "--strict-full",
        action="store_true",
        help="Enforce AC0.2 full 71-scenario coverage (Sprint N+2) instead of AC0.1.",
    )
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"[eval-dataset] ERROR: dataset not found: {args.dataset}", file=sys.stderr)
        return 2

    errors = validate(args.dataset, strict_full=args.strict_full)
    total = sum(
        1 for ln in args.dataset.read_text(encoding="utf-8").splitlines() if ln.strip()
    )

    if errors:
        print(f"[eval-dataset] FAIL — {len(errors)} error(s) in {total} scenario(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"[eval-dataset] PASS — {total} scenario(s) valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
