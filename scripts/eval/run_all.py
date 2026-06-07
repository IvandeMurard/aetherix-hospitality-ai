"""Eval runner entry point — ADR-0007 §5.a.

EVAL-1 (HOS-205) ships the `forecast` layer. parser/drift/latency land in
EVAL-3…EVAL-5. The CI gate (`check_eval_coverage.py`) is a separate follow-up;
this runner is callable standalone and by that gate.

Usage:
  python -m scripts.eval.run_all --layers forecast --md-out r.md --json-out r.json
  python -m scripts.eval.run_all --layers forecast --update-baseline   # freeze baseline
  python -m scripts.eval.run_all --layers forecast --strict            # exit 1 on regression
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import baselines, eval_forecast, eval_parser, reporter
from .loader import DEFAULT_DATASET

_RUNNERS = {"forecast": eval_forecast.run, "parser": eval_parser.run}
_DIFFS = {"forecast": baselines.diff_forecast, "parser": baselines.diff_parser}


def main() -> int:
    parser = argparse.ArgumentParser(description="Aetherix eval runner")
    parser.add_argument("--layers", default="forecast", help="Comma-separated: forecast")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--md-out", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=eval_forecast.SEED)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Freeze the current run as the layer baseline (eval/baselines/<layer>_baseline.json).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if a per-category regression > 3pp is detected (for the CI gate).",
    )
    args = parser.parse_args()

    layers = [s.strip() for s in args.layers.split(",") if s.strip()]
    exit_code = 0

    for layer in layers:
        runner = _RUNNERS.get(layer)
        if runner is None:
            print(f"[eval] layer {layer!r} not implemented yet — skipping")
            continue

        result = runner(dataset=args.dataset, seed=args.seed)

        if args.update_baseline:
            path = baselines.save_baseline(layer, result)
            print(f"[eval] {layer}: baseline frozen -> {path}")

        baseline = baselines.load_baseline(layer)
        diff = _DIFFS[layer](result, baseline)
        paths = reporter.write_reports(result, diff, args.json_out, args.md_out)

        if layer == "forecast":
            summary = (
                f"overall MAPE {(result['overall_mape_j1_holdout'] or 0) * 100:.2f}% · "
                f"coverage {(result['interval_coverage_pct'] or 0) * 100:.1f}% · "
                f"regressions {len(diff['regressions'])}"
            )
        else:  # parser
            summary = (
                f"accuracy {(result['accuracy'] or 0) * 100:.1f}% · n={result['n']} · "
                f"regressed={diff['regressed']}"
            )
        print(f"[eval] {layer}: {summary} -> {paths['md']}")

        regressed = bool(diff.get("regressions")) or diff.get("regressed", False)
        if args.strict and regressed:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
