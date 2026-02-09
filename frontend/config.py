"""Aetherix Design System Configuration"""

import os
from pathlib import Path

# API - Smart detection for different environments
def _detect_api_base() -> str:
    """
    Detect API base URL based on environment.
    - If AETHERIX_API_BASE is set, use it (highest priority)
    - If on Streamlit Cloud (detected via URL or env), use HuggingFace API
    - Otherwise, use localhost for local development
    """
    # Check if explicitly set (highest priority)
    api_base = os.environ.get("AETHERIX_API_BASE")
    if api_base:
        return api_base.rstrip("/")  # Remove trailing slash if present
    
    # Detect Streamlit Cloud environment
    # Streamlit Cloud sets specific environment variables
    # Check multiple indicators to be more reliable
    is_streamlit_cloud = False
    
    # Method 1: Check for Streamlit Cloud specific env vars
    if os.environ.get("STREAMLIT_SERVER_PORT"):
        is_streamlit_cloud = True
    
    # Method 2: Check if running in a cloud environment (not localhost)
    # On Streamlit Cloud, SERVER_NAME is set to the app domain
    server_name = os.environ.get("SERVER_NAME", "")
    if "streamlit.app" in server_name.lower():
        is_streamlit_cloud = True
    
    # Method 3: Check if we're not on localhost (fallback detection)
    # This is less reliable but can help if other methods fail
    if not is_streamlit_cloud:
        # If we're not explicitly on localhost and no API_BASE is set,
        # assume we're on Streamlit Cloud
        hostname = os.environ.get("HOSTNAME", "")
        if hostname and "localhost" not in hostname.lower() and "127.0.0.1" not in hostname.lower():
            # Additional check: if we have a port but it's not 8501 (default local), might be cloud
            port = os.environ.get("PORT", "")
            if port and port != "8501":
                is_streamlit_cloud = True
    
    # If on Streamlit Cloud and no API_BASE set, use HuggingFace API
    if is_streamlit_cloud:
        return "https://ivandemurard-fb-agent-api.hf.space"
    
    # Default to localhost for local development
    return "http://localhost:8000"

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
    
    /* ===== MENU BUTTON (SIDEBAR TOGGLE) ===== */
    #aetherix-menu-wrap {
        position: fixed !important;
        top: 0.75rem !important;
        right: 1rem !important;
        z-index: 99999 !important;
        display: block !important;
        visibility: visible !important;
    }
    
    #aetherix-menu-btn {
        background-color: #166534 !important;
        color: white !important;
        border: none !important;
        border-radius: 6px;
        padding: 0.5rem 0.75rem;
        font-size: 0.875rem;
        font-weight: 500;
        cursor: pointer;
        box-shadow: 0 1px 3px rgba(0,0,0,0.15);
        transition: opacity 0.2s, background-color 0.2s, visibility 0.2s;
    }
    
    #aetherix-menu-btn:hover {
        background-color: #14532d !important;
        opacity: 0.9;
    }
    
    #aetherix-menu-btn:active {
        opacity: 0.8;
    }
</style>
<script>
// Détecter si Streamlit JS n'est pas chargé après 2s
setTimeout(function() {
    if (typeof window.streamlit === 'undefined') {
        // Forcer rechargement sans cache
        window.location.reload(true);
    }
}, 2000);
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
