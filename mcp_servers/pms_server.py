"""
PMS MCP Server (Property Management System)

Standalone server showing what a hotel PMS vendor (Opera, Mews, Apaleo,
Cloudbeds) would ship as their MCP server.

This is the most strategically important server: the PMS holds the full
guest journey. When it speaks MCP, AI agents can act on guest data
without staff switching between systems.

Run standalone: python mcp_servers/pms_server.py
"""

import random
import uuid
from datetime import datetime
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PMSServer")


@mcp.tool()
def get_hotel_reservations(date: str) -> dict:
    """
    Get hotel reservation summary for a date.
    Returns occupancy rate, guest count, group bookings, meal plans,
    and special requests relevant to F&B planning.

    Args:
        date: Date in YYYY-MM-DD format
    """
    day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
    base_occupancy = 0.85 if day in ["Friday", "Saturday"] else 0.70 if day == "Sunday" else 0.62
    occupancy = min(1.0, max(0.0, base_occupancy + random.uniform(-0.08, 0.08)))
    total_rooms = 120
    occupied = int(total_rooms * occupancy)

    groups = []
    if day not in ["Saturday", "Sunday"]:
        groups = [{"name": "Tech conference group", "size": 28, "meal_plan": "half-board"}]
    elif day == "Saturday":
        groups = [{"name": "Wedding party", "size": 45, "meal_plan": "full-board"}]

    return {
        "date": date,
        "day_of_week": day,
        "total_rooms": total_rooms,
        "occupied_rooms": occupied,
        "occupancy_rate": round(occupancy * 100, 1),
        "expected_guests": occupied + int(occupied * 0.15),
        "groups": groups,
        "special_requests": {
            "dietary_restrictions": random.randint(5, 20),
            "late_checkout": random.randint(3, 12),
            "early_checkin": random.randint(2, 8)
        },
        "source": "mock_pms"
    }


@mcp.tool()
def create_service_request(guest_id: str, service_type: str, notes: str = "") -> dict:
    """
    Create a service request in the PMS for a guest.
    Enables AI to book spa, room service, housekeeping, late checkout,
    and other services without staff intervention.

    Args:
        guest_id: Guest identifier (e.g. "G-1042")
        service_type: Service type — "spa", "room_service", "housekeeping",
                      "late_checkout", "restaurant_reservation", "luggage"
        notes: Additional notes or special instructions
    """
    routing = {
        "spa": "spa_desk",
        "room_service": "kitchen",
        "housekeeping": "housekeeping",
        "late_checkout": "front_desk",
        "restaurant_reservation": "restaurant_host",
        "luggage": "concierge"
    }
    ticket_id = f"SR-{uuid.uuid4().hex[:8].upper()}"
    return {
        "ticket_id": ticket_id,
        "guest_id": guest_id,
        "service_type": service_type,
        "notes": notes,
        "status": "created",
        "assigned_to": routing.get(service_type, "front_desk"),
        "created_at": datetime.now().isoformat(),
        "estimated_response_minutes": 5,
        "source": "mock_pms"
    }


@mcp.tool()
def get_guest_profile(guest_id: str) -> dict:
    """
    Get guest profile and stay history from CRM/CDP.
    Returns preferences, past stays, loyalty tier, and spend patterns.

    Args:
        guest_id: Guest identifier (e.g. "G-1042")
    """
    tiers = ["bronze", "silver", "gold", "platinum"]
    preferences = ["vegetarian", "gluten-free", "seafood allergies", "halal", "vegan"]
    return {
        "guest_id": guest_id,
        "loyalty_tier": random.choice(tiers),
        "total_stays": random.randint(1, 24),
        "avg_spend_per_stay": random.randint(200, 800),
        "preferences": random.sample(preferences, random.randint(0, 2)),
        "preferred_room_type": random.choice(["standard", "deluxe", "suite"]),
        "last_stay": "2025-11-15",
        "source": "mock_crm"
    }


@mcp.tool()
def get_fb_forecast_context(date: str) -> dict:
    """
    Get F&B-specific operational context for a date, aggregated from PMS data.
    Returns meal plan breakdown, breakfast covers, dietary restrictions by type,
    VIP guests, and group meal commitments — the exact inputs an F&B manager
    needs to plan staffing and mise en place.

    This is the PMS tool most directly relevant to F&B planning.
    It aggregates data that would otherwise require 3-4 separate PMS screens.

    Args:
        date: Date in YYYY-MM-DD format
    """
    day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
    is_weekend = day in ["Friday", "Saturday", "Sunday"]

    # Occupancy base (mirrors get_hotel_reservations logic)
    base_occupancy = 0.85 if day in ["Friday", "Saturday"] else 0.70 if day == "Sunday" else 0.62
    occupancy = min(1.0, max(0.0, base_occupancy + random.uniform(-0.05, 0.05)))
    occupied_rooms = int(120 * occupancy)

    # Meal plan breakdown — how many guests have pre-paid meals
    half_board_rooms = int(occupied_rooms * (0.30 if not is_weekend else 0.20))
    full_board_rooms = int(occupied_rooms * (0.10 if not is_weekend else 0.25))
    bb_only_rooms = occupied_rooms - half_board_rooms - full_board_rooms

    # Breakfast covers = all guests with any meal plan + some room-only guests
    breakfast_covers = int(
        (full_board_rooms + half_board_rooms) * 1.8   # avg 1.8 guests/room
        + bb_only_rooms * 1.6
        + int(bb_only_rooms * 0.25)                    # ~25% room-only still eat breakfast
    )

    # Dietary restrictions breakdown (more granular than get_hotel_reservations)
    total_dietary = random.randint(8, 25)
    dietary_breakdown = {
        "vegetarian": int(total_dietary * 0.35),
        "vegan": int(total_dietary * 0.15),
        "gluten_free": int(total_dietary * 0.20),
        "halal": int(total_dietary * 0.15),
        "seafood_allergy": int(total_dietary * 0.10),
        "other": int(total_dietary * 0.05),
    }

    # VIP guests (loyalty platinum + special flags)
    vip_count = random.randint(2, 8) if is_weekend else random.randint(1, 4)

    # Group meal commitments (pre-contracted F&B)
    group_meals = []
    if day not in ["Saturday", "Sunday"]:
        group_meals.append({
            "group": "Tech conference group",
            "size": 28,
            "meal": "dinner",
            "time": "19:30",
            "menu": "set_menu_B",
            "prepaid": True,
        })
    if day == "Saturday":
        group_meals.append({
            "group": "Wedding party",
            "size": 45,
            "meal": "dinner",
            "time": "20:00",
            "menu": "wedding_banquet",
            "prepaid": True,
        })

    # Revenue opportunity flag
    upsell_opportunity = vip_count >= 4 or len(group_meals) > 0

    return {
        "date": date,
        "day_of_week": day,
        "meal_plan_breakdown": {
            "full_board_rooms": full_board_rooms,
            "half_board_rooms": half_board_rooms,
            "bb_only_rooms": bb_only_rooms,
            "room_only_rooms": bb_only_rooms,  # alias for clarity
        },
        "expected_breakfast_covers": breakfast_covers,
        "dietary_restrictions": dietary_breakdown,
        "dietary_total": total_dietary,
        "vip_guests": vip_count,
        "group_meal_commitments": group_meals,
        "upsell_opportunity": upsell_opportunity,
        "source": "mock_pms",
    }


if __name__ == "__main__":
    mcp.run()
