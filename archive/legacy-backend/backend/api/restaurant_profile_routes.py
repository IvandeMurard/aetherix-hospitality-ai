# -*- coding: utf-8 -*-
"""Restaurant Profile API Routes - IVA-52"""

import math
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from supabase import Client

from backend.api.routes import get_supabase
from backend.models.restaurant_profile import (
    RestaurantProfileCreate,
    RestaurantProfileUpdate,
    RestaurantProfileResponse,
    StaffRecommendation,
    INDUSTRY_DEFAULTS,
)

router = APIRouter(prefix="/api/restaurant", tags=["restaurant"])


@router.get("/profiles", response_model=list[RestaurantProfileResponse])
async def list_profiles(supabase: Client = Depends(get_supabase)):
    """List all restaurant profiles"""
    response = supabase.table("restaurant_profiles").select("*").execute()
    return response.data


@router.get("/profile/by-name/{outlet_name}", response_model=RestaurantProfileResponse)
async def get_profile_by_name(
    outlet_name: str, supabase: Client = Depends(get_supabase)
):
    """Get profile by outlet name (for backward compatibility)"""
    response = (
        supabase.table("restaurant_profiles")
        .select("*")
        .eq("outlet_name", outlet_name)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return response.data[0]


@router.get("/profile/{profile_id}", response_model=RestaurantProfileResponse)
async def get_profile(
    profile_id: UUID, supabase: Client = Depends(get_supabase)
):
    """Get a specific restaurant profile"""
    response = (
        supabase.table("restaurant_profiles")
        .select("*")
        .eq("id", str(profile_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return response.data[0]


@router.post("/profile", response_model=RestaurantProfileResponse, status_code=201)
async def create_profile(
    profile: RestaurantProfileCreate,
    supabase: Client = Depends(get_supabase),
):
    """Create a new restaurant profile"""
    response = (
        supabase.table("restaurant_profiles")
        .insert(profile.model_dump())
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to create profile")
    return response.data[0]


@router.put("/profile/{profile_id}", response_model=RestaurantProfileResponse)
async def update_profile(
    profile_id: UUID,
    profile: RestaurantProfileUpdate,
    supabase: Client = Depends(get_supabase),
):
    """Update an existing restaurant profile"""
    update_data = {k: v for k, v in profile.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    response = (
        supabase.table("restaurant_profiles")
        .update(update_data)
        .eq("id", str(profile_id))
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return response.data[0]


@router.delete("/profile/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: UUID, supabase: Client = Depends(get_supabase)
):
    """Delete a restaurant profile"""
    response = (
        supabase.table("restaurant_profiles")
        .delete()
        .eq("id", str(profile_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return None


@router.get("/defaults/{restaurant_type}")
async def get_industry_defaults(restaurant_type: str):
    """Get industry default values for a restaurant type"""
    if restaurant_type not in INDUSTRY_DEFAULTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown type. Valid options: {list(INDUSTRY_DEFAULTS.keys())}",
        )
    return INDUSTRY_DEFAULTS[restaurant_type]


@router.get("/profile/{profile_id}/staff-recommendation", response_model=StaffRecommendation)
async def get_staff_recommendation(
    profile_id: UUID,
    predicted_covers: int,
    supabase: Client = Depends(get_supabase),
):
    """
    Calculate staff recommendation based on profile ratios and predicted covers.
    """
    response = (
        supabase.table("restaurant_profiles")
        .select("*")
        .eq("id", str(profile_id))
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = response.data[0]

    # Calculate raw staff needs
    raw_servers = predicted_covers / profile["covers_per_server"]
    raw_hosts = predicted_covers / profile["covers_per_host"]
    raw_runners = predicted_covers / profile["covers_per_runner"]
    raw_kitchen = predicted_covers / profile["covers_per_kitchen"]

    # Round up and apply minimums
    servers = max(math.ceil(raw_servers), profile.get("min_foh_staff", 2))
    hosts = max(math.ceil(raw_hosts), 1)
    runners = max(math.ceil(raw_runners), 0)
    kitchen = max(math.ceil(raw_kitchen), profile.get("min_boh_staff", 2))

    total_foh = servers + hosts + runners
    total_boh = kitchen

    # Generate human-readable message
    turns_dinner = profile.get("turns_dinner", 2.0)
    capacity_pct = (
        predicted_covers / (profile["total_seats"] * turns_dinner)
    ) * 100

    if capacity_pct < 50:
        intensity = "light"
    elif capacity_pct < 80:
        intensity = "moderate"
    else:
        intensity = "busy"

    breakeven = profile.get("breakeven_covers")
    if breakeven and predicted_covers < breakeven:
        message = f"Below breakeven ({breakeven} covers). Consider {servers} servers minimum to control costs."
    elif intensity == "busy":
        message = f"Busy service expected ({int(capacity_pct)}% capacity). Full team recommended."
    else:
        message = f"{intensity.capitalize()} service ({int(capacity_pct)}% capacity). Standard staffing."

    return StaffRecommendation(
        servers=servers,
        hosts=hosts,
        runners=runners,
        kitchen=kitchen,
        total_foh=total_foh,
        total_boh=total_boh,
        message=message,
    )
