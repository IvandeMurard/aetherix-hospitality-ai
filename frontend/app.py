"""Aetherix - Main Application"""

import streamlit as st
import json

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

# Inject CSS using JavaScript to ensure it's applied to the document head
# This approach works more reliably across different Streamlit deployments
css_escaped = json.dumps(AETHERIX_CSS)  # Escape for JavaScript
inject_css_js = f"""
<script>
(function() {{
    // Remove existing Aetherix CSS if present
    var existing = document.getElementById('aetherix-css-injected');
    if (existing) existing.remove();
    
    // Create style element and inject CSS
    var style = document.createElement('style');
    style.id = 'aetherix-css-injected';
    style.type = 'text/css';
    style.innerHTML = {css_escaped};
    
    // Inject into head immediately
    (document.head || document.getElementsByTagName('head')[0]).appendChild(style);
    
    // Also inject meta tags for cache control
    var metaCache = document.createElement('meta');
    metaCache.httpEquiv = 'Cache-Control';
    metaCache.content = 'no-cache, no-store, must-revalidate';
    (document.head || document.getElementsByTagName('head')[0]).appendChild(metaCache);
    
    var metaPragma = document.createElement('meta');
    metaPragma.httpEquiv = 'Pragma';
    metaPragma.content = 'no-cache';
    (document.head || document.getElementsByTagName('head')[0]).appendChild(metaPragma);
    
    var metaExpires = document.createElement('meta');
    metaExpires.httpEquiv = 'Expires';
    metaExpires.content = '0';
    (document.head || document.getElementsByTagName('head')[0]).appendChild(metaExpires);
}})();
</script>
"""
st.markdown(inject_css_js, unsafe_allow_html=True)

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
