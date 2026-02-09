"""Aetherix - Main Application"""

import streamlit as st
import time

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

try:
    from config import AETHERIX_CSS, get_text
    from components.sidebar import render_sidebar
    from views.forecast_view import render_forecast_view
    from views.history_view import render_history_view
    from views.settings_view import render_settings_view
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

# Inject CSS early with cache-busting to avoid BodyStreamBuffer errors
# Add version/timestamp to force browser reload and avoid caching issues
css_version = int(time.time())  # Cache-busting timestamp
css_with_cache_bust = AETHERIX_CSS.replace('</style>', f'</style>\n<!-- CSS Version: {css_version} -->')
st.markdown(css_with_cache_bust, unsafe_allow_html=True)

# Render sidebar and get context (lang comes from context, set by sidebar selectbox)
context = render_sidebar()
lang = context.get("language", "en")

# Route to correct view based on sidebar selection
if context["page"] == "forecast":
    render_forecast_view(context)
elif context["page"] == "history":
    render_history_view(context)
elif context["page"] == "settings":
    render_settings_view(context)
