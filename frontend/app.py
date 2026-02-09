"""Aetherix - Main Application"""

import streamlit as st

# MUST be first Streamlit command
st.set_page_config(
    page_title="Aetherix",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from config import AETHERIX_CSS, get_text
    from components.sidebar import render_sidebar
    from views.forecast_view import render_forecast_view
    from views.history_view import render_history_view
    from views.settings_view import render_settings_view
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

# Inject CSS directly using st.markdown - simplest and most reliable approach
# The CSS includes its own <style> and <script> tags, so we just inject it directly
st.markdown(AETHERIX_CSS, unsafe_allow_html=True)

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
