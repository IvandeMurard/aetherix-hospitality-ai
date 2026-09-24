"""Currency formatting — one configured currency, never a hard-coded symbol.

ADR-0007 §17.1 (24/09/2026): client-facing text mixed £ and $ although the
product targets EU hotels and the ROI simulator already spoke €. Every amount a
manager or a host agent reads goes through ``format_money``; the currency is
``config.CURRENCY`` (ISO 4217, default ``EUR``).
"""
from __future__ import annotations

from app.core import config

_SYMBOLS = {"EUR": "€", "GBP": "£", "USD": "$", "CHF": "CHF "}


def currency_code() -> str:
    return (config.CURRENCY or "EUR").upper()


def currency_symbol() -> str:
    code = currency_code()
    return _SYMBOLS.get(code, f"{code} ")


def format_money(amount: float, decimals: int = 0) -> str:
    """``format_money(1234.5)`` → ``"€1,235"`` (EUR). Symbol first, like the
    strings it replaces; grouping with commas."""
    return f"{currency_symbol()}{float(amount):,.{decimals}f}"
