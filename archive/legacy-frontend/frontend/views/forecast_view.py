"""Forecast view - predictions, KPIs, timeline chart."""

import streamlit as st
import requests
from datetime import datetime, timedelta
from typing import Optional
import time

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
    """Render KPI cards for day view (single day values) with Perplexity-style design."""
    col1, col2, col3, col4 = st.columns(4)
    
    # Perplexity-style card wrapper HTML
    card_style = """
    <div style="
        background-color: white;
        border-radius: 8px;
        border: 1px solid #E9ECEF;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        padding: 1.25rem;
        height: 100%;
    ">
    """
    
    if prediction:
        covers = prediction.get("predicted_covers", "—")
        accuracy_metrics = prediction.get("accuracy_metrics", {})
        interval = accuracy_metrics.get("prediction_interval")
        range_text = f"{interval[0]} – {interval[1]}" if interval and len(interval) == 2 else "—"
        confidence = prediction.get("confidence", 0)
        confidence_label = _confidence_label(confidence, lang)
        servers = _parse_staff(prediction.get("staff_recommendation", {}))
        
        # Determine confidence color (semantic colors)
        if confidence >= 0.85:
            conf_color = "#40916C"  # Green for high confidence
        elif confidence >= 0.7:
            conf_color = "#E9C46A"  # Yellow/Orange for medium
        else:
            conf_color = "#E76F51"  # Red for low
        
        with col1:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(
                get_text("kpi.covers", lang).upper(),
                str(covers) if covers != "—" else "—",
                delta=None,
            )
        with col2:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(
                get_text("kpi.range", lang).upper(),
                range_text,
                delta=None,
            )
        with col3:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(
                get_text("kpi.staff", lang).upper(),
                f"{servers} servers" if servers != "—" else "—",
                delta=None,
            )
        with col4:
            st.markdown(card_style, unsafe_allow_html=True)
            # Custom metric with color for confidence
            st.markdown(
                f"""
                <div style="margin-bottom: 0.5rem;">
                    <p style="
                        color: #6C757D;
                        font-size: 0.7rem;
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                        margin: 0;
                        font-weight: 500;
                    ">{get_text("kpi.confidence", lang).upper()}</p>
                </div>
                <div>
                    <p style="
                        color: {conf_color};
                        font-size: 1.75rem;
                        font-weight: 600;
                        margin: 0;
                    ">{confidence_label}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        with col1:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.covers", lang).upper(), "—", delta=None)
        with col2:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.range", lang).upper(), "—", delta=None)
        with col3:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.staff", lang).upper(), "—", delta=None)
        with col4:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.confidence", lang).upper(), "—", delta=None)
        st.warning(f"Could not load prediction for {date_display}")


def _render_kpi_cards_week(lang: str, week_predictions: list) -> None:
    """Render KPI cards for week view (totals, peak, avg) with Perplexity-style design."""
    col1, col2, col3, col4 = st.columns(4)
    
    # Perplexity-style card wrapper
    card_style = """
    <div style="
        background-color: white;
        border-radius: 8px;
        border: 1px solid #E9ECEF;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        padding: 1.25rem;
        height: 100%;
    ">
    """
    
    if not week_predictions:
        for col in [col1, col2, col3, col4]:
            with col:
                st.markdown(card_style, unsafe_allow_html=True)
                st.metric("—", "—", delta=None)
        return
    
    total = sum(p.get("covers", 0) for p in week_predictions)
    avg_covers = int(total / 7)
    peak_day = max(week_predictions, key=lambda x: x.get("covers", 0))
    confidences = [p.get("confidence", 0) for p in week_predictions]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    
    # Determine confidence color
    if avg_conf >= 0.85:
        conf_color = "#40916C"
    elif avg_conf >= 0.7:
        conf_color = "#E9C46A"
    else:
        conf_color = "#E76F51"
    
    with col1:
        st.markdown(card_style, unsafe_allow_html=True)
        st.metric(get_text("kpi.total_week", lang), f"{total} covers", delta=None)
    with col2:
        st.markdown(card_style, unsafe_allow_html=True)
        st.metric(get_text("kpi.daily_avg", lang), f"{avg_covers} covers", delta=None)
    with col3:
        st.markdown(card_style, unsafe_allow_html=True)
        st.metric(
            get_text("kpi.peak_day", lang),
            f"{peak_day.get('day', '—')} ({peak_day.get('covers', 0)})",
            delta=None,
        )
    with col4:
        st.markdown(card_style, unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="margin-bottom: 0.5rem;">
                <p style="
                    color: #6C757D;
                    font-size: 0.7rem;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    margin: 0;
                    font-weight: 500;
                ">{get_text("kpi.avg_confidence", lang).upper()}</p>
            </div>
            <div>
                <p style="
                    color: {conf_color};
                    font-size: 1.75rem;
                    font-weight: 600;
                    margin: 0;
                ">{_confidence_label(avg_conf, lang)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_kpi_cards_month(
    lang: str, month_predictions: Optional[list] = None
) -> None:
    """Render KPI cards for month view with Perplexity-style design."""
    col1, col2, col3, col4 = st.columns(4)
    
    # Perplexity-style card wrapper
    card_style = """
    <div style="
        background-color: white;
        border-radius: 8px;
        border: 1px solid #E9ECEF;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        padding: 1.25rem;
        height: 100%;
    ">
    """
    
    if month_predictions:
        total = sum(p.get("predicted_covers", 0) for p in month_predictions)
        n = len(month_predictions)
        avg = int(total / n) if n else 0
        peak = max(month_predictions, key=lambda x: x.get("predicted_covers", 0))
        confidences = [p.get("confidence", 0) for p in month_predictions]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        
        # Determine confidence color
        if avg_conf >= 0.85:
            conf_color = "#40916C"
        elif avg_conf >= 0.7:
            conf_color = "#E9C46A"
        else:
            conf_color = "#E76F51"
        
        with col1:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.total_month", lang), f"{total} covers", delta=None)
        with col2:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.daily_avg", lang), f"{avg} covers", delta=None)
        with col3:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(
                get_text("kpi.peak_day", lang),
                f"Day {peak.get('date', '')[-2:]} ({peak.get('predicted_covers', 0)})",
                delta=None,
            )
        with col4:
            st.markdown(card_style, unsafe_allow_html=True)
            st.markdown(
                f"""
                <div style="margin-bottom: 0.5rem;">
                    <p style="
                        color: #6C757D;
                        font-size: 0.7rem;
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                        margin: 0;
                        font-weight: 500;
                    ">{get_text("kpi.avg_confidence", lang).upper()}</p>
                </div>
                <div>
                    <p style="
                        color: {conf_color};
                        font-size: 1.75rem;
                        font-weight: 600;
                        margin: 0;
                    ">{_confidence_label(avg_conf, lang)}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        with col1:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.total_month", lang), "…", delta=None)
        with col2:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.daily_avg", lang), "…", delta=None)
        with col3:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.peak_day", lang), "…", delta=None)
        with col4:
            st.markdown(card_style, unsafe_allow_html=True)
            st.metric(get_text("kpi.confidence", lang), "…", delta=None)


def _make_api_request_with_retry(
    url: str,
    json_data: dict,
    max_retries: int = 3,
    timeout: int = 90,
    retry_delay: float = 2.0,
) -> Optional[requests.Response]:
    """
    Make API request with retry logic and explicit headers.
    Handles 403 errors with automatic retry.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Aetherix-Streamlit-Cloud/1.0",
        "Origin": "https://aetherix.streamlit.app",
        "Referer": "https://aetherix.streamlit.app/",
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                json=json_data,
                headers=headers,
                timeout=timeout,
            )
            
            # Success
            if response.status_code == 200:
                return response
            
            # 403 Forbidden - retry with delay
            if response.status_code == 403:
                if attempt < max_retries - 1:
                    error_msg = (
                        f"API returned 403 (Forbidden). "
                        f"Retrying ({attempt + 1}/{max_retries})..."
                    )
                    st.warning(error_msg)
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    # Enhanced error message with diagnostic information
                    response_text = response.text[:500] if response.text else "(empty response)"
                    all_headers = "\n".join(f"{k}: {v}" for k, v in response.headers.items())
                    
                    error_details = f"""
**API Error 403 - Forbidden**

**Request Details:**
- URL: `{url}`
- Method: POST
- Attempts: {max_retries}
- Headers sent: `{headers}`

**Response Details:**
- Status: {response.status_code}
- Response text: `{response_text}`
- Content-Type: `{response.headers.get('Content-Type', 'not-set')}`

**All Response Headers:**
```
{all_headers}
```

**Possible Causes:**
1. HuggingFace Spaces may be blocking POST requests from Streamlit Cloud
2. HuggingFace Spaces backend may be sleeping (try restarting the space)
3. Proxy/nginx configuration issue in HuggingFace Space
4. Backend not started or crashed
5. Missing environment variables on HuggingFace Spaces

**Diagnostic Steps:**
1. Check if backend is accessible: `{API_BASE}/health`
2. Check diagnostic endpoint: `{API_BASE}/diagnostic`
3. Verify HuggingFace Space is running: https://huggingface.co/spaces/IvandeMurard/fb-agent-api
4. Check HuggingFace Space logs for errors
5. Try restarting the HuggingFace Space
6. Test POST request directly: `curl -X POST {API_BASE}/predict -H "Content-Type: application/json" -d '{{"restaurant_id": "hotel_main", "service_date": "2026-02-09", "service_type": "dinner"}}'`
                    """
                    st.error(error_details)
                    return response
            
            # Other HTTP errors
            if response.status_code >= 400:
                error_details = f"""
**API Error {response.status_code}**

**Request Details:**
- URL: `{url}`
- Method: POST

**Response:**
```
{response.text[:500]}
```

**Diagnostic:**
- Check backend health: `{API_BASE}/health`
- Check diagnostic: `{API_BASE}/diagnostic`
                """
                st.warning(error_details)
                return response
                
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                st.warning(
                    f"Connection error. Retrying ({attempt + 1}/{max_retries})..."
                )
                time.sleep(retry_delay * (attempt + 1))
                continue
            else:
                st.error(
                    "Unable to connect to backend API after multiple attempts. "
                    "Please ensure the backend is running and accessible."
                )
                return None
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                st.warning(
                    f"Request timed out. Retrying ({attempt + 1}/{max_retries})..."
                )
                time.sleep(retry_delay * (attempt + 1))
                continue
            else:
                st.error(
                    f"Backend API request timed out after {max_retries} attempts. "
                    "The first prediction can take up to 90 seconds "
                    "(embedding + Qdrant + Claude). "
                    "Please try again or check backend logs."
                )
                return None
                
        except Exception as e:
            if attempt < max_retries - 1:
                st.warning(f"Error: {e}. Retrying ({attempt + 1}/{max_retries})...")
                time.sleep(retry_delay * (attempt + 1))
                continue
            else:
                st.error(f"Prediction error after {max_retries} attempts: {e}")
                return None
    
    return None


def fetch_prediction(date: datetime, restaurant: str, service: str) -> dict:
    """Fetch prediction from backend API with improved error handling and retry logic."""
    restaurant_map = {
        "Main Restaurant": "hotel_main",
        "Pool Bar": "pool_bar",
        "Room Service": "room_service",
    }
    restaurant_id = restaurant_map.get(
        restaurant, restaurant.lower().replace(" ", "_")
    )
    
    json_data = {
        "service_date": date.strftime("%Y-%m-%d"),
        "service_type": service.lower(),
        "restaurant_id": restaurant_id,
    }
    
    response = _make_api_request_with_retry(
        url=f"{API_BASE}/predict",
        json_data=json_data,
        max_retries=3,
        timeout=90,
    )
    
    if response and response.status_code == 200:
        try:
            return response.json()
        except Exception as e:
            st.error(f"Failed to parse API response: {e}")
            return None
    
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

    # Initialize session state variables if not set
    if "forecast_requested" not in st.session_state:
        st.session_state.forecast_requested = False
    if "view_toggle" not in st.session_state:
        st.session_state.view_toggle = "day"

    # Cache invalidation: clear caches when restaurant or service changes
    cache_context = f"{context['restaurant']}_{context['service']}"
    if "last_cache_context" not in st.session_state:
        st.session_state.last_cache_context = cache_context

    if st.session_state.last_cache_context != cache_context:
        for key in ["prediction_cache", "week_predictions_cache"]:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.last_cache_context = cache_context

    # Perplexity-style hierarchy: Title → KPIs → Graphs → Factors → Feedback
    
    # 1. HEADER (Title + Navigation)
    header = render_header(lang=lang)
    
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

    # Fetch week/month data if needed
    if view == "week":
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
    elif view == "month":
        with st.spinner(get_text("loading.month", lang)):
            month_predictions = get_month_predictions(
                selected_date.year,
                selected_date.month,
                context["restaurant"],
                context["service"],
            )

    # 2. TITLE SECTION (Perplexity-style: Clear title for context)
    st.markdown("<br>", unsafe_allow_html=True)
    if view == "day":
        title_text = date_display
    elif view == "week":
        week_start = selected_date - timedelta(days=selected_date.weekday())
        week_end = week_start + timedelta(days=6)
        title_text = f"{week_start.strftime('%B %d')} – {week_end.strftime('%B %d, %Y')}"
    else:
        title_text = selected_date.strftime("%B %Y")
    
    st.markdown(
        f"""
        <h2 style="
            color: #212529;
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
            font-family: 'Inter', sans-serif;
        ">{title_text}</h2>
        """,
        unsafe_allow_html=True,
    )

    # 3. KPI CARDS (Perplexity-style: Key figures prominently displayed)
    if view == "day":
        _render_kpi_cards_day(lang, prediction, date_display)
    elif view == "week":
        _render_kpi_cards_week(lang, week_predictions or [])
    else:
        _render_kpi_cards_month(lang, month_predictions)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. GRAPHS (Perplexity-style: Visualizations after key figures)
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

    # 5. FACTORS PANEL (Perplexity-style: Expandable details after main content)
    render_factors_panel(
        prediction,
        view,
        lang,
        week_predictions=week_predictions,
        month_predictions=month_predictions,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # 6. FEEDBACK PANEL (Perplexity-style: Action panel at the end)
    render_feedback_panel(
        prediction_id=(prediction or {}).get("prediction_id"),
        predicted_covers=prediction.get("predicted_covers", 0) if prediction else 0,
        date=header["selected_date"],
        service=context["service"],
        restaurant=context["restaurant"],
        lang=lang,
        view=view,
    )
