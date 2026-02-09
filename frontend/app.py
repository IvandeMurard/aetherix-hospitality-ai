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

try:
    from config import AETHERIX_CSS, get_text
    from components.sidebar import render_sidebar
    from views.forecast_view import render_forecast_view
    from views.history_view import render_history_view
    from views.settings_view import render_settings_view
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

# Inject CSS
st.markdown(AETHERIX_CSS, unsafe_allow_html=True)

# Render sidebar and get context (lang comes from context, set by sidebar selectbox)
context = render_sidebar()
lang = context.get("language", "en")

# Button to restore sidebar when it is collapsed (no server-side API; use JS to click Streamlit's toggle)
_show_menu_label = get_text("sidebar.show_menu", lang)

# Use st.markdown instead of components.html to avoid BodyStreamBuffer errors
_sidebar_toggle_html = f"""
<div id="aetherix-menu-wrap" style="position: fixed; top: 0.75rem; right: 1rem; z-index: 99999; display: block !important;">
    <button id="aetherix-menu-btn" type="button" onclick="window.aetherixToggleSidebar()" style="background-color: #166534; color: white; border: none; border-radius: 6px; padding: 0.5rem 0.75rem; font-size: 0.875rem; font-weight: 500; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.15);">{_show_menu_label}</button>
</div>
<script>
(function() {{
    function getSidebar() {{
        return document.querySelector('[data-testid="stSidebar"]') || document.querySelector('section.stSidebar');
    }}
    
    function toggleSidebar() {{
        var sidebar = getSidebar();
        if (!sidebar) {{
            console.warn('Sidebar not found');
            return;
        }}
        
        // Try native toggle button first
        var nativeToggle = document.querySelector('[data-testid="collapsedControl"]') 
            || document.querySelector('button[aria-label*="sidebar" i]')
            || document.querySelector('button[aria-label*="Sidebar"]');
        
        if (nativeToggle) {{
            nativeToggle.click();
            return;
        }}
        
        // Direct manipulation fallback
        var currentState = sidebar.getAttribute('aria-expanded');
        var isCollapsed = currentState === 'false';
        
        sidebar.setAttribute('aria-expanded', isCollapsed ? 'true' : 'false');
        
        if (isCollapsed) {{
            sidebar.style.transform = '';
        }} else {{
            var width = sidebar.offsetWidth || 300;
            sidebar.style.transform = 'translateX(-' + width + 'px)';
        }}
        
        window.dispatchEvent(new Event('resize'));
    }}
    
    // Expose globally
    window.aetherixToggleSidebar = toggleSidebar;
}})();
</script>
"""

st.markdown(_sidebar_toggle_html, unsafe_allow_html=True)

# Route to correct view based on sidebar selection
if context["page"] == "forecast":
    render_forecast_view(context)
elif context["page"] == "history":
    render_history_view(context)
elif context["page"] == "settings":
    render_settings_view(context)
