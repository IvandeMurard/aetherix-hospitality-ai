"""Dedicated home for LLM prompt templates (HOS-204 / ADR-0007 §D2.a).

Prompts are extracted here from the service modules so that (1) prompt diffs are
readable in PR review and (2) the eval-by-design gate can invalidate its cache
deterministically when a prompt changes. Services keep import shims for
backward compatibility (no breaking change — ADR-0007 R8).

Lives at `app/prompts/` (not `backend/prompts/`) so the `app.prompts.*` import
path matches the rest of the `app` package.
"""
