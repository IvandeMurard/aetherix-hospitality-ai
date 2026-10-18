"""Vendor-neutral PMS layer — HOS-280 / HOS-352 (Décisions #28, #33, #43, ADR-0006 §9).

Only an adapter knows its PMS's native format. Everything else in Aetherix
reads these dataclasses, so adding a PMS means writing its adapter, not
touching the forecast or the sync. Mirrors the POS provider design of
ADR-0006 §D6 (Protocol + frozen dataclasses + read-only).

A PMS figure is true or absent, never invented (HOS-352):

* a value is either what the PMS reported, or absent with a ``status`` that
  says why (``not_configured``, ``pms_error``, ``no_data``). No adapter returns
  a default "so the pipeline is never blocked": the pipeline handles absence.
* occupancy has one unit everywhere: rooms sold + rooms available, both
  counts. The rate is computed (``rate``), never stored as a third figure in
  an unverified unit.
* revenue is F&B revenue only, net of tax, in the PMS's currency. A source
  that cannot isolate F&B gives no figure, never the total instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional, Protocol, runtime_checkable


class PMSProviderName(str, Enum):
    MOCK = "mock"
    APALEO = "apaleo"


class PMSDataStatus(str, Enum):
    OK = "ok"                          # reported by the hotel's PMS
    FIXTURE = "fixture"                # dev / demo fixture (mock adapter), never a hotel's data
    NOT_CONFIGURED = "not_configured"  # no credentials / server for this PMS
    PMS_ERROR = "pms_error"            # the PMS call failed
    NO_DATA = "no_data"                # the PMS answered with nothing usable for that day

    @property
    def has_value(self) -> bool:
        return self in (PMSDataStatus.OK, PMSDataStatus.FIXTURE)


@dataclass(slots=True, frozen=True)
class NormalizedOccupancy:
    pms_property_id: str
    day: date
    provider: PMSProviderName
    status: PMSDataStatus
    rooms_sold: Optional[int] = None
    rooms_available: Optional[int] = None   # sellable rooms that day (out of order excluded)
    detail: Optional[str] = None            # why it is absent, for logs

    def __post_init__(self):
        present = self.rooms_sold is not None and self.rooms_available is not None
        if present != self.status.has_value:
            raise ValueError(f"occupancy status {self.status.value} does not match its values")

    @property
    def rate(self) -> Optional[float]:
        """Rooms sold / rooms available, 0–1. None when absent."""
        if self.rooms_sold is None or not self.rooms_available:
            return None
        return self.rooms_sold / self.rooms_available

    @classmethod
    def absent(cls, pms_property_id: str, day: date, provider: PMSProviderName,
               status: PMSDataStatus, detail: Optional[str] = None) -> "NormalizedOccupancy":
        return cls(pms_property_id=pms_property_id, day=day, provider=provider, status=status, detail=detail)


@dataclass(slots=True, frozen=True)
class NormalizedRevenue:
    """F&B revenue of one day, net of tax."""

    pms_property_id: str
    day: date
    provider: PMSProviderName
    status: PMSDataStatus
    amount: Optional[float] = None
    currency: Optional[str] = None
    detail: Optional[str] = None

    def __post_init__(self):
        if (self.amount is not None) != self.status.has_value:
            raise ValueError(f"revenue status {self.status.value} does not match its value")

    @classmethod
    def absent(cls, pms_property_id: str, day: date, provider: PMSProviderName,
               status: PMSDataStatus, detail: Optional[str] = None) -> "NormalizedRevenue":
        return cls(pms_property_id=pms_property_id, day=day, provider=provider, status=status, detail=detail)


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
    adapter methods behind their own read-only guard.

    ``fetch_occupancy`` and ``fetch_fb_revenue`` never raise for a PMS-side
    problem: they return an absent value with its status.
    """

    @property
    def provider_name(self) -> PMSProviderName: ...

    @property
    def is_configured(self) -> bool: ...

    async def fetch_occupancy(self, pms_property_id: str, day: date) -> NormalizedOccupancy: ...

    async def fetch_fb_revenue(self, pms_property_id: str, day: date) -> NormalizedRevenue: ...

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
