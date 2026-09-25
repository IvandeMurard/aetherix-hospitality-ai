"""Eval runner entry point — ADR-0007 §5.a.

EVAL-1 (HOS-205) ships the `forecast` layer. parser/drift/latency land in
EVAL-3…EVAL-5. The CI gate (`check_eval_coverage.py`) is a separate follow-up;
this runner is callable standalone and by that gate.

Usage:
  python -m scripts.eval.run_all --layers forecast --md-out r.md --json-out r.json
  python -m scripts.eval.run_all --layers forecast --update-baseline   # freeze baseline
  python -m scripts.eval.run_all --layers forecast --strict            # exit 1 on regression
  EVAL_PARSER_BACKEND=real python -m scripts.eval.run_all --layers parser --runs 3 --strict

Exit codes: 0 ok · 1 regression / threshold breach (with --strict) · 2 not measured
(e.g. real parser eval without an API key, or a refused baseline freeze).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import baselines, eval_forecast, eval_guardrail, eval_parser, reporter
from .loader import DEFAULT_DATASET

_RUNNERS = {
    "forecast": eval_forecast.run,
    "parser": eval_parser.run,
    "guardrail": eval_guardrail.run,
}
_DIFFS = {
    "forecast": baselines.diff_forecast,
    "parser": baselines.diff_parser,
    "guardrail": baselines.diff_guardrail,
}


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
        "--runs",
        type=int,
        default=1,
        help="parser/real only: repeat the eval N times to measure run-to-run variance "
        "(>= 3 identical runs required to freeze a real baseline).",
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

        kwargs = {"runs": args.runs} if layer == "parser" else {}
        try:
            result = runner(dataset=args.dataset, seed=args.seed, **kwargs)
        except eval_parser.ParserEvalNotMeasured as exc:
            print(f"[eval] {layer}: NOT MEASURED — {exc}", file=sys.stderr)
            return 2

        # A real-LLM parser run has its own baseline per (target, dataset
        # version) — never the fake-backend path the PR gate uses (HOS-337).
        if layer == "parser" and result.get("target"):
            bpath = baselines.parser_target_baseline_path(
                result["target"], result["dataset_version"]
            )
        else:
            bpath = baselines.baseline_path(layer)

        if args.update_baseline:
            refusal = (
                baselines.parser_baseline_freeze_refusal(result) if layer == "parser" else None
            )
            if refusal:
                print(f"[eval] {layer}: baseline NOT frozen — {refusal}", file=sys.stderr)
                return 2
            path = baselines.save_baseline_at(bpath, result)
            print(f"[eval] {layer}: baseline frozen -> {path}")

        baseline = baselines.load_baseline_at(bpath)
        diff = _DIFFS[layer](result, baseline)
        paths = reporter.write_reports(result, diff, args.json_out, args.md_out)

        if layer == "forecast":
            summary = (
                f"overall MAPE {(result['overall_mape_j1_holdout'] or 0) * 100:.2f}% · "
                f"coverage {(result['interval_coverage_pct'] or 0) * 100:.1f}% · "
                f"regressions {len(diff['regressions'])}"
            )
        elif layer == "guardrail":
            summary = (
                f"accuracy {(result['accuracy'] or 0) * 100:.1f}% · n={result['n']} "
                f"({result['n_negative']} négatifs) · "
                f"{result['n_reasons_covered']} raisons couvertes · "
                f"regressed={diff['regressed']}"
            )
            if diff.get("lost_reasons"):
                summary += f" · PERDUES: {', '.join(diff['lost_reasons'])}"
        else:  # parser
            ceiling = result["production_path_ceiling"]["max_accuracy"]
            if result.get("quality_signal"):
                summary = (
                    f"decision accuracy {(result['accuracy'] or 0) * 100:.1f}% (free-text "
                    f"path, real model) · n={result['n']} · errors={result['n_errors']} · "
                    f"auto-written {result['auto_write']['n_written']} · "
                    f"trigger auto-writes {result['confirmation_trigger']['auto_written']} · "
                    f"threshold breaches={len(result['thresholds']['breaches'])} · "
                    f"regressed={diff['regressed']} · target={result.get('target')} · "
                    f"model failure rate {(result.get('llm_failure_rate') or 0) * 100:.1f}%"
                )
            else:
                summary = (
                    "PLUMBING CHECK ONLY (fake backend) — not a model-quality measurement · "
                    f"n={result['n']} · model quality: not measured"
                )
            summary += f" · production-path ceiling {(ceiling or 0) * 100:.1f}%"
        print(f"[eval] {layer}: {summary} -> {paths['md']}")

        regressed = (
            bool(diff.get("regressions"))
            or diff.get("regressed", False)
            or diff.get("below_threshold", False)
        )
        if args.strict and regressed:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
