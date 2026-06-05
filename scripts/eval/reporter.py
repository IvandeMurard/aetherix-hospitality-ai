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
