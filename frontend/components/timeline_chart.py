"""Timeline Chart Component - Apollo Style"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests

from config import API_BASE, get_text


def render_day_hero(prediction: dict, date: datetime, lang: str = "en") -> None:
    """Render day view as prominent hero card instead of bar chart."""
    if not prediction:
        st.warning("No prediction available for this date")
        return

    covers = prediction.get("predicted_covers", 0)
    metrics = prediction.get("accuracy_metrics") or {}
    interval = metrics.get("prediction_interval") or []
    range_low = interval[0] if len(interval) >= 1 else max(0, covers - 10)
    range_high = interval[1] if len(interval) >= 2 else covers + 10
    confidence = prediction.get("confidence", 0)  # 0-1
    confidence_pct = int(confidence * 100)

    if confidence_pct >= 85:
        conf_label = get_text("confidence.high", lang)
        conf_color = "#40916C"
    elif confidence_pct >= 70:
        conf_label = get_text("confidence.medium", lang)
        conf_color = "#E9C46A"
    else:
        conf_label = get_text("confidence.low", lang)
        conf_color = "#E76F51"

    expected_label = get_text("hero.expected_covers", lang)
    range_label = get_text("hero.range", lang)
    conf_header = get_text("hero.confidence", lang)

    st.html(
        f"""<div style="
            background: linear-gradient(135deg, #1B4332 0%, #2D6A4F 100%);
            border-radius: 16px;
            padding: 40px;
            text-align: center;
            margin: 1rem 0;
        ">
            <p style="
                color: #a7f3d0;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 16px;
            ">{date.strftime('%A, %B %d, %Y')}</p>

            <div style="
                font-size: 96px;
                font-weight: 700;
                line-height: 1;
                color: #4ade80;
                letter-spacing: -2px;
                margin-bottom: 8px;
            ">{covers}</div>

            <p style="
                color: #d1d5db;
                font-size: 18px;
                font-weight: 400;
                margin-bottom: 32px;
            ">{expected_label}</p>

            <div style="
                display: flex;
                justify-content: center;
                gap: 48px;
                font-size: 14px;
            ">
                <div>
                    <p style="color: #9ca3af; font-size: 14px; margin: 0;">{range_label}</p>
                    <p style="color: #ffffff; font-weight: 600; font-size: 18px; margin-top: 4px; margin-bottom: 0;">
                        {range_low} – {range_high}
                    </p>
                </div>
                <div>
                    <p style="color: #9ca3af; font-size: 14px; margin: 0;">{conf_header}</p>
                    <p style="color: {conf_color}; font-weight: 600; font-size: 18px; margin-top: 4px; margin-bottom: 0;">
                        {conf_label}
                    </p>
                </div>
            </div>
        </div>"""
    )


def _restaurant_to_id(restaurant: str) -> str:
    """Map restaurant display name to backend ID."""
    restaurant_map = {
        "Main Restaurant": "hotel_main",
        "Pool Bar": "pool_bar",
        "Room Service": "room_service",
    }
    return restaurant_map.get(restaurant, restaurant.lower().replace(" ", "_"))


def _normalize_prediction(p: dict, dates: list, start_date: datetime, i: int) -> dict:
    """Normalize a single prediction from API response. Returns None if invalid."""
    date_str = p.get("date") or p.get("service_date") or (dates[i] if i < len(dates) else "")
    if hasattr(date_str, "isoformat"):
        date_str = date_str.isoformat() if hasattr(date_str, "date") else str(date_str)
    date_str = str(date_str).replace("Z", "").split("T")[0] if date_str else ""
    try:
        dt = datetime.fromisoformat(date_str) if date_str else start_date + timedelta(days=i)
    except (ValueError, TypeError):
        dt = start_date + timedelta(days=i)
    covers = p.get("predicted_covers") if p.get("predicted_covers") is not None else p.get("covers", 0)
    metrics = p.get("accuracy_metrics") or {}
    interval = metrics.get("prediction_interval") or [0, 0]
    range_low = interval[0] if len(interval) >= 1 else 0
    range_high = interval[1] if len(interval) >= 2 else 0
    return {
        "date": dt,
        "day": dt.strftime("%a"),
        "covers": int(covers) if covers is not None else 0,
        "range_low": range_low,
        "range_high": range_high,
        "confidence": p.get("confidence") or p.get("confidence_score") or 0,
    }


def get_week_predictions(
    start_date: datetime, restaurant: str, service: str
) -> List[Dict]:
    """Fetch predictions for 7 days using batch API."""
    dates = [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(7)
    ]
    restaurant_id = _restaurant_to_id(restaurant)
    service_type = service.lower()
    try:
        response = requests.post(
            f"{API_BASE}/predict/batch",
            json={
                "dates": dates,
                "service_type": service_type,
                "restaurant_id": restaurant_id,
            },
            timeout=120,
        )
        if response.status_code != 200:
            st.error(f"Week forecast API returned {response.status_code}. Check backend.")
            return []
        data = response.json()
        raw = data if isinstance(data, list) else (data.get("predictions") or [])
        predictions = []
        for i, p in enumerate(raw):
            if not isinstance(p, dict):
                continue
            norm = _normalize_prediction(p, dates, start_date, i)
            if norm:
                if p.get("reasoning") is not None:
                    norm["reasoning"] = p.get("reasoning")
                predictions.append(norm)
        if len(predictions) < 7:
            for i in range(len(predictions), 7):
                dt = start_date + timedelta(days=i)
                predictions.append({
                    "date": dt,
                    "day": dt.strftime("%a"),
                    "covers": 0,
                    "range_low": 0,
                    "range_high": 0,
                    "confidence": 0,
                })
        return predictions[:7]
    except requests.exceptions.ConnectionError:
        st.error("Unable to connect to backend API. Please ensure the backend is running.")
        return []
    except requests.exceptions.Timeout:
        st.error(
            "Batch API request timed out. Week forecast can take up to 2 minutes. Try again."
        )
        return []
    except Exception as e:
        st.error(f"Failed to load week predictions: {e}")
        return []


def get_month_predictions(
    year: int, month: int, restaurant: str, service: str
) -> Optional[List[Dict]]:
    """Fetch all predictions for a month using batch API."""
    from calendar import monthrange
    from datetime import date as date_cls

    _, last_day = monthrange(year, month)
    dates = [date_cls(year, month, day).strftime("%Y-%m-%d") for day in range(1, last_day + 1)]
    restaurant_id = _restaurant_to_id(restaurant)
    service_type = service.lower()
    try:
        response = requests.post(
            f"{API_BASE}/predict/batch",
            json={
                "dates": dates,
                "service_type": service_type,
                "restaurant_id": restaurant_id,
            },
            timeout=120,
        )
        if response.status_code != 200:
            st.error(f"Month forecast API returned {response.status_code}. Check backend.")
            return None
        data = response.json()
        raw = data if isinstance(data, list) else (data.get("predictions") or [])
        start_date = datetime(year, month, 1)
        normalized = []
        for i, p in enumerate(raw):
            if not isinstance(p, dict):
                continue
            norm = _normalize_prediction(p, dates, start_date, i)
            if norm:
                normalized.append({
                    "date": p.get("date") or p.get("service_date") or (
                        dates[i] if i < len(dates) else (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
                    ),
                    "predicted_covers": norm["covers"],
                    "confidence": norm["confidence"],
                    "reasoning": p.get("reasoning"),
                })
        return normalized if normalized else None
    except requests.exceptions.ConnectionError:
        st.error("Unable to connect to backend API. Please ensure the backend is running.")
        return None
    except requests.exceptions.Timeout:
        st.error(
            "Month forecast request timed out. Loading 28–31 days can take several minutes."
        )
        return None
    except Exception as e:
        st.error(f"Failed to load month predictions: {e}")
        return None


def render_week_chart(
    predictions: List[Dict],
    selected_date: Optional[datetime] = None,
    baseline: Optional[float] = None,
    lang: str = "en",
) -> None:
    """Render Apollo-style weekly bar chart."""
    if not predictions:
        st.info(get_text("week.no_data", lang))
        return

    days = [p["day"] for p in predictions]
    covers = [p["covers"] for p in predictions]

    colors = []
    for p in predictions:
        if selected_date and p["date"].date() == selected_date.date():
            colors.append("#1B4332")
        else:
            colors.append("#2D6A4F")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=days,
            y=covers,
            marker_color=colors,
            text=covers,
            textposition="outside",
            textfont=dict(size=14, color="#212529"),
            hovertemplate="<b>%{x}</b><br>%{y} covers<extra></extra>",
        )
    )

    if baseline is not None:
        fig.add_hline(
            y=baseline,
            line_dash="dash",
            line_color="#ADB5BD",
            annotation_text=f"Avg: {int(baseline)}",
            annotation_position="right",
        )

    fig.update_layout(
        title=get_text("chart.week_forecast", lang),
        xaxis=dict(
            title=None,
            tickfont=dict(size=14, color="#495057"),
            showgrid=False,
        ),
        yaxis=dict(
            title=None,
            tickfont=dict(size=12, color="#6C757D"),
            gridcolor="#E9ECEF",
            zeroline=False,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=40, r=40, t=20, b=40),
        height=300,
        showlegend=False,
        bargap=0.3,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_day_chart(prediction: Dict) -> None:
    """Render single day view with range indicator."""
    covers = prediction.get("covers", 0)
    range_low = prediction.get("range_low", 0)
    range_high = prediction.get("range_high", 0)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=["Forecast"],
            y=[range_high - range_low],
            base=range_low,
            marker_color="#D8F3DC",
            name="Range",
            hoverinfo="skip",
            width=0.6,
        )
    )
    fig.add_trace(
        go.Bar(
            x=["Forecast"],
            y=[covers],
            marker_color="#2D6A4F",
            name="Predicted",
            text=[f"{covers}"],
            textposition="outside",
            textfont=dict(size=24, color="#212529"),
            width=0.4,
        )
    )
    fig.update_layout(
        title=None,
        xaxis=dict(visible=False),
        yaxis=dict(
            title="Covers",
            tickfont=dict(size=12, color="#6C757D"),
            gridcolor="#E9ECEF",
            zeroline=False,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=60, r=40, t=20, b=20),
        height=250,
        showlegend=False,
        barmode="overlay",
    )
    fig.add_annotation(
        x="Forecast",
        y=range_high,
        text=f"Range: {range_low} – {range_high}",
        showarrow=False,
        yshift=30,
        font=dict(size=12, color="#6C757D"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_month_chart_from_data(month_predictions: List[Dict], lang: str = "en") -> None:
    """Render monthly bar chart from pre-fetched predictions."""
    if not month_predictions:
        return
    days = [p.get("date", "")[-2:] for p in month_predictions]
    covers = [p.get("predicted_covers", 0) for p in month_predictions]
    colors = ["#2D6A4F"] * len(covers)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=days,
            y=covers,
            marker_color=colors,
            text=covers,
            textposition="outside",
            textfont=dict(size=10, color="#212529"),
            hovertemplate="<b>Day %{x}</b><br>%{y} covers<extra></extra>",
        )
    )
    fig.update_layout(
        title=get_text("chart.month_forecast", lang),
        xaxis=dict(title="Day", tickfont=dict(size=11, color="#495057"), showgrid=False),
        yaxis=dict(title=None, tickfont=dict(size=11, color="#6C757D"), gridcolor="#E9ECEF", zeroline=False),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=40, r=40, t=20, b=40),
        height=300,
        showlegend=False,
        bargap=0.3,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_month_chart(
    year: int, month: int, restaurant: str, service: str
) -> None:
    """Render monthly view using batch API (fetches and renders)."""
    month_predictions = get_month_predictions(year, month, restaurant, service)
    if not month_predictions:
        st.info("Monthly view: load failed or batch API not available.")
        st.markdown("*Ensure backend is running and supports `/predict/batch`*")
        return
    render_month_chart_from_data(month_predictions)
