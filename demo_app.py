"""
F&B Operations Agent — Streamlit Demo

Two modes:
  · Text input  — type or paste event context (works without any API key)
  · Voice input — speak your query, Whisper transcribes it (local or API)

Architecture note: this UI runs the heuristic pipeline when no API keys are
set, and the MCP / Claude path when ANTHROPIC_API_KEY is configured.
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="F&B Operations Agent",
    page_icon="🍽️",
    layout="wide",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.header("Configuration")

date_input = st.sidebar.date_input(
    "Prediction Date",
    value=datetime.now() + timedelta(days=1),
    min_value=datetime.now().date(),
)
location = st.sidebar.text_input("Hotel Location", value="Paris, France")
city = st.sidebar.text_input("City (for weather)", value="Paris")

st.sidebar.markdown("---")
has_claude  = bool(os.getenv("ANTHROPIC_API_KEY"))
has_mistral = bool(os.getenv("MISTRAL_API_KEY"))
has_apaleo  = bool(os.getenv("APALEO_CLIENT_ID"))

st.sidebar.markdown("**Credential status:**")
st.sidebar.markdown(f"{'✅' if has_claude  else '❌'} ANTHROPIC_API_KEY — MCP agent")
st.sidebar.markdown(f"{'✅' if has_mistral else '❌'} MISTRAL_API_KEY  — direct agent")
st.sidebar.markdown(f"{'✅' if has_apaleo  else '❌'} APALEO_CLIENT_ID — real PMS data")

mode_label = "Claude MCP" if has_claude else ("Mistral direct" if has_mistral else "Heuristic (mock data)")
st.sidebar.markdown(f"\n**Active path:** `{mode_label}`")

st.sidebar.markdown("---")
st.sidebar.markdown("**Tech stack:**")
st.sidebar.markdown("• Claude / Anthropic — primary LLM")
st.sidebar.markdown("• Mistral AI — fallback LLM + embeddings")
st.sidebar.markdown("• Qdrant — vector pattern memory")
st.sidebar.markdown("• Apaleo — PMS (reservations)")
st.sidebar.markdown("• PredictHQ — local events")
st.sidebar.markdown("• OpenWeatherMap — weather")
st.sidebar.markdown("• ElevenLabs — voice output")
st.sidebar.markdown("• Whisper — voice input")
st.sidebar.markdown("• MCP — hotel context protocol")

# ── Main layout ───────────────────────────────────────────────────────────────

st.title("🍽️ F&B Operations Agent")
st.caption("AI-powered demand forecasting for hotel Food & Beverage operations · Pioneers AILab Hackathon")

tab_text, tab_voice = st.tabs(["📝 Text Input", "🎙️ Voice Input"])


# ── Helper: run heuristic pipeline ───────────────────────────────────────────

def _run_heuristic(date_str: str, loc: str, city_name: str) -> dict:
    from mcp_servers.pms_server      import get_hotel_reservations, get_fb_forecast_context, parse_reservation_comments
    from mcp_servers.events_server   import get_local_events
    from mcp_servers.weather_server  import get_weather
    from mcp_servers.hotel_context_server import search_historical_patterns
    from run_scenario import _heuristic_predict

    reservations    = get_hotel_reservations(date=date_str)
    fb_context      = get_fb_forecast_context(date=date_str)
    comment_signals = parse_reservation_comments(date=date_str)
    events          = get_local_events(date=date_str, location=loc)
    weather         = get_weather(city=city_name)

    event_desc = (
        "weekend " if datetime.strptime(date_str, "%Y-%m-%d").weekday() >= 4 else "weekday "
    ) + (events[0]["title"] if events else "business day")
    patterns = search_historical_patterns(event_description=event_desc, limit=3)

    return _heuristic_predict(
        date=date_str,
        reservations=reservations,
        fb_context=fb_context,
        events=events,
        weather=weather,
        patterns=patterns,
        comment_signals=comment_signals,
    ), reservations, fb_context, comment_signals, events, weather, patterns


def _run_mcp(date_str: str, loc: str, city_name: str) -> str:
    from mcp_agent import run_hotel_mcp_agent
    return asyncio.run(run_hotel_mcp_agent(date_str, loc, city_name))


def _show_results(result: dict, reservations: dict, fb_ctx: dict,
                  comment_signals: dict, events: list, weather: dict,
                  patterns: list, date_str: str) -> None:
    st.success("Prediction generated!")

    col1, col2, col3 = st.columns(3)
    with col1:
        normal = 60
        delta = result["expected_covers"] - normal
        st.metric("🍽️ Expected Covers", result["expected_covers"],
                  delta=f"+{delta} vs baseline" if delta >= 0 else f"{delta} vs baseline")
    with col2:
        st.metric("👥 Recommended Staff", result["recommended_staff"])
    with col3:
        conf = result["confidence"]
        st.metric("📊 Confidence", f"{conf}%",
                  delta="high" if conf > 80 else "medium")

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("🔑 Key factors")
        for f in result.get("key_factors", []):
            st.write(f"· {f}")

        st.subheader("⚡ Operational recommendations")
        for a in result.get("operational_recommendations", []):
            st.write(f"→ {a}")

    with col_r:
        st.subheader("📋 Context breakdown")

        with st.expander("PMS — Reservations", expanded=True):
            st.write(f"Occupancy: **{reservations.get('occupancy_rate', 'n/a')}%**")
            st.write(f"Expected guests: **{reservations.get('expected_guests', 'n/a')}**")
            groups = reservations.get("groups", [])
            if groups:
                for g in groups:
                    st.write(f"· Group: {g['name']} ({g['size']} guests, {g['meal_plan']})")

        if comment_signals.get("reservations_with_signals", 0):
            with st.expander("💬 Reservation comment signals"):
                if comment_signals.get("celebration_summary"):
                    st.write("**Celebrations:**", comment_signals["celebration_summary"])
                if comment_signals.get("dietary_summary"):
                    st.write("**Dietary:**", comment_signals["dietary_summary"])
                if comment_signals.get("fb_request_summary"):
                    st.write("**F&B requests:**", comment_signals["fb_request_summary"])

        if events:
            with st.expander("🎪 Local events"):
                for ev in events[:5]:
                    st.write(f"· [{ev.get('rank', '?'):>3}] {ev['title']} ({ev.get('category', '')})")

        with st.expander("🌤️ Weather"):
            st.write(weather.get("description", "n/a"))
            st.write(f"Humidity: {weather.get('humidity', 'n/a')}%  |  Source: {weather.get('source', 'n/a')}")

        if patterns:
            with st.expander("📚 Closest historical patterns"):
                for p in patterns:
                    sc = p["scenario"]
                    st.write(
                        f"**{sc['event_name']}** — {sc['actual_covers']} covers, "
                        f"{sc['staffing']} staff (similarity {p['similarity_score']:.2f})"
                    )

    st.caption(f"Method: {result.get('method', 'n/a')}")


# ── Tab 1: Text Input ─────────────────────────────────────────────────────────

with tab_text:
    st.markdown("Enter event context manually, or leave defaults for a quick demo.")

    col1, col2 = st.columns(2)
    with col1:
        events_text = st.text_area(
            "Planned Events",
            value="Coldplay concert at Stade de France, sunny evening",
            height=80,
        )
    with col2:
        weather_text = st.text_area(
            "Weather Conditions",
            value="Clear sky, 22°C",
            height=80,
        )

    if st.button("🎯 Generate Prediction", type="primary", use_container_width=True):
        date_str = str(date_input)
        with st.spinner("Agent analyzing ..."):
            try:
                if has_claude:
                    text_result = _run_mcp(date_str, location, city)
                    st.code(text_result, language=None)
                else:
                    result, reservations, fb_ctx, comment_signals, events, weather, patterns = \
                        _run_heuristic(date_str, location, city)
                    _show_results(result, reservations, fb_ctx, comment_signals,
                                  events, weather, patterns, date_str)
            except Exception as e:
                st.error(f"Error: {e}")
                st.info("Check the terminal for details.")


# ── Tab 2: Voice Input ────────────────────────────────────────────────────────

with tab_voice:
    st.markdown(
        "Speak your query and Whisper will transcribe it. "
        "Works with local Whisper model (no API key needed) "
        "or the OpenAI Whisper API if `OPENAI_API_KEY` is set."
    )

    voice_col1, voice_col2 = st.columns([2, 1])

    with voice_col1:
        uploaded = st.file_uploader(
            "Upload an audio file (WAV / MP3 / M4A / OGG)",
            type=["wav", "mp3", "m4a", "ogg", "flac"],
        )
        sample_query = st.text_input(
            "Or type to simulate voice (will be parsed the same way)",
            placeholder="What's the demand for Saturday in Paris?",
        )

    with voice_col2:
        st.markdown("**Example queries:**")
        st.caption("• Forecast for tomorrow in London")
        st.caption("• Saturday covers for Paris")
        st.caption("• December 24 dinner demand")
        st.caption("• Next Friday staffing in Berlin")

    if st.button("🎙️ Transcribe & Predict", type="primary", use_container_width=True):
        from voice_input import parse_query

        text = ""
        if uploaded:
            import tempfile, os
            suffix = "." + uploaded.name.rsplit(".", 1)[-1]
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            with st.spinner("Transcribing audio ..."):
                try:
                    from voice_input import transcribe
                    text = transcribe(tmp_path)
                    os.unlink(tmp_path)
                except RuntimeError as e:
                    st.error(str(e))
        elif sample_query:
            text = sample_query
        else:
            st.warning("Upload an audio file or type a query.")

        if text:
            st.info(f'Transcription: "{text}"')
            query = parse_query(text)
            st.write(f"Parsed → **date:** {query['date']}  |  **location:** {query['location']}")

            date_str = query["date"]
            loc      = query["location"]
            city_q   = query["city"]

            with st.spinner("Agent analyzing ..."):
                try:
                    if has_claude:
                        text_result = _run_mcp(date_str, loc, city_q)
                        st.code(text_result, language=None)
                    else:
                        result, reservations, fb_ctx, comment_signals, events, weather, patterns = \
                            _run_heuristic(date_str, loc, city_q)
                        _show_results(result, reservations, fb_ctx, comment_signals,
                                      events, weather, patterns, date_str)
                except Exception as e:
                    st.error(f"Error: {e}")
