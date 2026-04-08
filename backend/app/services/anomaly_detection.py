"""Anomaly detection service.

Implements:
  - AnomalyDetectionService.generate_windows()   — 4-hour UTC window generator
  - AnomalyDetectionService.detect_for_property() — per-property anomaly detection
  - AnomalyDetectionService.run_full_scan()       — parallel cross-tenant scan (NFR5)

Architecture constraints:
- All detection logic lives here (Fat Backend).
- Bulk upsert via INSERT ... ON CONFLICT for idempotency (AC 7).
- asyncio.gather for parallel scans (NFR5 / AC 8).
[Source: architecture.md#Structure-Patterns, story 3.3a Dev Notes]
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

import sqlalchemy.exc
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AnomalyDetectionError
from app.db.models import DemandAnomaly, LocalEvent, WeatherForecast
from app.services.demand_modifiers import event_modifier, weather_modifier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ANOMALY_DEVIATION_THRESHOLD: float = float(
    os.getenv("ANOMALY_DEVIATION_THRESHOLD", "20.0")
)

# Combined modifier cap: weather + events bounded to [-0.50, +0.75]
_COMBINED_MIN = -0.50
_COMBINED_MAX = +0.75


class AnomalyDetectionService:
    """Core anomaly detection service.

    All public methods accept an AsyncSession which must be provided by the
    caller (route handler or background worker).
    """

    # ------------------------------------------------------------------
    # Window generation
    # ------------------------------------------------------------------
    @staticmethod
    def generate_windows(
        start: datetime,
        days_ahead: int = 14,
    ) -> List[Tuple[datetime, datetime]]:
        """Generate non-overlapping 4-hour UTC windows for the next `days_ahead` days.

        Windows are aligned to UTC hours 0, 4, 8, 12, 16, 20.

        Args:
            start:      The reference datetime (typically utcnow).
            days_ahead: Number of calendar days to cover (default 14).

        Returns:
            List of (window_start, window_end) tuples in ascending order.
        """
        # Align to the next 4-hour boundary
        start_utc = start.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        hour_offset = (start_utc.hour // 4) * 4
        first_window = start_utc.replace(hour=hour_offset)
        if first_window < start_utc:
            first_window += timedelta(hours=4)

        end_boundary = first_window + timedelta(days=days_ahead)
        windows: List[Tuple[datetime, datetime]] = []
        current = first_window
        while current < end_boundary:
            windows.append((current, current + timedelta(hours=4)))
            current += timedelta(hours=4)
        return windows

    # ------------------------------------------------------------------
    # Per-property detection
    # ------------------------------------------------------------------
    async def detect_for_property(
        self,
        db: AsyncSession,
        property_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> List[DemandAnomaly]:
        """Detect demand anomalies for a single property over the next 14 days.

        Steps for each 4-hour window:
          1. Load baseline demand from captation_rates (day-of-week segmented).
          2. Get weather forecast covering that window.
          3. Get local events overlapping that window.
          4. Compute expected_demand = baseline * (1 + combined_modifier).
          5. Compute deviation_pct.
          6. Record anomaly if abs(deviation_pct) >= threshold.
          7. Bulk upsert via INSERT ... ON CONFLICT.

        Args:
            db:          Async SQLAlchemy session.
            property_id: UUID of the property being scanned.
            tenant_id:   UUID of the owning tenant (for RLS-safe inserts).

        Returns:
            List of DemandAnomaly ORM instances that were upserted.
        """
        now_utc = datetime.now(timezone.utc)
        windows = self.generate_windows(now_utc)
        anomalies_to_upsert: List[dict] = []

        for window_start, window_end in windows:
            # 1. Baseline demand from captation_rates (fallback to 1000.0 if missing)
            baseline_demand = await self._get_baseline_demand(
                db, property_id, tenant_id, window_start
            )

            # 2. Weather forecast
            weather_row = await self._get_weather_for_window(
                db, property_id, window_start
            )
            weather_mod = 0.0
            weather_factor = None
            if weather_row:
                weather_mod, weather_factor = weather_modifier(
                    weather_row.condition_code
                )

            # 3. Local events overlapping the window
            event_rows = await self._get_events_for_window(
                db, property_id, window_start, window_end
            )
            event_mod = 0.0
            event_factors: list = []
            if event_rows:
                event_mod, event_factors = event_modifier(event_rows)

            # 4. Combine modifiers with caps [-0.50, +0.75]
            combined = weather_mod + event_mod
            combined = max(_COMBINED_MIN, min(_COMBINED_MAX, combined))

            expected_demand = float(baseline_demand) * (1.0 + combined)

            # 5. Deviation
            if float(baseline_demand) == 0:
                continue  # Avoid division by zero
            deviation_pct = (expected_demand - float(baseline_demand)) / float(
                baseline_demand
            ) * 100.0

            # 6. Threshold check
            if abs(deviation_pct) < ANOMALY_DEVIATION_THRESHOLD:
                continue

            direction = "surge" if deviation_pct > 0 else "lull"
            triggering_factors = []
            if weather_factor:
                triggering_factors.append(weather_factor)
            triggering_factors.extend(event_factors)

            anomalies_to_upsert.append(
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": str(tenant_id),
                    "property_id": str(property_id),
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "expected_demand": round(expected_demand, 2),
                    "baseline_demand": round(float(baseline_demand), 2),
                    "deviation_pct": round(deviation_pct, 2),
                    "direction": direction,
                    "triggering_factors": triggering_factors,
                    "status": "detected",
                }
            )

        if not anomalies_to_upsert:
            return []

        # 7. Bulk upsert — idempotent via ON CONFLICT (AC 7)
        upserted_ids = await self._bulk_upsert(db, anomalies_to_upsert)

        # Return ORM instances without an extra round-trip: reconstruct from the
        # already-computed data (R3 — fix return type List[str] → List[DemandAnomaly]).
        # On conflict the RETURNING clause gives the existing row's ID which may differ
        # from anomalies_to_upsert[i]["id"]; fall back to a bare instance with id only.
        if not upserted_ids:
            return []
        id_to_data = {a["id"]: a for a in anomalies_to_upsert}
        orm_result: List[DemandAnomaly] = []
        for uid in upserted_ids:
            data = id_to_data.get(uid)
            da = DemandAnomaly()
            if data:
                da.id = data["id"]
                da.tenant_id = data["tenant_id"]
                da.property_id = data["property_id"]
                da.window_start = data["window_start"]
                da.window_end = data["window_end"]
                da.expected_demand = data["expected_demand"]
                da.baseline_demand = data["baseline_demand"]
                da.deviation_pct = data["deviation_pct"]
                da.direction = data["direction"]
                da.triggering_factors = data["triggering_factors"]
                da.status = data["status"]
            else:
                da.id = uid  # existing row ID from conflict resolution
            orm_result.append(da)
        return orm_result

    # ------------------------------------------------------------------
    # Full cross-tenant scan (NFR5)
    # ------------------------------------------------------------------
    async def run_full_scan(self, db: AsyncSession) -> None:
        """Run anomaly detection for all active properties in parallel.

        Uses asyncio.gather to fulfil NFR5 (<5s for 50 properties).
        Logs elapsed time and emits WARNING if approaching the 4.5s boundary.

        Args:
            db: Async SQLAlchemy session (shared for property listing;
                each property detection re-uses the same session in gather).
        """
        t_start = time.monotonic()

        # Fetch all active (tenant_id, id) pairs from properties
        try:
            result = await db.execute(
                text(
                    "SELECT id, tenant_id FROM properties WHERE is_active = TRUE"
                )
            )
            properties = result.fetchall()
        except sqlalchemy.exc.SQLAlchemyError:
            logger.exception("Failed to fetch active properties for anomaly scan")
            return

        if not properties:
            logger.info("anomaly_scan: no active properties found, skipping")
            return

        tasks = [
            self.detect_for_property(
                db,
                property_id=row[0],
                tenant_id=row[1],
            )
            for row in properties
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.monotonic() - t_start

        error_count = sum(1 for r in results if isinstance(r, Exception))
        if error_count:
            logger.warning(
                "anomaly_scan: %d/%d property scans raised exceptions",
                error_count,
                len(tasks),
            )
        for i, exc in enumerate(results):
            if isinstance(exc, AnomalyDetectionError):
                logger.error(
                    "anomaly_scan: AnomalyDetectionError for property %s — skipping: %s",
                    properties[i][0] if i < len(properties) else "unknown",
                    exc,
                )
            elif isinstance(exc, Exception):
                logger.error("anomaly_scan property error: %s", exc)

        if elapsed > 4.5:
            logger.warning(
                "anomaly_scan: elapsed %.2fs exceeds 4.5s early-warning threshold "
                "(NFR5 limit is 5s)",
                elapsed,
            )
        else:
            logger.info(
                "anomaly_scan: completed %d properties in %.3fs",
                len(tasks),
                elapsed,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    async def _get_baseline_demand(
        self,
        db: AsyncSession,
        property_id: uuid.UUID,
        tenant_id: uuid.UUID,
        window_start: datetime,
    ) -> Decimal:
        """Load baseline demand from captation_rates table (Story 2.4).

        Falls back to Decimal("1000.00") if no baseline is found so that
        modifier maths still runs correctly during early test/dev.
        """
        dow = window_start.strftime("%A").lower()  # e.g. "monday"
        hour_block = (window_start.hour // 4) * 4  # 0, 4, 8, 12, 16, 20

        try:
            result = await db.execute(
                text(
                    """
                    SELECT baseline_revenue
                    FROM captation_rates
                    WHERE property_id = :property_id
                      AND tenant_id   = :tenant_id
                      AND day_of_week = :dow
                      AND hour_block  = :hour_block
                    LIMIT 1
                    """
                ),
                {
                    "property_id": str(property_id),
                    "tenant_id": str(tenant_id),
                    "dow": dow,
                    "hour_block": hour_block,
                },
            )
            row = result.fetchone()
            if row and row[0] is not None:
                return Decimal(str(row[0]))
        except sqlalchemy.exc.ProgrammingError:
            # Table does not exist (dev/test environment) — use fallback silently
            logger.debug(
                "captation_rates table not found for property %s — using fallback",
                property_id,
            )
        except sqlalchemy.exc.SQLAlchemyError:
            logger.error(
                "captation_rates lookup failed for property %s — DB error, raising",
                property_id,
            )
            raise AnomalyDetectionError(
                f"DB error during baseline lookup for property {property_id}"
            )

        return Decimal("1000.00")

    async def _get_weather_for_window(
        self,
        db: AsyncSession,
        property_id: uuid.UUID,
        window_start: datetime,
    ) -> Optional[WeatherForecast]:
        """Return the nearest weather forecast row for the given window start."""
        try:
            result = await db.execute(
                text(
                    """
                    SELECT id, condition_code, forecast_timestamp
                    FROM weather_forecasts
                    WHERE property_id = :property_id
                      AND forecast_timestamp >= :ts_from
                      AND forecast_timestamp <  :ts_to
                    ORDER BY ABS(EXTRACT(EPOCH FROM (forecast_timestamp - :ts_from)))
                    LIMIT 1
                    """
                ),
                {
                    "property_id": str(property_id),
                    "ts_from": window_start.isoformat(),
                    "ts_to": (window_start + timedelta(hours=4)).isoformat(),
                },
            )
            row = result.fetchone()
            if row:
                wf = WeatherForecast()
                wf.id = row[0]
                wf.condition_code = row[1]
                return wf
        except sqlalchemy.exc.SQLAlchemyError:
            logger.debug(
                "weather_forecasts lookup failed for property %s", property_id
            )
        return None

    async def _get_events_for_window(
        self,
        db: AsyncSession,
        property_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> List[LocalEvent]:
        """Return all active local events overlapping the given window."""
        try:
            result = await db.execute(
                text(
                    """
                    SELECT id, predicthq_event_id, category, impact_score
                    FROM local_events
                    WHERE property_id = :property_id
                      AND start_dt < :window_end
                      AND (end_dt IS NULL OR end_dt > :window_start)
                    ORDER BY impact_score DESC NULLS LAST
                    """
                ),
                {
                    "property_id": str(property_id),
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                },
            )
            rows = result.fetchall()
            events = []
            for row in rows:
                e = LocalEvent()
                e.id = row[0]
                e.predicthq_event_id = row[1]
                e.category = row[2]
                e.impact_score = row[3]
                events.append(e)
            return events
        except sqlalchemy.exc.SQLAlchemyError:
            logger.debug(
                "local_events lookup failed for property %s", property_id
            )
        return []

    async def _bulk_upsert(
        self,
        db: AsyncSession,
        anomalies: List[dict],
    ) -> List[str]:
        """Bulk upsert anomalies using INSERT ... ON CONFLICT DO UPDATE.

        Idempotent: duplicate (tenant_id, property_id, window_start) rows are
        updated in place rather than inserted again (AC 7).

        Returns:
            List of UUID strings for the upserted rows (from RETURNING id).
        """
        import json

        stmt = text(
            """
            INSERT INTO demand_anomalies
                (id, tenant_id, property_id, window_start, window_end,
                 expected_demand, baseline_demand, deviation_pct,
                 direction, triggering_factors, status, detected_at)
            VALUES
                (:id, :tenant_id, :property_id, :window_start, :window_end,
                 :expected_demand, :baseline_demand, :deviation_pct,
                 :direction, :triggering_factors, :status, NOW())
            ON CONFLICT (tenant_id, property_id, window_start)
            DO UPDATE SET
                window_end          = EXCLUDED.window_end,
                expected_demand     = EXCLUDED.expected_demand,
                baseline_demand     = EXCLUDED.baseline_demand,
                deviation_pct       = EXCLUDED.deviation_pct,
                direction           = EXCLUDED.direction,
                triggering_factors  = EXCLUDED.triggering_factors,
                status              = EXCLUDED.status
            RETURNING id
            """
        )
        result_ids = []
        for a in anomalies:
            params = dict(a)
            params["triggering_factors"] = json.dumps(params["triggering_factors"])
            res = await db.execute(stmt, params)
            row = res.fetchone()
            if row:
                result_ids.append(row[0])

        await db.commit()
        return result_ids
