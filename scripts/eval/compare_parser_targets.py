"""Side-by-side table of real-LLM parser runs (HOS-337, Décision #35 D3).

Reads the JSON reports written by `run_all --layers parser` (one per target)
and prints a Markdown comparison. The result is written as is, gap included,
including when it is unfavourable to the fallback: that is the information
the matrix exists to produce.

Refuses to compare runs scored on different dataset versions — their numbers
are not about the same cases.

    python -m scripts.eval.compare_parser_targets out/claude.json out/gemini.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def compare(results: list[dict]) -> str:
    versions = {r["dataset_version"] for r in results}
    if len(versions) != 1:
        raise SystemExit(
            f"[compare] runs span several dataset versions {sorted(versions)} — not comparable"
        )
    stages = sorted({s for r in results for s in (r.get("decided_by") or {})})
    lines = [
        "# Parser — provider matrix",
        "",
        f"Dataset version `{versions.pop()}` · {len(results)} target(s)",
        "",
        "| Target | decision accuracy (model-graded) | n | model failure rate | "
        "auto-write precision | confirmation rate | "
        + " | ".join(stages)
        + " |",
        "|---|---|---|---|---|---|" + "---|" * len(stages),
    ]
    for r in results:
        counts = r.get("decided_by") or {}
        aw = r.get("auto_write") or {}
        lines.append(
            f"| `{r['target']}` | {_pct(r['accuracy_llm_decided'])} | {r['llm_decided_n']} "
            f"| {_pct(r['llm_failure_rate'])} | {_pct(aw.get('precision'))} "
            f"| {_pct(r.get('confirmation_rate'))} | "
            + " | ".join(str(counts.get(s, 0)) for s in stages)
            + " |"
        )
    lines += [
        "",
        "Every graded reply reaches the model: replies settled before it (keywords,",
        "bare acknowledgement, covers pattern) are reported apart as the deterministic",
        "block and score the same on every provider. A model error or an answer that",
        "fails the schema is a miss, never rescued by a heuristic; the failure rate is",
        "where a formatting gap between providers shows up.",
    ]
    ns = [r["llm_decided_n"] for r in results]
    if min(ns) < 5:
        lines += [
            "",
            f"> ⚠️ Only {min(ns)} model-graded case(s) on at least one target: "
            "too few to conclude anything about the model.",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    results = [json.loads(Path(p).read_text(encoding="utf-8"))["result"] for p in argv]
    missing = [r.get("backend") for r in results if not r.get("target")]
    if missing:
        raise SystemExit("[compare] every input must be a real-LLM run (backend=real with a target)")
    print(compare(results), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
