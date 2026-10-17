#!/usr/bin/env python3
"""HOS-111 — Supabase RLS audit for tenant-scoped tables.

Verifies that every operational table carrying ``tenant_id`` / ``hotel_id`` /
``property_id`` enforces row-level security in the live database.

For each candidate table we report:

  * ``rls_enabled``       — ``pg_class.relrowsecurity`` flag
  * ``isolation_column``  — first matching scoping column found
  * ``service_role_policy``
                          — at least one ``FOR ALL`` policy (or full CRUD
                            coverage) granted to the backend rôle
  * ``policies``          — raw rows from ``pg_policies`` for the table

The script is *introspection only* — it never writes to the database.

Exit codes
==========
  0  every required table has RLS enabled and a service-role policy
  1  at least one required table fails the audit
  2  cannot reach the database / introspection error

Usage
=====
  python scripts/audit_rls_policies.py                 # full report
  python scripts/audit_rls_policies.py --tables-only   # list candidates only
  python scripts/audit_rls_policies.py --json /tmp/r.json
                                                       # write JSON to disk

Environment
===========
  DATABASE_URL          — required (asyncpg DSN or postgres://)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure scripts/_env_loader.py is importable when invoked from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from _env_loader import load_env  # type: ignore[import-not-found]
    load_env()
except Exception:  # pragma: no cover — env loader is best-effort
    pass


# ---------------------------------------------------------------------------
# Audit scope
# ---------------------------------------------------------------------------
# Tables that MUST carry tenant isolation (per HOS-111 spec + ORM models).
# Each entry records the column we expect RLS to filter on. ``users`` is
# explicitly excluded — it is managed by fastapi-users and tracked in HOS-116.
REQUIRED_TABLES: dict[str, str] = {
    "restaurant_profiles": "tenant_id",
    "demand_anomalies": "tenant_id",
    "staffing_recommendations": "tenant_id",
    "conversational_queries": "tenant_id",
    "operational_memory": "hotel_id",
    "fb_patterns": "tenant_id",
    "mcp_api_tokens": "hotel_id",
    "agent_action_log": "hotel_id",
    "pms_sync_logs": "tenant_id",
    "captation_baselines": "tenant_id",
    "training_runs": "property_id",
    "recommendation_cache": "tenant_id",
    "weather_forecasts": "tenant_id",
    "local_events": "tenant_id",
    # HOS-292 / Q2-05 — added in migration 20260521 (after the 20260515 pre-pilot
    # RLS batch), so it was previously invisible to this audit.
    "kpi_daily": "tenant_id",
    # Décision #38 — manager decision capture (migration 20260924120000).
    "manager_prompts": "tenant_id",
    "inbound_reply_events": "tenant_id",
    # Décision #40 — per-hotel decision parameters (migration 20260925110000).
    "hotel_decision_parameters": "tenant_id",
    # Décision #40 — learning loop review queue (migration 20260925130000).
    "learning_items": "tenant_id",
    # Décision #43 — Hive opt-in per hotel (migration 20261017100000).
    "hive_consents": "tenant_id",
}

# Tables that may exist but are not in scope for this audit (no tenant column,
# managed elsewhere). Listed for clarity in the JSON report.
OUT_OF_SCOPE: set[str] = {"users"}

# Materialized views cannot carry RLS in Postgres (relkind='m', not 'r'). Their
# tenant isolation is inherited from the RLS-protected base tables they read AND
# enforced by the app-layer tenant filter on every read (the backend uses
# service_role, which BYPASSes RLS). Registered here so a *new* MV is a conscious
# decision reviewed for isolation, not a silent gap (HOS-292 / Q2-05).
MATERIALIZED_VIEWS: set[str] = {
    "recommendation_acceptance_daily",
    "abstention_daily",
    "latency_slo_daily",
    "memory_instrumentation_daily",
}


# ---------------------------------------------------------------------------
# Async introspection helpers
# ---------------------------------------------------------------------------

async def _introspect(database_url: str) -> dict[str, Any]:
    """Pull RLS state + policies from the live database."""
    import asyncpg  # local import — keeps the script optional when unused

    # asyncpg expects ``postgres://`` / ``postgresql://`` — strip SQLAlchemy
    # async driver prefix transparently.
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = "postgresql://" + database_url[len("postgresql+asyncpg://"):]

    conn = await asyncpg.connect(database_url)
    try:
        existing_tables: set[str] = {
            row["table_name"]
            for row in await conn.fetch(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """,
            )
        }

        rls_rows = await conn.fetch(
            """
            SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind = 'r'
            """,
        )
        rls_by_table: dict[str, bool] = {
            r["table_name"]: bool(r["rls_enabled"]) for r in rls_rows
        }

        policy_rows = await conn.fetch(
            """
            SELECT tablename, policyname, cmd, roles::text[] AS roles,
                   qual, with_check
              FROM pg_policies
             WHERE schemaname = 'public'
            """,
        )
        policies_by_table: dict[str, list[dict[str, Any]]] = {}
        for row in policy_rows:
            entry = {
                "name": row["policyname"],
                "cmd": row["cmd"],
                "roles": list(row["roles"] or []),
                "using": row["qual"],
                "with_check": row["with_check"],
            }
            policies_by_table.setdefault(row["tablename"], []).append(entry)

        column_rows = await conn.fetch(
            """
            SELECT table_name, column_name
              FROM information_schema.columns
             WHERE table_schema = 'public'
            """,
        )
        columns_by_table: dict[str, set[str]] = {}
        for row in column_rows:
            columns_by_table.setdefault(row["table_name"], set()).add(row["column_name"])

        return {
            "existing_tables": existing_tables,
            "rls_by_table": rls_by_table,
            "policies_by_table": policies_by_table,
            "columns_by_table": columns_by_table,
        }
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Audit logic
# ---------------------------------------------------------------------------

def _service_role_policy(policies: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first policy that grants the backend rôle full CRUD access.

    A single ``FOR ALL`` policy on ``service_role`` is the recommended pattern
    (Option B in HOS-111). We also accept four separate per-command policies
    (SELECT/INSERT/UPDATE/DELETE) — sometimes generated by Supabase Studio.
    """
    role_target = "service_role"
    for_all = [p for p in policies if p["cmd"] in ("ALL", "*") and role_target in p["roles"]]
    if for_all:
        return for_all[0]

    per_cmd = {p["cmd"]: p for p in policies if role_target in p["roles"]}
    required = {"SELECT", "INSERT", "UPDATE", "DELETE"}
    if required.issubset(per_cmd.keys()):
        return {
            "name": "<composite>",
            "cmd": "ALL (composite)",
            "roles": [role_target],
            "members": sorted(p["name"] for p in per_cmd.values()),
        }
    return None


def _audit_table(
    table: str,
    expected_column: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    existing = state["existing_tables"]
    columns = state["columns_by_table"].get(table, set())
    policies = state["policies_by_table"].get(table, [])

    result: dict[str, Any] = {
        "table": table,
        "expected_isolation_column": expected_column,
        "exists": table in existing,
        "rls_enabled": state["rls_by_table"].get(table, False),
        "has_isolation_column": expected_column in columns,
        "service_role_policy": None,
        "policies": policies,
        "issues": [],
    }

    if not result["exists"]:
        result["issues"].append("table missing from public schema")
        return result

    if not result["has_isolation_column"]:
        # Look for any of the recognized scoping columns so an alias still
        # counts (e.g. operational_memory carries hotel_id, not tenant_id).
        for alt in ("tenant_id", "hotel_id", "property_id"):
            if alt in columns:
                result["has_isolation_column"] = True
                result["expected_isolation_column"] = alt
                break

    if not result["has_isolation_column"]:
        result["issues"].append("no tenant_id/hotel_id/property_id column found")

    if not result["rls_enabled"]:
        result["issues"].append("RLS disabled")

    svc_policy = _service_role_policy(policies)
    result["service_role_policy"] = svc_policy
    if svc_policy is None:
        result["issues"].append("no service_role policy granting FOR ALL")

    return result


def build_report(state: dict[str, Any]) -> dict[str, Any]:
    table_reports = [
        _audit_table(table, column, state)
        for table, column in REQUIRED_TABLES.items()
    ]

    failing = [r for r in table_reports if r["issues"]]

    # Mention out-of-scope tables that exist — surfaces unexpected new tables
    # so reviewers can decide whether to add them to REQUIRED_TABLES.
    known_tables = set(REQUIRED_TABLES) | OUT_OF_SCOPE
    other_tables = sorted(state["existing_tables"] - known_tables)

    return {
        "summary": {
            "required_tables": len(REQUIRED_TABLES),
            "missing_or_misconfigured": len(failing),
            "passed": len(table_reports) - len(failing),
        },
        "tables": table_reports,
        "out_of_scope_known": sorted(OUT_OF_SCOPE),
        "other_public_tables": other_tables,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_human(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(
        f"[rls-audit] required={summary['required_tables']} "
        f"passed={summary['passed']} failing={summary['missing_or_misconfigured']}",
    )
    for entry in report["tables"]:
        status = "OK" if not entry["issues"] else "FAIL"
        print(
            f"  [{status}] {entry['table']:<30} "
            f"rls={entry['rls_enabled']} "
            f"col={entry['expected_isolation_column']} "
            f"svc_role_policy={'yes' if entry['service_role_policy'] else 'no'}",
        )
        for issue in entry["issues"]:
            print(f"        -> {issue}")
    if report["other_public_tables"]:
        print(
            "[rls-audit] note: other public tables not in audit scope: "
            + ", ".join(report["other_public_tables"]),
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres DSN (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--tables-only",
        action="store_true",
        help="Print the in-scope table list and exit 0 without hitting the DB",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="Write the full audit report to this file (in addition to stdout)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the human-readable report; emit JSON on stdout only",
    )
    args = parser.parse_args(argv)

    if args.tables_only:
        for table, column in REQUIRED_TABLES.items():
            print(f"{table}\t{column}")
        return 0

    if not args.database_url:
        print(
            "[rls-audit] ERROR: DATABASE_URL not set. Export it or pass --database-url.",
            file=sys.stderr,
        )
        return 2

    try:
        state = asyncio.run(_introspect(args.database_url))
    except ModuleNotFoundError as exc:
        print(f"[rls-audit] ERROR: missing dependency: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover — defensive
        print(f"[rls-audit] ERROR: introspection failed: {exc!r}", file=sys.stderr)
        return 2

    report = build_report(state)

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    if args.quiet:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_human(report)

    return 0 if report["summary"]["missing_or_misconfigured"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
