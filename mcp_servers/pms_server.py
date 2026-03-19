"""
PMS MCP Server (Property Management System) — Apaleo Integration

Connects to the Apaleo PMS API using OAuth2 client credentials.
Falls back to mock data if APALEO_CLIENT_ID / APALEO_CLIENT_SECRET
are not set, so the server works for demos without credentials.

Required env vars:
    APALEO_CLIENT_ID      OAuth2 client ID from Apaleo developer portal
    APALEO_CLIENT_SECRET  OAuth2 client secret
    APALEO_PROPERTY_ID    Property code (e.g. "MUC", "BER")

Run standalone: python mcp_servers/pms_server.py
"""

import base64
import os
import random
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PMSServer")

# ---------------------------------------------------------------------------
# Apaleo API client
# ---------------------------------------------------------------------------

APALEO_TOKEN_URL = "https://identity.apaleo.com/connect/token"
APALEO_API_BASE = "https://api.apaleo.com"


class ApaleoClient:
    """Thin Apaleo API client with cached token and graceful fallback."""

    def __init__(self) -> None:
        self.client_id = os.getenv("APALEO_CLIENT_ID", "")
        self.client_secret = os.getenv("APALEO_CLIENT_SECRET", "")
        self.property_id = os.getenv("APALEO_PROPERTY_ID", "")
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @property
    def has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret and self.property_id)

    def _get_token(self) -> str:
        """Return a valid bearer token, refreshing if expired."""
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token

        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        resp = httpx.post(
            APALEO_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 3600)
        return self._token

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        token = self._get_token()
        resp = httpx.get(
            f"{APALEO_API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, body: dict) -> dict:
        token = self._get_token()
        resp = httpx.post(
            f"{APALEO_API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


_apaleo = ApaleoClient()


# ---------------------------------------------------------------------------
# Helpers to parse Apaleo reservation objects
# ---------------------------------------------------------------------------

def _meal_plan_from_reservation(res: dict) -> str:
    """Extract meal plan code from an Apaleo reservation object."""
    rate_plan = res.get("ratePlan", {})
    meal_plan = rate_plan.get("mealPlan", "")
    # Apaleo codes: BreakfastIncluded, HalfBoard, FullBoard, AllInclusive, RoomOnly
    mapping = {
        "BreakfastIncluded": "bb",
        "HalfBoard": "half_board",
        "FullBoard": "full_board",
        "AllInclusive": "full_board",
        "RoomOnly": "room_only",
    }
    return mapping.get(meal_plan, "room_only")


def _parse_reservations(reservations: list) -> dict:
    """Aggregate a list of Apaleo reservations into summary stats."""
    in_house = [r for r in reservations if r.get("status") in ("InHouse", "Confirmed", "Arrived")]
    occupied_rooms = len(in_house)

    meal_counts: Counter = Counter()
    total_adults = 0
    dietary_requests: list[str] = []

    for r in in_house:
        meal_counts[_meal_plan_from_reservation(r)] += 1
        adults = r.get("adults", 1)
        total_adults += adults

        # Special requests / comments — look for dietary keywords
        comment = (r.get("comment", "") or "").lower()
        for tag, keyword in [
            ("vegetarian", "vegetar"),
            ("vegan", "vegan"),
            ("gluten_free", "gluten"),
            ("halal", "halal"),
            ("seafood_allergy", "seafood"),
        ]:
            if keyword in comment:
                dietary_requests.append(tag)

    groups = []
    for r in in_house:
        company = r.get("company", {})
        if company:
            groups.append({
                "name": company.get("name", "Group booking"),
                "size": r.get("adults", 1),
                "meal_plan": _meal_plan_from_reservation(r),
            })

    dietary_breakdown = Counter(dietary_requests)

    return {
        "occupied_rooms": occupied_rooms,
        "total_adults": total_adults,
        "meal_counts": dict(meal_counts),
        "dietary_breakdown": dict(dietary_breakdown),
        "groups": groups,
        "in_house_reservations": in_house,
    }


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_hotel_reservations(date: str) -> dict:
    """
    Get hotel reservation summary for a date.
    Returns occupancy rate, guest count, group bookings, meal plans,
    and special requests relevant to F&B planning.

    Pulls from Apaleo PMS if credentials are configured;
    falls back to mock data otherwise.

    Args:
        date: Date in YYYY-MM-DD format
    """
    if not _apaleo.has_credentials:
        return _mock_hotel_reservations(date)

    try:
        # Fetch reservations arriving, in-house, or departing on this date
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        next_day = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")

        data = _apaleo.get(
            "/booking/v1/reservations",
            params={
                "propertyIds": _apaleo.property_id,
                "dateFilter": "Arrival",
                "from": date,
                "to": next_day,
                "pageSize": 500,
                "expand": "ratePlan,company",
            },
        )
        reservations = data.get("reservations", [])

        # Also fetch in-house guests (staying, not just arriving)
        inhouse_data = _apaleo.get(
            "/booking/v1/reservations",
            params={
                "propertyIds": _apaleo.property_id,
                "dateFilter": "Stay",
                "from": date,
                "to": next_day,
                "pageSize": 500,
                "expand": "ratePlan,company",
            },
        )
        all_res = {r["id"]: r for r in reservations}
        for r in inhouse_data.get("reservations", []):
            all_res[r["id"]] = r
        all_reservations = list(all_res.values())

        stats = _parse_reservations(all_reservations)
        total_rooms = _get_property_room_count()
        occupied = stats["occupied_rooms"]
        occupancy = round(occupied / total_rooms * 100, 1) if total_rooms else 0.0

        day = date_obj.strftime("%A")
        return {
            "date": date,
            "day_of_week": day,
            "total_rooms": total_rooms,
            "occupied_rooms": occupied,
            "occupancy_rate": occupancy,
            "expected_guests": stats["total_adults"],
            "groups": stats["groups"],
            "special_requests": {
                "dietary_restrictions": sum(stats["dietary_breakdown"].values()),
                "late_checkout": 0,   # requires service request query
                "early_checkin": 0,
            },
            "source": "apaleo",
            "property_id": _apaleo.property_id,
        }

    except Exception as exc:
        # Return mock with error note so the agent can still function
        result = _mock_hotel_reservations(date)
        result["source"] = "mock_pms_fallback"
        result["apaleo_error"] = str(exc)
        return result


def _get_property_room_count() -> int:
    """Fetch total unit count for the property, cached per process."""
    if not hasattr(_get_property_room_count, "_cache"):
        try:
            data = _apaleo.get(f"/inventory/v1/properties/{_apaleo.property_id}")
            units = data.get("unitCount", 120)
            _get_property_room_count._cache = units
        except Exception:
            _get_property_room_count._cache = 120
    return _get_property_room_count._cache


@mcp.tool()
def create_service_request(guest_id: str, service_type: str, notes: str = "") -> dict:
    """
    Create a service request in the PMS for a guest.
    Enables AI to book spa, room service, housekeeping, late checkout,
    and other services without staff intervention.

    Args:
        guest_id: Guest identifier or reservation ID
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
        "luggage": "concierge",
    }

    # Apaleo does not have a generic "service request" endpoint in the public
    # booking API — this would require the Apaleo Housekeeping or Task API
    # (separate add-on). We create a structured ticket locally and log it.
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
        "source": "apaleo" if _apaleo.has_credentials else "mock_pms",
        "note": "Ticket logged locally; sync to Apaleo Task API requires housekeeping module.",
    }


@mcp.tool()
def get_guest_profile(guest_id: str) -> dict:
    """
    Get guest profile from a reservation ID.
    Returns primary guest name, loyalty info, and stay preferences.

    When Apaleo credentials are configured, fetches real reservation data.

    Args:
        guest_id: Apaleo reservation ID (e.g. "RES-001") or guest code
    """
    if not _apaleo.has_credentials:
        return _mock_guest_profile(guest_id)

    try:
        res = _apaleo.get(f"/booking/v1/reservations/{guest_id}")
        guest = res.get("primaryGuest", {})
        name = guest.get("firstName", "") + " " + guest.get("lastName", "")
        return {
            "guest_id": guest_id,
            "name": name.strip(),
            "email": guest.get("email", ""),
            "loyalty_tier": "unknown",  # Apaleo doesn't have loyalty natively
            "total_stays": 1,
            "meal_plan": _meal_plan_from_reservation(res),
            "arrival": res.get("arrival", ""),
            "departure": res.get("departure", ""),
            "adults": res.get("adults", 1),
            "children": res.get("childrenAges", []),
            "comment": res.get("comment", ""),
            "source": "apaleo",
        }
    except Exception as exc:
        result = _mock_guest_profile(guest_id)
        result["source"] = "mock_crm_fallback"
        result["apaleo_error"] = str(exc)
        return result


@mcp.tool()
def get_fb_forecast_context(date: str) -> dict:
    """
    Get F&B-specific operational context for a date, aggregated from PMS data.
    Returns meal plan breakdown, breakfast covers, dietary restrictions by type,
    VIP guests, and group meal commitments — the exact inputs an F&B manager
    needs to plan staffing and mise en place.

    Pulls from Apaleo PMS if credentials are configured;
    falls back to mock data otherwise.

    Args:
        date: Date in YYYY-MM-DD format
    """
    if not _apaleo.has_credentials:
        return _mock_fb_forecast_context(date)

    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        next_day = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")

        data = _apaleo.get(
            "/booking/v1/reservations",
            params={
                "propertyIds": _apaleo.property_id,
                "dateFilter": "Stay",
                "from": date,
                "to": next_day,
                "pageSize": 500,
                "expand": "ratePlan,company",
            },
        )
        reservations = data.get("reservations", [])
        stats = _parse_reservations(reservations)

        mc = stats["meal_counts"]
        full_board = mc.get("full_board", 0)
        half_board = mc.get("half_board", 0)
        bb_only = mc.get("bb", 0)
        room_only = mc.get("room_only", 0)

        # Breakfast covers: full-board + half-board guests always eat breakfast.
        # B&B guests eat breakfast. ~25% of room-only guests eat à la carte.
        avg_guests_per_room = (
            stats["total_adults"] / len(reservations) if reservations else 1.8
        )
        breakfast_covers = int(
            (full_board + half_board + bb_only) * avg_guests_per_room
            + room_only * avg_guests_per_room * 0.25
        )

        db = stats["dietary_breakdown"]
        dietary_total = sum(db.values())
        # Fill in zeros for categories not found in comments
        dietary_breakdown = {
            "vegetarian": db.get("vegetarian", 0),
            "vegan": db.get("vegan", 0),
            "gluten_free": db.get("gluten_free", 0),
            "halal": db.get("halal", 0),
            "seafood_allergy": db.get("seafood_allergy", 0),
            "other": max(0, dietary_total - sum(db.values())),
        }

        # VIP = guests with "VIP" flag in Apaleo (vipCode field)
        vip_count = sum(
            1 for r in reservations
            if r.get("primaryGuest", {}).get("vipCode")
        )

        # Group meal commitments from company-linked reservations
        group_meals = []
        seen_companies: set = set()
        for r in reservations:
            company = r.get("company", {})
            if company and company.get("name") not in seen_companies:
                seen_companies.add(company.get("name"))
                group_meals.append({
                    "group": company.get("name", "Group booking"),
                    "size": r.get("adults", 1),
                    "meal": "dinner",
                    "time": "19:30",
                    "menu": "set_menu",
                    "prepaid": _meal_plan_from_reservation(r) in ("half_board", "full_board"),
                })

        upsell_opportunity = vip_count >= 4 or len(group_meals) > 0

        return {
            "date": date,
            "day_of_week": date_obj.strftime("%A"),
            "meal_plan_breakdown": {
                "full_board_rooms": full_board,
                "half_board_rooms": half_board,
                "bb_only_rooms": bb_only,
                "room_only_rooms": room_only,
            },
            "expected_breakfast_covers": breakfast_covers,
            "dietary_restrictions": dietary_breakdown,
            "dietary_total": dietary_total,
            "vip_guests": vip_count,
            "group_meal_commitments": group_meals,
            "upsell_opportunity": upsell_opportunity,
            "total_reservations": len(reservations),
            "source": "apaleo",
            "property_id": _apaleo.property_id,
        }

    except Exception as exc:
        result = _mock_fb_forecast_context(date)
        result["source"] = "mock_pms_fallback"
        result["apaleo_error"] = str(exc)
        return result


# ---------------------------------------------------------------------------
# Mock fallbacks (kept so the server works without credentials)
# ---------------------------------------------------------------------------

def _mock_hotel_reservations(date: str) -> dict:
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
            "early_checkin": random.randint(2, 8),
        },
        "source": "mock_pms",
    }


def _mock_guest_profile(guest_id: str) -> dict:
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
        "source": "mock_crm",
    }


def _mock_fb_forecast_context(date: str) -> dict:
    day = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
    is_weekend = day in ["Friday", "Saturday", "Sunday"]
    base_occupancy = 0.85 if day in ["Friday", "Saturday"] else 0.70 if day == "Sunday" else 0.62
    occupancy = min(1.0, max(0.0, base_occupancy + random.uniform(-0.05, 0.05)))
    occupied_rooms = int(120 * occupancy)
    half_board_rooms = int(occupied_rooms * (0.30 if not is_weekend else 0.20))
    full_board_rooms = int(occupied_rooms * (0.10 if not is_weekend else 0.25))
    bb_only_rooms = occupied_rooms - half_board_rooms - full_board_rooms
    breakfast_covers = int(
        (full_board_rooms + half_board_rooms) * 1.8
        + bb_only_rooms * 1.6
        + int(bb_only_rooms * 0.25)
    )
    total_dietary = random.randint(8, 25)
    dietary_breakdown = {
        "vegetarian": int(total_dietary * 0.35),
        "vegan": int(total_dietary * 0.15),
        "gluten_free": int(total_dietary * 0.20),
        "halal": int(total_dietary * 0.15),
        "seafood_allergy": int(total_dietary * 0.10),
        "other": int(total_dietary * 0.05),
    }
    vip_count = random.randint(2, 8) if is_weekend else random.randint(1, 4)
    group_meals = []
    if day not in ["Saturday", "Sunday"]:
        group_meals.append({"group": "Tech conference group", "size": 28, "meal": "dinner",
                            "time": "19:30", "menu": "set_menu_B", "prepaid": True})
    if day == "Saturday":
        group_meals.append({"group": "Wedding party", "size": 45, "meal": "dinner",
                            "time": "20:00", "menu": "wedding_banquet", "prepaid": True})
    return {
        "date": date,
        "day_of_week": day,
        "meal_plan_breakdown": {
            "full_board_rooms": full_board_rooms,
            "half_board_rooms": half_board_rooms,
            "bb_only_rooms": bb_only_rooms,
            "room_only_rooms": bb_only_rooms,
        },
        "expected_breakfast_covers": breakfast_covers,
        "dietary_restrictions": dietary_breakdown,
        "dietary_total": total_dietary,
        "vip_guests": vip_count,
        "group_meal_commitments": group_meals,
        "upsell_opportunity": vip_count >= 4 or len(group_meals) > 0,
        "source": "mock_pms",
    }


if __name__ == "__main__":
    mcp.run()
