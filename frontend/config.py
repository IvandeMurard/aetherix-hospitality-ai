"""Aetherix Design System Configuration"""

import os
from pathlib import Path

# API - Improved detection: always use HuggingFace API in production
def _detect_api_base() -> str:
    """
    Detect API base URL based on environment.
    - If AETHERIX_API_BASE is set, use it (highest priority)
    - If running on localhost (local development), use localhost API
    - Otherwise (production: Streamlit Cloud, HuggingFace Space), use HuggingFace API
    """
    # Check if explicitly set (highest priority)
    api_base = os.environ.get("AETHERIX_API_BASE")
    if api_base:
        detected_url = api_base.rstrip("/")
        print(f"[API_DETECT] Using explicit AETHERIX_API_BASE: {detected_url}")
        return detected_url
    
    # Check if we're running locally (localhost or 127.0.0.1)
    # This is the only case where we use localhost API
    hostname = os.environ.get("HOSTNAME", "").lower()
    server_name = os.environ.get("SERVER_NAME", "").lower()
    streamlit_server_port = os.environ.get("STREAMLIT_SERVER_PORT", "")
    port = os.environ.get("PORT", "")
    
    # More comprehensive local detection
    is_local = (
        "localhost" in hostname or "127.0.0.1" in hostname or
        "localhost" in server_name or "127.0.0.1" in server_name or
        (not hostname and not server_name and not streamlit_server_port)  # No hostname/server_port usually means local
    )
    
    # Use localhost API only for local development
    if is_local:
        detected_url = "http://localhost:8000"
        print(f"[API_DETECT] Detected local environment, using: {detected_url}")
        return detected_url
    
    # For all production environments (Streamlit Cloud, HuggingFace Space), use HuggingFace API
    detected_url = "https://ivandemurard-fb-agent-api.hf.space"
    print(f"[API_DETECT] Detected production environment (hostname={hostname}, server_name={server_name}, port={port}), using: {detected_url}")
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
    
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.5rem;
    }
    
    /* ALL SIDEBAR TEXT - PURE WHITE */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #FFFFFF !important;
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
    .stApp .stButton > button {
        background-color: #166534 !important;
        color: white !important;
        border: none !important;
        border-radius: 6px;
        font-weight: 600;
    }
    
    .stApp .stButton > button:hover {
        background-color: #14532d !important;
        color: white !important;
    }
    
    /* Fallback for any button outside sidebar (legacy selector) */
    .stButton > button {
        background-color: #2D6A4F;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 500;
    }
    
    .stButton > button:hover {
        background-color: #1B4332;
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
    
    /* ===== SIDEBAR ALWAYS VISIBLE ===== */
    /* Hide all possible sidebar collapse buttons/arrows - ULTRA AGGRESSIVE */
    [data-testid="collapsedControl"],
    button[data-testid="collapsedControl"],
    button[aria-label*="sidebar" i],
    button[aria-label*="Sidebar" i],
    button[aria-label*="collapse" i],
    button[aria-label*="expand" i],
    button[aria-label*="Close sidebar" i],
    button[aria-label*="Open sidebar" i],
    [data-testid="collapsedControl"] button,
    .stApp [data-testid="collapsedControl"],
    .stApp button[data-testid="collapsedControl"],
    /* Hide any arrow icons in sidebar header */
    [data-testid="stSidebar"] > button:first-child,
    [data-testid="stSidebar"] > button,
    [data-testid="stSidebar"] button[aria-label*="arrow" i],
    [data-testid="stSidebar"] button[aria-label*="chevron" i],
    /* Hide collapse control in main app area */
    .stApp > header button[data-testid="collapsedControl"],
    .stApp > header button[aria-label*="sidebar" i],
    header button[data-testid="collapsedControl"],
    header button[aria-label*="sidebar" i],
    /* Hide any button with collapse/expand in aria-label anywhere */
    button[aria-label*="Collapse" i],
    button[aria-label*="Expand" i],
    /* Nuclear option: hide any button that might be a collapse button */
    button[type="button"][aria-label]:has([aria-label*="sidebar" i]),
    button[type="button"]:has([aria-label*="collapse" i]) {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
        height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        position: absolute !important;
        left: -9999px !important;
        pointer-events: none !important;
    }
    
    /* Force sidebar to always be visible */
    [data-testid="stSidebar"] {
        transform: none !important;
        min-width: 21rem !important;
        display: block !important;
        visibility: visible !important;
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    [data-testid="stSidebar"][aria-expanded="false"] {
        transform: none !important;
        display: block !important;
        visibility: visible !important;
        min-width: 21rem !important;
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* Adjust sidebar content positioning - move content up */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem !important;
        margin-top: 0 !important;
    }
    
    /* Prevent sidebar from being hidden */
    section.stSidebar {
        transform: none !important;
        min-width: 21rem !important;
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
</style>
<script>
// Prevent sidebar from collapsing - force it to always be visible
// ULTRA AGGRESSIVE approach to hide collapse button and force sidebar visible
(function() {{
    function hideCollapseButton() {{
        // Find and hide ALL possible collapse buttons
        var selectors = [
            '[data-testid="collapsedControl"]',
            'button[data-testid="collapsedControl"]',
            'button[aria-label*="sidebar" i]',
            'button[aria-label*="Sidebar" i]',
            'button[aria-label*="collapse" i]',
            'button[aria-label*="expand" i]',
            'button[aria-label*="Close sidebar" i]',
            'button[aria-label*="Open sidebar" i]',
            '.stApp [data-testid="collapsedControl"]',
            'header button[data-testid="collapsedControl"]',
            '[data-testid="stSidebar"] > button:first-child'
        ];
        
        selectors.forEach(function(selector) {{
            try {{
                var elements = document.querySelectorAll(selector);
                elements.forEach(function(el) {{
                    if (el) {{
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                        el.style.opacity = '0';
                        el.style.width = '0';
                        el.style.height = '0';
                        el.style.position = 'absolute';
                        el.style.left = '-9999px';
                        el.style.pointerEvents = 'none';
                        el.remove();
                    }}
                }});
            }} catch(e) {{
                // Ignore selector errors
            }}
        }});
    }}
    
    function forceSidebarVisible() {{
        var sidebar = document.querySelector('[data-testid="stSidebar"]') || document.querySelector('section.stSidebar');
        if (sidebar) {{
            sidebar.setAttribute('aria-expanded', 'true');
            sidebar.style.transform = '';
            sidebar.style.display = 'block';
            sidebar.style.visibility = 'visible';
            sidebar.style.minWidth = '21rem';
            sidebar.style.paddingTop = '0';
            sidebar.style.marginTop = '0';
        }}
    }}
    
    // Run immediately
    hideCollapseButton();
    forceSidebarVisible();
    
    // Run on DOM ready
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', function() {{
            hideCollapseButton();
            forceSidebarVisible();
        }});
    }}
    
    // Run periodically to prevent collapse and hide button
    setInterval(function() {{
        hideCollapseButton();
        forceSidebarVisible();
    }}, 50); // More frequent checks
    
    // Watch for any attempts to collapse or add buttons
    var observer = new MutationObserver(function(mutations) {{
        mutations.forEach(function(mutation) {{
            if (mutation.type === 'attributes') {{
                forceSidebarVisible();
            }}
            if (mutation.type === 'childList') {{
                hideCollapseButton();
                forceSidebarVisible();
            }}
        }});
    }});
    
    // Start observing document body for any changes
    setTimeout(function() {{
        var sidebar = document.querySelector('[data-testid="stSidebar"]') || document.querySelector('section.stSidebar');
        if (sidebar) {{
            observer.observe(document.body, {{
                attributes: true,
                childList: true,
                subtree: true,
                attributeFilter: ['aria-expanded', 'style', 'class']
            }});
        }}
    }}, 100);
}})();

// Détecter si Streamlit JS n'est pas chargé après 2s
setTimeout(function() {{
    if (typeof window.streamlit === 'undefined') {{
        // Forcer rechargement sans cache
        window.location.reload(true);
    }}
}}, 2000);
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
