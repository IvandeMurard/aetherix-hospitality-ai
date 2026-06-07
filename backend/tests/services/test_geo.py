"""HOS-215 (P3-11b) — haversine distance + event enrichment/sort."""
from __future__ import annotations

import pytest

from app.services.geo import enrich_events_with_distance, haversine_km

# Paris reference point (hotel).
_HOTEL = (48.8566, 2.3522)


class TestHaversine:
    def test_zero_distance(self):
        assert haversine_km(*_HOTEL, *_HOTEL) == pytest.approx(0.0, abs=1e-9)

    def test_one_degree_latitude(self):
        # 1° of latitude ≈ 111.19 km anywhere on the globe.
        assert haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.19, abs=0.5)

    def test_symmetric(self):
        a = haversine_km(48.8566, 2.3522, 48.8738, 2.2950)
        b = haversine_km(48.8738, 2.2950, 48.8566, 2.3522)
        assert a == pytest.approx(b, abs=1e-9)


class TestEnrichEvents:
    def test_injects_distance_and_sorts_nearest_first(self):
        # ~2.1 km north (pure latitude offset) and ~5.6 km north.
        near = {"title": "PSG vs Arsenal", "latitude": 48.8566 + 0.018886, "longitude": 2.3522}
        far = {"title": "Concert Bercy", "latitude": 48.8566 + 0.05, "longitude": 2.3522}
        out = enrich_events_with_distance([far, near], *_HOTEL)

        assert [e["title"] for e in out] == ["PSG vs Arsenal", "Concert Bercy"]  # nearest first
        assert out[0]["distance_km"] == pytest.approx(2.1, abs=0.05)
        assert out[1]["distance_km"] > out[0]["distance_km"]

    def test_missing_event_coords_keeps_no_distance_and_sorts_last(self):
        located = {"title": "Near", "latitude": 48.8566 + 0.009, "longitude": 2.3522}
        no_coords = {"title": "Unknown venue"}
        out = enrich_events_with_distance([no_coords, located], *_HOTEL)

        assert out[0]["title"] == "Near"
        assert "distance_km" in out[0]
        assert out[1]["title"] == "Unknown venue"
        assert "distance_km" not in out[1]  # AC3 — no distance, no crash

    def test_missing_hotel_coords_is_noop(self):
        events = [{"title": "X", "latitude": 48.9, "longitude": 2.3}]
        out = enrich_events_with_distance(events, None, None)
        assert "distance_km" not in out[0]

    def test_does_not_mutate_input(self):
        events = [{"title": "X", "latitude": 48.9, "longitude": 2.3}]
        enrich_events_with_distance(events, *_HOTEL)
        assert "distance_km" not in events[0]

    def test_empty_list(self):
        assert enrich_events_with_distance([], *_HOTEL) == []
