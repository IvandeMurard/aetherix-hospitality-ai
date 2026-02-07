"""Aetherix - Main Application"""

import streamlit as st

# MUST be first Streamlit command
st.set_page_config(
    page_title="Aetherix",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Meta tags pour forcer le rechargement et éviter le cache JavaScript
st.markdown("""
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
""", unsafe_allow_html=True)

from config import AETHERIX_CSS, get_text
from components.sidebar import render_sidebar
from views.forecast_view import render_forecast_view
from views.history_view import render_history_view
from views.settings_view import render_settings_view

# Inject CSS
st.markdown(AETHERIX_CSS, unsafe_allow_html=True)

# Render sidebar and get context (lang comes from context, set by sidebar selectbox)
context = render_sidebar()
lang = context.get("language", "en")

# Button to restore sidebar when it is collapsed (no server-side API; use JS to click Streamlit's toggle)
_show_menu_label = get_text("sidebar.show_menu", lang)
st.markdown(
    f"""
    <div style="
        position: fixed;
        top: 1rem;
        left: 1rem;
        z-index: 9999;
    ">
        <button type="button" onclick="
            (function() {{
                var el = document.querySelector('[data-testid=\"collapsedControl\"]') 
                    || document.querySelector('[aria-label*=\"sidebar\"]')
                    || document.querySelector('[aria-label*=\"Sidebar\"]');
                if (el) el.click();
            }})();
        " style="
            background-color: #166534;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 0.5rem 0.75rem;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
        ">{_show_menu_label}</button>
    </div>
    """,
    unsafe_allow_html=True,
)

# Route to correct view based on sidebar selection
if context["page"] == "forecast":
    render_forecast_view(context)
elif context["page"] == "history":
    render_history_view(context)
elif context["page"] == "settings":
    render_settings_view(context)
