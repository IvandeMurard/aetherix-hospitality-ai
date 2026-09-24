"""Weekly report — the deterministic recap template for one week (ADR-0007 §17.1).

Until 24/09/2026 this was the "Friday Audit": when no ground-truth rows
existed it fell back to hard-coded demo covers, then printed "Accuracy",
"MAPE", "Estimated Savings: £…", "Value Delivered: Nx monthly cost" (from a
"$50 mock SaaS cost") and "Aetherix is optimizing your labor costs
effectively", with nothing saying the numbers were invented.

Now:
  * no mock anywhere on this path — no data → "no measured data yet", no metric;
  * the content is ``decision_recap`` for the week: one definition shared with
    the WhatsApp ``recap`` command, the MCP ``get_decision_recap`` tool and the
    acceptance KPI;
  * no savings, no ROI: nothing measured feeds them (no measured labour hours,
    no measured revenue). They come back only with measured inputs and the
    formula and assumptions printed next to the figure;
  * no marketing prose.

The internal ops side effect (Obsidian note, Linear alert on a degraded forecast)
is kept, fed by measured numbers only.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from app.services.decision_recap import build_recap, render_text

logger = logging.getLogger(__name__)

MAPE_ALERT_THRESHOLD = 30.0  # % — above this triggers a Linear issue
# Below this many measured recommendations a weekly mean is not alerted on.
MAPE_ALERT_MIN_OBSERVATIONS = 3

NO_DATA_STATUS = "no_measured_data"
FINANCIAL_OMITTED = (
    "Not computed: no measured labour-cost or revenue input exists for this "
    "tenant. A savings figure is reported only from measured inputs, with its "
    "formula and assumptions stated."
)


def no_data_text(locale: Optional[str] = "fr") -> str:
    if (locale or "").lower().startswith("en"):
        return "Weekly report: no measured data yet for this period."
    return "Rapport hebdomadaire : pas encore de donnée mesurée sur la période."


class ReportingService:
    def __init__(self, db_service=None):
        self.db = db_service

    async def generate_weekly_metrics(
        self, tenant_id: str, week_start: date, locale: Optional[str] = "fr"
    ) -> Dict[str, Any]:
        """Weekly recap for ``tenant_id`` (Monday ``week_start`` → Sunday).

        ``status`` is ``no_measured_data`` when the week holds no
        recommendation, ``ok`` otherwise. ``financial_impact`` is always
        ``None`` today (see ``FINANCIAL_OMITTED``).
        """
        week_end = week_start + timedelta(days=6)
        if self.db is None:
            summary = None
        else:
            summary = await build_recap(self.db, tenant_id, "week", start=week_start, end=week_end)

        no_data = summary is None or summary.received == 0
        result: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "period": f"{week_start} to {week_end}",
            "status": NO_DATA_STATUS if no_data else "ok",
            "recap": summary.as_dict() if summary else None,
            "summary_text": no_data_text(locale) if no_data else render_text(summary, locale),
            "financial_impact": None,
            "financial_impact_note": FINANCIAL_OMITTED,
        }
        if not no_data:
            await self._dispatch_ops(result)
        return result

    async def _dispatch_ops(self, result: Dict[str, Any]) -> None:
        """Fire-and-forget internal ops note (Obsidian) + Linear alert when the
        measured weekly forecast error is degraded.

        HOS-248 (AC5): any failure here is swallowed and trips a typed ops
        alert instead of breaking the caller. Only measured numbers are written.
        """
        try:
            from app.integrations.obsidian import VAULT_FOLDERS
            from app.services.ops_dispatcher import dispatch_anomaly, dispatch_report

            r = result["recap"]
            period = result["period"]
            tenant = result["tenant_id"]
            err = r["forecast_error_pct"]
            err_cell = (
                f"{err}% over {r['forecast_error_days']} day(s), "
                f"{r['forecast_error_observations']} recommendation(s)"
                if err is not None else "not measured (no actual covers)"
            )
            human = r["human"]
            note_content = (
                f"# Weekly recap — {tenant}\n\n"
                f"**Period:** {period}\n\n"
                f"| Metric | Value |\n|---|---|\n"
                f"| Recommendations received | {r['received']} |\n"
                f"| Accepted / rejected / corrected | {r['accepted']} / {r['rejected']} / {r['corrected']} |\n"
                f"| No reply / awaiting confirmation | {r['no_reply']} / {r['awaiting_confirmation']} |\n"
                f"| Human acceptance rate | {human['acceptance_rate']} (n={human['decided']}) |\n"
                f"| Mean forecast error | {err_cell} |\n"
            )
            await dispatch_report(
                title=f"Weekly recap {period}",
                content=note_content,
                folder=VAULT_FOLDERS["reports"],
                tags=["weekly-recap", tenant],
            )

            if (
                err is not None
                and err > MAPE_ALERT_THRESHOLD
                and r["forecast_error_observations"] >= MAPE_ALERT_MIN_OBSERVATIONS
            ):
                await dispatch_anomaly(
                    title=f"[{tenant}] Forecast error degraded — {err}%",
                    detail=(
                        f"Weekly mean forecast error above {MAPE_ALERT_THRESHOLD}% for {period} "
                        f"({r['forecast_error_observations']} measured recommendation(s), "
                        f"{r['forecast_error_days']} day(s)).\n\n"
                        "Possible causes: missing PMS data, model drift, or unusual demand spike."
                    ),
                    tags=["model", "accuracy"],
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("reporting_service._dispatch_ops failed (non-blocking)")
            try:
                from app.workers.heartbeat import REASON_JOB_ERROR, record_trip

                await record_trip(
                    "reporting_service",
                    REASON_JOB_ERROR,
                    f"_dispatch_ops failed during weekly report. Error: {exc!r}",
                )
            except Exception as inner:  # noqa: BLE001
                logger.warning("reporting_service: trip alert failed: %s", inner)
