"""AetherixOrchestrator — proto-orchestrator stub (ADR-0004 · HOS-184 PR-A).

This is intentionally minimal in Phase 3 PR-A. It establishes:

  - The class shape and constructor signature.
  - The MCP-client-only contract for downstream calls (no Python imports from
    app.services).
  - A placeholder for the agentic loop (`handle_request`) that PR-B will fill
    by migrating `AetherixEngine.get_forecast` orchestration logic out of
    `app/services/aetherix_engine.py`.

Phase 4 will:
  - Replace the in-process dispatch shortcut with HTTP MCP calls
    (`httpx.AsyncClient` → Aetherix `/mcp/v1/`).
  - Add Tacet and Anima MCP clients.
  - Implement business-rules-aware routing.
  - Move this module to a standalone repo.

Until then, this stub is a placeholder that documents the boundary and makes
the architectural decision visible at import time.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPCallTarget:
    """Identifies one node the orchestrator can call via MCP.

    Phase 3: targets are local (same-process Aetherix dispatch). Phase 4:
    targets are remote (HTTP base URL + bearer token).
    """

    name: str  # "aetherix" | "tacet" | "anima" | "apaleo"
    base_url: Optional[str] = None  # None = in-process Aetherix (Phase 3)
    bearer_token: Optional[str] = None
    timeout_s: float = 5.0


@dataclass
class AetherixOrchestrator:
    """Supervisory agent — routes between Mesh nodes via MCP.

    Phase 3 PR-A: skeleton only. The `handle_request` method raises
    NotImplementedError until PR-B migrates the AetherixEngine logic.

    Usage (Phase 4 target shape, illustrative):

        orch = AetherixOrchestrator(targets={
            "aetherix": MCPCallTarget(name="aetherix", base_url="http://aetherix/mcp/v1/", bearer_token="atx_..."),
            "tacet":    MCPCallTarget(name="tacet",    base_url="http://tacet/mcp/v0/",    bearer_token="tct_..."),
        })
        result = await orch.handle_request(
            query="staffing for tomorrow dinner",
            target_date=date(2026, 6, 1),
            hotel_id="<resolved-server-side>",
        )
    """

    targets: dict[str, MCPCallTarget] = field(default_factory=dict)

    async def handle_request(
        self,
        query: str,
        target_date: Any = None,
        hotel_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Agentic loop placeholder.

        Will be implemented in PR-B with the following flow:

          1. recall_memory(query) via MCP → memory_hits, top_similarity
          2. If top_similarity < 0.7: recall_memory(query, k_memory=10) for broader context
          3. get_operational_predictions(target_date, ...) via MCP
          4. If confidence < 0.6: enrich context and retry forecast
          5. LLM synthesis of memory + forecast → final recommendation
          6. Return structured result

        For now, this raises so any accidental call surfaces the gap loudly.
        """
        raise NotImplementedError(
            "AetherixOrchestrator.handle_request is a PR-A stub. "
            "The agentic loop is implemented in PR-B (HOS-184 phase 2). "
            "See ADR-0004 §3 D7."
        )
