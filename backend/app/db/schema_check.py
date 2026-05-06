"""Boot-time schema validation — HOS-150 AC7.

Replaces the old `Base.metadata.create_all` boot path that silently created
divergent tables in fresh environments. Now we *verify* that the critical
tables exist (created by Supabase migrations) and refuse to start otherwise
with an actionable error message.

Skip with `AETHERIX_SKIP_BOOT_SCHEMA_CHECK=true` (intended for local dev / tests
that don't actually use the DB).
"""
from __future__ import annotations

import logging
import os
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


# Tables the app cannot start without. Adding to this list should be a deliberate
# decision — it raises the floor for every fresh deploy.
CRITICAL_TABLES: tuple[str, ...] = (
    "restaurant_profiles",
    "operational_memory",
    "mcp_api_tokens",
    "agent_action_log",
)


class SchemaValidationError(RuntimeError):
    """Raised at boot when a critical table is missing from the live DB."""


_REMEDIATION = (
    "Apply Supabase migrations before starting the app:\n"
    "    supabase db reset            # local: drops + reapplies all migrations\n"
    "    supabase db push             # remote: pushes new migrations to staging/prod\n"
    "Or set AETHERIX_SKIP_BOOT_SCHEMA_CHECK=true to bypass this check "
    "(local dev only — never in production)."
)


async def verify_schema(
    engine: AsyncEngine,
    *,
    tables: Iterable[str] = CRITICAL_TABLES,
) -> None:
    """Verify that each critical table exists by issuing `SELECT 1 FROM <t> LIMIT 0`.

    Raises SchemaValidationError listing every missing table when the check fails.
    """
    if os.environ.get("AETHERIX_SKIP_BOOT_SCHEMA_CHECK", "").lower() in {"1", "true", "yes"}:
        logger.warning(
            "AETHERIX_SKIP_BOOT_SCHEMA_CHECK is set — skipping critical-table verification. "
            "Do not use this in production."
        )
        return

    missing: list[tuple[str, str]] = []
    async with engine.connect() as conn:
        for table in tables:
            try:
                # LIMIT 0 returns no rows but still validates that the table exists
                # and is selectable. Identifier is hard-coded from CRITICAL_TABLES,
                # never user input — safe to interpolate.
                await conn.execute(text(f"SELECT 1 FROM {table} LIMIT 0"))
            except SQLAlchemyError as exc:
                missing.append((table, str(exc).splitlines()[0]))

    if missing:
        details = "\n".join(f"  - {tbl}: {err}" for tbl, err in missing)
        raise SchemaValidationError(
            "Boot aborted: critical tables missing or unreadable:\n"
            f"{details}\n"
            f"{_REMEDIATION}"
        )

    logger.info(
        "Schema check passed: %d critical tables verified",
        len(tuple(tables)),
    )
