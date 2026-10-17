"""One mapping between a hotel's Aetherix tenant and its PMS property (HOS-347).

``tenant_id`` is Aetherix's key for a hotel: every row Aetherix stores is keyed
by it. ``pms_property_id`` is the hotel's id in its PMS (``PAR`` in the Apaleo
sandbox), stored on ``restaurant_profiles``. They are different things and are
never substituted for one another:

* calls **to the PMS** use ``pms_property_id``;
* everything Aetherix **stores or logs** uses ``tenant_id``.

Before HOS-347 the PMS sync route passed the tenant id to Apaleo as if it were
the property id (wrong property as soon as the two differ), and the training
route used one field for both. Every PMS path resolves through here; an
unknown or unlinked hotel is a typed error, never an id made up from the other.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class PmsIdentityError(LookupError):
    """Typed refusal: ``reason`` is unknown_tenant | unknown_pms_property | pms_not_linked."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


@dataclass(frozen=True)
class PmsTarget:
    tenant_id: str            # Aetherix key: storage, logs, parameters
    pms_type: str             # apaleo | mews | ...
    pms_property_id: str      # the PMS's own id: API calls only
    property_name: Optional[str] = None


def target_from_profile(profile, *, allow_unlinked_mock: bool = False) -> PmsTarget:
    """The PMS target of an already-loaded profile. ``allow_unlinked_mock``:
    the mock adapter needs no real property, so an unlinked hotel gets an
    explicit placeholder instead of an error (never its tenant id)."""
    pms_id = getattr(profile, "pms_property_id", None)
    if not pms_id:
        if not allow_unlinked_mock:
            raise PmsIdentityError("pms_not_linked",
                                   f"hotel {profile.tenant_id} has no PMS property id on its profile")
        pms_id = "mock-property"
    return PmsTarget(tenant_id=profile.tenant_id, pms_type=getattr(profile, "pms_type", None) or "apaleo",
                     pms_property_id=pms_id, property_name=getattr(profile, "property_name", None))


async def resolve_by_tenant(db: AsyncSession, tenant_id: str, *, allow_unlinked_mock: bool = False) -> PmsTarget:
    from app.db.models import RestaurantProfile

    profile = (await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.tenant_id == tenant_id)
    )).scalars().first()
    if profile is None:
        raise PmsIdentityError("unknown_tenant", f"no hotel profile for tenant {tenant_id}")
    return target_from_profile(profile, allow_unlinked_mock=allow_unlinked_mock)


async def resolve_by_pms_property(db: AsyncSession, pms_property_id: str, pms_type: str = "apaleo") -> PmsTarget:
    """For anything arriving from the PMS side (webhooks, imports)."""
    from app.db.models import RestaurantProfile

    rows = (await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.pms_property_id == pms_property_id)
    )).scalars().all()
    rows = [p for p in rows if (getattr(p, "pms_type", None) or "apaleo") == pms_type]
    if not rows:
        raise PmsIdentityError("unknown_pms_property",
                               f"no hotel linked to {pms_type} property {pms_property_id}")
    if len(rows) > 1:
        raise PmsIdentityError("ambiguous_pms_property",
                               f"{len(rows)} hotels linked to {pms_type} property {pms_property_id}")
    return target_from_profile(rows[0])
