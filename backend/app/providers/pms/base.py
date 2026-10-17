"""Vendor-neutral PMS layer — HOS-280 (Décision #28, ADR-0006 §9).

Only an adapter knows its PMS's native format. Everything else in Aetherix
reads these dataclasses, so adding a PMS means writing its adapter, not
touching the forecast or the sync. Mirrors the POS provider design of
ADR-0006 §D6 (Protocol + frozen dataclasses + read-only).

Every value says what it is (``unit``, ``scope``) and whether it is real
(``is_placeholder``): a canonical layer that hid a made-up number behind a
clean type would be worse than the raw payload. Behaviour is unchanged by
this story (values identical to before); the flags make the existing gaps
visible, they do not fix them:

* ``ApaleoMCPAdapter`` returned occupancy 80 and revenue 0.0 when not
  configured or on error → ``is_placeholder=True``.
* the two Apaleo transports do not measure occupancy the same way (REST:
  the metrics endpoint's own figure, unit not verified; MCP: a percentage of
  rooms sold) → ``unit``.
* REST falls back to total revenue when the category sums to zero; MCP
  ignores the category → ``scope``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional, Protocol, runtime_checkable


class PMSProviderName(str, Enum):
    MOCK = "mock"
    APALEO = "apaleo"


class OccupancyUnit(str, Enum):
    PERCENT = "percent"            # rooms sold / rooms available × 100
    ROOMS = "rooms"                # rooms sold
    AS_REPORTED = "as_reported"    # the PMS's own figure, unit not verified


class RevenueScope(str, Enum):
    CATEGORY = "category"                  # revenue of the requested category
    TOTAL_FALLBACK = "total_fallback"      # category summed to 0 → total returned instead
    ALL_REVENUE = "all_revenue"            # the source ignores the category


@dataclass(slots=True, frozen=True)
class NormalizedOccupancy:
    pms_property_id: str
    day: date
    value: int                         # the figure stored by the sync (unchanged)
    unit: OccupancyUnit
    provider: PMSProviderName
    rooms_sold: Optional[int] = None
    rooms_available: Optional[int] = None
    is_placeholder: bool = False       # True = not from the PMS (unconfigured / error)


@dataclass(slots=True, frozen=True)
class NormalizedRevenue:
    pms_property_id: str
    day: date
    amount: float
    category: str
    scope: RevenueScope
    provider: PMSProviderName
    currency: Optional[str] = None
    is_placeholder: bool = False


@dataclass(slots=True, frozen=True)
class NormalizedReservation:
    vendor_reservation_id: Optional[str]
    arrival: Optional[date]
    departure: Optional[date]
    adults: int
    children: int
    status: Optional[str]
    provider: PMSProviderName
    raw_fields: tuple[str, ...] = field(default=())   # native keys seen, for audit only

    @property
    def guests(self) -> int:
        return self.adults + self.children


@runtime_checkable
class PMSProvider(Protocol):
    """Read-only interface of a PMS (Décision #7). Writes stay on the legacy
    adapter methods behind their own read-only guard."""

    @property
    def provider_name(self) -> PMSProviderName: ...

    @property
    def is_configured(self) -> bool: ...

    async def fetch_occupancy(self, pms_property_id: str, day: date) -> NormalizedOccupancy: ...

    async def fetch_revenue(self, pms_property_id: str, day: date, category: str = "Total") -> NormalizedRevenue: ...

    async def fetch_reservations(self, pms_property_id: str, start: date, end: date) -> list[NormalizedReservation]: ...

    async def aclose(self) -> None: ...


def parse_day(value) -> Optional[date]:
    """``YYYY-MM-DD`` prefix of an ISO string, or None."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None
