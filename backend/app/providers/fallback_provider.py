"""FallbackLLMProvider — automatic failover between two LLMProvider instances.

When the primary provider fails for any reason (API error, rate limit, missing
key, timeout), this composite transparently retries the same call on the
fallback provider.  Services never know a fallover occurred.

Activation:
    Set ``LLM_FALLBACK_BACKEND=gemini`` alongside ``LLM_BACKEND=claude`` in
    the environment.  The factory will automatically wrap the primary provider
    in a ``FallbackLLMProvider`` — no code changes needed.

Failure semantics:
    - Any exception from the primary triggers failover and a WARNING log.
    - If the fallback also fails, its exception propagates to the caller.
    - Both provider identities are recorded in ``model_id`` for observability.
"""
from __future__ import annotations

import logging

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class FallbackLLMProvider:
    """Composite LLMProvider: tries *primary*, falls back to *fallback* on any error.

    Args:
        primary:  The preferred provider (e.g. ``ClaudeProvider``).
        fallback: The backup provider (e.g. ``GeminiProvider``).
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 500,
        temperature: float = 0.3,
        system: str | None = None,
    ) -> str:
        """Try primary provider; on any exception, transparently retry with fallback.

        Args:
            messages:    OpenAI-style message list.
            max_tokens:  Maximum tokens to generate.
            temperature: Sampling temperature.
            system:      Optional system instruction.

        Returns:
            The first successful text response (primary or fallback).

        Raises:
            Exception: The fallback's exception if both providers fail.
        """
        try:
            return await self._primary.complete(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
            )
        except Exception as primary_exc:
            logger.warning(
                "FallbackLLMProvider: primary provider %s failed (%s: %s) — "
                "retrying with fallback %s",
                self._primary.model_id,
                type(primary_exc).__name__,
                primary_exc,
                self._fallback.model_id,
            )
            return await self._fallback.complete(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
            )

    @property
    def model_id(self) -> str:
        """Composite identifier showing both providers for observability."""
        return f"{self._primary.model_id}→{self._fallback.model_id}"
