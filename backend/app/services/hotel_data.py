"""Hotel data ownership: export and deletion of everything about one hotel.

HOS-346, Décision #43. The hotel owns its data: it can see, export and delete
everything Aetherix holds about it, including what the learning loop derived
from it (proposals, approved parameters, calibrations live in
``learning_items`` and ``hotel_decision_parameters``).

Same discipline as ``dsar.py`` (which covers *people*, art. 15/17):

* **One inventory.** ``HOTEL_TABLES`` says, for every table keyed to a hotel,
  which column holds the hotel and what deletion does to it; ``NOT_HOTEL_DATA``
  says why the remaining tables are out of scope. The test
  ``test_every_table_is_classified`` fails when a table is added to the schema
  without being classified here, so the export and the deletion cannot rot as
  the schema grows.
* **A readable plan, dry-run by default.** ``build_deletion_plan`` returns the
  ordered steps with their reason; ``execute_deletion`` touches nothing unless
  ``dry_run=False`` is passed explicitly, and the route also asks the caller
  to type the tenant id.
* **Limits said, not hidden.** ``CAVEATS`` goes into every export and every
  deletion report.

People (``users``) are not deleted with a hotel: a person's data follows the
DSAR path. Data on disk is not per hotel today (the Prophet model file is the
shared demo model); a per-hotel file store must join the inventory before it
ships.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Table, delete, or_, select

from app.db.models import Base

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TableRule:
    key: str                     # column holding the hotel (tenant_id, or hotel_id for MCP-era tables)
    order: int                   # deletion order: children before the rows they reference
    rationale: str
    also_pms_property: bool = False  # key may hold the PMS property id instead (HOS-347)
    omit: tuple[str, ...] = ()       # columns never exported (secrets, raw vectors)


# Deletion order follows the foreign keys: rows that reference a
# recommendation, a prompt or an anomaly go first; restaurant_profiles, which
# several tables reference by tenant_id, goes last.
HOTEL_TABLES: dict[str, TableRule] = {
    "inbound_reply_events": TableRule("tenant_id", 10, "Manager replies and decisions (references manager_prompts, staffing_recommendations)."),
    "conversational_queries": TableRule("tenant_id", 11, "Inbound messages (references staffing_recommendations)."),
    "manager_prompts": TableRule("tenant_id", 12, "Prompts sent to the manager (references staffing_recommendations)."),
    "operational_memory": TableRule("hotel_id", 13, "The hotel's private memory and its embeddings (references staffing_recommendations).",
                                    omit=("embedding",)),
    "staffing_recommendations": TableRule("tenant_id", 20, "Recommendations, decisions and their risk statements (references demand_anomalies)."),
    "demand_anomalies": TableRule("tenant_id", 21, "Detected demand anomalies."),
    "agent_action_log": TableRule("hotel_id", 30, "Agent audit trail for this hotel."),
    "learning_items": TableRule("tenant_id", 31, "What the learning loop proposed from this hotel's decisions and outcomes, approved or not."),
    "hotel_decision_parameters": TableRule("tenant_id", 32, "The hotel's rules and costs, with who set each value, how and when."),
    "hive_consents": TableRule("tenant_id", 33, "The hotel's Hive opt-in history."),
    "hotel_data_requests": TableRule("tenant_id", 38, "Deletion and Hive opt-in requests made by the hotel's agent (codes are stored hashed and never exported).",
                                     omit=("code_hash",)),
    "kpi_daily": TableRule("tenant_id", 34, "Daily KPIs."),
    "fb_patterns": TableRule("tenant_id", 35, "Patterns private to this hotel. Global patterns (tenant_id NULL) hold nothing of the hotel and stay.",
                             omit=("embedding",)),
    "mcp_api_tokens": TableRule("hotel_id", 36, "API tokens bound to the hotel (the token hash is never exported).",
                                omit=("token_hash",)),
    "training_runs": TableRule("property_id", 37, "Forecast training runs.", also_pms_property=True),
    "captation_baselines": TableRule("tenant_id", 40, "Capture-rate baselines (references restaurant_profiles)."),
    "local_events": TableRule("tenant_id", 41, "Local events synced for the hotel (references restaurant_profiles)."),
    "pms_sync_logs": TableRule("tenant_id", 42, "PMS sync history (references restaurant_profiles).", also_pms_property=True),
    "recommendation_cache": TableRule("tenant_id", 43, "Cached recommendations (references restaurant_profiles)."),
    "weather_forecasts": TableRule("tenant_id", 44, "Weather fetched for the hotel (references restaurant_profiles)."),
    "restaurant_profiles": TableRule("tenant_id", 90, "The hotel's profile. Last: other tables reference it."),
}

NOT_HOTEL_DATA: dict[str, str] = {
    "users": "People, not hotels: a person's data is exported or erased through the DSAR path (dsar.py).",
    "eval_baselines": "Evaluation baselines of the product (git sha, layer metrics); no hotel data.",
    "scheduler_event": "Scheduler heartbeats of the platform; no hotel data.",
}

CAVEATS = (
    "Database backups are not purged by a deletion: deleted rows can survive in "
    "snapshots until their retention window ends.",
    "Embedding vectors and token hashes are not included in the export: the "
    "vectors are derived from text that is exported, the hashes are secrets. "
    "Both are deleted with the hotel.",
    "Anonymized Hive aggregates already computed cannot be separated back into "
    "hotels and are kept; later aggregates exclude a hotel that left or opted out "
    "(Décision #43). No Hive aggregate exists yet.",
    "People are not deleted with a hotel: a manager's own data follows the DSAR path.",
)


@dataclass(frozen=True)
class DeletionStep:
    order: int
    table: str
    match: str
    rationale: str


@dataclass
class DeletionReport:
    tenant_id: str
    dry_run: bool
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rows: dict[str, int] = field(default_factory=dict)
    caveats: tuple[str, ...] = CAVEATS

    def as_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id, "dry_run": self.dry_run,
            "executed_at": self.executed_at.isoformat(), "rows": dict(self.rows),
            "total_rows": sum(self.rows.values()), "caveats": list(self.caveats),
        }


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def _keys(tenant_id: str, pms_property_id: Optional[str], rule: TableRule) -> list[str]:
    keys = [tenant_id]
    if rule.also_pms_property and pms_property_id and pms_property_id != tenant_id:
        keys.append(pms_property_id)
    return keys


def _where(name: str, rule: TableRule, keys: list[str]):
    col = _table(name).c[rule.key]
    return or_(*(col == k for k in keys))


def build_deletion_plan(tenant_id: str, pms_property_id: Optional[str] = None) -> list[DeletionStep]:
    """Ordered deletion steps for one hotel, with what each matches and why."""
    if not tenant_id:
        raise ValueError("tenant_id required")
    steps = []
    for name, rule in sorted(HOTEL_TABLES.items(), key=lambda kv: kv[1].order):
        keys = _keys(tenant_id, pms_property_id, rule)
        match = " or ".join(f"{rule.key} = {k!r}" for k in keys)
        steps.append(DeletionStep(rule.order, name, match, rule.rationale))
    return steps


def render_plan(tenant_id: str, steps: list[DeletionStep]) -> str:
    lines = [f"Hotel data deletion plan: {tenant_id}", ""]
    for i, s in enumerate(steps, start=1):
        lines += [f"{i}. {s.table}: DELETE where {s.match}", f"   why: {s.rationale}"]
    lines += ["", *(f"Note: {c}" for c in CAVEATS)]
    return "\n".join(lines)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value) if isinstance(value, uuid.UUID) else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return None
    return value


async def _pms_property_id(session, tenant_id: str) -> Optional[str]:
    profiles = _table("restaurant_profiles")
    row = (await session.execute(
        select(profiles.c.pms_property_id).where(profiles.c.tenant_id == tenant_id)
    )).first()
    return row[0] if row else None


async def export_hotel_data(session, tenant_id: str) -> dict[str, Any]:
    """Everything held about one hotel, table by table, as JSON-ready rows."""
    pms_property_id = await _pms_property_id(session, tenant_id)
    records: dict[str, list[dict]] = {}
    omitted: dict[str, list[str]] = {}
    for name, rule in sorted(HOTEL_TABLES.items(), key=lambda kv: kv[1].order):
        table = _table(name)
        rows = (await session.execute(
            select(table).where(_where(name, rule, _keys(tenant_id, pms_property_id, rule)))
        )).mappings().all()
        records[name] = [
            {k: _jsonable(v) for k, v in row.items() if k not in rule.omit} for row in rows
        ]
        if rule.omit:
            omitted[name] = list(rule.omit)
    return {
        "tenant_id": tenant_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "row_counts": {k: len(v) for k, v in records.items()},
        "omitted_columns": omitted,
        "caveats": list(CAVEATS),
    }


async def execute_deletion(session, tenant_id: str, *, dry_run: bool = True) -> DeletionReport:
    """Delete everything about one hotel, in plan order, in one transaction.

    **Touches nothing** unless ``dry_run=False``: a dry run reports the row
    counts the deletion would remove.
    """
    pms_property_id = await _pms_property_id(session, tenant_id)
    report = DeletionReport(tenant_id=tenant_id, dry_run=dry_run)
    for step in build_deletion_plan(tenant_id, pms_property_id):
        rule = HOTEL_TABLES[step.table]
        where = _where(step.table, rule, _keys(tenant_id, pms_property_id, rule))
        table = _table(step.table)
        if dry_run:
            report.rows[step.table] = len((await session.execute(select(table.c[rule.key]).where(where))).all())
        else:
            result = await session.execute(delete(table).where(where))
            report.rows[step.table] = result.rowcount or 0
    if not dry_run:
        await session.commit()
        logger.info("hotel_data: deleted %d rows for %s", sum(report.rows.values()), tenant_id)
    return report
