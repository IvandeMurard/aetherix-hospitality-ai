"""
Derive F&B covers patterns from Hotel Booking dataset
Transforms hotel reservations into realistic F&B demand data
"""

import pandas as pd
import numpy as np
import json
import random
import sys
import io
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict

# Configure UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_PATH = DATA_DIR / "raw" / "hotel_bookings.csv"
OUTPUT_PATH = DATA_DIR / "processed" / "patterns.json"

# Ensure output directory exists
(DATA_DIR / "processed").mkdir(parents=True, exist_ok=True)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Meal plan impact on F&B covers (what % of guests dine at hotel restaurant)
MEAL_PLAN_FACTORS = {
    "BB": 0.25,    # Bed & Breakfast - mostly breakfast, some dinner
    "HB": 0.70,    # Half Board - breakfast + dinner included
    "FB": 1.00,    # Full Board - all meals included
    "SC": 0.15,    # Self Catering - occasional dining
    "Undefined": 0.20
}

# Day type multipliers
DAY_TYPE_FACTORS = {
    "weekend": 1.20,    # Sat-Sun: more leisure dining
    "friday": 1.15,     # Friday: pre-weekend boost
    "weekday": 1.00     # Mon-Thu: baseline
}

# Service type distribution (what % of daily covers per service)
SERVICE_DISTRIBUTION = {
    "breakfast": 0.35,
    "lunch": 0.25,
    "dinner": 0.40
}

# Weather conditions (simulated based on month)
WEATHER_BY_MONTH = {
    1: {"conditions": ["Clear", "Cloudy", "Rain"], "weights": [0.3, 0.4, 0.3], "temp_range": (5, 12)},
    2: {"conditions": ["Clear", "Cloudy", "Rain"], "weights": [0.3, 0.4, 0.3], "temp_range": (6, 14)},
    3: {"conditions": ["Clear", "Partly Cloudy", "Rain"], "weights": [0.4, 0.4, 0.2], "temp_range": (10, 18)},
    4: {"conditions": ["Clear", "Partly Cloudy", "Rain"], "weights": [0.5, 0.3, 0.2], "temp_range": (12, 20)},
    5: {"conditions": ["Clear", "Partly Cloudy", "Cloudy"], "weights": [0.6, 0.3, 0.1], "temp_range": (16, 24)},
    6: {"conditions": ["Clear", "Partly Cloudy", "Hot"], "weights": [0.7, 0.2, 0.1], "temp_range": (20, 30)},
    7: {"conditions": ["Clear", "Hot", "Partly Cloudy"], "weights": [0.6, 0.3, 0.1], "temp_range": (22, 35)},
    8: {"conditions": ["Clear", "Hot", "Partly Cloudy"], "weights": [0.6, 0.3, 0.1], "temp_range": (22, 34)},
    9: {"conditions": ["Clear", "Partly Cloudy", "Rain"], "weights": [0.5, 0.3, 0.2], "temp_range": (18, 28)},
    10: {"conditions": ["Clear", "Cloudy", "Rain"], "weights": [0.4, 0.3, 0.3], "temp_range": (14, 22)},
    11: {"conditions": ["Cloudy", "Rain", "Clear"], "weights": [0.4, 0.3, 0.3], "temp_range": (8, 16)},
    12: {"conditions": ["Cloudy", "Rain", "Clear"], "weights": [0.4, 0.4, 0.2], "temp_range": (5, 12)}
}

# Event types and probability by day type
EVENT_CONFIG = {
    "weekend": {"probability": 0.4, "types": ["Concert", "Sports Match", "Festival", "Market"]},
    "friday": {"probability": 0.3, "types": ["Concert", "Theater", "Sports Match"]},
    "weekday": {"probability": 0.15, "types": ["Conference", "Business Event", "Theater"]}
}

# Holidays (month, day) -> name
HOLIDAYS = {
    (1, 1): "New Year's Day",
    (12, 24): "Christmas Eve",
    (12, 25): "Christmas",
    (12, 31): "New Year's Eve",
    (7, 14): "Bastille Day",  # French national holiday
    (11, 11): "Armistice Day"
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_day_type(weekday: int) -> str:
    """Convert weekday number to day type"""
    if weekday >= 5:  # Saturday=5, Sunday=6
        return "weekend"
    elif weekday == 4:  # Friday
        return "friday"
    return "weekday"


def get_weather(month: int, seed: int) -> Dict:
    """Generate deterministic weather based on month"""
    random.seed(seed)
    config = WEATHER_BY_MONTH[month]
    condition = random.choices(config["conditions"], weights=config["weights"])[0]
    temp = random.randint(*config["temp_range"])
    return {
        "condition": condition,
        "temperature": temp,
        "humidity": random.randint(40, 80)
    }


def get_events(day_type: str, seed: int) -> List[Dict]:
    """Generate deterministic events based on day type"""
    random.seed(seed)
    config = EVENT_CONFIG[day_type]
    
    if random.random() > config["probability"]:
        return []
    
    event_type = random.choice(config["types"])
    return [{
        "type": event_type,
        "name": f"{event_type} Event",
        "distance_km": round(random.uniform(0.5, 5.0), 1),
        "attendance": random.randint(500, 5000)
    }]


def check_holiday(month: int, day: int) -> tuple:
    """Check if date is a holiday"""
    key = (month, day)
    if key in HOLIDAYS:
        return True, HOLIDAYS[key]
    return False, None


def calculate_covers(
    guests: int,
    meal_plan: str,
    day_type: str,
    is_holiday: bool,
    holiday_name: str,
    weather: Dict,
    events: List[Dict]
) -> int:
    """Calculate F&B covers based on all factors"""
    
    # Base: guests × meal plan factor
    meal_factor = MEAL_PLAN_FACTORS.get(meal_plan, 0.20)
    base_covers = guests * meal_factor
    
    # Day type adjustment
    day_factor = DAY_TYPE_FACTORS[day_type]
    covers = base_covers * day_factor
    
    # Holiday adjustments
    if is_holiday:
        if holiday_name in ["Christmas Eve", "Christmas"]:
            covers *= 0.4  # Very quiet
        elif holiday_name == "New Year's Eve":
            covers *= 1.8  # Very busy
        elif holiday_name == "New Year's Day":
            covers *= 0.5  # Recovery day
        else:
            covers *= 0.7  # Other holidays slightly quieter
    
    # Weather adjustments
    if weather["condition"] == "Rain":
        covers *= 0.92  # -8%
    elif weather["condition"] == "Heavy Rain":
        covers *= 0.85  # -15%
    elif weather["condition"] == "Hot" and weather["temperature"] > 32:
        covers *= 0.95  # Very hot = less dining
    
    # Event boost
    for event in events:
        if event["distance_km"] < 2:
            covers *= 1.15  # +15% for nearby events
        elif event["distance_km"] < 5:
            covers *= 1.08  # +8% for events within 5km
    
    return max(10, int(round(covers)))  # Minimum 10 covers


# =============================================================================
# MAIN PROCESSING
# =============================================================================

def process_dataset() -> List[Dict]:
    """Process hotel bookings into F&B patterns"""
    
    print("Loading dataset...")
    df = pd.read_csv(RAW_PATH)
    
    # Filter: only non-canceled bookings
    df = df[df['is_canceled'] == 0].copy()
    print(f"Non-canceled bookings: {len(df):,}")
    
    # Create proper date column
    df['arrival_date'] = pd.to_datetime(
        df['arrival_date_year'].astype(str) + '-' +
        df['arrival_date_month'] + '-' +
        df['arrival_date_day_of_month'].astype(str),
        format='%Y-%B-%d'
    )
    
    # Calculate total guests
    df['total_guests'] = df['adults'] + df['children'].fillna(0) + df['babies'].fillna(0)
    
    # Aggregate by date
    print("Aggregating by date...")
    daily = df.groupby('arrival_date').agg({
        'total_guests': 'sum',
        'meal': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'BB',  # Most common meal plan
        'hotel': 'first',
        'adr': 'mean'  # Average daily rate
    }).reset_index()
    
    print(f"Unique dates: {len(daily):,}")
    
    # Generate patterns
    print("Generating F&B patterns...")
    patterns = []
    
    for _, row in daily.iterrows():
        date_obj = row['arrival_date']
        month = date_obj.month
        day = date_obj.day
        weekday = date_obj.weekday()
        
        # Deterministic seed based on date
        seed = date_obj.toordinal()
        
        # Get context
        day_type = get_day_type(weekday)
        weather = get_weather(month, seed)
        events = get_events(day_type, seed)
        is_holiday, holiday_name = check_holiday(month, day)
        
        # Calculate covers for each service type
        total_guests = int(row['total_guests'])
        meal_plan = row['meal']
        
        for service_type, service_ratio in SERVICE_DISTRIBUTION.items():
            # Adjust guests for service type
            service_guests = int(total_guests * service_ratio)
            
            covers = calculate_covers(
                guests=service_guests,
                meal_plan=meal_plan,
                day_type=day_type,
                is_holiday=is_holiday,
                holiday_name=holiday_name,
                weather=weather,
                events=events
            )
            
            # Skip very low cover entries
            if covers < 15:
                continue
            
            pattern = {
                "pattern_id": f"pat_{len(patterns)+1:05d}",
                "date": date_obj.strftime("%Y-%m-%d"),
                "day_of_week": date_obj.strftime("%A"),
                "service_type": service_type,
                "hotel_type": row['hotel'],
                "hotel_occupancy": round(min(1.0, total_guests / 200), 2),  # Assume 200 capacity
                "guests_in_house": total_guests,
                "actual_covers": covers,
                "meal_plan_dominant": meal_plan,
                "adr": round(row['adr'], 2) if pd.notna(row['adr']) else 100.0,
                "weather": weather,
                "events": events,
                "is_holiday": is_holiday,
                "holiday_name": holiday_name,
                "day_type": day_type
            }
            
            patterns.append(pattern)
    
    print(f"Total patterns generated: {len(patterns):,}")
    return patterns


def save_patterns(patterns: List[Dict], max_patterns: int = 500):
    """Save patterns to JSON, sampling if needed"""
    
    if len(patterns) > max_patterns:
        print(f"Sampling {max_patterns} patterns from {len(patterns)}...")
        # Stratified sampling by service_type and day_type
        df = pd.DataFrame(patterns)
        sampled = df.groupby(['service_type', 'day_type'], group_keys=False).apply(
            lambda x: x.sample(min(len(x), max_patterns // 9), random_state=42)
        )
        patterns = sampled.to_dict('records')
    
    print(f"Saving {len(patterns)} patterns to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)
    
    print("[OK] Patterns saved successfully!")
    
    # Summary statistics
    df = pd.DataFrame(patterns)
    print("\n" + "=" * 60)
    print("PATTERN SUMMARY")
    print("=" * 60)
    print(f"\nTotal patterns: {len(patterns)}")
    print(f"\nBy service type:")
    print(df['service_type'].value_counts().to_string())
    print(f"\nBy day type:")
    print(df['day_type'].value_counts().to_string())
    print(f"\nCovers statistics:")
    print(f"   Min: {df['actual_covers'].min()}")
    print(f"   Max: {df['actual_covers'].max()}")
    print(f"   Mean: {df['actual_covers'].mean():.1f}")
    print(f"   Median: {df['actual_covers'].median():.1f}")
    print("=" * 60)


if __name__ == "__main__":
    patterns = process_dataset()
    save_patterns(patterns, max_patterns=500)
