"""Small, auditable tools for daily-bar quantitative research."""

from .engine import backtest
from .metrics import performance_metrics
from .strategies import mean_reversion, moving_average

__all__ = ["backtest", "performance_metrics", "mean_reversion", "moving_average"]
