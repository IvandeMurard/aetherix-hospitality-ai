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

# Use components.v1.html for cleaner JavaScript injection
import streamlit.components.v1 as components

# Build HTML with proper escaping
_sidebar_toggle_html = f"""
<div id="aetherix-menu-wrap" style="position: fixed; top: 1rem; left: 1rem; z-index: 9999;">
    <button id="aetherix-menu-btn" type="button" style="background-color: #166534; color: white; border: none; border-radius: 6px; padding: 0.5rem 0.75rem; font-size: 0.875rem; font-weight: 500; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.15);">{_show_menu_label}</button>
</div>
<script>
(function() {{
    function tryClick(el) {{
        if (!el || el.disabled) return false;
        try {{
            el.click();
            el.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }}));
            return true;
        }} catch (e) {{
            return false;
        }}
    }}
    
    function findSidebarToggle() {{
        var selectors = [
            '[data-testid="collapsedControl"]',
            '[data-testid="stSidebarCollapseControl"]',
            'button[aria-label*="sidebar" i]',
            'button[aria-label*="Sidebar"]',
            'section.stSidebar > div:first-child button',
            '[data-testid="stSidebar"] > div:first-child button'
        ];
        
        for (var i = 0; i < selectors.length; i++) {{
            try {{
                var el = document.querySelector(selectors[i]);
                if (el && el.offsetParent !== null) return el;
            }} catch (e) {{
                continue;
            }}
        }}
        
        var sidebar = document.querySelector('[data-testid="stSidebar"]') || document.querySelector('section.stSidebar');
        if (sidebar && sidebar.parentElement) {{
            var parentBtns = sidebar.parentElement.querySelectorAll('button');
            for (var j = 0; j < parentBtns.length; j++) {{
                var btn = parentBtns[j];
                if (btn.closest && btn.closest('#aetherix-menu-wrap')) continue;
                var rect = btn.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && rect.left < 200 && rect.top < 150) {{
                    return btn;
                }}
            }}
        }}
        
        return null;
    }}
    
    function toggleSidebar() {{
        var toggleBtn = findSidebarToggle();
        if (toggleBtn) {{
            tryClick(toggleBtn);
        }}
    }}
    
    function initMenuButton() {{
        var btn = document.getElementById('aetherix-menu-btn');
        if (btn) {{
            btn.addEventListener('click', toggleSidebar);
        }} else {{
            setTimeout(initMenuButton, 100);
        }}
    }}
    
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', initMenuButton);
    }} else {{
        setTimeout(initMenuButton, 50);
    }}
    
    window.aetherixToggleSidebar = toggleSidebar;
}})();
</script>
"""

components.html(_sidebar_toggle_html, height=50)

# Route to correct view based on sidebar selection
if context["page"] == "forecast":
    render_forecast_view(context)
elif context["page"] == "history":
    render_history_view(context)
elif context["page"] == "settings":
    render_settings_view(context)
