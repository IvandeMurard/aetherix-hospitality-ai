"""Golden-dataset loader — ADR-0007 §5.

Parses `eval/golden_dataset.jsonl` and filters scenarios by layer. Stdlib only
(the heavy per-layer runners import pandas/prophet, the loader does not).
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATASET = _ROOT / "eval" / "golden_dataset.jsonl"


def load_scenarios(
    dataset: Path | str = DEFAULT_DATASET,
    layer: str | None = None,
) -> list[dict]:
    """Return scenarios from the JSONL dataset, optionally filtered by `layer`."""
    path = Path(dataset)
    scenarios: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if layer is None or row.get("layer") == layer:
            scenarios.append(row)
    return scenarios
