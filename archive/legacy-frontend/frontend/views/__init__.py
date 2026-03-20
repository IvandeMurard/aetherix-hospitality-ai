"""Aetherix views - forecast, history, settings."""

from .forecast_view import render_forecast_view
from .history_view import render_history_view
from .settings_view import render_settings_view

__all__ = ["render_forecast_view", "render_history_view", "render_settings_view"]
