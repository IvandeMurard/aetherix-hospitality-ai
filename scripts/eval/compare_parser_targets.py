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

from .eval_parser import SOURCE_LLM, SOURCES


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def compare(results: list[dict]) -> str:
    versions = {r["dataset_version"] for r in results}
    if len(versions) != 1:
        raise SystemExit(
            f"[compare] runs span several dataset versions {sorted(versions)} — not comparable"
        )
    lines = [
        "# Parser — provider matrix",
        "",
        f"Dataset version `{versions.pop()}` · {len(results)} target(s)",
        "",
        "| Target | end-to-end accuracy | LLM-decided accuracy | LLM-decided n | LLM failure rate | "
        + " | ".join(SOURCES)
        + " |",
        "|---|---|---|---|---|" + "---|" * len(SOURCES),
    ]
    for r in results:
        counts = r["decided_by"]
        lines.append(
            f"| `{r['target']}` | {_pct(r['accuracy'])} | {_pct(r['accuracy_llm_decided'])} "
            f"| {r['llm_decided_n']} | {_pct(r['llm_failure_rate'])} | "
            + " | ".join(str(counts[s]) for s in SOURCES)
            + " |"
        )
    lines += [
        "",
        f"Only the `{SOURCE_LLM}` column is decided by the model's own answer. `regex` and",
        "`llm_free_form_heuristic` cases score identically on every provider, so end-to-end",
        "accuracy understates any gap. A failed call (API error or unparseable output) is",
        "rescued by the heuristic and does not lower accuracy at all: compare the failure",
        "rate, not the accuracy. Part of it is formatting, which Décision #35 D2 (HOS-338)",
        "removes — read this table again after HOS-338.",
    ]
    llm_ns = [r["llm_decided_n"] for r in results]
    if min(llm_ns) < 5:
        lines += [
            "",
            f"> ⚠️ Only {min(llm_ns)} case(s) decided by the LLM on at least one target: "
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
