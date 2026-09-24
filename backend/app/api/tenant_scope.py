"""Tenant scoping for HTTP routes — one rule, one place.

A route that takes a tenant identifier from the caller (path, query or body)
must check it against the identity the caller authenticated with. Two identity
kinds exist in this API:

* **MCP bearer token** (``MCPApiToken``) — the token carries ``hotel_id``
  (ADR-0001 D4). ``require_token_hotel`` refuses any other ``hotel_id``.
* **Dashboard user** (fastapi-users JWT, ``get_current_user``) — the user owns
  properties through ``RestaurantProfile.owner_id``.
  ``require_user_owns_tenant`` refuses a tenant the user does not own
  (superusers excepted: internal ops accounts).

Both answer 403 without saying whether the other tenant exists.
Defect fixed on 24/09/2026 (ADR-0007 §17.7): several routes accepted any
``hotel_id`` / ``tenant_id`` from an authenticated caller.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

TENANT_FORBIDDEN = "Credentials not scoped to this tenant"


def require_token_hotel(token: Any, hotel_id: str) -> None:
    """403 unless the bearer token is bound to ``hotel_id``. A token without a
    hotel binding is never a wildcard."""
    bound: Optional[str] = getattr(token, "hotel_id", None)
    if not bound or bound != hotel_id:
        raise HTTPException(status_code=403, detail=TENANT_FORBIDDEN)


async def require_user_owns_tenant(
    db: AsyncSession, current_user: Mapping[str, Any], tenant_id: str
):
    """Return the caller's ``RestaurantProfile`` for ``tenant_id``, or 403.

    The profile must exist and be owned by the user; a superuser may act on
    any existing tenant. A missing profile answers 403 too (no enumeration).
    """
    from app.db.models import RestaurantProfile

    profile = (
        await db.execute(
            select(RestaurantProfile).where(RestaurantProfile.tenant_id == tenant_id)
        )
    ).scalars().first()
    if profile is None:
        raise HTTPException(status_code=403, detail=TENANT_FORBIDDEN)
    if current_user.get("is_superuser"):
        return profile
    if str(profile.owner_id or "") != str(current_user.get("id") or "-"):
        raise HTTPException(status_code=403, detail=TENANT_FORBIDDEN)
    return profile


async def require_superuser(current_user: Mapping[str, Any]) -> Mapping[str, Any]:
    """403 unless the dashboard user is a superuser. For routes that act on
    every tenant or send to an arbitrary recipient (ops-only)."""
    if not current_user.get("is_superuser"):
        raise HTTPException(status_code=403, detail="Superuser required")
    return current_user
