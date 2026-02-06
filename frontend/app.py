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

from config import AETHERIX_CSS
from components.sidebar import render_sidebar
from views.forecast_view import render_forecast_view
from views.history_view import render_history_view
from views.settings_view import render_settings_view

# Inject CSS
st.markdown(AETHERIX_CSS, unsafe_allow_html=True)

# Render sidebar and get context (lang comes from context, set by sidebar selectbox)
context = render_sidebar()

# Route to correct view based on sidebar selection
if context["page"] == "forecast":
    render_forecast_view(context)
elif context["page"] == "history":
    render_history_view(context)
elif context["page"] == "settings":
    render_settings_view(context)
