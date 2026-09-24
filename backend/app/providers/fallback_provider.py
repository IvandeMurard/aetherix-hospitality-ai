"""FallbackLLMProvider — automatic failover between two LLMProvider instances.

When the primary provider fails with a *transient* error (5xx, timeout, network)
this composite transparently retries the same call on the fallback provider.
Client errors (HTTP 4xx) are re-raised immediately — the same malformed request
would fail identically on the fallback, making failover wasteful and misleading.

Activation:
    Set ``LLM_FALLBACK_BACKEND=gemini`` alongside ``LLM_BACKEND=claude`` in
    the environment.  The factory will automatically wrap the primary provider
    in a ``FallbackLLMProvider`` — no code changes needed.

Failure semantics:
    - Transient errors from the primary trigger failover and a WARNING log.
    - Non-transient (4xx) errors are re-raised immediately with an ERROR log.
    - If the fallback also fails, its exception propagates to the caller.
    - Both provider identities are recorded in ``model_id`` for observability.
"""
from __future__ import annotations

import logging

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


def _is_transient_error(exc: Exception) -> bool:
    """Return True for errors that warrant failover to the backup provider.

    HTTP 4xx errors (bad request, auth failure, context too long, invalid input)
    indicate a malformed or rejected request — the identical call will fail on
    the fallback too, so failover only costs money without fixing anything.

    5xx errors, timeouts, and network-level errors may resolve on a different
    backend and are worth retrying.
    """
    for attr in ("status_code", "http_status"):
        status = getattr(exc, attr, None)
        if isinstance(status, int):
            return status >= 500  # 4xx → False (don't fallback), 5xx → True
    # No HTTP status code → network/timeout/config error → assume transient
    return True


class FallbackLLMProvider:
    """Composite LLMProvider: tries *primary*, falls back to *fallback* on transient errors.

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
        model: str | None = None,
    ) -> str:
        """Try primary provider; on transient errors, transparently retry with fallback.

        4xx client errors (bad request, invalid input, context too long) are
        re-raised immediately — they indicate a request problem that the fallback
        cannot fix.

        Args:
            messages:    OpenAI-style message list.
            max_tokens:  Maximum tokens to generate.
            temperature: Sampling temperature.
            system:      Optional system instruction.
            model:       Optional per-call model override (HOS-283). It is a
                         vendor-specific identifier, so it is sent to the
                         primary only. The fallback always runs on its own
                         default model: forwarding e.g. a Claude model ID to
                         Gemini is rejected by the Gemini API, which silently
                         killed the failover for every overridden call.

        Returns:
            The first successful text response (primary or fallback).

        Raises:
            Exception: Non-transient (4xx) errors from the primary, or the
                       fallback's exception if both providers fail.
        """
        try:
            return await self._primary.complete(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                model=model,
            )
        except Exception as primary_exc:
            if not _is_transient_error(primary_exc):
                logger.error(
                    "FallbackLLMProvider: primary %s raised non-transient error "
                    "(%s status=%s) — NOT falling back",
                    self._primary.model_id,
                    type(primary_exc).__name__,
                    getattr(
                        primary_exc,
                        "status_code",
                        getattr(primary_exc, "http_status", "n/a"),
                    ),
                )
                raise
            logger.warning(
                "FallbackLLMProvider: primary provider %s failed (%s: %s) — "
                "retrying with fallback %s",
                self._primary.model_id,
                type(primary_exc).__name__,
                primary_exc,
                self._fallback.model_id,
            )
            if model is not None:
                logger.info(
                    "FallbackLLMProvider: dropping primary-specific model override "
                    "%r — fallback %s runs on its default model",
                    model,
                    self._fallback.model_id,
                )
            return await self._fallback.complete(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                model=None,
            )

    async def check_fallback_health(self) -> bool:
        """Ping the fallback provider with a minimal request to surface silent rot.

        The fallback path (Gemini) almost never runs in prod because the primary
        (Claude) rarely 5xx's — so an expired key, lapsed quota, or drifted SDK
        contract stays invisible until a real Claude outage, i.e. the one moment
        it must work. This canary exercises the fallback directly so the rot is
        caught early (boot health-check or scheduled job — HOS-282).

        Non-raising: logs a WARNING and returns ``False`` on any failure so it can
        be fired safely from startup without ever taking the process down.
        """
        try:
            text = await self._fallback.complete(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0.0,
            )
        except Exception as exc:
            logger.warning(
                "FallbackLLMProvider: fallback %s health-check FAILED (%s: %s) — "
                "the parachute may be down; rotate/verify the fallback key",
                self._fallback.model_id,
                type(exc).__name__,
                exc,
            )
            return False

        if not (text and text.strip()):
            logger.warning(
                "FallbackLLMProvider: fallback %s health-check returned an empty "
                "response — treating as unavailable",
                self._fallback.model_id,
            )
            return False

        logger.info(
            "FallbackLLMProvider: fallback %s health-check OK", self._fallback.model_id
        )
        return True

    @property
    def model_id(self) -> str:
        """Composite identifier showing both providers for observability."""
        return f"{self._primary.model_id}→{self._fallback.model_id}"
