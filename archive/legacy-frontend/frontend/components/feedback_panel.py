"""Feedback Panel Component — Pre-service and Post-service feedback."""

import streamlit as st
import requests
from datetime import datetime
from typing import Optional

from config import get_text, API_BASE


def _restaurant_to_id(restaurant: str) -> str:
    """Map restaurant display name to backend ID."""
    restaurant_map = {
        "Main Restaurant": "hotel_main",
        "Pool Bar": "pool_bar",
        "Room Service": "room_service",
    }
    return restaurant_map.get(restaurant, restaurant.lower().replace(" ", "_"))


def render_feedback_panel(
    prediction_id: Optional[str],
    predicted_covers: int,
    date: datetime,
    service: str,
    restaurant: str,
    lang: str = "en",
    view: str = "day",
) -> None:
    """
    Render feedback panel with pre-service and post-service options.

    Pre-service: "Does X covers look right?" → Yes / Higher / Lower
    Post-service: "How did it go?" → Actual covers input

    Only shown for day view with a valid prediction_id (UUID, not pred_xxx).
    """
    if view != "day":
        return

    if not prediction_id:
        msg = get_text("feedback.no_prediction", lang)
    elif prediction_id.startswith("pred_"):
        msg = get_text("feedback.storage_failed", lang)
    else:
        msg = None

    if msg:
        st.markdown(
            f"""
            <div style="
                background-color: #F8F9FA;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 1.5rem;
                text-align: center;
                color: #6C757D;
            ">
                {msg}
            </div>
        """,
            unsafe_allow_html=True,
        )
        return

    now = datetime.now()
    service_date = date.date() if hasattr(date, "date") else date
    is_past = service_date < now.date() or (
        service_date == now.date() and _service_has_ended(service)
    )

    if is_past:
        _render_post_service_feedback(
            prediction_id, predicted_covers, date, service, restaurant, lang
        )
    else:
        _render_pre_service_feedback(
            prediction_id, predicted_covers, date, service, restaurant, lang
        )


def _render_pre_service_feedback(
    prediction_id: str,
    predicted_covers: int,
    date: datetime,
    service: str,
    restaurant: str,
    lang: str,
) -> None:
    """Pre-service: Validate prediction before service starts."""
    st.markdown(
        f"""
        <h4 style="color: #212529; margin: 0 0 0.5rem 0; font-size: 1rem;">
            {get_text("feedback.pre_title", lang)}
        </h4>
        <p style="color: #495057; margin: 0 0 1rem 0; font-size: 0.9rem;">
            {get_text("feedback.pre_question", lang).format(
                covers=predicted_covers,
                service=service.lower(),
                day=date.strftime("%A") if hasattr(date, "strftime") else str(date),
            )}
        </p>
    """,
        unsafe_allow_html=True,
    )

    feedback_key = f"feedback_state_{prediction_id}"
    if feedback_key not in st.session_state:
        st.session_state[feedback_key] = {"status": None, "submitted": False}

    if st.session_state[feedback_key].get("submitted"):
        st.success(get_text("feedback.success_pre", lang))
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            f"✓ {get_text('feedback.accurate', lang)}",
            key=f"btn_accurate_{prediction_id}",
            use_container_width=True,
        ):
            _submit_pre_service_feedback(
                prediction_id, "accurate", None, restaurant, lang, feedback_key
            )

    with col2:
        if st.button(
            f"↑ {get_text('feedback.higher', lang)}",
            key=f"btn_higher_{prediction_id}",
            use_container_width=True,
        ):
            st.session_state[feedback_key]["status"] = "higher"
            st.rerun()

    with col3:
        if st.button(
            f"↓ {get_text('feedback.lower', lang)}",
            key=f"btn_lower_{prediction_id}",
            use_container_width=True,
        ):
            st.session_state[feedback_key]["status"] = "lower"
            st.rerun()

    if st.session_state[feedback_key].get("status") in ["higher", "lower"]:
        st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

        adjustment = (
            15 if st.session_state[feedback_key]["status"] == "higher" else -15
        )

        expected = st.number_input(
            get_text("feedback.expected_covers", lang),
            min_value=0,
            value=max(0, predicted_covers + adjustment),
            key=f"expected_{prediction_id}",
        )

        reason = st.text_input(
            get_text("feedback.reason_optional", lang),
            placeholder=get_text("feedback.reason_placeholder", lang),
            key=f"reason_{prediction_id}",
        )

        if st.button(
            get_text("feedback.confirm", lang),
            key=f"confirm_{prediction_id}",
            type="primary",
        ):
            _submit_pre_service_feedback(
                prediction_id,
                st.session_state[feedback_key]["status"],
                {"expected_covers": expected, "reason": reason} if reason else {"expected_covers": expected},
                restaurant,
                lang,
                feedback_key,
            )


def _render_post_service_feedback(
    prediction_id: str,
    predicted_covers: int,
    date: datetime,
    service: str,
    restaurant: str,
    lang: str,
) -> None:
    """Post-service: Record actual results."""
    existing_list = _get_existing_feedback(prediction_id)
    existing = None
    if existing_list and len(existing_list) > 0:
        for fb in existing_list:
            if fb.get("actual_covers") is not None:
                existing = fb
                break

    if existing and existing.get("actual_covers") is not None:
        actual = existing["actual_covers"]
        diff = actual - predicted_covers
        accuracy = (
            max(0, 100 - abs(diff / predicted_covers * 100))
            if predicted_covers > 0
            else 0
        )

        if accuracy >= 90:
            acc_color = "#40916C"
        elif accuracy >= 80:
            acc_color = "#E9C46A"
        else:
            acc_color = "#E76F51"

        st.markdown(
            f"""
            <h4 style="color: #212529; margin: 0 0 1rem 0; font-size: 1rem;">
                {get_text("feedback.submitted_title", lang)}
            </h4>
            <div style="display: flex; gap: 2rem;">
                <div>
                    <p style="color: #6C757D; font-size: 0.7rem; margin: 0; text-transform: uppercase;">
                        {get_text("feedback.predicted", lang)}
                    </p>
                    <p style="color: #212529; font-size: 1.5rem; font-weight: 600; margin: 0.25rem 0 0 0;">
                        {predicted_covers}
                    </p>
                </div>
                <div>
                    <p style="color: #6C757D; font-size: 0.7rem; margin: 0; text-transform: uppercase;">
                        {get_text("feedback.actual", lang)}
                    </p>
                    <p style="color: #212529; font-size: 1.5rem; font-weight: 600; margin: 0.25rem 0 0 0;">
                        {actual}
                    </p>
                </div>
                <div>
                    <p style="color: #6C757D; font-size: 0.7rem; margin: 0; text-transform: uppercase;">
                        {get_text("feedback.accuracy", lang)}
                    </p>
                    <p style="color: {acc_color}; font-size: 1.5rem; font-weight: 600; margin: 0.25rem 0 0 0;">
                        {accuracy:.0f}%
                    </p>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <h4 style="color: #212529; margin: 0 0 0.5rem 0; font-size: 1rem;">
            {get_text("feedback.post_title", lang)}
        </h4>
        <p style="color: #495057; margin: 0 0 1rem 0; font-size: 0.9rem;">
            {get_text("feedback.post_question", lang)}
        </p>
    """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        actual_covers = st.number_input(
            get_text("feedback.actual_covers", lang),
            min_value=0,
            value=predicted_covers,
            key=f"actual_{prediction_id}",
        )

    with col2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button(
            get_text("feedback.submit", lang),
            key=f"submit_{prediction_id}",
            type="primary",
            use_container_width=True,
        ):
            _submit_post_service_feedback(
                prediction_id, actual_covers, restaurant, lang
            )


def _submit_pre_service_feedback(
    prediction_id: str,
    feedback_type: str,
    data: Optional[dict],
    restaurant: str,
    lang: str,
    state_key: str,
) -> None:
    """Submit pre-service feedback to API. Backend expects FeedbackCreate schema."""
    try:
        payload = {
            "prediction_id": prediction_id,
            "restaurant_id": _restaurant_to_id(restaurant),
            "feedback_type": "pre_service",
            "pre_validation": feedback_type,
            "pre_reasons": [data["reason"]] if data and data.get("reason") else [],
            "pre_adjusted_covers": (
                data.get("expected_covers") if data and feedback_type != "accurate" else None
            ),
        }

        response = requests.post(
            f"{API_BASE}/api/feedback",
            json=payload,
            timeout=10,
        )

        if response.status_code in [200, 201]:
            st.session_state[state_key]["submitted"] = True
            st.rerun()
        else:
            st.error(
                f"{get_text('feedback.error', lang)}: {response.status_code}"
            )

    except requests.exceptions.RequestException:
        st.error(f"{get_text('feedback.error', lang)}: Connection failed")


def _submit_post_service_feedback(
    prediction_id: str,
    actual_covers: int,
    restaurant: str,
    lang: str,
) -> None:
    """Submit post-service feedback to API."""
    try:
        payload = {
            "prediction_id": prediction_id,
            "restaurant_id": _restaurant_to_id(restaurant),
            "feedback_type": "post_service",
            "actual_covers": actual_covers,
        }

        response = requests.post(
            f"{API_BASE}/api/feedback",
            json=payload,
            timeout=10,
        )

        if response.status_code in [200, 201]:
            st.success(get_text("feedback.success_post", lang))
            st.rerun()
        else:
            st.error(
                f"{get_text('feedback.error', lang)}: {response.status_code}"
            )

    except requests.exceptions.RequestException:
        st.error(f"{get_text('feedback.error', lang)}: Connection failed")


def _get_existing_feedback(prediction_id: str) -> Optional[list]:
    """Check if feedback already exists. GET /api/feedback/prediction/{id} returns list."""
    try:
        response = requests.get(
            f"{API_BASE}/api/feedback/prediction/{prediction_id}",
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def _service_has_ended(service: str) -> bool:
    """Check if a service has ended based on typical times."""
    hour = datetime.now().hour
    service_end_times = {
        "breakfast": 11,
        "lunch": 15,
        "dinner": 23,
    }
    return hour >= service_end_times.get(service.lower(), 23)
