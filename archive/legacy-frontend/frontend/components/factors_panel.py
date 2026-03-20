"""Factors Panel Component — Display reasoning and contextual factors."""

import streamlit as st
from typing import Optional, List, Dict

from config import get_text


def _aggregate_reasoning(predictions: List[Dict], lang: str) -> tuple:
    """Collect summaries and confidence_factors from a list of predictions with reasoning."""
    summaries = []
    all_factors = []
    patterns_count = 0
    for item in predictions:
        r = item.get("reasoning")
        if not r or not isinstance(r, dict):
            continue
        summary = r.get("summary")
        if summary and isinstance(summary, str):
            summaries.append(summary)
        factors = r.get("confidence_factors") or []
        for f in factors:
            if isinstance(f, str) and f and f not in all_factors:
                all_factors.append(f)
        patterns = r.get("patterns_used") or []
        if isinstance(patterns, list):
            patterns_count += len(patterns)
    return summaries, all_factors[:5], patterns_count


def render_factors_panel(
    prediction: Optional[dict],
    view: str,
    lang: str = "en",
    week_predictions: Optional[List[Dict]] = None,
    month_predictions: Optional[List[Dict]] = None,
) -> None:
    """
    Render factors panel with real prediction reasoning.

    Shows: events, weather, historical baseline, most similar day, confidence factors.
    For day view uses prediction; for week/month uses aggregated reasoning from
    week_predictions or month_predictions when provided.
    """
    if view == "week":
        if not week_predictions:
            with st.expander(get_text("factors.title", lang), expanded=False):
                st.info(get_text("factors.no_data", lang))
            return
        summaries, factors, patterns_count = _aggregate_reasoning(week_predictions, lang)
        if not summaries and not factors:
            with st.expander(get_text("factors.title", lang), expanded=False):
                st.info(get_text("factors.no_data", lang))
            return
        with st.expander(get_text("factors.title", lang), expanded=False):
            st.markdown("**Summary**")
            if summaries:
                st.markdown(f"- {summaries[0]}")
                if len(summaries) > 1:
                    for s in summaries[1:3]:
                        st.caption(f"- {s}")
            else:
                st.caption("Based on 7-day analysis.")
            if patterns_count:
                st.caption(f"{get_text('factors.patterns_count', lang)}: {patterns_count}")
            if factors:
                st.markdown("---")
                st.markdown(f"**{get_text('factors.confidence', lang)}**")
                for f in factors:
                    st.markdown(f"- {f}")
        return

    if view == "month":
        if not month_predictions:
            with st.expander(get_text("factors.title", lang), expanded=False):
                st.info(get_text("factors.no_data", lang))
            return
        summaries, factors, patterns_count = _aggregate_reasoning(month_predictions, lang)
        if not summaries and not factors:
            with st.expander(get_text("factors.title", lang), expanded=False):
                st.info(get_text("factors.no_data", lang))
            return
        with st.expander(get_text("factors.title", lang), expanded=False):
            st.markdown("**Summary**")
            if summaries:
                st.markdown(f"- {summaries[0]}")
                if len(summaries) > 1:
                    for s in summaries[1:2]:
                        st.caption(f"- {s}")
            else:
                st.caption(f"Based on {len(month_predictions)}-day analysis.")
            if patterns_count:
                st.caption(f"{get_text('factors.patterns_count', lang)}: {patterns_count}")
            if factors:
                st.markdown("---")
                st.markdown(f"**{get_text('factors.confidence', lang)}**")
                for f in factors:
                    st.markdown(f"- {f}")
        return

    if view != "day":
        with st.expander(get_text("factors.title", lang), expanded=False):
            st.info(get_text("factors.no_data", lang))
        return

    if not prediction:
        with st.expander(get_text("factors.title", lang), expanded=False):
            st.info(get_text("factors.no_data", lang))
        return

    reasoning = prediction.get("reasoning") or {}
    if isinstance(reasoning, str):
        reasoning = {"summary": reasoning}
    patterns = reasoning.get("patterns_used") or []
    confidence_factors = reasoning.get("confidence_factors") or []

    with st.expander(get_text("factors.title", lang), expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**{get_text('factors.events', lang)}**")
            events = (
                prediction.get("events")
                or (reasoning.get("events") if isinstance(reasoning.get("events"), list) else None)
            )
            if events and len(events) > 0:
                for ev in events[:3]:
                    if isinstance(ev, dict):
                        name = ev.get("name", ev.get("event_type", "Event"))
                        impact = ev.get("impact", "")
                        st.markdown(f"- {name}" + (f" ({impact})" if impact else ""))
                    else:
                        st.markdown(f"- {ev}")
            else:
                st.caption(get_text("factors.no_events", lang))

            st.markdown("---")
            st.markdown(f"**{get_text('factors.weather', lang)}**")
            weather = prediction.get("weather") or reasoning.get("weather")
            if weather:
                if isinstance(weather, dict):
                    condition = weather.get("condition", weather.get("description", "—"))
                    temp = weather.get("temperature", weather.get("temp", "—"))
                    st.markdown(f"- {condition}" + (f", {temp}°C" if temp != "—" else ""))
                else:
                    st.write(weather)
            else:
                st.caption(get_text("factors.no_weather", lang))

        with col2:
            st.markdown(f"**{get_text('factors.baseline', lang)}**")
            if patterns:
                valid_covers = [p.get("actual_covers", p.get("covers", 0)) for p in patterns]
                avg = (
                    sum(valid_covers) / len(valid_covers)
                    if valid_covers
                    else 0
                )
                st.markdown(
                    f"- {get_text('factors.avg_similar', lang)}: {int(avg)} covers"
                )
                st.markdown(
                    f"- {get_text('factors.patterns_count', lang)}: {len(patterns)}"
                )
            else:
                accuracy_metrics = prediction.get("accuracy_metrics") or {}
                baseline = accuracy_metrics.get("historical_avg", "—")
                st.caption(
                    f"{get_text('factors.historical_avg', lang)}: {baseline}"
                )

            st.markdown("---")
            st.markdown(f"**{get_text('factors.similar_day', lang)}**")
            if patterns and len(patterns) > 0:
                best = patterns[0]
                date_val = best.get("date", "—")
                covers = best.get("actual_covers", best.get("covers", "—"))
                sim = best.get("similarity", 0)
                sim_pct = int(sim * 100) if isinstance(sim, (int, float)) else "—"
                day_type = best.get("event_type", best.get("metadata", {}).get("day_of_week", ""))
                st.markdown(f"- {date_val}" + (f" ({day_type})" if day_type else ""))
                st.markdown(f"- {covers} covers, {sim_pct}% similar")
            else:
                st.caption(get_text("factors.no_similar", lang))

        if confidence_factors:
            st.markdown("---")
            st.markdown(f"**{get_text('factors.confidence', lang)}**")
            for factor in confidence_factors[:5]:
                if isinstance(factor, str):
                    st.markdown(f"- {factor}")
                else:
                    st.markdown(f"- {factor}")
