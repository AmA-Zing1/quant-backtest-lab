"""Causal long/flat signals, computed using observations through each row only."""
import numpy as np
import pandas as pd

from .data import validate_prices


def moving_average(prices: pd.Series, fast: int = 20, slow: int = 100) -> pd.Series:
    prices = validate_prices(prices)
    if not (isinstance(fast, int) and isinstance(slow, int) and 1 <= fast < slow):
        raise ValueError("Require integer windows: 1 <= fast < slow.")
    if len(prices) < slow + 2:
        raise ValueError("Need at least slow + 2 prices for delayed execution.")
    short = prices.rolling(fast, min_periods=fast).mean()
    long = prices.rolling(slow, min_periods=slow).mean()
    return (short > long).astype(float).rename("signal")


def mean_reversion(prices: pd.Series, window: int = 20, entry_z: float = 1.5,
                   exit_z: float = 0.0) -> pd.Series:
    prices = validate_prices(prices)
    if not isinstance(window, int) or window < 2 or len(prices) < window + 2:
        raise ValueError("Require window >= 2 and at least window + 2 prices.")
    if not np.isfinite([entry_z, exit_z]).all() or not 0 <= exit_z < entry_z:
        raise ValueError("Require finite thresholds: 0 <= exit_z < entry_z.")
    average = prices.rolling(window).mean()
    deviation = prices.rolling(window).std(ddof=1).replace(0, np.nan)
    zscore = (prices - average) / deviation
    position = 0.0
    result = []
    for z in zscore:
        if np.isfinite(z):
            if position == 0 and z <= -entry_z:
                position = 1.0
            elif position == 1 and z >= -exit_z:
                position = 0.0
        result.append(position)
    return pd.Series(result, index=prices.index, name="signal")
