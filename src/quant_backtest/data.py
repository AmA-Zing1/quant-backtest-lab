"""Validated single-instrument close prices; no silent gap filling."""
from pathlib import Path

import numpy as np
import pandas as pd


def validate_prices(prices: pd.Series) -> pd.Series:
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("Prices must have a DatetimeIndex.")
    if prices.index.hasnans or prices.index.has_duplicates:
        raise ValueError("Dates must be valid and unique.")
    if not prices.index.is_monotonic_increasing:
        raise ValueError("Dates must be in ascending order.")
    values = pd.to_numeric(prices, errors="raise").astype(float)
    if len(values) < 3 or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Provide at least three finite, positive closing prices with no gaps.")
    return values.rename("close")


def load_csv(path: str | Path) -> pd.Series:
    frame = pd.read_csv(path)
    if not {"Date", "Close"}.issubset(frame.columns):
        raise ValueError("CSV requires Date and Close columns (adjusted daily closes recommended).")
    dates = pd.to_datetime(frame["Date"], errors="raise", utc=True).dt.tz_convert(None)
    return validate_prices(pd.Series(frame["Close"].to_numpy(), index=pd.DatetimeIndex(dates)))


def fetch_yahoo(ticker: str, start: str, end: str) -> pd.Series:
    """Fetch adjusted daily closes. Start is inclusive; end is exclusive."""
    import yfinance as yf

    frame = yf.download(ticker, start=start, end=end, interval="1d", auto_adjust=True,
                        progress=False, multi_level_index=False, threads=False)
    if frame is None or frame.empty or "Close" not in frame:
        raise ValueError("No data returned; check ticker, dates, connection, and provider limits.")
    prices = frame["Close"].copy()
    prices.index = pd.to_datetime(prices.index, utc=True).tz_convert(None)
    return validate_prices(prices)
