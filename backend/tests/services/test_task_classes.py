"""Point of no return per task class (ADR-0007 §18.1, Décision #40)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.services import task_classes as tc
from app.services.decision_policy import TaskClass

SERVICE = datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)  # Friday 19:00 Paris
PARIS = ZoneInfo("Europe/Paris")


def test_every_class_is_fully_specified():
    assert set(tc.CATALOG) == set(tc.TaskClassKey)
    for key, s in tc.CATALOG.items():
        assert s.key == key
        assert s.commit_point
        assert s.corrective_before_commit, key
        assert s.downside_if_accepted_wrongly and s.downside_if_refused_wrongly
        assert s.offset_basis == "default_assumption"  # defaults are never presented as measured
        assert tc.COMMIT_OFFSET_MIN_HOURS <= s.commit_offset_hours <= tc.COMMIT_OFFSET_MAX_HOURS


def test_only_staffing_is_recommended_today_and_policy_scoped():
    recommended = {k for k, s in tc.CATALOG.items() if s.recommended_by_product}
    assert recommended == {tc.TaskClassKey.staffing_add, tc.TaskClassKey.staffing_reduce}
    assert tc.spec("staffing.add").policy_task_class == TaskClass.staffing
    # food prep is catalogued (window known) but not recommended: no policy scope
    assert tc.spec("food_prep.batch").policy_task_class is None


def test_direction_maps_to_task_class():
    assert tc.for_direction("surge") == tc.TaskClassKey.staffing_add
    assert tc.for_direction("lull") == tc.TaskClassKey.staffing_reduce


@pytest.mark.parametrize(
    "issued_before_service_h, status",
    [(24 * 7, "open"), (24 + 47, "closing"), (24 + 1, "closing"), (24, "passed"), (3, "passed")],
)
def test_window_status_for_staffing_add(issued_before_service_h, status):
    issued = SERVICE - timedelta(hours=issued_before_service_h)
    w = tc.correction_window("staffing.add", SERVICE, issued)
    assert w.commit_at == SERVICE - timedelta(hours=24)
    assert w.status.value == status
    assert tc.should_surface(w) == (status != "open")


def test_hotel_offset_overrides_default_and_is_labelled():
    w = tc.correction_window("staffing.reduce", SERVICE, SERVICE - timedelta(days=10), offset_hours=168)
    assert w.commit_at == SERVICE - timedelta(hours=168)
    assert w.offset_basis == "hotel_configured"
    d = w.as_dict()
    assert d["task_class"] == "staffing.reduce" and d["catalog_version"] == tc.CATALOG_VERSION


@pytest.mark.parametrize("bad", [-1, 24 * 31, float("nan")])
def test_hotel_offset_is_bounded(bad):
    with pytest.raises(ValueError):
        tc.correction_window("staffing.add", SERVICE, SERVICE, offset_hours=bad)


def test_render_is_deterministic_localised_and_says_default():
    w = tc.correction_window("staffing.add", SERVICE, SERVICE - timedelta(hours=30))
    fr = tc.render_window(w, PARIS, None)
    assert fr == "Modifiable jusqu'à jeu. 19:00 (confirmation des extras) — valeur par défaut, non réglée par l'hôtel."
    en = tc.render_window(w, PARIS, "en")
    assert en == "Can still be changed until Thu 19:00 (extra shifts confirmed) — default, not set by the hotel."
    configured = tc.correction_window("staffing.add", SERVICE, SERVICE - timedelta(hours=30), offset_hours=12)
    assert "défaut" not in tc.render_window(configured, PARIS, "fr")


def test_render_passed_window():
    w = tc.correction_window("staffing.add", SERVICE, SERVICE - timedelta(hours=2), offset_hours=24)
    assert tc.render_window(w, PARIS, "en") == "Past the usual commit point (extra shifts confirmed, Thu 19:00)."


def test_autonomy_eligibility_facts_are_facts_not_a_gate():
    facts = tc.autonomy_eligibility_facts("food_prep.batch")
    assert facts["has_correction_window"] is True and facts["downside_bounded"] is True
    assert facts["recommended_by_product"] is False
    assert "eligible" not in facts  # ADR-0013 stays proposed: nothing here decides eligibility
