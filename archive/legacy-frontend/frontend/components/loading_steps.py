"""Loading Steps Component - Show AI reasoning transparency."""

import streamlit as st
import time
from typing import List, Dict, Callable, Any, Optional

from config import get_text


def render_loading_steps(
    steps: List[Dict], execute: bool = True, lang: str = "en"
) -> Optional[Any]:
    """
    Render loading progress with AI reasoning steps.

    On step failure: that step turns red, process stops, display stays visible.

    Args:
        steps: List of {"label": str, "action": callable or None, "error_key": str}
        execute: Whether to actually execute actions
        lang: Language for error messages

    Returns:
        Result of the last step's action, or None on failure.
    """
    steps_placeholder = st.empty()
    result = None
    step_results: List[Dict] = []  # {"label": str, "status": "completed"|"failed", "error_key": str|None}
    failed_step: Optional[Dict] = None

    for i, step in enumerate(steps):
        label = step["label"]
        action = step.get("action")
        error_key = step.get("error_key", "loading.step_staff_error")

        # Build HTML: completed (check), current (arrow), remaining (circle)
        lines = []
        for s in step_results:
            if s["status"] == "completed":
                lines.append(
                    f'<div style="display: flex; align-items: center; margin-bottom: 0.5rem; color: #40916C;">'
                    f'<span style="margin-right: 0.5rem;">✓</span>'
                    f'<span style="font-size: 0.875rem;">{s["label"]}</span></div>'
                )
            else:
                err_msg = get_text(s.get("error_key", "loading.step_staff_error"), lang)
                lines.append(
                    f'<div style="display: flex; flex-direction: column; margin-bottom: 0.5rem; color: #E76F51;">'
                    f'<div style="display: flex; align-items: center;">'
                    f'<span style="margin-right: 0.5rem;">✗</span>'
                    f'<span style="font-size: 0.875rem;">{s["label"]}</span></div>'
                    f'<div style="font-size: 0.75rem; margin-left: 1.25rem; margin-top: 0.25rem;">{err_msg}</div>'
                    f'</div>'
                )
        lines.append(
            f'<div style="display: flex; align-items: center; margin-bottom: 0.5rem; color: #495057;">'
            f'<span style="margin-right: 0.5rem;">→</span>'
            f'<span style="font-size: 0.875rem;">{label}</span></div>'
        )
        for k in range(i + 1, len(steps)):
            lines.append(
                f'<div style="display: flex; align-items: center; margin-bottom: 0.5rem; color: #ADB5BD;">'
                f'<span style="margin-right: 0.5rem;">○</span>'
                f'<span style="font-size: 0.875rem;">{steps[k]["label"]}</span></div>'
            )

        card_html = f"""
        <div style="
            background-color: #FFFFFF;
            border: 1px solid #E9ECEF;
            border-radius: 8px;
            padding: 1.5rem;
            margin: 1rem 0;
        ">
            <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                <div style="
                    width: 8px; height: 8px;
                    background-color: #2D6A4F;
                    border-radius: 50%;
                    margin-right: 0.75rem;
                    animation: pulse 1s infinite;
                "></div>
                <span style="color: #212529; font-weight: 500;">Generating forecast...</span>
            </div>
            {"".join(lines)}
        </div>
        """
        steps_placeholder.markdown(card_html, unsafe_allow_html=True)

        if execute and action and callable(action):
            try:
                result = action()
                step_results.append({"label": label, "status": "completed", "error_key": None})
            except Exception:
                step_results.append({"label": label, "status": "failed", "error_key": error_key})
                failed_step = {"label": label, "error_key": error_key}
                break
        else:
            time.sleep(0.25)
            step_results.append({"label": label, "status": "completed", "error_key": None})

    # Final state
    if failed_step:
        # Error state: render and keep displayed, do NOT empty
        final_lines = []
        for s in step_results:
            if s["status"] == "completed":
                final_lines.append(
                    f'<div style="display: flex; align-items: center; margin-bottom: 0.5rem; color: #40916C;">'
                    f'<span style="margin-right: 0.5rem;">✓</span>'
                    f'<span style="font-size: 0.875rem;">{s["label"]}</span></div>'
                )
            else:
                err_msg = get_text(s["error_key"], lang)
                final_lines.append(
                    f'<div style="display: flex; flex-direction: column; margin-bottom: 0.5rem; color: #E76F51;">'
                    f'<div style="display: flex; align-items: center;">'
                    f'<span style="margin-right: 0.5rem;">✗</span>'
                    f'<span style="font-size: 0.875rem;">{s["label"]}</span></div>'
                    f'<div style="font-size: 0.75rem; margin-left: 1.25rem; margin-top: 0.25rem;">{err_msg}</div>'
                    f'</div>'
                )
        for k in range(len(step_results), len(steps)):
            final_lines.append(
                f'<div style="display: flex; align-items: center; margin-bottom: 0.5rem; color: #ADB5BD;">'
                f'<span style="margin-right: 0.5rem;">○</span>'
                f'<span style="font-size: 0.875rem;">{steps[k]["label"]}</span></div>'
            )
        fail_header = get_text("loading.forecast_failed", lang)
        final_html = f"""
        <div style="
            background-color: #FFFFFF;
            border: 1px solid #E9ECEF;
            border-radius: 8px;
            padding: 1.5rem;
            margin: 1rem 0;
        ">
            <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                <span style="color: #E76F51; font-weight: 500;">{fail_header}</span>
            </div>
            {"".join(final_lines)}
        </div>
        """
        steps_placeholder.markdown(final_html, unsafe_allow_html=True)
        return None

    # Success state: all complete, clear placeholder
    final_lines = []
    for s in step_results:
        final_lines.append(
            f'<div style="display: flex; align-items: center; margin-bottom: 0.5rem; color: #40916C;">'
            f'<span style="margin-right: 0.5rem;">✓</span>'
            f'<span style="font-size: 0.875rem;">{s["label"]}</span></div>'
        )
    final_html = f"""
    <div style="
        background-color: #FFFFFF;
        border: 1px solid #E9ECEF;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
    ">
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <span style="color: #212529; font-weight: 500;">Forecast ready</span>
        </div>
        {"".join(final_lines)}
    </div>
    """
    steps_placeholder.markdown(final_html, unsafe_allow_html=True)
    steps_placeholder.empty()

    return result


# Predefined step sequences (caller attaches action to last step)
PREDICTION_STEPS = [
    {"label": "Loading historical data...", "action": None, "error_key": "loading.step_data_error"},
    {"label": "Analyzing day-of-week patterns...", "action": None, "error_key": "loading.step_patterns_error"},
    {"label": "Checking for local events...", "action": None, "error_key": "loading.step_events_error"},
    {"label": "Finding similar past days...", "action": None, "error_key": "loading.step_similar_error"},
    {"label": "Calculating confidence interval...", "action": None, "error_key": "loading.step_confidence_error"},
    {"label": "Generating staff recommendation...", "action": None, "error_key": "loading.step_staff_error"},
]

WEEK_PREDICTION_STEPS = [
    {"label": "Loading week data...", "action": None, "error_key": "loading.step_week_data_error"},
    {"label": "Analyzing 7-day patterns...", "action": None, "error_key": "loading.step_week_patterns_error"},
    {"label": "Processing each day...", "action": None, "error_key": "loading.step_week_process_error"},
    {"label": "Calculating weekly totals...", "action": None, "error_key": "loading.step_week_totals_error"},
]
