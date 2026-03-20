"""
F&B Operations Agent — Streamlit Demo

Two input modes:
  · Text  — manual date / location (always works, even without API keys)
  · Voice — upload audio or type query, Whisper transcribes it

Active path (auto-selected):
  · Claude MCP   — when ANTHROPIC_API_KEY is set  (primary, full LLM reasoning)
  · Heuristic    — zero keys needed               (fast, rule-based fallback)
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATE_FMT = "%Y-%m-%d"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="F&B Operations Agent",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Credential detection ──────────────────────────────────────────────────────

has_claude   = bool(os.getenv("ANTHROPIC_API_KEY"))
has_mistral  = bool(os.getenv("MISTRAL_API_KEY"))
has_apaleo   = bool(os.getenv("APALEO_CLIENT_ID"))
has_predicthq = bool(os.getenv("PREDICTHQ_API_KEY"))
has_openweather = bool(os.getenv("OPENWEATHER_API_KEY"))
has_elevenlabs  = bool(os.getenv("ELEVENLABS_API_KEY"))
has_qdrant      = bool(os.getenv("QDRANT_URL"))

if has_claude:
    active_path = "Claude MCP"
    path_color  = "green"
    path_icon   = "🟢"
else:
    active_path = "Heuristic (mock data)"
    path_color  = "orange"
    path_icon   = "🟡"

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    date_input = st.date_input(
        "Prediction Date",
        value=(datetime.now() + timedelta(days=1)).date(),
        min_value=datetime.now().date(),
    )
    location = st.text_input("Hotel Location", value="Paris, France")
    city     = st.text_input("City (weather)", value="Paris")

    st.markdown("---")
    st.markdown(f"**Active path:** {path_icon} `{active_path}`")

    st.markdown("---")
    st.markdown("**Credentials**")

    def _dot(flag: bool) -> str:
        return "✅" if flag else "⬜"

    st.markdown(f"{_dot(has_claude)}  ANTHROPIC_API_KEY — MCP agent")
    st.markdown(f"{_dot(has_mistral)} MISTRAL_API_KEY — direct agent")
    st.markdown(f"{_dot(has_qdrant)}  QDRANT_URL — cloud vector DB")
    st.markdown(f"{_dot(has_apaleo)} APALEO_CLIENT_ID — real PMS")
    st.markdown(f"{_dot(has_predicthq)} PREDICTHQ_API_KEY — real events")
    st.markdown(f"{_dot(has_openweather)} OPENWEATHER_API_KEY — real weather")
    st.markdown(f"{_dot(has_elevenlabs)} ELEVENLABS_API_KEY — voice output")

    st.markdown("---")
    st.markdown("**Tech stack**")
    st.markdown(
        "Claude · Mistral · Qdrant · Apaleo  \n"
        "PredictHQ · OpenWeatherMap  \n"
        "ElevenLabs · Whisper · MCP"
    )
    st.markdown("---")
    st.caption("Pioneers AILab Hackathon · Qdrant Track")


# ── Header ────────────────────────────────────────────────────────────────────

st.title("🍽️ F&B Operations Agent")
st.caption(
    "AI-powered demand forecasting for hotel Food & Beverage operations — "
    "48 h ahead staffing and procurement recommendations."
)

if not has_claude:
    st.info(
        "**Heuristic mode** — running with mock data (no API keys needed).  \n"
        "Set `ANTHROPIC_API_KEY` in your `.env` to enable the Claude MCP path.",
        icon="ℹ️",
    )

# ── Pipeline helpers ──────────────────────────────────────────────────────────

def _run_heuristic(date_str: str, loc: str, city_name: str):
    """Returns (result_dict, context_dict) for display."""
    from run_scenario import (
        step_reservations, step_fb_context, step_comment_signals,
        step_events, step_weather, step_patterns, _heuristic_predict,
    )

    reservations    = step_reservations(date_str)
    fb_ctx          = step_fb_context(date_str)
    comment_signals = step_comment_signals(date_str)
    events          = step_events(date_str, loc)
    weather         = step_weather(city_name)

    day = datetime.strptime(date_str, DATE_FMT).weekday()
    event_desc = ("weekend " if day >= 4 else "weekday ") + (
        events[0]["title"] if events else "business day"
    )
    patterns = step_patterns(event_desc)

    result = _heuristic_predict(
        date=date_str,
        reservations=reservations,
        fb_context=fb_ctx,
        events=events,
        weather=weather,
        patterns=patterns,
        comment_signals=comment_signals,
    )
    ctx = dict(
        reservations=reservations,
        fb_ctx=fb_ctx,
        comment_signals=comment_signals,
        events=events,
        weather=weather,
        patterns=patterns,
    )
    return result, ctx


def _run_mcp(date_str: str, loc: str, city_name: str) -> str:
    from mcp_agent import run_hotel_mcp_agent
    return asyncio.run(run_hotel_mcp_agent(date_str, loc, city_name))


def _parse_mcp_output(raw: str) -> dict:
    """Best-effort parse of Claude free-text output into a display dict."""
    import re

    def _int(pattern, default=0):
        m = re.search(pattern, raw, re.IGNORECASE)
        return int(m.group(1).replace(",", "")) if m else default

    covers     = _int(r"expected covers[:\s]*(\d[\d,]*)")
    staff      = _int(r"recommended staff[:\s]*(\d+)")
    conf_m     = re.search(r"confidence[:\s]*(\d+)\s*%?", raw, re.IGNORECASE)
    confidence = int(conf_m.group(1)) if conf_m else 75
    factors    = re.findall(r"[·•]\s+(.+)", raw)

    reco_m = re.search(
        r"operational recommendations[:\s]*\n(.*?)(?:\n\n|\Z)",
        raw, re.IGNORECASE | re.DOTALL,
    )
    recommendations = []
    if reco_m:
        recommendations = [
            l.strip().lstrip("→·•-* ")
            for l in reco_m.group(1).split("\n") if l.strip()
        ]

    return {
        "expected_covers": covers if covers > 0 else 80,
        "recommended_staff": staff if staff > 0 else 5,
        "confidence": confidence,
        "key_factors": factors[:5] if factors else [],
        "operational_recommendations": recommendations[:5],
        "method": "claude_mcp",
        "_raw": raw,
    }


# ── Result display ────────────────────────────────────────────────────────────

def _show_forecast(result: dict, ctx: dict | None, date_str: str) -> None:
    st.success("Forecast ready")

    # KPI row
    c1, c2, c3 = st.columns(3)
    baseline = 60
    delta    = result["expected_covers"] - baseline
    with c1:
        st.metric(
            "🍽️ Expected Covers",
            result["expected_covers"],
            delta=f"{'+' if delta >= 0 else ''}{delta} vs baseline",
        )
    with c2:
        st.metric("👥 Recommended Staff", result["recommended_staff"])
    with c3:
        conf = result["confidence"]
        st.metric(
            "📊 Confidence",
            f"{conf}%",
            delta="high" if conf >= 80 else ("medium" if conf >= 60 else "low"),
        )

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("🔑 Key factors")
        for f in result.get("key_factors", []):
            st.write(f"· {f}")

        st.subheader("⚡ Recommendations")
        for a in result.get("operational_recommendations", []):
            st.write(f"→ {a}")

        # Show full Claude analysis (collapsible)
        if result.get("_raw"):
            with st.expander("📄 Full Claude analysis"):
                st.code(result["_raw"], language=None)

    with col_r:
        st.subheader("📋 Context breakdown")

        if ctx:
            res = ctx.get("reservations", {})
            with st.expander("🏨 PMS — Reservations", expanded=True):
                st.write(f"Occupancy: **{res.get('occupancy_rate', 'n/a')}%**")
                st.write(f"Expected guests: **{res.get('expected_guests', 'n/a')}**")
                for g in res.get("groups", []):
                    st.write(f"· Group: {g['name']} ({g['size']} guests, {g['meal_plan']})")

            cs = ctx.get("comment_signals", {})
            if cs.get("reservations_with_signals", 0):
                with st.expander("💬 Reservation signals"):
                    if cs.get("celebration_summary"):
                        st.write("**Celebrations:**", cs["celebration_summary"])
                    if cs.get("dietary_summary"):
                        st.write("**Dietary:**", cs["dietary_summary"])
                    if cs.get("fb_request_summary"):
                        st.write("**F&B requests:**", cs["fb_request_summary"])

            evs = ctx.get("events", [])
            if evs:
                with st.expander("🎪 Local events"):
                    for ev in evs[:5]:
                        st.write(f"· [{ev.get('rank', '?'):>3}] {ev['title']} ({ev.get('category', '')})")

            wth = ctx.get("weather", {})
            with st.expander("🌤️ Weather"):
                st.write(wth.get("description", "n/a"))
                st.write(
                    f"Humidity: {wth.get('humidity', 'n/a')}%  "
                    f"|  Source: {wth.get('source', 'n/a')}"
                )

            pats = ctx.get("patterns", [])
            if pats:
                with st.expander("📚 Historical patterns"):
                    for p in pats:
                        sc = p["scenario"]
                        st.write(
                            f"**{sc['event_name']}** — {sc['actual_covers']} covers, "
                            f"{sc['staffing']} staff  "
                            f"(similarity {p['similarity_score']:.2f})"
                        )
        else:
            st.info("Context breakdown available in heuristic mode.")

    st.caption(f"Method: `{result.get('method', 'n/a')}`  |  Date: {date_str}")


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_text, tab_voice = st.tabs(["📝 Text Input", "🎙️ Voice Input"])


# ── Tab 1 : Text Input ────────────────────────────────────────────────────────

with tab_text:
    st.markdown(
        "Adjust date and location in the sidebar, then click **Generate Forecast**. "
        "Works with zero credentials — real data activates automatically when keys are set."
    )

    if st.button("🎯 Generate Forecast", type="primary", use_container_width=True, key="btn_text"):
        date_str = str(date_input)
        with st.spinner(f"Running {active_path} pipeline …"):
            try:
                if has_claude:
                    raw    = _run_mcp(date_str, location, city)
                    result = _parse_mcp_output(raw)
                    _show_forecast(result, ctx=None, date_str=date_str)
                else:
                    result, ctx = _run_heuristic(date_str, location, city)
                    _show_forecast(result, ctx=ctx, date_str=date_str)
            except Exception as exc:
                st.error(f"Error: {exc}")
                st.info("Check the terminal for the full traceback.")


# ── Tab 2 : Voice Input ───────────────────────────────────────────────────────

with tab_voice:
    st.markdown(
        "Upload an audio file **or** type a natural-language query. "
        "Whisper extracts the date and location; the same forecast pipeline runs."
    )

    col_upload, col_examples = st.columns([3, 1])

    with col_upload:
        uploaded = st.file_uploader(
            "Audio file (WAV / MP3 / M4A / OGG / FLAC)",
            type=["wav", "mp3", "m4a", "ogg", "flac"],
        )
        typed_query = st.text_input(
            "Or type your query",
            placeholder="What's the forecast for Saturday in Paris?",
        )

    with col_examples:
        st.markdown("**Examples**")
        st.caption("Forecast for tomorrow in London")
        st.caption("Saturday covers in Paris")
        st.caption("December 24 dinner demand")
        st.caption("Next Friday staffing in Berlin")

    if st.button("🎙️ Transcribe & Forecast", type="primary", use_container_width=True, key="btn_voice"):
        from voice_input import parse_query

        text = ""

        if uploaded:
            import tempfile
            _MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB
            raw_bytes = uploaded.read()
            if len(raw_bytes) > _MAX_AUDIO_BYTES:
                st.error(f"File too large ({len(raw_bytes) // (1024*1024)} MB). Maximum is 25 MB.")
            else:
                suffix = "." + uploaded.name.rsplit(".", 1)[-1].lower()
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(raw_bytes)
                    tmp_path = tmp.name
                with st.spinner("Transcribing …"):
                    try:
                        from voice_input import transcribe
                        text = transcribe(tmp_path)
                        os.unlink(tmp_path)
                    except RuntimeError as e:
                        st.error(str(e))
        elif typed_query:
            text = typed_query
        else:
            st.warning("Upload an audio file or type a query.")

        if text:
            st.info(f'**Transcript:** "{text}"')
            query    = parse_query(text)
            date_str = query["date"]
            loc      = query["location"]
            city_q   = query["city"]
            st.write(f"→ **date:** `{date_str}`  |  **location:** `{loc}`")

            with st.spinner(f"Running {active_path} pipeline …"):
                try:
                    if has_claude:
                        raw    = _run_mcp(date_str, loc, city_q)
                        result = _parse_mcp_output(raw)
                        _show_forecast(result, ctx=None, date_str=date_str)
                    else:
                        result, ctx = _run_heuristic(date_str, loc, city_q)
                        _show_forecast(result, ctx=ctx, date_str=date_str)
                except Exception as exc:
                    st.error(f"Error: {exc}")
                    st.info("Check the terminal for the full traceback.")
