"""
Legacy helpers preserved for Phase 2 re-integration.
API_URL, EXPLAINER_CONTENT, BASELINE_STATS, and helper functions.
"""

import os
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor

import requests

# Configuration (use API_URL env for local dev, e.g. http://localhost:8000)
API_URL = os.getenv("API_URL", "https://ivandemurard-fb-agent-api.hf.space")

# Explanatory content (English)
EXPLAINER_CONTENT = {
    "how_it_works": """
### How does this prediction work?

**Data source:**
- 495 historical patterns derived from a hotel dataset (119K reservations, 2015-2017)
- Each pattern captures: day of week, weather, events, holidays, actual covers

**Method:**
1. Your request (date, service) is converted into a numerical "fingerprint" (embedding)
2. Search for the 5 most similar historical patterns (cosine similarity)
3. Weighted average of covers from these patterns = prediction
4. AI generates a natural language explanation

**Current limitations:**
- Derived data (not real hotel data)
- No PMS connection (simulated occupancy)
- Weather and events are simulated
    """,
    "reliability_explanation": """
**Estimated Reliability**

Based on MAPE (Mean Absolute Percentage Error) — measures the estimated average gap between prediction and reality.

| Score | Meaning | Recommendation |
|-------|---------|----------------|
| Excellent | < 15% variance | Plan normally |
| Acceptable | 15-25% variance | Consider ±10% buffer |
| Monitor | 25-40% variance | Plan for flexibility |
| Low reliability | > 40% variance | High variance expected |

*Note: Estimated from pattern variance, not backtested on real predictions.*
    """,
    "model_diagnostics": """
**Model Diagnostics**

Advanced metrics for technical users:

**Pattern Similarity (Confidence)**
- Measures how well historical patterns match your query context
- High similarity (>90%) = patterns found are very relevant
- Low similarity (<70%) = unusual context, fewer comparable patterns

**Drift Detection**
- If Confidence drops AND MAPE spikes → patterns may be outdated
- Triggers: Confidence < 60% combined with MAPE > 40%
    """,
}

# Historical baseline (derived from patterns)
BASELINE_STATS = {
    "weekly_covers_range": (180, 320),
    "breakeven_covers": 35,
    "avg_daily_dinner": 35,
    "avg_daily_lunch": 22,
    "avg_daily_breakfast": 28,
    "patterns_count": 495,
    "data_period": "2015-2017",
}


def get_reliability_score(mape_value):
    """
    Calculate reliability score based on MAPE.
    Returns: (color, emoji, label, advice)
    """
    if mape_value is None:
        return ("gray", "", "Unknown", "Insufficient data for reliability estimate.")
    elif mape_value < 15:
        return ("green", "", "Excellent", "High reliability. Plan staffing normally.")
    elif mape_value < 25:
        return ("yellow", "", "Acceptable", "Good reliability. Consider a ±10% staffing buffer.")
    elif mape_value < 40:
        return (
            "orange",
            "",
            "Monitor",
            "Moderate variance. Plan for flexibility — have backup staff available.",
        )
    else:
        return ("red", "", "Low reliability", f"High variance expected. Consider a wider staffing range.")


def get_prediction_interval_text(interval, predicted):
    """Format prediction interval for display"""
    if interval:
        low, high = interval
        return f"Expected range: {low} – {high} covers"
    return None


def detect_drift(confidence, mape):
    """
    Detect potential model drift based on combined metrics.
    Returns alert message or None.
    """
    if confidence is None or mape is None:
        return None
    if confidence < 0.60 and mape > 40:
        return "Potential drift detected — patterns may be outdated or context is highly unusual. Manual review recommended."
    elif confidence < 0.70 and mape > 50:
        return "Model uncertainty high — consider manual validation for this prediction."
    return None


def get_factor_breakdown(reasoning: dict, predicted_covers: int) -> list:
    """
    Generate human-readable factor breakdown from reasoning data.
    Returns list of factor dicts with name, impact, icon, description.
    """
    factors = []
    patterns = reasoning.get("similar_patterns", []) or reasoning.get("patterns_used", [])
    context = reasoning.get("context_summary", {})

    if patterns:
        avg_pattern_covers = sum(p.get("actual_covers", 0) for p in patterns) / len(patterns)
        baseline_diff = predicted_covers - avg_pattern_covers
        factors.append({
            "name": "Historical baseline",
            "icon": "📊",
            "value": f"{avg_pattern_covers:.0f} covers",
            "impact": f"{baseline_diff:+.0f}",
            "description": f"Average of {len(patterns)} similar days",
        })

    weather = context.get("weather", {})
    if weather:
        weather_condition = weather.get("condition", "Clear")
        weather_impact = -3 if "rain" in weather_condition.lower() else 0
        if weather_impact != 0:
            factors.append({
                "name": "Weather",
                "icon": "🌧️" if weather_impact < 0 else "☀️",
                "value": weather_condition,
                "impact": f"{weather_impact:+.0f}",
                "description": "Rainy days typically reduce covers by 10%",
            })

    events = context.get("events", [])
    if events:
        factors.append({
            "name": "Local events",
            "icon": "🎉",
            "value": events[0] if events else "None",
            "impact": "+2",
            "description": "Events nearby can increase walk-ins",
        })
    else:
        factors.append({
            "name": "Local events",
            "icon": "📅",
            "value": "None detected",
            "impact": "±0",
            "description": "No major events affecting predictions",
        })

    factors.append({
        "name": "Day pattern",
        "icon": "📆",
        "value": "Typical for this day",
        "impact": "±0",
        "description": "Based on historical patterns for this weekday",
    })

    return factors


def get_similar_day_context(patterns: list) -> dict:
    """Get the most similar historical day for human context."""
    if not patterns:
        return None

    best = patterns[0]
    day_of_week = best.get("day_of_week") or (best.get("metadata", {}) or {}).get("day_of_week", "")
    return {
        "date": best.get("date", "Unknown"),
        "covers": best.get("actual_covers", 0),
        "similarity": best.get("similarity", 0),
        "day_of_week": day_of_week,
    }


def get_contextual_recommendation(
    predicted: int,
    range_low: int,
    range_high: int,
    breakeven: int = 35,
    reliability_label: str = "Monitor",
) -> str:
    """Generate contextual, actionable recommendation (not generic)."""
    variance = range_high - range_low

    if predicted < breakeven:
        return f"""⚠️ **Below breakeven** ({breakeven} covers)

Expected revenue may not cover costs. Consider:
- Promotional push (social media, hotel guests)
- Minimum staffing configuration
- Evaluate if service should run"""

    if variance > 30:
        return f"""📊 **Wide range expected** ({range_low}-{range_high} covers)

Staffing strategy:
- Schedule for {predicted} covers ({predicted // 20} servers)
- Have 1 server on-call for flex
- Kitchen prep for {range_high} (avoid 86s)"""

    if reliability_label == "Excellent":
        return f"""✅ **High confidence prediction**

Plan normally for {predicted} covers:
- {max(2, predicted // 20)} servers
- Standard prep levels
- No special adjustments needed"""

    return f"""💡 **Plan for {predicted} covers** (range: {range_low}-{range_high})

Staffing: {max(2, predicted // 20)} servers, {max(1, predicted // 30)} kitchen
Buffer: Consider +1 server on-call if trending up"""


def fetch_prediction(params: dict) -> dict:
    """Fetch a single prediction from API"""
    try:
        response = requests.post(
            f"{API_URL}/predict",
            json=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        data["_params"] = params
        data["_error"] = None
        return data
    except Exception as e:
        return {
            "_params": params,
            "_error": str(e),
            "predicted_covers": None,
            "confidence": None,
        }


def fetch_week_predictions(
    start_date: date, service_types: list, restaurant_id: str
) -> list:
    """Fetch predictions for a week (7 days × service types)"""
    requests_list = []
    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
        for service in service_types:
            requests_list.append({
                "restaurant_id": restaurant_id,
                "service_date": current_date.isoformat(),
                "service_type": service,
            })

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(fetch_prediction, requests_list))

    return results
