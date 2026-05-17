"""
generate_demo_data.py — Synthetic Prophet training dataset (Decision #11).

Generates 365 days of dinner-service cover data for a simulated Paris 4*
hotel and writes the result to demo_data/prophet_training.json.

Output format: list of dicts ready for pd.DataFrame — the same structure
expected by PredictionEngine.train():

    [{"ds": "2025-01-01", "y": 62, "weather_score": 0.3,
      "event_impact": 0.0, "occupancy": 0.65}, ...]

Usage:
    python scripts/generate_demo_data.py
    # → demo_data/prophet_training.json

Environment:
    DEMO_DATA_SEED   — integer seed for reproducibility (default: 42)
    DEMO_DATA_YEAR   — base year for the dataset (default: 2025)
"""
from __future__ import annotations

import json
import math
import os
import random
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SEED = int(os.getenv("DEMO_DATA_SEED", "42"))
BASE_YEAR = int(os.getenv("DEMO_DATA_YEAR", "2025"))
OUTPUT_PATH = Path(__file__).parent.parent.parent / "backend" / "data" / "demo" / "prophet_training.json"

# Baseline dinner covers for a Paris 4* (60–80 range)
BASE_COVERS = 68

# 12 fictitious events with (month, day, duration_days, cover_impact_pct)
EVENTS = [
    # Concerts / shows
    (1, 18, 2, +0.30),   # Salon de la Gastronomie (fictif)
    (2, 14, 1, +0.25),   # Saint-Valentin
    (3, 22, 3, +0.20),   # Salon du Livre (fictif)
    (4, 12, 2, +0.18),   # Marathon de Paris
    (5,  1, 1, +0.22),   # Fête du Travail (restaurant plein)
    (6, 21, 2, +0.28),   # Fête de la Musique weekend
    (7, 14, 1, +0.35),   # Fête Nationale
    (8, 15, 2, +0.15),   # Assomption — touristes
    (9, 20, 3, +0.25),   # Fashion Week (début)
    (10, 5, 2, +0.20),   # Nuit Blanche Paris
    (11, 11, 1, +0.12),  # Armistice
    (12, 31, 1, +0.50),  # Saint-Sylvestre
]


def _build_event_map(year: int) -> dict[date, float]:
    """Return {date: impact_multiplier} for all event days."""
    event_map: dict[date, float] = {}
    for month, day, duration, impact in EVENTS:
        try:
            start = date(year, month, day)
        except ValueError:
            continue
        for i in range(duration):
            d = start + timedelta(days=i)
            # Events can stack (e.g. holiday + event): take the max impact
            event_map[d] = max(event_map.get(d, 0.0), impact)
    return event_map


def _seasonality(d: date) -> float:
    """Return a multiplicative seasonal factor for the date."""
    # Summer peak: July–August → +30%
    if d.month in (7, 8):
        return 1.30
    # Christmas / New Year: Dec 20 – Jan 3 → +20%
    if (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 3):
        return 1.20
    # Shoulder seasons (spring/autumn) — slight boost
    if d.month in (4, 5, 9, 10):
        return 1.10
    # Low season (Jan rest, Feb, Nov)
    if d.month in (1, 2, 11):
        return 0.88
    return 1.00


def _weekly_multiplier(d: date) -> float:
    """Return multiplicative day-of-week factor (Mon=0 … Sun=6)."""
    dow = d.weekday()
    if dow == 0:    # Monday
        return 0.80
    if dow == 1:    # Tuesday
        return 0.85
    if dow in (4,): # Friday
        return 1.25
    if dow == 5:    # Saturday
        return 1.25
    if dow == 6:    # Sunday
        return 1.08
    return 1.00     # Wednesday / Thursday


def _weather_score(d: date) -> float:
    """Approximate seasonal weather pleasantness [0, 1]."""
    # Simple sinusoidal: peaks in summer (month 7), troughs in winter
    return round(0.5 + 0.4 * math.sin(math.pi * (d.month - 1) / 6 - math.pi / 2), 2)


def _occupancy(d: date, season: float) -> float:
    """Hotel occupancy rate correlated with seasonality + noise."""
    base = min(0.95, 0.60 + (season - 0.88) * 1.5)
    jitter = random.gauss(0, 0.04)
    return round(max(0.30, min(0.98, base + jitter)), 2)


def generate(year: int, seed: int) -> list[dict]:
    random.seed(seed)
    event_map = _build_event_map(year)

    rows = []
    start = date(year, 1, 1)
    for i in range(365):
        d = start + timedelta(days=i)

        season = _seasonality(d)
        weekly = _weekly_multiplier(d)
        event_impact = event_map.get(d, 0.0)
        weather = _weather_score(d)
        occ = _occupancy(d, season)

        # Covers = base × season × weekly × (1 + event_impact) + noise
        covers_raw = (
            BASE_COVERS
            * season
            * weekly
            * (1.0 + event_impact)
            * (0.85 + 0.30 * occ)   # occupancy pulls covers up
        )
        noise = random.gauss(0, covers_raw * 0.06)  # ±6% noise
        covers = max(10, int(round(covers_raw + noise)))

        rows.append(
            {
                "ds": d.isoformat(),
                "y": covers,
                "weather_score": weather,
                "event_impact": round(event_impact, 2),
                "occupancy": occ,
            }
        )

    return rows


def main() -> None:
    data = generate(BASE_YEAR, SEED)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    total = sum(r["y"] for r in data)
    print(
        f"Generated {len(data)} days → {OUTPUT_PATH}\n"
        f"  covers/day: min={min(r['y'] for r in data)}, "
        f"max={max(r['y'] for r in data)}, "
        f"avg={total // len(data)}"
    )


if __name__ == "__main__":
    main()
