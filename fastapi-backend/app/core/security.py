from fastapi import Depends, HTTPException, status
from typing import Dict, Any

# Story 1.3: This will be replaced by real fastapi-users Dependency
async def get_current_user() -> Dict[str, Any]:
    """
    Mock dependency to represent the currently authenticated user.
    In production (Story 1.3), this will validate JWT tokens from Supabase Auth.
    """
    # For now, we return a mock user with a specific ID to allow RLS/Tenant Logic to work
    return {
        "id": "e8a93b3a-5906-4444-9999-000000000000",
        "email": "pilot.manager@grandhotel.com",
        "is_active": True,
        "is_superuser": False
    }
