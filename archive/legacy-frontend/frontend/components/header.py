"""Aetherix Header Component"""

import streamlit as st
from datetime import datetime, timedelta, date
from config import get_text


def _navigate_period(direction: int, view: str) -> None:
    """Navigate to previous/next period"""
    current = st.session_state.selected_date

    if view == "day":
        st.session_state.selected_date = current + timedelta(days=direction)
    elif view == "week":
        st.session_state.selected_date = current + timedelta(weeks=direction)
    else:
        # Month navigation
        if direction > 0:
            next_month = current.replace(day=28) + timedelta(days=4)
            st.session_state.selected_date = next_month.replace(day=1)
        else:
            st.session_state.selected_date = (
                current.replace(day=1) - timedelta(days=1)
            ).replace(day=1)
    
    # Mark that user has requested a forecast
    st.session_state.forecast_requested = True
    st.rerun()


def _to_datetime(d: date) -> datetime:
    """Convert date to datetime (midnight)."""
    return datetime.combine(d, datetime.min.time())


def render_header(lang: str = "en") -> dict:
    """
    Render the page header with view toggle and period selector.

    Returns:
        dict with: {
            "view": "day" | "week" | "month",
            "selected_date": datetime,
            "period_start": datetime,
            "period_end": datetime
        }
    """
    # Initialize session state for date
    if "selected_date" not in st.session_state:
        st.session_state.selected_date = datetime.now()

    col1, col2 = st.columns([1, 2])

    with col1:
        # View toggle - mark forecast requested when view changes
        previous_view = st.session_state.get("previous_view")
        view = st.radio(
            label="View",
            options=["day", "week", "month"],
            format_func=lambda x: get_text(f"header.{x}", lang),
            horizontal=True,
            label_visibility="collapsed",
            key="view_toggle",
        )
        # Check if view changed and mark forecast requested
        if previous_view is not None and previous_view != view:
            st.session_state.forecast_requested = True
        st.session_state.previous_view = view

    with col2:
        # Period selector
        subcol1, subcol2, subcol3, subcol4 = st.columns([1, 3, 1, 1])

        with subcol1:
            if st.button(get_text("header.previous", lang), key="prev_period"):
                _navigate_period(-1, view)

        with subcol2:
            current = st.session_state.selected_date
            current_date = current.date() if hasattr(current, "date") else current

            if view == "day":
                picker = st.date_input(
                    get_text("header.select_date", lang),
                    value=current_date,
                    label_visibility="collapsed",
                    key="date_picker_day",
                )
                if picker != current_date:
                    st.session_state.selected_date = _to_datetime(picker)
                    st.session_state.forecast_requested = True
                    st.rerun()
            elif view == "week":
                week_start = current - timedelta(days=current.weekday())
                picker = st.date_input(
                    get_text("header.select_date", lang),
                    value=week_start.date() if hasattr(week_start, "date") else week_start,
                    label_visibility="collapsed",
                    key="date_picker_week",
                )
                new_week_start = picker - timedelta(days=picker.weekday())
                if new_week_start != (week_start.date() if hasattr(week_start, "date") else week_start):
                    st.session_state.selected_date = _to_datetime(new_week_start)
                    st.session_state.forecast_requested = True
                    st.rerun()
            else:
                # Month view: month + year selectboxes
                months_en = [
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December",
                ]
                months_fr = [
                    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
                ]
                months = months_fr if lang == "fr" else months_en
                current_year = date.today().year
                years = list(range(current_year - 2, current_year + 3))
                if current.year not in years:
                    years.append(current.year)
                    years.sort()
                year_idx = years.index(current.year)
                month_1 = current.month - 1

                mc, yc = st.columns(2)
                with mc:
                    sel_month = st.selectbox(
                        "",
                        months,
                        index=month_1,
                        label_visibility="collapsed",
                        key="month_picker",
                    )
                with yc:
                    sel_year = st.selectbox(
                        "",
                        years,
                        index=year_idx,
                        label_visibility="collapsed",
                        key="year_picker",
                    )
                new_month = months.index(sel_month) + 1
                if new_month != current.month or sel_year != current.year:
                    st.session_state.selected_date = _to_datetime(
                        date(sel_year, new_month, 1)
                    )
                    st.session_state.forecast_requested = True
                    st.rerun()

        with subcol3:
            if st.button(get_text("header.next", lang), key="next_period"):
                _navigate_period(1, view)

        with subcol4:
            if st.button(get_text("header.today", lang), key="today_btn"):
                st.session_state.selected_date = datetime.now()
                st.session_state.forecast_requested = True
                st.rerun()

    # Calculate period bounds
    if view == "day":
        period_start = st.session_state.selected_date.replace(
            hour=0, minute=0, second=0
        )
        period_end = period_start + timedelta(days=1)
    elif view == "week":
        period_start = st.session_state.selected_date - timedelta(
            days=st.session_state.selected_date.weekday()
        )
        period_end = period_start + timedelta(days=7)
    else:
        period_start = st.session_state.selected_date.replace(day=1)
        next_month = period_start.replace(day=28) + timedelta(days=4)
        period_end = next_month.replace(day=1)

    return {
        "view": view,
        "selected_date": st.session_state.selected_date,
        "period_start": period_start,
        "period_end": period_end,
    }
