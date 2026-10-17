"""PMS provider factory — HOS-280 (Décision #28, consistent with Décision #10).

One instance per (PMS type, transport), created once. Unlike the env-driven
POS factory of ADR-0006 §D6-bis, the PMS is chosen **per hotel** (its
``pms_type``, HOS-347): a global switch would put every hotel on the same PMS.

Adding a PMS = its adapter + one entry in ``_BUILDERS``. A PMS without an
adapter is refused (``PmsIdentityError("pms_not_supported")``), never routed
to another vendor's adapter.
"""
from __future__ import annotations

from functools import lru_cache

from app.providers.pms.base import PMSProvider


def _apaleo_rest():
    from app.providers.pms.apaleo_adapter import ApaleoPMSAdapter

    return ApaleoPMSAdapter()


def _apaleo_mcp():
    from app.providers.pms.apaleo_mcp_adapter import ApaleoMCPAdapter

    return ApaleoMCPAdapter()


def _mock():
    from app.providers.pms.mock_adapter import MockPMSAdapter

    return MockPMSAdapter()


_BUILDERS = {
    ("apaleo", "rest"): _apaleo_rest,
    ("apaleo", "mcp"): _apaleo_mcp,
    ("mock", "mock"): _mock,
}


def supported() -> list[tuple[str, str]]:
    return sorted(_BUILDERS)


@lru_cache(maxsize=None)
def get_pms_provider(pms_type: str, transport: str = "rest") -> PMSProvider:
    from app.services.pms_identity import PmsIdentityError

    builder = _BUILDERS.get((pms_type, transport))
    if builder is None:
        if any(t == pms_type for t, _ in _BUILDERS):
            raise PmsIdentityError("pms_not_supported", f"{pms_type} has no '{transport}' transport")
        raise PmsIdentityError("pms_not_supported",
                               f"no adapter yet for this hotel's PMS ({pms_type}); nothing was synced")
    return builder()
