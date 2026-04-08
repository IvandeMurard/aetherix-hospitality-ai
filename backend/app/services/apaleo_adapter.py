from app.services.pms_sync import PMSAdapter
from app.integrations.apaleo_logger import (
    ApaleoAgentLogger,
    ApaleoWriteBlockedError,
    is_readonly_mode,
)
from typing import List, Dict, Any, Optional
import os
import logging
import time
import httpx
from datetime import date, datetime
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)
_agent_logger = ApaleoAgentLogger()


class ApaleoSyncError(Exception):
    """Raised when the Apaleo API returns an error response during sync."""


class ApaleoPMSAdapter(PMSAdapter):
    """
    Adapter for the Apaleo PMS API.
    Implementation of Story 2.1 (Establish PMS API Connection & Auth).
    """

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
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "offline_access openid profile read:occupancy read:revenue write:schedules"
                }
            )
            response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)
        self.token_expiry = time.time() + expires_in
        logger.info("Successfully authenticated with Apaleo")

    async def get_occupancy(self, property_id: str, target_date: date) -> int:
        """
        Fetches occupancy metrics for a given date.
        Raises ApaleoSyncError on non-200 responses.
        """
        if not self.access_token:
            await self._authenticate()

        tool = "REST_GET_OCCUPANCY"
        params = {"date": target_date.isoformat(), "propertyId": property_id}
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"{self.api_base_url}/booking/v1/metrics/occupancy"
        t0 = time.monotonic()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers)
                duration_ms = (time.monotonic() - t0) * 1000
                if response.status_code == 200:
                    data = response.json()
                    result = int(data.get("occupancy") or 85)
                    _agent_logger.log(tool, params, mode="read", duration_ms=duration_ms,
                                      result_summary=str(result))
                    return result
                else:
                    _agent_logger.log(tool, params, mode="read", duration_ms=duration_ms,
                                      error=f"HTTP {response.status_code}")
                    raise ApaleoSyncError(f"HTTP {response.status_code}")
        except ApaleoSyncError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.error(f"Apaleo API error: {str(e)}")
            _agent_logger.log(tool, params, mode="read", duration_ms=duration_ms, error=str(e))
            raise

    async def get_revenue(self, property_id: str, target_date: date, category: str = "Total") -> float:
        """
        Fetches revenue metrics.
        Raises ApaleoSyncError on non-200 responses.
        """
        if not self.access_token:
            await self._authenticate()

        tool = "REST_GET_REVENUE"
        params = {
            "from": target_date.isoformat(),
            "to": target_date.isoformat(),
            "propertyId": property_id,
            "category": category,
        }
        url = f"{self.api_base_url}/finance/v1/metrics/revenue"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        t0 = time.monotonic()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers)
                duration_ms = (time.monotonic() - t0) * 1000
                if response.status_code == 200:
                    data = response.json()
                    revenue_list = data.get("revenue", [])
                    fb_revenue = sum(item.get("amount", 0.0) for item in revenue_list if category.lower() in item.get("category", "").lower())
                    result = fb_revenue if fb_revenue > 0 else sum(item.get("amount", 0.0) for item in revenue_list)
                    _agent_logger.log(tool, params, mode="read", duration_ms=duration_ms,
                                      result_summary=str(result))
                    return result
                _agent_logger.log(tool, params, mode="read", duration_ms=duration_ms,
                                  error=f"HTTP {response.status_code}")
                raise ApaleoSyncError(f"HTTP {response.status_code}")
        except ApaleoSyncError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - t0) * 1000
            _agent_logger.log(tool, params, mode="read", duration_ms=duration_ms, error=str(e))
            raise

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
