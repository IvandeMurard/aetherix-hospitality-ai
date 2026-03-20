"""Aetherix Design System Configuration"""

import os
from pathlib import Path

# API - Improved detection: always use HuggingFace API in production
def _detect_api_base() -> str:
    """
    Detect API base URL based on environment.
    Priority order:
    1. USE_LOCAL_API=true (force localhost)
    2. AETHERIX_API_BASE explicit (highest priority)
    3. Streamlit Cloud detection (via multiple signals)
    4. Local development detection
    5. Fallback: HuggingFace API (production default)
    """
    # Collect environment variables for logging
    env_vars = {
        "USE_LOCAL_API": os.environ.get("USE_LOCAL_API", ""),
        "AETHERIX_API_BASE": os.environ.get("AETHERIX_API_BASE", ""),
        "HOSTNAME": os.environ.get("HOSTNAME", ""),
        "SERVER_NAME": os.environ.get("SERVER_NAME", ""),
        "STREAMLIT_SERVER_PORT": os.environ.get("STREAMLIT_SERVER_PORT", ""),
        "PORT": os.environ.get("PORT", ""),
        "STREAMLIT_SHARING_MODE": os.environ.get("STREAMLIT_SHARING_MODE", ""),
        "STREAMLIT_SERVER_HEADLESS": os.environ.get("STREAMLIT_SERVER_HEADLESS", ""),
    }
    
    print(f"[API_DETECT] Environment detection started")
    print(f"[API_DETECT] Env vars: {', '.join(f'{k}={v[:50]}' if v else f'{k}=<not-set>' for k, v in env_vars.items())}")
    
    # 1. Check for forced local API (for development/testing)
    use_local = env_vars["USE_LOCAL_API"].lower() in ("true", "1", "yes")
    if use_local:
        detected_url = "http://localhost:8000"
        print(f"[API_DETECT] USE_LOCAL_API=true, forcing local API: {detected_url}")
        print("[API_DETECT] WARNING: Using local API in production environment!")
        return detected_url
    
    # 2. Check if explicitly set (highest priority)
    api_base = env_vars["AETHERIX_API_BASE"]
    if api_base:
        detected_url = api_base.rstrip("/")
        print(f"[API_DETECT] Using explicit AETHERIX_API_BASE: {detected_url}")
        return detected_url
    
    # 3. Detect Streamlit Cloud explicitly
    # Streamlit Cloud sets specific environment variables
    server_name_lower = env_vars["SERVER_NAME"].lower()
    is_streamlit_cloud = (
        env_vars["STREAMLIT_SHARING_MODE"] == "true" or
        "streamlit.app" in server_name_lower or
        "share.streamlit.io" in server_name_lower or
        env_vars["STREAMLIT_SERVER_HEADLESS"] == "true"
    )
    
    if is_streamlit_cloud:
        # Always use HuggingFace API for Streamlit Cloud
        detected_url = "https://ivandemurard-fb-agent-api.hf.space"
        print(f"[API_DETECT] Detected Streamlit Cloud (SERVER_NAME={env_vars['SERVER_NAME']}, STREAMLIT_SHARING_MODE={env_vars['STREAMLIT_SHARING_MODE']}), using: {detected_url}")
        return detected_url
    
    # 4. Detect local development
    hostname_lower = env_vars["HOSTNAME"].lower()
    is_local = (
        "localhost" in hostname_lower or "127.0.0.1" in hostname_lower or
        "localhost" in server_name_lower or "127.0.0.1" in server_name_lower or
        (not env_vars["HOSTNAME"] and not env_vars["SERVER_NAME"] and 
         not env_vars["STREAMLIT_SERVER_PORT"] and not env_vars["PORT"])
    )
    
    if is_local:
        detected_url = "http://localhost:8000"
        print(f"[API_DETECT] Detected local environment (hostname={env_vars['HOSTNAME']}, server_name={env_vars['SERVER_NAME']}), using: {detected_url}")
        return detected_url
    
    # 5. Fallback: Always use HuggingFace API for any production environment
    detected_url = "https://ivandemurard-fb-agent-api.hf.space"
    print(f"[API_DETECT] Using production fallback (hostname={env_vars['HOSTNAME']}, server_name={env_vars['SERVER_NAME']}), using: {detected_url}")
    return detected_url

API_BASE = _detect_api_base()

# Brand
BRAND_NAME = "Aetherix"
BRAND_TAGLINE = "Intelligence layer for hotel F&B operations"

# Colors
COLORS = {
    # Primary (Green)
    "primary_900": "#081C15",
    "primary_800": "#1B4332",  # Sidebar background
    "primary_700": "#2D6A4F",  # Buttons, accents
    "primary_600": "#40916C",  # Hover, success
    "primary_100": "#D8F3DC",  # Light backgrounds
    # Neutral
    "white": "#FFFFFF",
    "gray_50": "#F8F9FA",  # Page background
    "gray_100": "#E9ECEF",  # Card borders
    "gray_200": "#DEE2E6",  # Dividers
    "gray_400": "#ADB5BD",  # Disabled
    "gray_500": "#6C757D",  # Secondary text
    "gray_700": "#495057",  # Body text
    "gray_900": "#212529",  # Headings
    # Semantic
    "success": "#40916C",
    "warning": "#E9C46A",
    "error": "#E76F51",
    "info": "#457B9D",
}

# Custom CSS
AETHERIX_CSS = """
<style>
    /* Import Inter font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global */
    .stApp {
        background-color: #F8F9FA;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Hide ALL Streamlit UI */
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stSidebarNav"] {display: none !important;}
    
    /* ===== SIDEBAR ===== */
    [data-testid="stSidebar"] {
        background-color: #1B4332 !important;
    }
    
    /* ALL SIDEBAR TEXT - PURE WHITE */
    /* Catch-all rule to override any gray colors - very aggressive */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] *,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] h6,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] a,
    [data-testid="stSidebar"] li,
    [data-testid="stSidebar"] td,
    [data-testid="stSidebar"] th,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
        color: #FFFFFF !important;
    }
    
    /* Override any inline styles that might set gray colors */
    /* Match various formats: with/without spaces, uppercase/lowercase */
    [data-testid="stSidebar"] [style*="color: #6b7280"],
    [data-testid="stSidebar"] [style*="color:#6b7280"],
    [data-testid="stSidebar"] [style*="color: #9ca3af"],
    [data-testid="stSidebar"] [style*="color:#9ca3af"],
    [data-testid="stSidebar"] [style*="color: #94a3b8"],
    [data-testid="stSidebar"] [style*="color:#94a3b8"],
    [data-testid="stSidebar"] [style*="color: #d1d5db"],
    [data-testid="stSidebar"] [style*="color:#d1d5db"],
    [data-testid="stSidebar"] [style*="color: gray"],
    [data-testid="stSidebar"] [style*="color:grey"],
    [data-testid="stSidebar"] [style*="COLOR: #d1d5db"],
    [data-testid="stSidebar"] [style*="COLOR:#d1d5db"] {
        color: #FFFFFF !important;
    }
    
    /* Exception for muted/secondary text - use light gray instead of dark gray */
    /* Only apply if explicitly marked as muted */
    [data-testid="stSidebar"] .muted,
    [data-testid="stSidebar"] .secondary,
    [data-testid="stSidebar"] span[style*="#d1d5db"],
    [data-testid="stSidebar"] div[style*="#d1d5db"],
    [data-testid="stSidebar"] p[style*="#d1d5db"],
    [data-testid="stSidebar"] label[style*="#d1d5db"],
    [data-testid="stSidebar"] *[style*="#d1d5db"] {
        color: #d1d5db !important;
    }
    
    /* Sidebar buttons - transparent, left-align, white text */
    [data-testid="stSidebar"] .stButton > button {
        background-color: transparent;
        border: none;
        color: #FFFFFF !important;
        text-align: left;
        padding: 0.6rem 0.75rem;
        width: 100%;
        justify-content: flex-start;
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: rgba(255,255,255,0.1);
    }
    
    /* Sidebar dropdowns - white text, readable on dark green */
    [data-testid="stSidebar"] .stSelectbox label {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stSelectbox > div > div {
        background-color: #14532d !important;
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.2);
    }
    [data-testid="stSidebar"] .stSelectbox input,
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
        color: #ffffff !important;
    }
    
    /* Sidebar dividers */
    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.15);
        margin: 1rem 0;
    }
    
    /* ===== MAIN CONTENT ===== */
    
    /* Headings */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        color: #212529 !important;
    }
    
    /* Body text */
    .stApp p {
        color: #495057;
    }
    
    /* Form labels */
    .stApp .stTextInput label,
    .stApp .stNumberInput label,
    .stApp .stSelectbox label,
    .stApp .stTextArea label {
        color: #495057 !important;
    }
    
    /* Radio buttons in main content */
    .stApp [data-testid="stRadio"] label,
    .stApp [data-testid="stRadio"] label p,
    .stApp [data-testid="stRadio"] label span {
        color: #212529 !important;
    }
    
    /* ===== KPI CARDS ===== */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 1.25rem;
        border-radius: 8px;
        border: 1px solid #E9ECEF;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    
    div[data-testid="stMetric"] label {
        color: #6C757D !important;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #212529 !important;
        font-size: 1.75rem;
        font-weight: 600;
    }
    
    /* ===== BUTTONS ===== */
    /* Main content: high-contrast navigation (Prev, Today, Next) and primary actions */
    /* Ultra-specific selectors to override Streamlit defaults */
    .stApp .stButton > button,
    .stApp .stButton > button[kind="primary"],
    .stApp button.stButton > button,
    .stApp [data-testid="stButton"] > button,
    .stApp button[type="button"]:not([data-testid="collapsedControl"]):not([aria-label*="sidebar" i]) {
        background-color: #166534 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        padding: 8px 16px !important;
        min-height: auto !important;
    }
    
    /* Force text color on all child elements inside buttons */
    .stApp .stButton > button *,
    .stApp .stButton > button[kind="primary"] *,
    .stApp button[type="button"]:not([data-testid="collapsedControl"]) * {
        color: #ffffff !important;
    }
    
    .stApp .stButton > button:hover,
    .stApp .stButton > button[kind="primary"]:hover,
    .stApp button.stButton > button:hover,
    .stApp [data-testid="stButton"] > button:hover,
    .stApp button[type="button"]:not([data-testid="collapsedControl"]):not([aria-label*="sidebar" i]):hover {
        background-color: #14532d !important;
        color: #ffffff !important;
    }
    
    .stApp .stButton > button:hover *,
    .stApp .stButton > button[kind="primary"]:hover * {
        color: #ffffff !important;
    }
    
    /* Target buttons in columns (navigation area) */
    .stApp [data-testid="column"] .stButton > button {
        background-color: #166534 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        padding: 8px 16px !important;
    }
    
    .stApp [data-testid="column"] .stButton > button * {
        color: #ffffff !important;
    }
    
    .stApp [data-testid="column"] .stButton > button:hover {
        background-color: #14532d !important;
        color: #ffffff !important;
    }
    
    .stApp [data-testid="column"] .stButton > button:hover * {
        color: #ffffff !important;
    }
    
    /* Fallback for any button outside sidebar (legacy selector) */
    .stButton > button:not([data-testid="stSidebar"] button) {
        background-color: #166534 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        padding: 8px 16px !important;
    }
    
    .stButton > button:not([data-testid="stSidebar"] button) * {
        color: #ffffff !important;
    }
    
    .stButton > button:not([data-testid="stSidebar"] button):hover {
        background-color: #14532d !important;
        color: #ffffff !important;
    }
    
    .stButton > button:not([data-testid="stSidebar"] button):hover * {
        color: #ffffff !important;
    }
    
    /* ===== VIEW TOGGLE ===== */
    [data-testid="stRadio"][data-testid*="view"] > div {
        gap: 0;
    }
    
    /* ===== CHARTS ===== */
    .js-plotly-plot {
        border-radius: 8px;
    }
    
    /* Loading animation */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    /* Sidebar: hide collapse button (arrow) and its row to free space */
    [data-testid="collapsedControl"],
    button[data-testid="collapsedControl"],
    button[aria-label*="sidebar" i],
    button[aria-label*="collapse" i],
    button[aria-label*="expand" i],
    .stApp header [data-testid="collapsedControl"],
    [data-testid="stSidebar"] > div:first-child > button,
    [data-testid="stSidebar"] > div:first-child > div:first-child > button,
    [data-testid="stSidebar"] button:first-of-type {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
        width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
    }
    /* Hide the header row that contains the collapse arrow (frees top space) */
    [data-testid="stSidebar"] > div:first-child > div:first-child:has(button) {
        min-height: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
    }
    [data-testid="stSidebar"],
    section.stSidebar,
    [data-testid="stSidebar"][aria-expanded="false"] {
        transform: none !important;
        min-width: 21rem !important;
        display: block !important;
        visibility: visible !important;
        padding: 0 !important;
        margin-top: 0 !important;
    }
    [data-testid="stSidebar"] > div:first-child,
    [data-testid="stSidebar"] > div:first-child > *:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }
</style>
<script>
(function() {{
    function sidebarCleanup() {{
        var sidebar = document.querySelector('[data-testid="stSidebar"]');
        if (!sidebar) return;
        sidebar.setAttribute('aria-expanded', 'true');
        sidebar.style.paddingTop = '0';
        sidebar.style.marginTop = '0';
        var first = sidebar.querySelector('> div:first-child');
        if (first) {{
            first.style.paddingTop = '0';
            first.style.marginTop = '0';
            var firstRow = first.querySelector(':first-child');
            if (firstRow && firstRow.querySelector('button svg')) {{
                var text = (firstRow.textContent || '').trim().replace(/\\s/g, '');
                if (!text || text === '\u00AB' || text === '\u2039' || text.length < 3) {{
                    firstRow.style.display = 'none';
                    firstRow.style.height = '0';
                    firstRow.style.overflow = 'hidden';
                    firstRow.style.margin = '0';
                    firstRow.style.padding = '0';
                }}
            }}
            var buttons = first.querySelectorAll('button');
            buttons.forEach(function(b) {{
                var hasSvg = b.querySelector('svg');
                var label = (b.getAttribute('aria-label') || '').toLowerCase();
                var text = (b.textContent || '').trim();
                var isArrow = /^[\\s\u00AB\u2039\u00AF\u201C]*$/.test(text) || text === '' || text === '\u00AB' || text === '\u2039';
                if (hasSvg || label.indexOf('sidebar') >= 0 || label.indexOf('collapse') >= 0 || label.indexOf('expand') >= 0 || (isArrow && b === buttons[0])) b.remove();
            }});
        }}
        sidebar.querySelectorAll('button').forEach(function(b) {{
            if (b.querySelector('svg') && (b.getAttribute('aria-label') || '').match(/sidebar|collapse|expand/i)) b.remove();
        }});
    }}
    sidebarCleanup();
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sidebarCleanup);
    setInterval(sidebarCleanup, 200);
    var obs = new MutationObserver(function() {{ sidebarCleanup(); }});
    setTimeout(function() {{ obs.observe(document.body, {{ childList: true, subtree: true }}); }}, 150);
}})();
// Force button styles for navigation buttons (Today, Prev, Next)
// Ultra-aggressive approach: target ALL buttons in main content area
var styledButtons = new WeakSet();
var styleSheet = null;

// Create a style sheet with maximum priority
function createStyleSheet() {{
    if (!styleSheet) {{
        var style = document.createElement('style');
        style.id = 'aetherix-button-override';
        style.textContent = `
            .stApp [data-testid="column"] .stButton > button,
            .stApp [data-testid="column"] button[type="button"] {{
                background-color: #166534 !important;
                color: #ffffff !important;
                border: none !important;
                border-radius: 6px !important;
                font-weight: 500 !important;
                padding: 8px 16px !important;
            }}
            .stApp [data-testid="column"] .stButton > button *,
            .stApp [data-testid="column"] button[type="button"] * {{
                color: #ffffff !important;
            }}
        `;
        document.head.appendChild(style);
        styleSheet = style;
    }}
}}

function styleNavigationButtons() {{
    // Create style sheet if not exists
    createStyleSheet();
    
    // Get all buttons in main content, excluding sidebar
    var allButtons = document.querySelectorAll('.stApp button:not([data-testid="stSidebar"] button)');
    
    allButtons.forEach(function(button) {{
        // Skip sidebar buttons
        if (button.closest('[data-testid="stSidebar"]')) {{
            return;
        }}
        
        // Skip radio buttons and other special buttons
        if (button.closest('[data-testid="stRadio"]') || 
            button.closest('.stDateInput') ||
            button.getAttribute('data-testid') === 'collapsedControl' ||
            button.closest('[data-testid="stHeader"]')) {{
            return;
        }}
        
        var buttonText = button.textContent.trim();
        
        // Check if it's a navigation button by text content
        var isNavButton = /today|aujourd|prev|précédent|next|suivant/i.test(buttonText);
        
        // Check by key/data attributes - Streamlit uses data-testid with baseWidgetHash
        var testId = button.getAttribute('data-testid') || '';
        var isNavByKey = /prev_period|next_period|today_btn/.test(testId);
        
        // Check if button is in columns near date picker (navigation area)
        var parentCol = button.closest('[data-testid="column"]');
        var isInNavArea = parentCol && parentCol.querySelector('[data-testid="stDateInput"]');
        
        // Apply to all buttons in navigation columns OR navigation buttons
        var shouldStyle = isNavButton || isNavByKey || isInNavArea;
        
        if (shouldStyle) {{
            // Force styles with maximum priority - override any inline styles
            // Remove and re-apply to ensure our styles take precedence
            button.style.removeProperty('background-color');
            button.style.removeProperty('color');
            button.style.removeProperty('border');
            button.style.removeProperty('border-radius');
            button.style.removeProperty('font-weight');
            button.style.removeProperty('padding');
            
            // Apply our styles with !important
            button.style.setProperty('background-color', '#166534', 'important');
            button.style.setProperty('color', '#ffffff', 'important');
            button.style.setProperty('border', 'none', 'important');
            button.style.setProperty('border-radius', '6px', 'important');
            button.style.setProperty('font-weight', '500', 'important');
            button.style.setProperty('padding', '8px 16px', 'important');
            
            // Also force text color on any child elements (spans, divs, etc.)
            var textElements = button.querySelectorAll('*');
            textElements.forEach(function(el) {{
                el.style.removeProperty('color');
                el.style.setProperty('color', '#ffffff', 'important');
            }});
            
            // Mark as styled
            if (!styledButtons.has(button)) {{
                styledButtons.add(button);
                
                // Add hover listener
                button.addEventListener('mouseenter', function() {{
                    this.style.setProperty('background-color', '#14532d', 'important');
                }}, true);
                button.addEventListener('mouseleave', function() {{
                    this.style.setProperty('background-color', '#166534', 'important');
                }}, true);
            }}
        }}
        
        // Re-apply styles for already styled buttons to override Streamlit's inline styles
        if (styledButtons.has(button)) {{
            // Check if styles were overridden
            var computedBg = window.getComputedStyle(button).backgroundColor;
            var computedColor = window.getComputedStyle(button).color;
            
            // If background is not our green or color is not white, re-apply
            if (!computedBg.includes('rgb(22, 101, 52)') || 
                (!computedColor.includes('rgb(255, 255, 255)') && !computedColor.includes('rgba(255, 255, 255'))) {{
                button.style.removeProperty('background-color');
                button.style.removeProperty('color');
                button.style.setProperty('background-color', '#166534', 'important');
                button.style.setProperty('color', '#ffffff', 'important');
                
                var textElements = button.querySelectorAll('*');
                textElements.forEach(function(el) {{
                    var elColor = window.getComputedStyle(el).color;
                    if (!elColor.includes('rgb(255, 255, 255)') && !elColor.includes('rgba(255, 255, 255')) {{
                        el.style.removeProperty('color');
                        el.style.setProperty('color', '#ffffff', 'important');
                    }}
                }});
            }}
        }}
    }});
}}

// Force sidebar text to be white - ultra aggressive
function styleSidebarText() {{
    var sidebar = document.querySelector('[data-testid="stSidebar"]');
    if (!sidebar) return;
    
    var allElements = sidebar.querySelectorAll('*');
    allElements.forEach(function(el) {{
        // Skip buttons (they have their own styles)
        if (el.tagName === 'BUTTON' || el.closest('.stButton')) {{
            return;
        }}
        
        // Check inline style attribute first (highest priority)
        var inlineStyle = el.getAttribute('style') || '';
        var hasGrayInline = inlineStyle && (
            inlineStyle.toLowerCase().includes('#d1d5db') ||
            inlineStyle.toLowerCase().includes('#6b7280') ||
            inlineStyle.toLowerCase().includes('#9ca3af') ||
            inlineStyle.toLowerCase().includes('#94a3b8') ||
            inlineStyle.toLowerCase().includes('color: gray') ||
            inlineStyle.toLowerCase().includes('color:grey')
        );
        
        // Check computed color
        var computedColor = window.getComputedStyle(el).color;
        var isGrayColor = computedColor && (
            computedColor.includes('rgb(107, 114, 128)') || // #6b7280
            computedColor.includes('rgb(156, 163, 175)') || // #9ca3af
            computedColor.includes('rgb(148, 163, 184)') || // #94a3b8
            computedColor.includes('rgb(75, 85, 99)') ||   // #4b5563
            computedColor.includes('rgb(209, 213, 219)')    // #d1d5db
        );
        
        // Force ALL gray text to white for maximum readability on dark green background
        if (hasGrayInline || isGrayColor) {{
            // Remove inline color style completely and force white
            if (hasGrayInline) {{
                // Remove color property from inline style
                var newStyle = inlineStyle.replace(/color\s*:\s*[^;]+;?/gi, '').trim();
                // Clean up any double semicolons or trailing semicolons
                newStyle = newStyle.replace(/;;+/g, ';').replace(/;\s*$/, '');
                if (newStyle && !newStyle.endsWith(';')) {{
                    newStyle += ';';
                }}
                // Add white color with !important
                el.setAttribute('style', newStyle + ' color: #ffffff !important;');
            }}
            
            // Force white color via style property (overrides inline styles)
            el.style.setProperty('color', '#ffffff', 'important');
            
            // Also force on any child text nodes
            var textNodes = [];
            var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
            var node;
            while (node = walker.nextNode()) {{
                if (node.parentElement) {{
                    node.parentElement.style.setProperty('color', '#ffffff', 'important');
                }}
            }}
        }}
    }});
}}

// Run immediately and on DOM changes
styleNavigationButtons();
styleSidebarText();

setInterval(function() {{
    styleNavigationButtons();
    styleSidebarText();
}}, 200);

// Watch for new elements AND style attribute changes
var observer = new MutationObserver(function(mutations) {{
    var shouldUpdate = false;
    mutations.forEach(function(mutation) {{
        if (mutation.type === 'childList' || 
            (mutation.type === 'attributes' && mutation.attributeName === 'style')) {{
            shouldUpdate = true;
        }}
    }});
    if (shouldUpdate) {{
        styleNavigationButtons();
        styleSidebarText();
    }}
}});
observer.observe(document.body, {{
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['style']
}});
</script>
"""


def get_text(key: str, lang: str = "en") -> str:
    """Get translated text by key"""
    import json

    locale_file = Path(__file__).parent / "locales" / f"{lang}.json"
    if locale_file.exists():
        with open(locale_file, "r", encoding="utf-8") as f:
            translations = json.load(f)
            keys = key.split(".")
            value = translations
            for k in keys:
                value = value.get(k, key)
            return value if isinstance(value, str) else key
    return key
