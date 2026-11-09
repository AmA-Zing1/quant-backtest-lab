"""Daily long/flat accounting with a full close-to-close execution delay."""
import numpy as np
import pandas as pd

from .data import validate_prices


def backtest(prices: pd.Series, signal: pd.Series, initial_cash: float = 100_000,
             commission_bps: float = 1.0, slippage_bps: float = 4.0) -> pd.DataFrame:
    prices = validate_prices(prices)
    settings = [initial_cash, commission_bps, slippage_bps]
    if not np.isfinite(settings).all() or initial_cash <= 0:
        raise ValueError("Cash must be positive and all settings finite.")
    if min(commission_bps, slippage_bps) < 0 or commission_bps + slippage_bps >= 10_000:
        raise ValueError("Costs must be nonnegative and total less than 10,000 bps.")
    if not signal.index.equals(prices.index) or not signal.isin([0.0, 1.0]).all():
        raise ValueError("Signal must align exactly with prices and contain only 0 or 1.")
    # Signal at close t executes at close t+1; first earns close t+1 -> t+2.
    position = signal.shift(2, fill_value=0).astype(float)
    return _account(prices, position, initial_cash, (commission_bps + slippage_bps) / 10_000)


def _account(prices: pd.Series, position: pd.Series, initial_cash: float,
             cost_rate: float) -> pd.DataFrame:
    frame = pd.DataFrame({"close": prices, "position": position}).iloc[1:].copy()
    frame["asset_return"] = prices.pct_change(fill_method=None).iloc[1:]
    frame["turnover"] = frame.position.diff().abs()
    frame.iloc[0, frame.columns.get_loc("turnover")] = frame.position.iloc[0]
    frame["cost_fraction"] = frame.turnover * cost_rate
    frame["net_return"] = (1 - frame.cost_fraction) * (1 + frame.position * frame.asset_return) - 1
    frame["equity"] = initial_cash * (1 + frame.net_return).cumprod()
    peaks = frame.equity.cummax().clip(lower=initial_cash)
    frame["drawdown"] = frame.equity / peaks - 1
    return frame


def buy_and_hold(prices: pd.Series, initial_cash: float = 100_000,
                 commission_bps: float = 1, slippage_bps: float = 4) -> pd.DataFrame:
    # Reuse public validation before applying benchmark entry at the first close.
    backtest(prices, pd.Series(0.0, index=prices.index), initial_cash,
             commission_bps, slippage_bps)
    return _account(prices, pd.Series(1.0, index=prices.index), initial_cash,
                    (commission_bps + slippage_bps) / 10_000)
