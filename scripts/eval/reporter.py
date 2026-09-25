"""Eval result rendering — JSON + Markdown (ADR-0007 §4 output formats).

Renders a plain-Python Markdown report (no jinja2 dependency) — the sticky-PR
templating lives with the CI gate (EVAL-1 follow-up). Output paths follow
ADR §4: `eval/reports/YYYY-MM-DD/<layer>_report.md` + `result.json`.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = _ROOT / "eval" / "reports"


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def render_markdown(result: dict, diff: dict) -> str:
    if result.get("layer") == "parser":
        return _render_parser_md(result, diff)
    if result.get("layer") == "guardrail":
        return _render_guardrail_md(result, diff)
    return _render_forecast_md(result, diff)


def _render_guardrail_md(result: dict, diff: dict) -> str:
    """Guardrail trip report — HOS-321.

    Leads with reason coverage rather than accuracy: the question this layer
    answers is "which typed reasons (NFR2) has no scenario exercised", which is
    what the hygiene agent's D4 detector watches.
    """
    lines = [
        "# Eval report — guardrail",
        "",
        f"- **Accuracy**: {_pct(result['accuracy'])}  ·  n={result['n']} "
        f"({result['n_negative']} négatifs)",
        f"- **Raisons typées couvertes**: {result['n_reasons_covered']}",
        "",
        "## Raisons couvertes",
        "",
    ]
    lines += [f"- `{reason}`" for reason in result["reasons_covered"]] or ["_aucune_"]

    failures = result.get("failures") or []
    lines += ["", "## Scénarios en échec", ""]
    if not failures:
        lines.append("Aucun.")
    else:
        lines += ["| id | guard | attendu | obtenu | erreur |", "|---|---|---|---|---|"]
        for f in failures:
            lines.append(
                f"| {f['id']} | {f['guard']} | {f['expected'] or '—'} | "
                f"{f['actual'] or '—'} | {f.get('error') or '—'} |"
            )

    lines.append("")
    if not diff.get("has_baseline"):
        lines.append("_Pas de baseline figée — première exécution._")
    elif diff.get("lost_reasons"):
        lines.append(
            "⚠️ **Régression** — raisons perdues depuis la baseline : "
            + ", ".join(f"`{r}`" for r in diff["lost_reasons"])
        )
    elif diff.get("regressed"):
        lines.append(f"⚠️ **Régression** — accuracy {diff.get('accuracy_delta_pp')}pp vs baseline.")
    else:
        lines.append("✅ Aucune régression vs baseline.")

    return "\n".join(lines) + "\n"


def _render_parser_target_md(result: dict) -> list[str]:
    """Real run on a pinned target (HOS-337): the fields compared across providers."""
    lines = [
        "",
        "## Target",
        "",
        f"- **Target**: `{result.get('target')}`  ·  dataset version `{result.get('dataset_version')}`",
        f"- **Decision accuracy on the model-graded cases**: {_pct(result.get('accuracy_llm_decided'))}"
        f"  ·  n={result.get('llm_decided_n')}  (comparable across providers: every one of"
        " these replies reaches the model)",
        f"- **Model failure rate** (API error or answer failing the schema): "
        f"{_pct(result.get('llm_failure_rate'))}. A failure is a miss here, never rescued "
        "by a heuristic; read the rate on its own too.",
        "",
        "## Which step settled each case",
        "",
        "| Step | n | accuracy |",
        "|---|---|---|",
    ]
    for src, n in (result.get("decided_by") or {}).items():
        lines.append(f"| {src} | {n} | {_pct((result.get('accuracy_by_source') or {}).get(src))} |")
    return lines


def _render_parser_md(result: dict, diff: dict) -> str:
    """Parser report (EVAL-4, ADR-0007 §15).

    The fake backend is labelled as a plumbing check at the top and never shows
    an "Accuracy" headline: its agreement with the labels is not a quality
    measure, and a reader skimming the first lines must not take it for one.
    """
    from .eval_parser import PREDICTED_LABELS
    from .fake_intent_classifier import INTENTS

    real = bool(result.get("quality_signal"))
    ceiling = result.get("production_path_ceiling") or {}
    det = result.get("deterministic") or {}
    if real:
        model = result.get("model") or {}
        canary = result.get("canary") or {}
        aw = result.get("auto_write") or {}
        trig = result.get("confirmation_trigger") or {}
        lines = [
            "# Eval report — parser (free-text path, real model)",
            "",
            f"- **Decision accuracy** (replies that reach the model; written or proposed "
            f"for confirmation): {_pct(result['accuracy'])}  ·  n={result['n']}  ·  "
            f"typed errors={result['n_errors']}",
            f"- **Auto-written** (no confirmation): {aw.get('n_written')} · precision "
            f"{_pct(aw.get('precision'))} · per decision "
            + " · ".join(f"{d} {_pct(p)}" for d, p in (aw.get('per_decision_precision') or {}).items())
            + f"  ·  **confirmation rate** {_pct(result.get('confirmation_rate'))}",
            f"- **Confirmation trigger** ({trig.get('n')} two-reading replies): "
            f"{trig.get('auto_written')} written without confirmation (must be 0)",
            f"- **Model**: {model.get('provider')} · fast model `{model.get('fast_model')}` · "
            f"tiers {model.get('tiers')} · temperature {model.get('temperatures')} · "
            f"{model.get('llm_calls')} API calls",
            f"- **Runs**: {canary.get('runs')} · accuracies "
            f"{[_pct(a) for a in canary.get('accuracies', [])]} · variance "
            f"{canary.get('variance_pp')}pp · identical predictions: "
            f"{canary.get('identical_predictions')}",
        ]
    else:
        lines = [
            "# Eval report — parser · PLUMBING CHECK (fake backend)",
            "",
            "> ⚠️ **Not a model-quality measurement.** The fake backend is a keyword "
            "heuristic whose rules were written against the `dev` cases. Its agreement "
            "with the labels says nothing about the production parser or the model. "
            "**Model quality: not measured on this run** — the real run is opt-in "
            "(`eval-parser-real` label or workflow_dispatch).",
            "",
            f"- **Pipeline**: ran end to end on n={result['n']} cases",
            f"- Heuristic agreement (plumbing only, not quality): "
            f"{_pct(result['accuracy'])} overall · "
            + " · ".join(
                f"{s} {_pct(v['accuracy'])} (n={v['n']})"
                for s, v in (result.get("per_split") or {}).items()
            ),
        ]

    lines += [
        f"- **Deterministic path** (no model — code check, not quality): "
        f"{det.get('agree')}/{det.get('n')} replies decided before the model land on "
        f"their label · by step {det.get('by_stage')} · "
        f"{det.get('confirmations')} sent to confirmation",
        f"- **Production-path ceiling** (model-independent, computed on the production "
        f"code with no API call): max accuracy {_pct(ceiling.get('max_accuracy'))} · "
        f"{ceiling.get('decided_before_model')}/{ceiling.get('n')} replies decided before "
        f"the model · max recall "
        + " · ".join(f"{i} {_pct(r)}" for i, r in (ceiling.get("max_recall") or {}).items()),
    ]

    if real:
        lines += ["", "## Per split", "", "| split | accuracy | n |", "|---|---|---|"]
        for s, v in (result.get("per_split") or {}).items():
            lines.append(f"| {s} | {_pct(v['accuracy'])} | {v['n']} |")
        lines += ["", "## Per proposal kind (ADR-0007 §19)", "",
                  "| proposal | accuracy | n |", "|---|---|---|"]
        for k, v in (result.get("per_proposal") or {}).items():
            lines.append(f"| {k} | {_pct(v['accuracy'])} | {v['n']} |")
        lines += ["", "## Per intent", "", "| Intent | precision | recall | support |",
                  "|---|---|---|---|"]
        for intent in INTENTS:
            m = result["per_intent"][intent]
            lines.append(
                f"| {intent} | {_pct(m['precision'])} | {_pct(m['recall'])} | {m['support']} |"
            )
        lines += ["", "## Confusion matrix (rows = expected, cols = recorded)", "",
                  "| expected ↓ / recorded → | " + " | ".join(PREDICTED_LABELS) + " |",
                  "|---|" + "---|" * len(PREDICTED_LABELS)]
        cm = result["confusion_matrix"]
        for t in INTENTS:
            lines.append(f"| {t} | " + " | ".join(str(cm[t][p]) for p in PREDICTED_LABELS) + " |")
        if result.get("target"):
            lines += _render_parser_target_md(result)
        else:
            lines += ["", f"Decided by: {result.get('decided_by')}"]

        breaches = (result.get("thresholds") or {}).get("breaches") or []
        lines.append("")
        if breaches:
            lines.append("> 🛑 **Below the FAILURE_THRESHOLDS.md contract:** " + "; ".join(breaches))
        else:
            lines.append("> ✅ Meets the FAILURE_THRESHOLDS.md contract.")
        if not diff.get("has_baseline"):
            lines.append("> No real-model baseline frozen yet — not yet measured.")
        elif diff.get("regressed"):
            lines.append(f"> ⚠️ **Accuracy regressed {diff['accuracy_delta_pp']}pp vs baseline.**")
        else:
            lines.append(f"> Δ vs real baseline: {diff.get('accuracy_delta_pp')}pp.")
    return "\n".join(lines) + "\n"


def _render_forecast_md(result: dict, diff: dict) -> str:
    layer = result["layer"]
    lines = [
        f"# Eval report — {layer}",
        "",
        f"- **Overall MAPE (held-out)**: {_pct(result['overall_mape_j1_holdout'])}",
        f"- **Interval coverage** (80%): {_pct(result['interval_coverage_pct'])}",
        f"- **Tolerance pass rate**: {_pct(result['tolerance_pass_rate'])}",
        f"- **Scenarios**: {result['scenario_count']} · seed {result['seed']}",
        f"- **Data**: {result.get('data_provenance', 'unspecified')}",
        "",
        "## Per-category MAPE",
        "",
        "| Category | n | MAPE | Δ vs baseline |",
        "|---|---|---|---|",
    ]
    deltas = diff.get("deltas", {})
    for cat, mape in result["per_category_mape"].items():
        n = result["per_category_count"].get(cat, 0)
        if cat in deltas:
            d = deltas[cat]
            delta_str = f"{'+' if d >= 0 else ''}{d * 100:.2f}pp"
        else:
            delta_str = "new"
        lines.append(f"| {cat} | {n} | {_pct(mape)} | {delta_str} |")

    lines.append("")
    if not diff.get("has_baseline"):
        lines.append("> No baseline yet — this run establishes it.")
    elif diff["regressions"]:
        lines.append(f"> ⚠️ **{len(diff['regressions'])} regression(s) > 3pp:**")
        for r in diff["regressions"]:
            lines.append(
                f"> - `{r['category']}`: {_pct(r['baseline'])} → {_pct(r['current'])} (+{r['delta_pp']}pp)"
            )
    else:
        lines.append("> ✅ No per-category regression > 3pp vs baseline.")
    return "\n".join(lines) + "\n"


def write_reports(result: dict, diff: dict, json_out: Path | None, md_out: Path | None) -> dict:
    """Write JSON + Markdown. Defaults to eval/reports/YYYY-MM-DD/ when paths omitted."""
    day_dir = REPORTS_DIR / date.today().isoformat()
    layer = result["layer"]
    json_path = json_out or (day_dir / f"{layer}_result.json")
    md_path = md_out or (day_dir / f"{layer}_report.md")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({"result": result, "diff": diff}, indent=2) + "\n", encoding="utf-8")

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(result, diff), encoding="utf-8")

    return {"json": str(json_path), "md": str(md_path)}
