#!/usr/bin/env python3
"""Eval-by-design coverage gate — ADR-0007 §4 (D2/D3).

The *enforcement* half of EVAL-1 (HOS-216). HOS-205 shipped the measurement
engine (`scripts/eval/run_all.py`); this gate decides whether a PR needs an eval
run, invokes the engine for the touched layers, and turns its output into a
verdict + a sticky-PR Markdown report.

Because it runs Prophet in CI and can block merges on a stochastic model, it
ships in **WARN mode first** (ADR §9 R2/R4): the script emits real exit codes
0/1/2/3, but `.github/workflows/eval-gate.yml` does not fail the build on them
until a one-line flip after N green PRs prove Prophet-in-CI stable (AC5).

Exit codes (ADR §D2.f)
  0  PASS  — eval green, or eval-exempt, or cache hit, or no trigger touched
  1  FAIL  — per-category regression > 3pp, or coverage < 60%
  2  ERROR — engine crash / dataset missing / corrupt
  3  WARN  — coverage 60–80%, or touched-but-not-evaluated (non-blocking)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/ci/ -> repo root
_CACHE_FILE = _ROOT / "eval" / "baselines" / ".cache_keys.json"

# Exit codes
PASS, FAIL, ERROR, WARN = 0, 1, 2, 3

# Coverage thresholds (ADR §D3) — categories with >=1 PASS scenario / total.
COVERAGE_PASS = 0.80
COVERAGE_FAIL = 0.60

# Paths whose change triggers the gate (ADR §D2.a / §4). Order-independent.
EVAL_TRIGGER_PATHS = [
    "backend/app/services/prediction_engine.py",
    # ADR-0007 §18.2: the interval every risk statement rests on.
    "backend/app/services/forecast_calibration.py",
    "backend/app/services/staffing_service.py",
    "backend/app/services/recommendation_formatter.py",
    "backend/app/services/reasoning_service.py",
    "backend/app/services/explainability_service.py",
    "backend/app/services/memory_service.py",
    "backend/app/services/memory_recall_service.py",
    "backend/app/services/rag_service.py",
    "backend/app/services/pattern_scorer.py",
    "backend/app/services/query_parser.py",
    "backend/app/services/receipts.py",
    # EVAL-4 production path (ADR-0007 §15): exact accept/reject keywords + the
    # route that turns a parsed reply into a recorded outcome.
    "backend/app/services/action_logger.py",
    "backend/app/api/routes/twilio_inbound.py",
    # Décision #38 (ADR-0007 §16): the decision rules (keywords, thresholds,
    # rule (b)) and the service that applies them decide what arm C records.
    "backend/app/services/manager_decision.py",
    "backend/app/services/inbound_decision.py",
    "backend/app/services/agent_constitution.py",
    "backend/app/services/data_transformer.py",
    "backend/app/services/demand_modifiers.py",
    "backend/app/providers/",
    "backend/prompts/",
    "eval/golden_dataset.jsonl",
    "eval/FAILURE_THRESHOLDS.md",
    "eval/baselines/",
]

# path -> eval layer (ADR §D2.b). Files absent here fall under the prefix rules.
LAYER_BY_PATH = {
    "backend/app/services/prediction_engine.py": "forecast",
    "backend/app/services/forecast_calibration.py": "forecast",
    "backend/app/services/staffing_service.py": "forecast",
    "backend/app/services/data_transformer.py": "forecast",
    "backend/app/services/demand_modifiers.py": "forecast",
    "backend/app/services/pattern_scorer.py": "forecast",
    "backend/app/services/recommendation_formatter.py": "recommendation",
    "backend/app/services/reasoning_service.py": "recommendation",
    "backend/app/services/explainability_service.py": "recommendation",
    "backend/app/services/memory_service.py": "recall",
    "backend/app/services/memory_recall_service.py": "recall",
    "backend/app/services/rag_service.py": "recall",
    "backend/app/services/query_parser.py": "parser",
    # receipts.py holds both the Receipt composer and parse_inbound (the inbound
    # parser under EVAL-4) — it maps to both layers.
    "backend/app/services/receipts.py": ("receipt", "parser"),
    "backend/app/services/action_logger.py": "parser",
    "backend/app/api/routes/twilio_inbound.py": "parser",
    "backend/app/services/manager_decision.py": "parser",
    "backend/app/services/inbound_decision.py": "parser",
}

# A change under these triggers a FULL run — an LLM/embedding/prompt swap impacts
# every layer (ADR §D2.b).
FULL_RUN_PREFIXES = (
    "backend/app/providers/",
    "backend/prompts/",
    "backend/app/services/agent_constitution.py",
)

# Shared-contract paths that re-run everything evaluable (we don't diff the JSONL
# line-by-line per layer here). A per-layer baseline file (eval/baselines/<layer>_
# baseline.json) instead re-runs only that layer — see detect() — so adding e.g. a
# latency baseline doesn't drag in a forecast run.
FULL_CONTRACT_PATHS = (
    "eval/golden_dataset.jsonl",
    "eval/FAILURE_THRESHOLDS.md",
)
# All contract paths (for the touched-but-not-evaluated exclusion — none of these
# are "code" triggers).
CONTRACT_PATHS = (*FULL_CONTRACT_PATHS, "eval/baselines/")
_BASELINE_SUFFIX = "_baseline.json"

# Layers that actually have a runner wired in scripts/eval/run_all.py today.
# Detected-but-unevaluable layers (recommendation/recall/receipt/drift/latency)
# surface as a note, never a hard fail (their runners land in EVAL-3/5 / Phase 4).
EVALUABLE_LAYERS = ("forecast", "parser", "guardrail")


# ---------------------------------------------------------------------------
# Inputs (dependency seams — tests monkeypatch these)
# ---------------------------------------------------------------------------

def get_changed_files(base_ref: str) -> list[str]:
    """Files changed vs base_ref (git diff --name-only base..HEAD)."""
    out = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        text=True,
        cwd=str(_ROOT),
    )
    return [ln.strip().replace("\\", "/") for ln in out.splitlines() if ln.strip()]


def get_pr_labels() -> set[str]:
    """PR labels, lower-cased. CI passes them via GITHUB_PR_LABELS (comma-sep)."""
    raw = os.environ.get("GITHUB_PR_LABELS", "")
    return {lbl.strip().lower() for lbl in raw.split(",") if lbl.strip()}


def invoke_run_all(layer: str, json_out: Path, md_out: Path) -> tuple[int, dict | None]:
    """Run the eval engine for one layer; return (returncode, parsed {result,diff}).

    Subprocess (not import) so Prophet/pandas stay out of this module's import
    graph and tests can monkeypatch the whole call.
    """
    proc = subprocess.run(
        [
            sys.executable, "-m", "scripts.eval.run_all",
            "--layers", layer,
            "--json-out", str(json_out),
            "--md-out", str(md_out),
            "--strict",
        ],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.returncode == 2 or not json_out.exists():
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, end="")
        return proc.returncode, None
    return proc.returncode, json.loads(json_out.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------

def _matches(path: str, trigger: str) -> bool:
    return path == trigger if not trigger.endswith("/") else path.startswith(trigger)


def detect(changed: list[str]) -> tuple[list[str], set[str]]:
    """Return (touched_trigger_files, detected_layers).

    detected_layers is the conceptual set (may include layers with no runner yet).
    """
    touched = [f for f in changed if any(_matches(f, t) for t in EVAL_TRIGGER_PATHS)]
    layers: set[str] = set()
    for f in touched:
        if f.startswith(FULL_RUN_PREFIXES):
            layers.update(EVALUABLE_LAYERS)
        elif f in LAYER_BY_PATH:
            mapped = LAYER_BY_PATH[f]
            layers.update((mapped,) if isinstance(mapped, str) else mapped)
        elif f in FULL_CONTRACT_PATHS:
            layers.update(EVALUABLE_LAYERS)
        elif f.startswith("eval/baselines/") and f.endswith(_BASELINE_SUFFIX):
            # A baseline bump re-runs only its own layer (ADR §D2.b).
            layers.add(Path(f).name[: -len(_BASELINE_SUFFIX)])
    return touched, layers


def cache_key(touched: list[str]) -> str:
    """sha256 over the contents of the touched trigger files (ADR §D2.e)."""
    h = hashlib.sha256()
    for path in sorted(touched):
        p = _ROOT / path
        h.update(path.encode())
        h.update(b"\0")
        if p.is_file():
            h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _load_cache() -> dict:
    if _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(key: str) -> None:
    cache = _load_cache()
    cache["last_pass_key"] = key
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")


def coverage_from_result(result: dict) -> tuple[int, int]:
    """(passed_categories, total_categories) — a category passes with >=1 PASS
    scenario (ADR §D3). Only layers exposing per-scenario detail (forecast)
    contribute; parser accuracy is judged by its own regression diff."""
    cats: dict[str, bool] = {}
    for sc in result.get("scenarios", []):
        cat = sc.get("category")
        if cat is None:
            continue
        cats.setdefault(cat, False)
        if sc.get("tolerance_pass"):
            cats[cat] = True
    return sum(1 for v in cats.values() if v), len(cats)


def has_regression(diff: dict) -> bool:
    return bool(diff.get("regressions")) or bool(diff.get("regressed"))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Eval-by-design coverage gate (ADR-0007 §4)")
    parser.add_argument("--base-ref", default="origin/main", help="Git ref to diff against")
    parser.add_argument("--strict", action="store_true", help="(reserved) caller decides blocking")
    parser.add_argument("--json-out", type=Path, default=None, help="Write aggregate result JSON")
    parser.add_argument("--md-out", type=Path, default=None, help="Write sticky-PR Markdown report")
    parser.add_argument("--print-ignored", action="store_true", help="List skipped trigger files")
    args = parser.parse_args()

    report: list[str] = ["## Eval-by-Design Gate", ""]

    # 1. eval-exempt label short-circuit (ADR §D2.c)
    if "eval-exempt" in get_pr_labels():
        print("[eval-coverage] SKIP — label eval-exempt présent")
        print("[eval-coverage] Authorized exemptions: refactor, doc, infra-only, ci-only, test-only")
        report.append("✅ **Skipped** — `eval-exempt` label present.")
        _write(args.md_out, report)
        return PASS

    # 2. detect touched trigger paths -> layers
    try:
        changed = get_changed_files(args.base_ref)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"[eval-coverage] ERROR: git diff failed: {exc}", file=sys.stderr)
        return ERROR

    touched, layers = detect(changed)
    if args.print_ignored:
        print(f"[eval-coverage] touched trigger files: {touched or 'none'}")

    if not touched:
        print("[eval-coverage] No trigger paths touched — no eval needed.")
        report.append("✅ No eval-trigger paths touched.")
        _write(args.md_out, report)
        return PASS

    run_layers = sorted(set(layers) & set(EVALUABLE_LAYERS))
    not_evaluable = sorted(set(layers) - set(EVALUABLE_LAYERS))

    # 3. cache hit (ADR §D2.e) — same touched-file contents already passed.
    key = cache_key(touched)
    if _load_cache().get("last_pass_key") == key:
        print("[eval-coverage] Cache hit — touched files unchanged since last PASS.")
        report.append("✅ Cache hit — eval-trigger files unchanged since last green run.")
        _write(args.md_out, report)
        return PASS

    if not run_layers:
        # Touched a trigger that maps only to layers without a runner yet.
        msg = f"layers detected but not yet evaluable: {', '.join(not_evaluable) or 'none'}"
        print(f"[eval-coverage] WARN — {msg}")
        report.append(f"⚠️ **WARN** — {msg} (runner lands in a later EVAL story).")
        _write(args.md_out, report)
        return WARN

    print(f"[eval-coverage] Running eval for layers: {', '.join(run_layers)}")

    # 4. run engine per layer, collect verdicts (ADR §4 steps 5-7)
    regressed = False
    passed_cats = total_cats = 0
    tmp_dir = _ROOT / "eval" / "reports" / "_gate"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for layer in run_layers:
        rc, payload = invoke_run_all(layer, tmp_dir / f"{layer}.json", tmp_dir / f"{layer}.md")
        if payload is None:
            print(f"[eval-coverage] ERROR — engine failed for layer {layer} (rc={rc}).")
            report.append(f"🛑 **ERROR** — eval engine crashed for `{layer}`.")
            _write(args.md_out, report)
            return ERROR
        result, diff = payload.get("result", {}), payload.get("diff", {})
        if has_regression(diff):
            regressed = True
        p, t = coverage_from_result(result)
        passed_cats += p
        total_cats += t
        report.append(_layer_summary(layer, result, diff, p, t))

    # 5. touched-but-not-evaluated (AC3 / ADR §D3): code trigger changed but the
    #    golden dataset wasn't, i.e. no scenario was added/modified.
    code_triggers = [f for f in touched if not any(_matches(f, c) for c in CONTRACT_PATHS)]
    dataset_touched = any(_matches(f, "eval/golden_dataset.jsonl") for f in touched)
    touched_not_evaluated = bool(code_triggers) and not dataset_touched

    coverage = (passed_cats / total_cats) if total_cats else None

    # 6. verdict (ADR §D2.f) — regression/low-coverage FAIL beats WARN beats PASS.
    code = PASS
    if regressed:
        code = FAIL
    elif coverage is not None and coverage < COVERAGE_FAIL:
        code = FAIL
    elif coverage is not None and coverage < COVERAGE_PASS:
        code = WARN
    if code == PASS and (touched_not_evaluated or not_evaluable):
        code = WARN

    report.insert(2, _verdict_line(code, coverage, regressed))
    if touched_not_evaluated:
        report.append(
            "⚠️ Touched model/LLM code but `eval/golden_dataset.jsonl` was not "
            "updated. Add a scenario or apply the `eval-exempt` label."
        )
    if not_evaluable:
        report.append(f"ℹ️ Detected layers without a runner yet: {', '.join(not_evaluable)}.")

    _write(args.md_out, report)
    if args.json_out:
        args.json_out.write_text(
            json.dumps(
                {
                    "exit_code": code,
                    "coverage_pct": coverage,
                    "regressed": regressed,
                    "run_layers": run_layers,
                    "touched_not_evaluated": touched_not_evaluated,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if code == PASS:
        _save_cache(key)

    print(f"[eval-coverage] verdict: exit {code} (coverage={coverage})")
    return code


def _layer_summary(layer: str, result: dict, diff: dict, passed: int, total: int) -> str:
    if layer == "forecast":
        mape = result.get("overall_mape_j1_holdout")
        mape_s = "—" if mape is None else f"{mape * 100:.2f}%"
        regs = len(diff.get("regressions", []))
        return (
            f"- **forecast** — overall MAPE {mape_s} · coverage {passed}/{total} "
            f"categories · {regs} regression(s) >3pp"
        )
    if layer == "parser":
        ceiling = (result.get("production_path_ceiling") or {}).get("max_accuracy")
        ceil_s = "—" if ceiling is None else f"{ceiling * 100:.1f}%"
        if not result.get("quality_signal"):
            # ADR-0007 §15: the PR gate runs the fake backend. Never print its
            # agreement as an accuracy — it is not a model-quality measurement.
            return (
                "- **parser** — plumbing check only (fake backend): pipeline ran on "
                f"n={result.get('n')} cases. **Model quality not measured on this PR** "
                "(opt-in: label `eval-parser-real`). Production-path ceiling "
                f"{ceil_s} (model-independent)."
            )
        acc = result.get("accuracy")
        acc_s = "—" if acc is None else f"{acc * 100:.1f}%"
        delta = diff.get("accuracy_delta_pp")
        return (
            f"- **parser** — accuracy {acc_s} (production path, real model) · "
            f"Δ {delta}pp vs baseline · ceiling {ceil_s}"
        )
    return f"- **{layer}** — evaluated"


def _verdict_line(code: int, coverage: float | None, regressed: bool) -> str:
    cov_s = "n/a" if coverage is None else f"{coverage * 100:.0f}%"
    label = {PASS: "✅ PASS", FAIL: "🛑 FAIL", WARN: "⚠️ WARN", ERROR: "🛑 ERROR"}[code]
    reason = " (regression >3pp)" if regressed else ""
    return f"**Verdict: {label}** — category coverage {cov_s}{reason}\n"


def _write(md_out: Path | None, lines: list[str]) -> None:
    if md_out is not None:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
