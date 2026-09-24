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


def _render_parser_md(result: dict, diff: dict) -> str:
    from .fake_intent_classifier import INTENTS

    lines = [
        "# Eval report — parser",
        "",
        f"- **Accuracy**: {_pct(result['accuracy'])}  ·  n={result['n']}  ·  backend={result['backend']}",
        "",
        "## Per-intent",
        "",
        "| Intent | precision | recall | support |",
        "|---|---|---|---|",
    ]
    for intent in INTENTS:
        m = result["per_intent"][intent]
        lines.append(
            f"| {intent} | {_pct(m['precision'])} | {_pct(m['recall'])} | {m['support']} |"
        )
    lines += ["", "## Confusion matrix (rows = true, cols = predicted)", "",
              "| true ↓ / pred → | " + " | ".join(INTENTS) + " |",
              "|---|" + "---|" * len(INTENTS)]
    cm = result["confusion_matrix"]
    for t in INTENTS:
        lines.append(f"| {t} | " + " | ".join(str(cm[t][p]) for p in INTENTS) + " |")

    if result.get("target"):
        lines += _render_parser_target_md(result)
    lines.append("")
    if not diff.get("has_baseline"):
        lines.append("> No baseline yet — this run establishes it.")
    elif diff.get("regressed"):
        lines.append(f"> ⚠️ **Accuracy regressed {diff['accuracy_delta_pp']}pp vs baseline.**")
    else:
        lines.append("> ✅ No accuracy regression > 2pp vs baseline.")
    return "\n".join(lines) + "\n"


def _render_parser_target_md(result: dict) -> list[str]:
    """Real-LLM run (HOS-337): who decided each case, and the LLM-only accuracy."""
    lines = [
        "",
        "## Target",
        "",
        f"- **Target**: `{result['target']}`  ·  dataset version `{result['dataset_version']}`",
        f"- **Accuracy on LLM-decided cases**: {_pct(result['accuracy_llm_decided'])}"
        f"  ·  n={result['llm_decided_n']}  (the only part comparable across providers)",
        f"- **LLM failure rate**: {_pct(result['llm_failure_rate'])} of the calls that reached the LLM",
        "",
        "## Who decided each case",
        "",
        "| Source | n | accuracy |",
        "|---|---|---|",
    ]
    for src, n in result["decided_by"].items():
        lines.append(f"| {src} | {n} | {_pct(result['accuracy_by_source'][src])} |")
    lines += [
        "",
        "> `regex` cases never reach the LLM, and `llm_free_form_heuristic` cases are",
        "> settled by the deterministic heuristic: both score the same on every provider.",
        "> `llm_failed` = API error or unparseable output. The heuristic then answers, so a",
        "> failure does NOT lower accuracy — read the failure rate above instead.",
    ]
    return lines


def _render_forecast_md(result: dict, diff: dict) -> str:
    layer = result["layer"]
    lines = [
        f"# Eval report — {layer}",
        "",
        f"- **Overall MAPE (held-out)**: {_pct(result['overall_mape_j1_holdout'])}",
        f"- **Interval coverage** (80%): {_pct(result['interval_coverage_pct'])}",
        f"- **Tolerance pass rate**: {_pct(result['tolerance_pass_rate'])}",
        f"- **Scenarios**: {result['scenario_count']} · seed {result['seed']}",
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
