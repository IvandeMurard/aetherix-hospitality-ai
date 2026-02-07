"""Forecast view - predictions, KPIs, timeline chart."""

import streamlit as st
import requests
from datetime import datetime, timedelta
from typing import Optional

from config import get_text, API_BASE
from components.header import render_header
from components.loading_steps import (
    render_loading_steps,
    PREDICTION_STEPS,
    WEEK_PREDICTION_STEPS,
)
from components.timeline_chart import (
    get_week_predictions,
    get_month_predictions,
    render_week_chart,
    render_day_hero,
    render_month_chart_from_data,
)
from components.feedback_panel import render_feedback_panel
from components.factors_panel import render_factors_panel


def _confidence_label(confidence: float, lang: str) -> str:
    """Map confidence 0-1 to High/Medium/Low."""
    if confidence >= 0.85:
        return get_text("confidence.high", lang)
    if confidence >= 0.7:
        return get_text("confidence.medium", lang)
    return get_text("confidence.low", lang)


def _parse_staff(staff_rec: dict) -> str:
    """Extract server count from staff_recommendation."""
    if not isinstance(staff_rec, dict):
        return "—"
    servers_dict = staff_rec.get("servers", {})
    if isinstance(servers_dict, dict):
        servers = servers_dict.get("recommended", "—")
    else:
        servers = servers_dict if servers_dict else "—"
    if servers == "—" and "recommended" in staff_rec:
        servers = staff_rec.get("recommended", "—")
    return servers


def _render_kpi_cards_day(lang: str, prediction: dict, date_display: str) -> None:
    """Render KPI cards for day view (single day values)."""
    col1, col2, col3, col4 = st.columns(4)
    if prediction:
        covers = prediction.get("predicted_covers", "—")
        accuracy_metrics = prediction.get("accuracy_metrics", {})
        interval = accuracy_metrics.get("prediction_interval")
        range_text = f"{interval[0]} – {interval[1]}" if interval and len(interval) == 2 else "—"
        confidence_label = _confidence_label(prediction.get("confidence", 0), lang)
        servers = _parse_staff(prediction.get("staff_recommendation", {}))
        with col1:
            st.metric(get_text("kpi.covers", lang).upper(), str(covers) if covers != "—" else "—")
        with col2:
            st.metric(get_text("kpi.range", lang).upper(), range_text)
        with col3:
            st.metric(get_text("kpi.staff", lang).upper(), f"{servers} servers" if servers != "—" else "—")
        with col4:
            st.metric(get_text("kpi.confidence", lang).upper(), confidence_label)
    else:
        with col1:
            st.metric(get_text("kpi.covers", lang).upper(), "—")
        with col2:
            st.metric(get_text("kpi.range", lang).upper(), "—")
        with col3:
            st.metric(get_text("kpi.staff", lang).upper(), "—")
        with col4:
            st.metric(get_text("kpi.confidence", lang).upper(), "—")
        st.warning(f"Could not load prediction for {date_display}")


def _render_kpi_cards_week(lang: str, week_predictions: list) -> None:
    """Render KPI cards for week view (totals, peak, avg)."""
    col1, col2, col3, col4 = st.columns(4)
    if not week_predictions:
        for col in [col1, col2, col3, col4]:
            with col:
                st.metric("—", "—")
        return
    total = sum(p.get("covers", 0) for p in week_predictions)
    avg_covers = int(total / 7)
    peak_day = max(week_predictions, key=lambda x: x.get("covers", 0))
    confidences = [p.get("confidence", 0) for p in week_predictions]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    with col1:
        st.metric(get_text("kpi.total_week", lang), f"{total} covers")
    with col2:
        st.metric(get_text("kpi.daily_avg", lang), f"{avg_covers} covers")
    with col3:
        st.metric(get_text("kpi.peak_day", lang), f"{peak_day.get('day', '—')} ({peak_day.get('covers', 0)})")
    with col4:
        st.metric(get_text("kpi.avg_confidence", lang), _confidence_label(avg_conf, lang))


def _render_kpi_cards_month(
    lang: str, month_predictions: Optional[list] = None
) -> None:
    """Render KPI cards for month view (placeholders or aggregated from batch)."""
    col1, col2, col3, col4 = st.columns(4)
    if month_predictions:
        total = sum(p.get("predicted_covers", 0) for p in month_predictions)
        n = len(month_predictions)
        avg = int(total / n) if n else 0
        peak = max(month_predictions, key=lambda x: x.get("predicted_covers", 0))
        confidences = [p.get("confidence", 0) for p in month_predictions]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        with col1:
            st.metric(get_text("kpi.total_month", lang), f"{total} covers")
        with col2:
            st.metric(get_text("kpi.daily_avg", lang), f"{avg} covers")
        with col3:
            st.metric(get_text("kpi.peak_day", lang), f"Day {peak.get('date', '')[-2:]} ({peak.get('predicted_covers', 0)})")
        with col4:
            st.metric(get_text("kpi.avg_confidence", lang), _confidence_label(avg_conf, lang))
    else:
        with col1:
            st.metric(get_text("kpi.total_month", lang), "…")
        with col2:
            st.metric(get_text("kpi.daily_avg", lang), "…")
        with col3:
            st.metric(get_text("kpi.peak_day", lang), "…")
        with col4:
            st.metric(get_text("kpi.confidence", lang), "…")


def fetch_prediction(date: datetime, restaurant: str, service: str) -> dict:
    """Fetch prediction from backend API."""
    try:
        restaurant_map = {
            "Main Restaurant": "hotel_main",
            "Pool Bar": "pool_bar",
            "Room Service": "room_service",
        }
        restaurant_id = restaurant_map.get(
            restaurant, restaurant.lower().replace(" ", "_")
        )
        response = requests.post(
            f"{API_BASE}/predict",
            json={
                "service_date": date.strftime("%Y-%m-%d"),
                "service_type": service.lower(),
                "restaurant_id": restaurant_id,
            },
            timeout=60,
        )
        if response.status_code == 200:
            return response.json()
        st.warning(f"Prediction API returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("Unable to connect to backend API. Please ensure the backend is running.")
    except requests.exceptions.Timeout:
        st.error(
            "Backend API request timed out. The first prediction can take up to a minute "
            "(embedding + Qdrant + Claude). Try again or check backend logs."
        )
    except Exception as e:
        st.error(f"Prediction error: {e}")
    return None


def _render_welcome_screen(lang: str) -> None:
    """Render enhanced welcome screen with preview cards."""
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    st.markdown(
        f"""
        <div style="text-align: center; padding: 2rem 0;">
            <h2 style="color: #1B4332; margin-bottom: 0.5rem;">
                {get_text("welcome.title", lang)}
            </h2>
            <p style="color: #6C757D; margin-bottom: 2rem;">
                {get_text("welcome.subtitle", lang)}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #1B4332 0%, #2D6A4F 100%);
                border-radius: 12px;
                padding: 1.5rem;
                text-align: center;
                height: 180px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <p style="color: rgba(255,255,255,0.7); font-size: 0.75rem; margin: 0;">
                    📅 {today.strftime("%A")}
                </p>
                <p style="color: white; font-size: 0.9rem; font-weight: 500; margin: 0.25rem 0;">
                    {today.strftime("%B %d")}
                </p>
                <p style="color: rgba(255,255,255,0.6); font-size: 0.7rem; margin-top: 0.5rem;">
                    {get_text("welcome.show_today", lang)}
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        if st.button(
            get_text("welcome.show_today", lang),
            key="welcome_today",
            use_container_width=True,
        ):
            st.session_state.forecast_requested = True
            st.session_state.selected_date = today
            if "view_toggle" not in st.session_state:
                st.session_state.view_toggle = "day"
            st.rerun()

    with col2:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #2D6A4F 0%, #40916C 100%);
                border-radius: 12px;
                padding: 1.5rem;
                text-align: center;
                height: 180px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <p style="color: rgba(255,255,255,0.7); font-size: 0.75rem; margin: 0;">
                    📊 {get_text("header.week", lang)}
                </p>
                <p style="color: white; font-size: 0.9rem; font-weight: 500; margin: 0.25rem 0;">
                    {week_start.strftime("%b %d")} – {week_end.strftime("%b %d")}
                </p>
                <p style="color: rgba(255,255,255,0.6); font-size: 0.7rem; margin-top: 0.5rem;">
                    {get_text("welcome.view_week", lang)}
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        if st.button(
            get_text("welcome.view_week", lang),
            key="welcome_week",
            use_container_width=True,
        ):
            st.session_state.forecast_requested = True
            st.session_state.selected_date = week_start
            st.session_state.view_toggle = "week"
            st.rerun()

    with col3:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #40916C 0%, #52B788 100%);
                border-radius: 12px;
                padding: 1.5rem;
                text-align: center;
                height: 180px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            ">
                <p style="color: rgba(255,255,255,0.7); font-size: 0.75rem; margin: 0;">
                    📈 {get_text("header.month", lang)}
                </p>
                <p style="color: white; font-size: 0.9rem; font-weight: 500; margin: 0.25rem 0;">
                    {today.strftime("%B %Y")}
                </p>
                <p style="color: rgba(255,255,255,0.6); font-size: 0.7rem; margin-top: 0.5rem;">
                    {get_text("welcome.view_month", lang)}
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        if st.button(
            get_text("welcome.view_month", lang),
            key="welcome_month",
            use_container_width=True,
        ):
            st.session_state.forecast_requested = True
            st.session_state.selected_date = today.replace(day=1)
            st.session_state.view_toggle = "month"
            st.rerun()


def render_forecast_view(context: dict) -> None:
    """Render the forecast page."""
    lang = context["language"]

    # Initialize forecast_requested flag if not set
    if "forecast_requested" not in st.session_state:
        st.session_state.forecast_requested = False

    # Cache invalidation: clear caches when restaurant or service changes
    cache_context = f"{context['restaurant']}_{context['service']}"
    if "last_cache_context" not in st.session_state:
        st.session_state.last_cache_context = cache_context

    if st.session_state.last_cache_context != cache_context:
        for key in ["prediction_cache", "week_predictions_cache"]:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.last_cache_context = cache_context

    header = render_header(lang=lang)
    st.markdown("<br>", unsafe_allow_html=True)

    # Show welcome screen if no forecast has been requested yet
    if not st.session_state.forecast_requested:
        _render_welcome_screen(lang)
        return

    selected_date = header["selected_date"]
    date_display = selected_date.strftime("%A, %B %d")
    view = header["view"]
    week_predictions = None
    month_predictions = None

    # Optional cache for day view prediction
    cache_key = f"{selected_date.strftime('%Y-%m-%d')}_{context['restaurant']}_{context['service']}"
    if "prediction_cache" not in st.session_state:
        st.session_state.prediction_cache = {}

    if view == "day" and cache_key not in st.session_state.prediction_cache:
        steps = [dict(s) for s in PREDICTION_STEPS]
        def safe_fetch_day():
            r = fetch_prediction(
                date=selected_date,
                restaurant=context["restaurant"],
                service=context["service"],
            )
            if r is None:
                raise RuntimeError("prediction_failed")
            return r
        steps[-1]["action"] = safe_fetch_day
        prediction = render_loading_steps(steps, lang=lang)
        if prediction is not None:
            st.session_state.prediction_cache[cache_key] = prediction
    elif view == "day":
        prediction = st.session_state.prediction_cache.get(cache_key)
    else:
        prediction = None  # Week/month use their own data fetch below

    # KPI cards (day view: single prediction; week/month handled below after data fetch)
    if view == "day":
        _render_kpi_cards_day(lang, prediction, date_display)
    elif view == "week":
        week_start = selected_date - timedelta(days=selected_date.weekday())
        if "week_predictions_cache" not in st.session_state:
            st.session_state.week_predictions_cache = {}
        week_cache_key = f"{week_start.strftime('%Y-%m-%d')}_{context['restaurant']}_{context['service']}"
        if week_cache_key not in st.session_state.week_predictions_cache:
            steps = [dict(s) for s in WEEK_PREDICTION_STEPS]
            def safe_fetch_week():
                r = get_week_predictions(
                    start_date=week_start,
                    restaurant=context["restaurant"],
                    service=context["service"],
                )
                if not r:
                    raise RuntimeError("week_data_failed")
                return r
            steps[-1]["action"] = safe_fetch_week
            week_predictions = render_loading_steps(steps, lang=lang)
            if week_predictions:
                st.session_state.week_predictions_cache[week_cache_key] = week_predictions
        else:
            week_predictions = st.session_state.week_predictions_cache[week_cache_key]
        _render_kpi_cards_week(lang, week_predictions or [])
    else:
        month_predictions = None
        with st.spinner(get_text("loading.month", lang)):
            month_predictions = get_month_predictions(
                selected_date.year,
                selected_date.month,
                context["restaurant"],
                context["service"],
            )
        _render_kpi_cards_month(lang, month_predictions)

    st.markdown("<br>", unsafe_allow_html=True)

    if view == "day":
        if prediction:
            render_day_hero(prediction, selected_date, lang=lang)
        else:
            st.info("Select a date to view forecast")
    elif view == "week":
        if week_predictions:
            covers_list = [p["covers"] for p in week_predictions if p["covers"] > 0]
            baseline = (
                sum(covers_list) / len(covers_list) if covers_list else None
            )
            render_week_chart(
                predictions=week_predictions,
                selected_date=selected_date,
                baseline=baseline,
                lang=lang,
            )
        else:
            st.info(get_text("week.no_data", lang))
    elif view == "month":
        if month_predictions:
            render_month_chart_from_data(month_predictions, lang=lang)
        else:
            st.info(get_text("month.no_data", lang))

    st.markdown("<br>", unsafe_allow_html=True)

    # Factors panel (expandable, uses real prediction data)
    render_factors_panel(
        prediction,
        view,
        lang,
        week_predictions=week_predictions,
        month_predictions=month_predictions,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Feedback panel (pre-service / post-service)
    render_feedback_panel(
        prediction_id=(prediction or {}).get("prediction_id"),
        predicted_covers=prediction.get("predicted_covers", 0) if prediction else 0,
        date=header["selected_date"],
        service=context["service"],
        restaurant=context["restaurant"],
        lang=lang,
        view=view,
    )
