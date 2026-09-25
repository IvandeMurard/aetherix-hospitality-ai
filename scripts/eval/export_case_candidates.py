"""Export reviewed eval cases from the learning loop to the golden dataset.

ADR-0007 §18.5 (Décision #40). A manager's override whose reason the model
routed to ``case_set`` becomes a ``learning_items`` row of kind ``eval_case``.
It becomes an eval case only after Ivan approves it **with the expected
output written by the reviewer** (``POST /api/v1/hotels/{tenant}/learning/
items/{id}/approve`` with ``case``). This script appends the approved cases
to ``eval/golden_dataset.jsonl`` (dated zone: ``created_at`` = today,
``author`` = reviewer — Décision #35 D5), validates the whole file with
``validate_dataset.validate``, and marks the items ``applied`` only if the
file is valid; otherwise it restores the file and exits 1.

Usage (needs DATABASE_URL):
  backend/.venv/bin/python -m scripts.eval.export_case_candidates [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "backend"))

from scripts.eval.loader import DEFAULT_DATASET  # noqa: E402
from scripts.eval.validate_dataset import validate  # noqa: E402


async def _run(dataset: Path, dry_run: bool) -> int:
    from app.db.session import AsyncSessionLocal
    from app.services.learning_store import export_approved_cases

    with tempfile.TemporaryDirectory() as tmp:
        backup = Path(tmp) / "golden_dataset.jsonl"
        shutil.copyfile(dataset, backup)
        async with AsyncSessionLocal() as db:
            written = await export_approved_cases(db, dataset, today=date.today().isoformat())
            errors = validate(dataset)
            if errors or dry_run:
                shutil.copyfile(backup, dataset)
                await db.rollback()
                for e in errors:
                    print(f"[export_case_candidates] invalid: {e}")
                print(f"[export_case_candidates] {'dry run' if dry_run and not errors else 'refused'}: "
                      f"{len(written)} case(s) not written")
                return 1 if errors else 0
            await db.commit()
    print(f"[export_case_candidates] appended {len(written)} case(s): {', '.join(written) or '-'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return asyncio.run(_run(args.dataset, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
