"""Aetherix Sidebar Component"""

import os
from typing import Optional

import streamlit as st
from config import get_text


def render_sidebar(lang: Optional[str] = None) -> dict:
    """
    Render the Aetherix sidebar with pure white text and button-based nav.

    Returns:
        dict with: page, restaurant, service, language
    """
    if lang is None:
        lang = st.session_state.get("lang_select", "en")
    if "current_page" not in st.session_state:
        st.session_state.current_page = "forecast"

    with st.sidebar:
        # ===== BRAND (FIRST, LARGE) =====
        st.markdown(
            """
            <div style="margin-bottom: 2rem;">
                <h1 style="
                    color: #FFFFFF;
                    font-size: 2rem;
                    font-weight: 700;
                    margin: 0;
                    padding: 0;
                    letter-spacing: -0.02em;
                ">Aetherix</h1>
                <p style="
                    color: #d1d5db;
                    font-size: 0.875rem;
                    margin: 0.25rem 0 0 0;
                    font-weight: 400;
                ">Intelligent forecasting</p>
            </div>
        """,
            unsafe_allow_html=True,
        )

        # ===== NAVIGATION =====
        st.markdown(
            """
            <p style="
                color: #ffffff;
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 0.5rem;
            ">Navigation</p>
        """,
            unsafe_allow_html=True,
        )

        nav_items = [
            ("forecast", get_text("nav.forecast", lang), "📊"),
            ("history", get_text("nav.history", lang), "📈"),
            ("settings", get_text("nav.settings", lang), "⚙️"),
        ]

        for page_id, label, _icon in nav_items:
            is_active = st.session_state.current_page == page_id
            if is_active:
                st.markdown(
                    f"""
                    <div style="
                        background-color: rgba(255,255,255,0.15);
                        border-radius: 6px;
                        padding: 0.6rem 0.75rem;
                        margin-bottom: 0.25rem;
                    ">
                        <span style="color: #FFFFFF; font-weight: 500;">
                            {label}
                        </span>
                    </div>
                """,
                    unsafe_allow_html=True,
                )
            else:
                if st.button(label, key=f"nav_{page_id}", use_container_width=True):
                    st.session_state.current_page = page_id
                    st.rerun()

        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        st.divider()

        # ===== CONTEXT =====
        st.markdown(
            """
            <p style="
                color: #ffffff;
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 0.5rem;
            ">Context</p>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <p style="color: #FFFFFF; font-size: 0.75rem; margin-bottom: 0.25rem;">
                Restaurant
            </p>
        """,
            unsafe_allow_html=True,
        )
        restaurant = st.selectbox(
            label="Restaurant",
            options=["Main Restaurant", "Pool Bar", "Room Service"],
            label_visibility="collapsed",
            key="restaurant_select",
        )

        st.markdown(
            """
            <p style="color: #FFFFFF; font-size: 0.75rem; margin-bottom: 0.25rem; margin-top: 0.75rem;">
                Service
            </p>
        """,
            unsafe_allow_html=True,
        )
        service = st.selectbox(
            label="Service",
            options=["Breakfast", "Lunch", "Dinner"],
            index=2,
            label_visibility="collapsed",
            key="service_select",
        )

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        st.divider()

        # ===== DATA STATUS =====
        st.markdown(
            """
            <p style="
                color: #ffffff;
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 0.75rem;
            ">Data</p>
            <div style="color: #ffffff; font-size: 0.875rem; line-height: 1.8;">
                <div><span style="color: #d1d5db;">Patterns:</span> 495</div>
                <div><span style="color: #d1d5db;">Period:</span> 2015-2017</div>
                <div><span style="color: #d1d5db;">Updated:</span> 2h ago</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        st.divider()

        # ===== COMING SOON =====
        st.markdown(
            """
            <p style="
                color: #ffffff;
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 0.75rem;
            ">Coming Soon</p>
            <div style="
                color: #a7f3d0;
                font-size: 0.85rem;
                font-style: italic;
                line-height: 1.8;
            ">
                ◇ PMS Integration<br>
                ◇ Staff Planner<br>
                ◇ Inventory<br>
                ◇ Alerts
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        st.divider()

        # ===== FOOTER =====
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                """
                <a href="#" style="
                    color: #ffffff;
                    text-decoration: none;
                    font-size: 0.875rem;
                ">? Help</a>
            """,
                unsafe_allow_html=True,
            )

        with col2:
            language = st.selectbox(
                label="Language",
                options=["en", "fr"],
                format_func=lambda x: "EN" if x == "en" else "FR",
                label_visibility="collapsed",
                key="lang_select",
            )

        # Build id (set in Dockerfile) to confirm deployed version
        build_id = os.environ.get("AETHERIX_BUILD", "dev")
        st.caption(f"Build {build_id}")

    return {
        "page": st.session_state.current_page,
        "restaurant": restaurant,
        "service": service,
        "language": language,
    }
