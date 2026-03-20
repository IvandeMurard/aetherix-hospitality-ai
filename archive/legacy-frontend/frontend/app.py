"""Aetherix - Main Application"""

import streamlit as st
import requests

# MUST be first Streamlit command
st.set_page_config(
    page_title="Aetherix",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from config import AETHERIX_CSS, get_text, API_BASE
    from components.sidebar import render_sidebar
    from views.forecast_view import render_forecast_view
    from views.history_view import render_history_view
    from views.settings_view import render_settings_view
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

# Test API connection at startup (only once per session)
if "api_connection_tested" not in st.session_state:
    st.session_state.api_connection_tested = True
    try:
        # Quick health check with headers
        headers = {
            "User-Agent": "Aetherix-Streamlit-Cloud/1.0",
            "Origin": "https://aetherix.streamlit.app",
            "Referer": "https://aetherix.streamlit.app/",
        }
        response = requests.get(f"{API_BASE}/health", headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"[STARTUP] API connection successful: {API_BASE}/health")
            print(f"[STARTUP] Response: {response.text[:200]}")
        else:
            print(f"[STARTUP] WARNING: API health check returned {response.status_code} for {API_BASE}")
            print(f"[STARTUP] Response headers: {dict(response.headers)}")
            print(f"[STARTUP] Response text: {response.text[:500]}")
    except requests.exceptions.RequestException as e:
        print(f"[STARTUP] WARNING: Could not connect to API at {API_BASE}: {e}")
        print(f"[STARTUP] This may be normal if the API is starting up or if you're running locally without the backend")

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
