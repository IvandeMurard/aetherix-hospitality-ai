"""AgentConstitutionService — Prompt B (Agent Constitution).

Builds the system prompt injected into every Claude call for the WhatsApp
conversational agent. The prompt is rendered at runtime from the property
profile and the current forecast context.

Template source: docs/context/demo-apaleo.md §4.2
"""
from __future__ import annotations

from typing import Any

from app.db.models import RestaurantProfile

# Prompt template lives in the dedicated prompts package (HOS-204 / ADR-0007
# §D2.a). Import shim keeps `_SYSTEM_PROMPT_TEMPLATE` resolvable here (R8 — no
# breaking change for callers that referenced it via this module).
from app.prompts.constitution import _SYSTEM_PROMPT_TEMPLATE

# Tone instructions by agent_tone_profile value (§4.5 of the spec)
_TONE_INSTRUCTIONS: dict[str, str] = {
    "luxury": (
        "Be precise and restrained. Use no contractions. "
        "Provide full context without being asked. No abbreviations. "
        "Address the manager with the professional deference appropriate "
        "to a luxury hospitality environment."
    ),
    "professional": (
        "Be formal but concise. Lead with numbers. Minimal prose."
    ),
    "casual": (
        "Be direct. Use short sentences. "
        "One qualifying phrase per point maximum."
    ),
}

class AgentConstitutionService:
    """Renders the WhatsApp agent system prompt from the property profile.

    Usage::

        service = AgentConstitutionService()
        system_prompt = service.build_system_prompt(profile, forecast_context)
        # Pass system_prompt to ReasoningService.generate_explanation() or
        # directly to self._llm.complete(system=system_prompt, ...)
    """

    def build_system_prompt(
        self,
        profile: RestaurantProfile,
        forecast_context: dict[str, Any],
    ) -> str:
        """Render the §4.2 system prompt with values from profile + context.

        Args:
            profile: The ``RestaurantProfile`` ORM instance for this tenant.
            forecast_context: Dict with optional keys:
                - ``date`` (str): forecast date, e.g. "2025-07-14"
                - ``covers`` (int | str): predicted covers
                - ``confidence`` (int | str): confidence percentage (0–100)
                - ``similar_nights`` (str): pre-formatted text from RAGService

        Returns:
            A non-empty string ready to be passed as the ``system=`` kwarg
            to ``LLMProvider.complete()``.

        Raises:
            ValueError: if ``profile.agent_tone_profile`` is not a known value.
        """
        tone = profile.agent_tone_profile or "luxury"
        if tone not in _TONE_INSTRUCTIONS:
            raise ValueError(
                f"Unknown agent_tone_profile {tone!r}. "
                f"Valid values: {sorted(_TONE_INSTRUCTIONS)}"
            )

        similar_nights = forecast_context.get("similar_nights", "")
        if not similar_nights:
            similar_nights = "No recent comparable nights available."

        return _SYSTEM_PROMPT_TEMPLATE.format(
            hotel_name=profile.property_name,
            restaurant_name=profile.outlet_name or profile.property_name,
            covers_capacity=profile.total_seats,
            manager_name=profile.manager_name or "Manager",
            tone_instructions=_TONE_INSTRUCTIONS[tone],
            forecast_date=forecast_context.get("date", "today"),
            covers=forecast_context.get("covers", "—"),
            confidence=forecast_context.get("confidence", "—"),
            last_3_similar_nights=similar_nights,
        )
