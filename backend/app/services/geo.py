"""Geospatial helpers (HOS-215 / P3-11b).

Haversine distance + event-distance enrichment so the forecast explanation can
cite how far an event is from the hotel — "PSG vs Arsenal (2.1 km)" instead of
just the name. Pure functions, no I/O.
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any, Optional

_EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two (lat, lon) points, in kilometres."""
    rlat1, rlat2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(a))


def enrich_events_with_distance(
    events: list[dict[str, Any]],
    hotel_lat: Optional[float],
    hotel_lon: Optional[float],
) -> list[dict[str, Any]]:
    """Inject ``distance_km`` into each event (when computable) and sort nearest-first.

    - An event gets ``distance_km`` only when both it and the hotel have
      latitude/longitude (AC3 — missing coords → no distance, no crash).
    - The result is sorted by ascending distance; events without a distance sort
      last (AC4 — the closest event leads, best demo read).

    Returns new dicts; the input list is not mutated.
    """
    enriched: list[dict[str, Any]] = []
    for event in events or []:
        e = dict(event)
        elat = e.get("latitude")
        elon = e.get("longitude")
        if (
            hotel_lat is not None
            and hotel_lon is not None
            and elat is not None
            and elon is not None
        ):
            e["distance_km"] = round(
                haversine_km(hotel_lat, hotel_lon, float(elat), float(elon)), 1
            )
        enriched.append(e)
    enriched.sort(key=lambda e: e.get("distance_km", float("inf")))
    return enriched
