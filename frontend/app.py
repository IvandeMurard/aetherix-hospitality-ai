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

# Build HTML with proper escaping - Improved sidebar toggle with direct manipulation
_sidebar_toggle_html = f"""
<div id="aetherix-menu-wrap" style="position: fixed; top: 0.75rem; right: 1rem; z-index: 9999; display: none;">
    <button id="aetherix-menu-btn" type="button" style="background-color: #166534; color: white; border: none; border-radius: 6px; padding: 0.5rem 0.75rem; font-size: 0.875rem; font-weight: 500; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.15); transition: opacity 0.2s;">{_show_menu_label}</button>
</div>
<script>
(function() {{
    var menuWrap = null;
    var sidebar = null;
    var observer = null;
    
    function getSidebar() {{
        return document.querySelector('[data-testid="stSidebar"]') || document.querySelector('section.stSidebar');
    }}
    
    function isSidebarCollapsed() {{
        if (!sidebar) return false;
        var ariaExpanded = sidebar.getAttribute('aria-expanded');
        var computedStyle = window.getComputedStyle(sidebar);
        var transform = computedStyle.transform;
        
        // Check aria-expanded attribute (false = collapsed)
        if (ariaExpanded === 'false') return true;
        
        // Check transform (translateX means collapsed)
        if (transform && transform !== 'none' && transform.includes('translateX')) {{
            var match = transform.match(/translateX\\(([^)]+)\\)/);
            if (match) {{
                var value = parseFloat(match[1]);
                // Negative translateX means sidebar is moved off-screen (collapsed)
                if (value < 0) return true;
            }}
        }}
        
        return false;
    }}
    
    function updateMenuVisibility() {{
        if (!menuWrap) return;
        var collapsed = isSidebarCollapsed();
        menuWrap.style.display = collapsed ? 'block' : 'none';
    }}
    
    function toggleSidebar() {{
        if (!sidebar) {{
            sidebar = getSidebar();
            if (!sidebar) return;
        }}
        
        // Try to find and click the native Streamlit toggle button first
        var selectors = [
            '[data-testid="collapsedControl"]',
            '[data-testid="stSidebarCollapseControl"]',
            'button[aria-label*="sidebar" i]',
            'button[aria-label*="Sidebar"]',
            'button[aria-label*="collapse" i]',
            'button[aria-label*="expand" i]'
        ];
        
        var toggleBtn = null;
        for (var i = 0; i < selectors.length; i++) {{
            try {{
                var el = document.querySelector(selectors[i]);
                if (el && el.offsetParent !== null) {{
                    toggleBtn = el;
                    break;
                }}
            }} catch (e) {{
                continue;
            }}
        }}
        
        if (toggleBtn) {{
            // Use native toggle if found
            toggleBtn.click();
            return;
        }}
        
        // Fallback: Direct manipulation of sidebar
        var currentState = sidebar.getAttribute('aria-expanded');
        var newState = currentState === 'false' ? 'true' : 'false';
        
        // Update aria-expanded
        sidebar.setAttribute('aria-expanded', newState);
        
        // Update transform style if needed
        var computedStyle = window.getComputedStyle(sidebar);
        var currentTransform = computedStyle.transform;
        
        if (newState === 'false') {{
            // Collapse: move sidebar off-screen
            var sidebarWidth = sidebar.offsetWidth || 300;
            sidebar.style.transform = 'translateX(-' + sidebarWidth + 'px)';
        }} else {{
            // Expand: reset transform
            sidebar.style.transform = '';
        }}
        
        // Trigger resize event for Streamlit to detect change
        window.dispatchEvent(new Event('resize'));
        
        // Update visibility after a short delay
        setTimeout(updateMenuVisibility, 100);
    }}
    
    function initMenuButton() {{
        menuWrap = document.getElementById('aetherix-menu-wrap');
        if (!menuWrap) {{
            setTimeout(initMenuButton, 100);
            return;
        }}
        
        var btn = document.getElementById('aetherix-menu-btn');
        if (!btn) {{
            setTimeout(initMenuButton, 100);
            return;
        }}
        
        sidebar = getSidebar();
        if (!sidebar) {{
            setTimeout(initMenuButton, 100);
            return;
        }}
        
        // Attach click handler
        btn.addEventListener('click', toggleSidebar);
        
        // Set up MutationObserver to watch for sidebar state changes
        observer = new MutationObserver(function(mutations) {{
            mutations.forEach(function(mutation) {{
                if (mutation.type === 'attributes' && mutation.attributeName === 'aria-expanded') {{
                    updateMenuVisibility();
                }}
            }});
        }});
        
        observer.observe(sidebar, {{
            attributes: true,
            attributeFilter: ['aria-expanded'],
            subtree: false
        }});
        
        // Also watch for style changes (transform)
        var styleObserver = new MutationObserver(function() {{
            updateMenuVisibility();
        }});
        
        styleObserver.observe(sidebar, {{
            attributes: true,
            attributeFilter: ['style'],
            subtree: false
        }});
        
        // Initial visibility check
        updateMenuVisibility();
        
        // Watch for window resize (sidebar state can change on resize)
        window.addEventListener('resize', function() {{
            setTimeout(updateMenuVisibility, 100);
        }});
    }}
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', initMenuButton);
    }} else {{
        // DOM already loaded, but wait a bit for Streamlit to render
        setTimeout(initMenuButton, 200);
    }}
    
    // Expose toggle function globally for debugging
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
