"""Apaleo PMS adapter over the REST API — Story 2.1, moved to the vendor-neutral
PMS layer by HOS-280 (Décision #28), true-or-absent figures since HOS-352.

Only this module knows Apaleo's native payloads. Occupancy and F&B revenue
both come from the property-performance report, the same payload the MCP
transport reads (``ListPropertyPerformanceReport``), mapped once by
``map_performance_report``: the two transports cannot disagree on a day.

Before HOS-352 this adapter called ``/booking/v1/metrics/occupancy`` and
``/finance/v1/metrics/revenue``. Probed against the sandbox on 18/10/2026,
both return 404, and the token request with their custom scopes returns 400:
the REST path never returned a real figure.
"""
import logging
import os
import time
from datetime import date
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.integrations.apaleo_logger import (
    ApaleoAgentLogger,
    ApaleoWriteBlockedError,
    is_readonly_mode,
)
from app.providers.pms.base import (
    NormalizedOccupancy,
    NormalizedReservation,
    NormalizedRevenue,
    PMSDataStatus,
    PMSProviderName,
    parse_day,
)

logger = logging.getLogger(__name__)
_agent_logger = ApaleoAgentLogger()


class ApaleoSyncError(Exception):
    """Raised when the Apaleo API returns an error response during sync."""


def map_stay_record(rec: Dict[str, Any]) -> NormalizedReservation:
    """Apaleo stay record / reservation → canonical reservation."""
    return NormalizedReservation(
        vendor_reservation_id=rec.get("id"),
        arrival=parse_day(rec.get("arrival")),
        departure=parse_day(rec.get("departure")),
        adults=int(rec.get("adults") or 0),
        children=int(rec.get("children") or 0) if not isinstance(rec.get("children"), list)
        else len(rec.get("children")),
        status=rec.get("status"),
        provider=PMSProviderName.APALEO,
        raw_fields=tuple(sorted(rec.keys())),
    )


def _count(report: Dict[str, Any], key: str) -> Optional[int]:
    value = report.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def map_performance_report(
    report: Any, pms_property_id: str, day: date
) -> tuple[NormalizedOccupancy, NormalizedRevenue]:
    """Apaleo property-performance report (REST or MCP) → canonical figures.

    * occupancy: ``soldCount`` rooms sold out of ``houseCount`` minus
      ``outOfOrderCount`` (a room out of order cannot be sold). No sellable
      room reported → absent (``no_data``), never a default.
    * revenue: ``netFoodAndBeveragesRevenue`` (F&B, net of tax). Missing →
      absent; the report's other revenue lines are never used in its place.
    """
    report = report if isinstance(report, dict) else {}
    apaleo = PMSProviderName.APALEO
    sold, house = _count(report, "soldCount"), _count(report, "houseCount")
    available = None if house is None else house - (_count(report, "outOfOrderCount") or 0)
    if sold is None or available is None or available <= 0:
        occupancy = NormalizedOccupancy.absent(pms_property_id, day, apaleo, PMSDataStatus.NO_DATA,
                                               "no sellable rooms in the performance report")
    else:
        occupancy = NormalizedOccupancy(pms_property_id=pms_property_id, day=day, provider=apaleo,
                                        status=PMSDataStatus.OK, rooms_sold=sold, rooms_available=available)

    money = report.get("netFoodAndBeveragesRevenue")
    amount = money.get("amount") if isinstance(money, dict) else None
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        revenue = NormalizedRevenue.absent(pms_property_id, day, apaleo, PMSDataStatus.NO_DATA,
                                           "no net F&B revenue in the performance report")
    else:
        revenue = NormalizedRevenue(pms_property_id=pms_property_id, day=day, provider=apaleo,
                                    status=PMSDataStatus.OK, amount=float(amount), currency=money.get("currency"))
    return occupancy, revenue


class ApaleoPMSAdapter:
    """
    Adapter for the Apaleo PMS API.
    Implementation of Story 2.1 (Establish PMS API Connection & Auth).
    """

    provider_name = PMSProviderName.APALEO
    transport = "rest"

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def aclose(self) -> None:
        return None

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.api_base_url = "https://api.apaleo.com"
        self.client_id = client_id or os.getenv("APALEO_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("APALEO_CLIENT_SECRET")
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def _authenticate(self):
        """Fetch/Refresh OAuth2 token for Apaleo (retries up to 3x on HTTPStatusError)."""
        # Check if token is still valid (with 60s buffer)
        if self.access_token and time.time() < self.token_expiry - 60:
            return

        if not self.client_id or not self.client_secret:
            raise ValueError("Apaleo credentials missing in environment.")

        token_url = "https://identity.apaleo.com/connect/token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                # No custom scope: "read:occupancy read:revenue write:schedules"
                # is rejected by Apaleo identity (400, HOS-352). The client's
                # granted scopes apply, as for the MCP client.
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                }
            )
            response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)
        self.token_expiry = time.time() + expires_in
        logger.info("Successfully authenticated with Apaleo")

    async def fetch_reservations(self, pms_property_id: str, start: date, end: date) -> List[NormalizedReservation]:
        return [map_stay_record(r) for r in await self.get_historical_data(pms_property_id, start, end)]

    async def _performance(self, property_id: str, target_date: date) -> tuple[NormalizedOccupancy, NormalizedRevenue]:
        """One day of the property-performance report, or both figures absent
        with the reason. Never raises for a PMS-side problem."""
        apaleo = PMSProviderName.APALEO
        if not self.is_configured:
            return (NormalizedOccupancy.absent(property_id, target_date, apaleo, PMSDataStatus.NOT_CONFIGURED),
                    NormalizedRevenue.absent(property_id, target_date, apaleo, PMSDataStatus.NOT_CONFIGURED))

        tool = "REST_GET_PROPERTY_PERFORMANCE"
        params = {"propertyId": property_id, "from": target_date.isoformat(), "to": target_date.isoformat()}
        url = f"{self.api_base_url}/reports/v1/reports/property-performance"
        t0 = time.monotonic()
        try:
            await self._authenticate()
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers={"Authorization": f"Bearer {self.access_token}"})
            duration_ms = (time.monotonic() - t0) * 1000
            if response.status_code != 200:
                raise ApaleoSyncError(f"HTTP {response.status_code}")
            _agent_logger.log(tool, params, mode="read", duration_ms=duration_ms, result_summary="performance report")
            return map_performance_report(response.json(), property_id, target_date)
        except Exception as exc:  # noqa: BLE001 — any failure is a pms_error, never a made-up figure
            duration_ms = (time.monotonic() - t0) * 1000
            logger.error("Apaleo property-performance failed for %s on %s: %s", property_id, target_date, exc)
            _agent_logger.log(tool, params, mode="read", duration_ms=duration_ms, error=str(exc))
            detail = str(exc)[:200]
            return (NormalizedOccupancy.absent(property_id, target_date, apaleo, PMSDataStatus.PMS_ERROR, detail),
                    NormalizedRevenue.absent(property_id, target_date, apaleo, PMSDataStatus.PMS_ERROR, detail))

    async def fetch_occupancy(self, property_id: str, target_date: date) -> NormalizedOccupancy:
        return (await self._performance(property_id, target_date))[0]

    async def fetch_fb_revenue(self, property_id: str, target_date: date) -> NormalizedRevenue:
        return (await self._performance(property_id, target_date))[1]

    async def get_historical_data(self, property_id: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Fetches bulk historical data from Apaleo Stay API with full pagination.
        Raises ApaleoSyncError on non-200 responses.
        """
        if not self.access_token:
            await self._authenticate()

        tool = "REST_GET_HISTORICAL_DATA"
        base_params = {
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "propertyId": property_id,
        }
        url = f"{self.api_base_url}/reports/v1/stay-records"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        t0 = time.monotonic()
        all_records: List[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient() as client:
                params = dict(base_params)
                while True:
                    response = await client.get(url, params=params, headers=headers)
                    if response.status_code != 200:
                        duration_ms = (time.monotonic() - t0) * 1000
                        logger.warning(f"Failed to fetch historical data: {response.status_code}")
                        _agent_logger.log(tool, base_params, mode="read", duration_ms=duration_ms,
                                          error=f"HTTP {response.status_code}")
                        raise ApaleoSyncError(f"HTTP {response.status_code}")

                    data = response.json()
                    # Support both list response (legacy) and paginated object response
                    if isinstance(data, list):
                        all_records.extend(data)
                        break
                    else:
                        page_records = data.get("stayRecords", [])
                        all_records.extend(page_records)
                        page_info = data.get("pageInfo", {})
                        if not page_info.get("hasNext", False):
                            break
                        next_token = page_info.get("nextPageToken")
                        if not next_token:
                            break
                        params = {**base_params, "pageToken": next_token}

            duration_ms = (time.monotonic() - t0) * 1000
            logger.info(
                "Apaleo historical data: fetched %d total records for %s (%s→%s)",
                len(all_records), property_id, start_date, end_date,
            )
            _agent_logger.log(tool, base_params, mode="read", duration_ms=duration_ms,
                              result_summary=f"{len(all_records)} records")
            return all_records

        except ApaleoSyncError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.error(f"Apaleo Historical fetch error: {str(e)}")
            _agent_logger.log(tool, base_params, mode="read", duration_ms=duration_ms, error=str(e))
            raise

    async def update_staffing_in_pms(self, property_id: str, target_date: date, staffing_deltas: Dict[str, int]) -> bool:
        """
        Writes staffing recommendations back to Apaleo Schedules/Operations.

        Write-guard (HOS-107)
        ---------------------
        Raises ``ApaleoWriteBlockedError`` when ``APALEO_READONLY`` is not
        explicitly set to ``"false"``.  The blocked attempt is logged at
        WARNING level before the exception is raised.

        Note: Target endpoint is exploratory based on 'Schedules' project requirement.
        """
        tool = "REST_UPDATE_STAFFING"
        params = {
            "propertyId": property_id,
            "date": target_date.isoformat(),
            "deltas": staffing_deltas,
        }

        # ── Write-guard ────────────────────────────────────────────────────
        if is_readonly_mode():
            _agent_logger.log(
                tool,
                params,
                mode="blocked",
                error="read-only mode active (Phase 0) — set APALEO_READONLY=false to enable writes",
            )
            raise ApaleoWriteBlockedError(
                "ApaleoPMSAdapter.update_staffing_in_pms blocked — "
                "Apaleo is in read-only mode (Phase 0). "
                "Set APALEO_READONLY=false to enable writes."
            )

        if not self.access_token:
            await self._authenticate()

        url = f"{self.api_base_url}/operations/v1/schedules"
        payload = {**params, "source": "Aetherix-AI"}
        headers = {"Authorization": f"Bearer {self.access_token}"}
        t0 = time.monotonic()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                duration_ms = (time.monotonic() - t0) * 1000
                if response.status_code in [200, 201, 204]:
                    logger.info(f"Successfully pushed staffing to Apaleo for {property_id}")
                    _agent_logger.log(tool, params, mode="write", duration_ms=duration_ms,
                                      result_summary=f"HTTP {response.status_code}")
                    return True
                logger.error(f"Apaleo Push Failed ({response.status_code}): {response.text}")
                _agent_logger.log(tool, params, mode="write", duration_ms=duration_ms,
                                  error=f"HTTP {response.status_code}")
                return False
        except ApaleoWriteBlockedError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.error(f"Apaleo Push Exception: {str(e)}")
            _agent_logger.log(tool, params, mode="write", duration_ms=duration_ms, error=str(e))
            return False
