"""ClaudeProvider — LLMProvider implementation backed by Anthropic's Claude.

This is the primary LLM provider for Aetherix (CLAUDE.md ADR #1 + ADR #9).
The Anthropic SDK is imported only here; no other module in ``app/services/``
should import ``anthropic`` directly.
"""
from __future__ import annotations

import os

from anthropic import AsyncAnthropic

from app.providers.base import LLMProvider  # noqa: F401 — satisfies Protocol


class ClaudeProvider:
    """Wraps ``AsyncAnthropic`` behind the ``LLMProvider`` protocol.

    Instantiation never raises even if ``ANTHROPIC_API_KEY`` is absent —
    the error is deferred to the first ``complete()`` call so that the app
    can start and serve health-check endpoints without a live key.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._model = model
        # Client is only created when a key is present; stays None otherwise.
        self._client: AsyncAnthropic | None = (
            AsyncAnthropic(api_key=self._api_key) if self._api_key else None
        )

    # ------------------------------------------------------------------
    # LLMProvider protocol
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 500,
        temperature: float = 0.3,
        system: str | None = None,
    ) -> str:
        """Call the Claude Messages API and return the assistant's text.

        Args:
            messages:    Conversation turns.  Must follow the Anthropic schema:
                         ``[{"role": "user"|"assistant", "content": str}]``.
            max_tokens:  Hard output token cap.
            temperature: Sampling temperature.
            system:      System-level instruction passed to Anthropic's
                         top-level ``system=`` field (not injected as a message).

        Raises:
            RuntimeError: If ``ANTHROPIC_API_KEY`` was not set at instantiation
                          time and was not set in the environment since then.
        """
        if self._client is None:
            # One last attempt — key may have been set after instantiation.
            key = os.getenv("ANTHROPIC_API_KEY", "")
            if not key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set — cannot call ClaudeProvider.complete()"
                )
            self._api_key = key
            self._client = AsyncAnthropic(api_key=key)

        kwargs: dict = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        if system is not None:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)
        return response.content[0].text

    @property
    def model_id(self) -> str:
        return f"claude/{self._model}"
