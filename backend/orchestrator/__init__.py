"""Aetherix Orchestrator — supervisory agent for the Hospitality Agentic Mesh.

This module is the proto-orchestrator introduced by ADR-0004. It is intentionally
kept separate from `app/` to enforce the bounded-context split:

  - `app/` = Aetherix F&B execution node (forecast, staffing, memory, receipts).
  - `orchestrator/` = supervisory agent (LLM root, routing, business rules).

INVARIANTS (enforced by `scripts/ci/check_orchestrator_boundary.py`):

  1. ZERO Python imports from `app.services.*` inside `orchestrator/`.
     The orchestrator must reach Aetherix services through MCP calls only.

  2. ZERO Python imports from `app.db.models` or `app.db.session` inside
     `orchestrator/`. The orchestrator is stateless; persistence belongs to
     execution nodes (Aetherix, Tacet, Anima).

  3. MCP is the only interface between the orchestrator and any node. This
     prepares the Phase 4 split where `orchestrator/` becomes its own repo
     and calls Aetherix exclusively over HTTP.

Allowed imports:
  - Standard library
  - Third-party libraries (anthropic, httpx, etc.)
  - `app.providers.*` for LLM/Embedding abstractions (provider singletons
    are constructed in lifespan and shared — they are infrastructure, not
    domain services).
  - `app.mcp_core` for shared MCP primitives (auth errors, sanitizers).

Phase 3 status: skeleton + structural boundary. The agentic loop itself
(dynamic tool selection, retry on low confidence, feedback) is not yet
implemented. See HOS-184 (PR-B) for the AetherixEngine migration.
"""
from __future__ import annotations

__all__ = ["AetherixOrchestrator"]

# Re-export the main class so callers can `from orchestrator import AetherixOrchestrator`
from orchestrator.agent import AetherixOrchestrator
