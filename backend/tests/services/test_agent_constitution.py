"""Tests for AgentConstitutionService (Prompt B — Agent Constitution).

Coverage:
- AC1: build_system_prompt renders without error for all 3 tone profiles
- AC2: Unknown tone profile raises ValueError
- AC3: Missing optional fields (manager_name, outlet_name) fall back gracefully
- AC4: Required profile fields appear verbatim in the rendered prompt
- AC5: forecast_context values are injected correctly
- AC6: Missing similar_nights defaults to fallback text
"""
from __future__ import annotations

import pytest

from app.db.models import RestaurantProfile
from app.services.agent_constitution import AgentConstitutionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(**overrides) -> RestaurantProfile:
    """Minimal valid RestaurantProfile with sane defaults."""
    profile = RestaurantProfile()
    profile.property_name = overrides.get("property_name", "Hotel Kleber")
    profile.outlet_name = overrides.get("outlet_name", "Le Bistrot Kleber")
    profile.total_seats = overrides.get("total_seats", 120)
    profile.manager_name = overrides.get("manager_name", "Sophie Lefebvre")
    profile.agent_tone_profile = overrides.get("agent_tone_profile", "luxury")
    return profile


_FORECAST_CTX = {
    "date": "2026-07-14",
    "covers": 95,
    "confidence": 82,
    "similar_nights": "- Friday 2025-06-20: 92 covers (confident)",
}

_SERVICE = AgentConstitutionService()


# ---------------------------------------------------------------------------
# AC1 — All tone profiles render
# ---------------------------------------------------------------------------

class TestAllToneProfiles:
    @pytest.mark.parametrize("tone", ["luxury", "professional", "casual"])
    def test_renders_without_error(self, tone: str):
        profile = _profile(agent_tone_profile=tone)
        result = _SERVICE.build_system_prompt(profile, _FORECAST_CTX)
        assert isinstance(result, str)
        assert len(result) > 100

    @pytest.mark.parametrize("tone", ["luxury", "professional", "casual"])
    def test_tone_instructions_present(self, tone: str):
        from app.services.agent_constitution import _TONE_INSTRUCTIONS
        profile = _profile(agent_tone_profile=tone)
        result = _SERVICE.build_system_prompt(profile, _FORECAST_CTX)
        # At least the first word of the tone instruction appears in the output
        first_word = _TONE_INSTRUCTIONS[tone].split()[0]
        assert first_word in result


# ---------------------------------------------------------------------------
# AC2 — Unknown tone raises ValueError
# ---------------------------------------------------------------------------

class TestUnknownToneProfile:
    def test_raises_value_error(self):
        profile = _profile(agent_tone_profile="zen")
        with pytest.raises(ValueError, match="zen"):
            _SERVICE.build_system_prompt(profile, _FORECAST_CTX)

    def test_error_lists_valid_values(self):
        profile = _profile(agent_tone_profile="corporate")
        with pytest.raises(ValueError) as exc_info:
            _SERVICE.build_system_prompt(profile, _FORECAST_CTX)
        assert "luxury" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC3 — Optional fields fallback gracefully
# ---------------------------------------------------------------------------

class TestOptionalFieldsFallback:
    def test_manager_name_none_uses_default(self):
        profile = _profile(manager_name=None)
        result = _SERVICE.build_system_prompt(profile, _FORECAST_CTX)
        assert "Manager" in result

    def test_outlet_name_none_falls_back_to_property_name(self):
        profile = _profile(outlet_name=None)
        result = _SERVICE.build_system_prompt(profile, _FORECAST_CTX)
        assert "Hotel Kleber" in result

    def test_empty_forecast_context_renders(self):
        profile = _profile()
        result = _SERVICE.build_system_prompt(profile, {})
        assert isinstance(result, str)
        assert "Hotel Kleber" in result


# ---------------------------------------------------------------------------
# AC4 — Required profile fields appear in output
# ---------------------------------------------------------------------------

class TestRequiredFieldsInjected:
    def test_hotel_name_present(self):
        result = _SERVICE.build_system_prompt(_profile(), _FORECAST_CTX)
        assert "Hotel Kleber" in result

    def test_restaurant_name_present(self):
        result = _SERVICE.build_system_prompt(_profile(), _FORECAST_CTX)
        assert "Le Bistrot Kleber" in result

    def test_covers_capacity_present(self):
        result = _SERVICE.build_system_prompt(_profile(), _FORECAST_CTX)
        assert "120" in result

    def test_manager_name_present(self):
        result = _SERVICE.build_system_prompt(_profile(), _FORECAST_CTX)
        assert "Sophie Lefebvre" in result


# ---------------------------------------------------------------------------
# AC5 — forecast_context values injected
# ---------------------------------------------------------------------------

class TestForecastContextInjected:
    def test_forecast_date_present(self):
        result = _SERVICE.build_system_prompt(_profile(), _FORECAST_CTX)
        assert "2026-07-14" in result

    def test_covers_present(self):
        result = _SERVICE.build_system_prompt(_profile(), _FORECAST_CTX)
        assert "95" in result

    def test_confidence_present(self):
        result = _SERVICE.build_system_prompt(_profile(), _FORECAST_CTX)
        assert "82" in result


# ---------------------------------------------------------------------------
# AC6 — similar_nights fallback text
# ---------------------------------------------------------------------------

class TestSimilarNightsFallback:
    def test_empty_similar_nights_uses_fallback(self):
        ctx = {**_FORECAST_CTX, "similar_nights": ""}
        result = _SERVICE.build_system_prompt(_profile(), ctx)
        assert "No recent comparable nights available." in result

    def test_missing_similar_nights_key_uses_fallback(self):
        ctx = {k: v for k, v in _FORECAST_CTX.items() if k != "similar_nights"}
        result = _SERVICE.build_system_prompt(_profile(), ctx)
        assert "No recent comparable nights available." in result

    def test_provided_similar_nights_appears_in_output(self):
        result = _SERVICE.build_system_prompt(_profile(), _FORECAST_CTX)
        assert "Friday 2025-06-20" in result
