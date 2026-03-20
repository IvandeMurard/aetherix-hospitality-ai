"""
Voice Input — Whisper STT for the F&B Operations Agent

Transcribes spoken queries ("What's the demand forecast for Saturday?")
into text, which is then passed to the agent pipeline.

Backends (chosen automatically):
  1. openai-whisper  — local model, no API key, runs on CPU (tiny/base model)
  2. OpenAI Whisper API — faster, requires OPENAI_API_KEY
  Fallback: manual text input if no audio library is available

Usage:
    python voice_input.py                     # record mic → transcribe → run agent
    python voice_input.py --file query.wav    # transcribe audio file → run agent
    python voice_input.py --text              # type query (no mic required)
    python voice_input.py --demo              # show what the module can do without recording
"""

import argparse
import os
import sys
import tempfile
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Audio recording
# ---------------------------------------------------------------------------

def record_audio(seconds: int = 5, sample_rate: int = 16000) -> str:
    """Record from default microphone for `seconds` seconds. Returns wav path."""
    try:
        import sounddevice as sd
        import scipy.io.wavfile as wav
        import numpy as np
    except ImportError:
        raise RuntimeError(
            "sounddevice / scipy not installed. "
            "Run: pip install sounddevice scipy"
        )

    print(f"  Recording {seconds}s ... (speak now)")
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate,
                   channels=1, dtype="int16")
    sd.wait()
    print("  Recording complete.")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav.write(tmp.name, sample_rate, audio)
    return tmp.name


# ---------------------------------------------------------------------------
# Transcription backends
# ---------------------------------------------------------------------------

def _transcribe_local(audio_path: str, model_size: str = "base") -> str:
    """Transcribe using local openai-whisper model (CPU-friendly)."""
    try:
        import whisper
    except ImportError:
        raise RuntimeError(
            "openai-whisper not installed. "
            "Run: pip install openai-whisper"
        )
    print(f"  Loading Whisper '{model_size}' (local) ...")
    model = whisper.load_model(model_size)
    result = model.transcribe(audio_path, fp16=False, language="en")
    return result["text"].strip()


def _transcribe_openai_api(audio_path: str) -> str:
    """Transcribe using the OpenAI Whisper API."""
    import openai
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", file=f
        )
    return transcript.text.strip()


def transcribe(audio_path: str) -> str:
    """
    Transcribe audio file to text.
    Tries OpenAI API first (faster), falls back to local Whisper.
    """
    if os.getenv("OPENAI_API_KEY"):
        try:
            print("  Transcribing via OpenAI Whisper API ...")
            return _transcribe_openai_api(audio_path)
        except Exception as e:
            print(f"  OpenAI API failed ({e}), falling back to local Whisper ...")

    return _transcribe_local(audio_path)


# ---------------------------------------------------------------------------
# Query parsing — extract date + location from transcribed text
# ---------------------------------------------------------------------------

import re

_DAYS = {
    "today": 0, "tonight": 0,
    "tomorrow": 1,
    "monday": None, "tuesday": None, "wednesday": None, "thursday": None,
    "friday": None, "saturday": None, "sunday": None,
}


def parse_query(text: str) -> dict:
    """
    Extract date and location from a natural-language query.

    Examples:
      "What's the demand forecast for Saturday in Paris?"
        → {date: next Saturday, location: "Paris, France"}
      "How many covers for tomorrow in London?"
        → {date: tomorrow, location: "London, UK"}
      "Forecast for December 24"
        → {date: 2026-12-24, location: "Paris, France"}
    """
    text_lower = text.lower()
    today = datetime.now().date()

    # ── Date extraction ──────────────────────────────────────────
    date = None

    # Explicit YYYY-MM-DD
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        date = m.group(1)

    # "December 24" / "24 December" / "Dec 24"
    if not date:
        months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                  "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
        m = re.search(
            r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
            r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
            r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})\b",
            text_lower
        )
        if not m:
            m = re.search(
                r"\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
                r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
                r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
                text_lower
            )
            if m:
                day_num, mon_str = int(m.group(1)), m.group(2)[:3]
            else:
                day_num, mon_str = None, None
        else:
            mon_str, day_num = m.group(1)[:3], int(m.group(2))

        if mon_str and day_num:
            year = today.year
            candidate = datetime(year, months[mon_str], day_num).date()
            if candidate < today:
                candidate = datetime(year + 1, months[mon_str], day_num).date()
            date = candidate.strftime("%Y-%m-%d")

    # Relative days (today, tomorrow, next Saturday, …)
    if not date:
        for word, offset in _DAYS.items():
            if word in text_lower:
                if offset is not None:
                    date = (today + timedelta(days=offset)).strftime("%Y-%m-%d")
                else:
                    # Named weekday — find next occurrence
                    target_wd = list(_DAYS.keys()).index(word) - 2  # mon=0
                    current_wd = today.weekday()
                    days_ahead = (target_wd - current_wd) % 7 or 7
                    date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                break

    date = date or (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # ── Location extraction ───────────────────────────────────────
    location = "Paris, France"
    city = "Paris"

    cities = {
        "paris": ("Paris, France", "Paris"),
        "london": ("London, UK", "London"),
        "new york": ("New York, USA", "New York"),
        "berlin": ("Berlin, Germany", "Berlin"),
        "amsterdam": ("Amsterdam, Netherlands", "Amsterdam"),
        "madrid": ("Madrid, Spain", "Madrid"),
        "rome": ("Rome, Italy", "Rome"),
        "barcelona": ("Barcelona, Spain", "Barcelona"),
        "lisbon": ("Lisbon, Portugal", "Lisbon"),
        "dubai": ("Dubai, UAE", "Dubai"),
    }
    for name, (loc, c) in cities.items():
        if name in text_lower:
            location, city = loc, c
            break

    return {"date": date, "location": location, "city": city, "raw_query": text}


# ---------------------------------------------------------------------------
# Integration with the agent
# ---------------------------------------------------------------------------

def voice_to_prediction(audio_path: str | None = None,
                         record_seconds: int = 6) -> None:
    """Full pipeline: audio → transcribe → parse → run scenario."""
    if audio_path:
        print(f"  Audio file: {audio_path}")
        text = transcribe(audio_path)
    else:
        audio_path = record_audio(seconds=record_seconds)
        text = transcribe(audio_path)
        os.unlink(audio_path)

    print(f"\n  Transcription: \"{text}\"")
    query = parse_query(text)
    print(f"  Parsed  — date: {query['date']} | location: {query['location']}")
    print()

    # Hand off to the scenario runner
    import subprocess
    import re as _re
    date_val     = query["date"]
    location_val = query["location"]
    city_val     = query["city"]

    # Validate before passing to subprocess (date comes from datetime so always clean;
    # location/city come from a whitelist dict — this is a belt-and-suspenders check).
    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_val):
        raise ValueError(f"Unexpected date format from parse_query: {date_val!r}")
    if not _re.fullmatch(r"[\w ,.\-]+", location_val) or len(location_val) > 100:
        raise ValueError(f"Unexpected location value from parse_query: {location_val!r}")
    if not _re.fullmatch(r"[\w .\-]+", city_val) or len(city_val) > 50:
        raise ValueError(f"Unexpected city value from parse_query: {city_val!r}")

    subprocess.run([
        sys.executable, "run_scenario.py",
        "--date", date_val,
        "--location", location_val,
        "--city", city_val,
    ], check=False)


# ---------------------------------------------------------------------------
# Demo (no mic / no API key needed)
# ---------------------------------------------------------------------------

def demo() -> None:
    """Show query parsing on sample phrases."""
    samples = [
        "What's the forecast for Saturday in Paris?",
        "How many covers do we need for tomorrow in London?",
        "Predict demand for December 24",
        "Tonight's staffing recommendation",
        "Give me the forecast for next Friday",
    ]
    print("\n  Query Parser Demo")
    print("  " + "─" * 50)
    for s in samples:
        q = parse_query(s)
        print(f"  Query   : \"{s}\"")
        print(f"  → date  : {q['date']}  location: {q['location']}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voice input — Whisper STT → F&B agent"
    )
    parser.add_argument("--file", help="Path to an audio file to transcribe")
    parser.add_argument("--text", action="store_true",
                        help="Type the query instead of recording")
    parser.add_argument("--demo", action="store_true",
                        help="Run query-parsing demo (no mic needed)")
    parser.add_argument("--seconds", type=int, default=6,
                        help="Recording duration in seconds (default 6)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  VOICE INPUT  —  Whisper STT")
    print("=" * 60)

    if args.demo:
        demo()
        return

    if args.text:
        text = input("\n  Enter your query: ").strip()
        if not text:
            print("  No input. Exiting.")
            return
        query = parse_query(text)
        print(f"\n  Parsed — date: {query['date']} | location: {query['location']}")
        print()
        import subprocess, re as _re
        date_val     = query["date"]
        location_val = query["location"]
        city_val     = query["city"]
        if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_val):
            raise ValueError(f"Unexpected date: {date_val!r}")
        if not _re.fullmatch(r"[\w ,.\-]+", location_val) or len(location_val) > 100:
            raise ValueError(f"Unexpected location: {location_val!r}")
        if not _re.fullmatch(r"[\w .\-]+", city_val) or len(city_val) > 50:
            raise ValueError(f"Unexpected city: {city_val!r}")
        subprocess.run([
            sys.executable, "run_scenario.py",
            "--date", date_val,
            "--location", location_val,
            "--city", city_val,
        ], check=False)
        return

    if args.file:
        voice_to_prediction(audio_path=args.file)
    else:
        voice_to_prediction(record_seconds=args.seconds)


if __name__ == "__main__":
    main()
