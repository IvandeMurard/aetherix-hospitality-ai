"""Moved to ``app.providers.pms.apaleo_adapter`` (HOS-280, Décision #28).

Kept as a re-export so existing imports keep working. ``httpx`` stays imported
so ``patch("app.services.apaleo_adapter.httpx.AsyncClient")`` still targets the
module the adapter uses.
"""
import httpx  # noqa: F401 — see docstring

from app.providers.pms.apaleo_adapter import (  # noqa: F401
    ApaleoPMSAdapter,
    ApaleoSyncError,
    map_stay_record,
    map_performance_report,
)
