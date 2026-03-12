import asyncio
import os
import json
import logging
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://app.backboard.io/api"

_SYSTEM_PROMPT = (
    "You are a hospitality operations memory system for an F&B revenue agent. "
    "Your role is to retain and recall operational insights, manager feedback, "
    "and historical patterns for hotel restaurant tenants. "
    "When asked about relevant context, surface the most applicable memories concisely."
)


class MemoryService:
    """
    Cognitive Memory Layer (Phase 3).
    Uses the Backboard REST API (https://app.backboard.io/api) for persistent
    memory across sessions. Relies only on httpx — no extra SDK required.

    Architecture:
    - One Backboard assistant shared across the service lifetime (class-level cache).
    - One long-lived thread per tenant for storing reflections (class-level cache).
    - A fresh thread per call to get_relevant_context so stored memories are
      injected cleanly without prior conversation noise.
    """

    # Class-level cache: one assistant shared across the whole process.
    _assistant_id: Optional[str] = None

    def __init__(self) -> None:
        api_key = os.getenv("BACKBOARD_API_KEY")
        if not api_key:
            logger.warning("BACKBOARD_API_KEY not set — memory layer disabled.")
            self._headers: Optional[dict] = None
        else:
            self._headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json",
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_or_create_assistant(self) -> Optional[str]:
        """Return the shared assistant ID.
        Looks up an existing 'Aetherix F&B Memory' assistant first to avoid
        accumulating stale assistants across process restarts.
        """
        if MemoryService._assistant_id:
            return MemoryService._assistant_id
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Try to find an existing assistant with this name.
                list_resp = await client.get(
                    f"{_BASE_URL}/assistants",
                    headers=self._headers,
                )
                if list_resp.is_success:
                    assistants = list_resp.json()
                    if isinstance(assistants, dict):
                        assistants = assistants.get("assistants", [])
                    for asst in assistants:
                        if asst.get("name") == "Aetherix F&B Memory":
                            MemoryService._assistant_id = asst["assistant_id"]
                            logger.info(f"Reusing existing Backboard assistant: {asst['assistant_id']}")
                            return MemoryService._assistant_id

                # None found — create one.
                create_resp = await client.post(
                    f"{_BASE_URL}/assistants",
                    json={"name": "Aetherix F&B Memory", "system_prompt": _SYSTEM_PROMPT},
                    headers=self._headers,
                )
                if not create_resp.is_success:
                    raise RuntimeError(f"HTTP {create_resp.status_code} — {create_resp.text[:300]}")
                assistant_id = create_resp.json()["assistant_id"]
                MemoryService._assistant_id = assistant_id
                logger.info(f"Created Backboard assistant: {assistant_id}")
                return assistant_id
        except Exception as e:
            logger.error(f"Failed to get/create Backboard assistant [{type(e).__name__}]: {repr(e)}")
            return None

    async def _create_thread(self, assistant_id: str) -> Optional[str]:
        """Create a fresh thread. Backboard memories are stored at the assistant level,
        so each reflection/query can safely use its own thread."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_BASE_URL}/assistants/{assistant_id}/threads",
                    headers=self._headers,
                )
                if not resp.is_success:
                    raise RuntimeError(f"HTTP {resp.status_code} — {resp.text[:500]}")
                return resp.json()["thread_id"]
        except Exception as e:
            logger.error(f"Failed to create Backboard thread [{type(e).__name__}]: {repr(e)}")
            return None

    async def _add_message(
        self, thread_id: str, content: str, retries: int = 4, backoff: float = 30.0
    ) -> Optional[str]:
        """POST a message to a thread with memory=Auto. Returns response content.
        Retries on 504 (Backboard gateway timeout during LLM/memory processing).
        """
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=180) as client:
                    resp = await client.post(
                        f"{_BASE_URL}/threads/{thread_id}/messages",
                        data={"content": content, "memory": "Auto", "stream": "false"},
                        headers={k: v for k, v in self._headers.items() if k != "Content-Type"},
                    )
                if resp.status_code == 504 and attempt < retries:
                    wait = backoff * (2 ** attempt)
                    logger.warning(
                        f"Backboard 504 on attempt {attempt + 1}/{retries + 1} — "
                        f"retrying in {wait:.0f}s"
                    )
                    await asyncio.sleep(wait)
                    continue
                if not resp.is_success:
                    raise RuntimeError(
                        f"Backboard add_message failed: HTTP {resp.status_code} — {resp.text[:500]}"
                    )
                return resp.json().get("content", "")
            except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                if attempt < retries:
                    wait = backoff * (2 ** attempt)
                    logger.warning(f"Backboard timeout on attempt {attempt + 1} — retrying in {wait:.0f}s")
                    await asyncio.sleep(wait)
                else:
                    raise
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def store_reflection(
        self,
        tenant_id: str,
        reflection: str = None,
        context: str = None,
        outcome: str = None,
        tags: List[str] = None,
    ) -> None:
        """
        Persists an operational insight or manager feedback into Backboard memory.
        Supports two call signatures:
          - seed script:  store_reflection(tenant_id, reflection="...", tags=[...])
          - feedback loop: store_reflection(tenant_id, context="...", outcome="...")
        """
        if not self._headers:
            return

        content = reflection if reflection else f"Context: {context} | Outcome: {outcome}"

        assistant_id = await self._get_or_create_assistant()
        if not assistant_id:
            raise RuntimeError("Backboard assistant unavailable — cannot store reflection.")

        # Fresh thread per reflection
        # memory operations on the same thread.
        thread_id = await self._create_thread(assistant_id)
        if not thread_id:
            raise RuntimeError("Backboard thread creation failed — cannot store reflection.")

        try:
            await self._add_message(thread_id, content)
            logger.info(f"Stored reflection for tenant '{tenant_id}'")
        except Exception as e:
            logger.error(f"Failed to store reflection for tenant '{tenant_id}' [{type(e).__name__}]: {repr(e)}")
            raise RuntimeError(f"[{type(e).__name__}] {repr(e)}") from e

    async def get_relevant_context(self, tenant_id: str, current_query: str) -> str:
        """
        Retrieves relevant historical context for a given query using Backboard memory recall.
        Opens a fresh thread each time so memories are injected without prior conversation noise.
        """
        if not self._headers:
            return ""

        assistant_id = await self._get_or_create_assistant()
        if not assistant_id:
            return ""

        try:
            thread_id = await self._create_thread(assistant_id)
            if not thread_id:
                return ""

            query = (
                f"For hotel tenant '{tenant_id}', recall any relevant operational "
                f"memories related to: {current_query}"
            )
            return await self._add_message(thread_id, query) or ""
        except Exception as e:
            logger.error(f"Failed to retrieve context for tenant '{tenant_id}': {e}")
            return ""

    async def learn_from_feedback(self, tenant_id: str, alert_id: str, feedback: str) -> None:
        """Stores negative manager feedback to prevent repeated unhelpful alerts."""
        await self.store_reflection(
            tenant_id,
            context=f"AlertID: {alert_id}",
            outcome=f"Manager Feedback: {feedback}",
        )

    async def cache_recommendation(self, tenant_id: str, data: Dict[str, Any]) -> None:
        """Persists the latest recommendation into Backboard memory as a structured note."""
        if not self._headers:
            return
        await self.store_reflection(
            tenant_id,
            reflection=f"[recommendation_cache] {json.dumps(data)}",
            tags=["recommendation_cache"],
        )

    async def get_latest_recommendation(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent cached recommendation via memory recall."""
        if not self._headers:
            return None
        try:
            raw = await self.get_relevant_context(tenant_id, "latest recommendation_cache")
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
            return None
        except Exception:
            return None
