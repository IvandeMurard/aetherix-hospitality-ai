# -*- coding: utf-8 -*-
"""Restaurant Profile Models"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class RestaurantProfileBase(BaseModel):
    """Base model for restaurant profile"""
    property_name: str = Field(..., min_length=1, max_length=255)
    outlet_name: str = Field(..., min_length=1, max_length=255)
    outlet_type: str = Field(default="restaurant")

    # Capacity
    total_seats: int = Field(..., gt=0)
    turns_breakfast: float = Field(default=1.0, ge=0)
    turns_lunch: float = Field(default=1.5, ge=0)
    turns_dinner: float = Field(default=2.0, ge=0)

    # Business Thresholds
    breakeven_covers: Optional[int] = Field(default=None, ge=0)
    target_covers: Optional[int] = Field(default=None, ge=0)
    average_ticket: Optional[float] = Field(default=None, ge=0)
    labor_cost_target_pct: Optional[float] = Field(default=None, ge=0, le=100)

    # Staffing Ratios
    covers_per_server: int = Field(default=16, gt=0)
    covers_per_host: int = Field(default=60, gt=0)
    covers_per_runner: int = Field(default=40, gt=0)
    covers_per_kitchen: int = Field(default=30, gt=0)
    min_foh_staff: int = Field(default=2, ge=1)
    min_boh_staff: int = Field(default=2, ge=1)

    # Hourly Rates (optional)
    rate_server: Optional[float] = Field(default=None, ge=0)
    rate_host: Optional[float] = Field(default=None, ge=0)
    rate_runner: Optional[float] = Field(default=None, ge=0)
    rate_kitchen: Optional[float] = Field(default=None, ge=0)


class RestaurantProfileCreate(RestaurantProfileBase):
    """Model for creating a new profile"""
    pass


class RestaurantProfileUpdate(BaseModel):
    """Model for updating a profile (all fields optional)"""
    property_name: Optional[str] = None
    outlet_name: Optional[str] = None
    outlet_type: Optional[str] = None
    total_seats: Optional[int] = Field(default=None, gt=0)
    turns_breakfast: Optional[float] = Field(default=None, ge=0)
    turns_lunch: Optional[float] = Field(default=None, ge=0)
    turns_dinner: Optional[float] = Field(default=None, ge=0)
    breakeven_covers: Optional[int] = Field(default=None, ge=0)
    target_covers: Optional[int] = Field(default=None, ge=0)
    average_ticket: Optional[float] = Field(default=None, ge=0)
    labor_cost_target_pct: Optional[float] = Field(default=None, ge=0, le=100)
    covers_per_server: Optional[int] = Field(default=None, gt=0)
    covers_per_host: Optional[int] = Field(default=None, gt=0)
    covers_per_runner: Optional[int] = Field(default=None, gt=0)
    covers_per_kitchen: Optional[int] = Field(default=None, gt=0)
    min_foh_staff: Optional[int] = Field(default=None, ge=1)
    min_boh_staff: Optional[int] = Field(default=None, ge=1)
    rate_server: Optional[float] = Field(default=None, ge=0)
    rate_host: Optional[float] = Field(default=None, ge=0)
    rate_runner: Optional[float] = Field(default=None, ge=0)
    rate_kitchen: Optional[float] = Field(default=None, ge=0)


class RestaurantProfileResponse(RestaurantProfileBase):
    """Model for API response"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StaffRecommendation(BaseModel):
    """Staff recommendation based on predicted covers (flat structure for /staff-recommendation)"""
    servers: int
    hosts: int
    runners: int
    kitchen: int
    total_foh: int
    total_boh: int
    message: str  # Human-readable recommendation


# Industry defaults for "Not sure? Use defaults" button
INDUSTRY_DEFAULTS = {
    "fine_dining": {
        "covers_per_server": 12,
        "covers_per_host": 40,
        "covers_per_runner": 30,
        "covers_per_kitchen": 20,
        "turns_dinner": 1.5,
        "labor_cost_target_pct": 32.0
    },
    "casual_dining": {
        "covers_per_server": 20,
        "covers_per_host": 60,
        "covers_per_runner": 50,
        "covers_per_kitchen": 35,
        "turns_dinner": 2.5,
        "labor_cost_target_pct": 28.0
    },
    "hotel_restaurant": {
        "covers_per_server": 16,
        "covers_per_host": 60,
        "covers_per_runner": 40,
        "covers_per_kitchen": 30,
        "turns_dinner": 2.0,
        "labor_cost_target_pct": 30.0
    }
}
