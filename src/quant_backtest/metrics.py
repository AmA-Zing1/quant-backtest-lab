"""Annualized metrics with explicit conventions and undefined ratios as None."""
import numpy as np
import pandas as pd


def performance_metrics(result: pd.DataFrame, initial_cash: float = 100_000,
                        risk_free_rate: float = 0.0, periods_per_year: int = 252) -> dict:
    if (not np.isfinite([initial_cash, risk_free_rate, periods_per_year]).all()
            or initial_cash <= 0 or risk_free_rate <= -1
            or not isinstance(periods_per_year, int) or periods_per_year <= 0):
        raise ValueError("Require positive cash, integer annual periods, and annual risk-free rate > -1.")
    returns = result.net_return
    if len(returns) < 2 or not np.isfinite(returns).all() or (returns <= -1).any():
        raise ValueError("Need at least two finite returns greater than -1.")
    daily_rf = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess = returns - daily_rf
    volatility = float(returns.std(ddof=1))
    excess_std = float(excess.std(ddof=1))
    downside = float(np.sqrt(np.mean(np.minimum(excess, 0) ** 2)))

    def ratio(numerator: float, denominator: float):
        return float(numerator / denominator) if denominator > 1e-12 else None

    total = float(result.equity.iloc[-1] / initial_cash - 1)
    cagr = float((1 + total) ** (periods_per_year / len(returns)) - 1)
    max_drawdown = float(result.drawdown.min())
    return {
        "total_return": total,
        "cagr": cagr,
        "annualized_volatility": volatility * np.sqrt(periods_per_year),
        "sharpe_ratio": ratio(float(excess.mean()) * np.sqrt(periods_per_year), excess_std),
        "sortino_ratio": ratio(float(excess.mean()) * np.sqrt(periods_per_year), downside),
        "max_drawdown": max_drawdown,
        "calmar_ratio": ratio(cagr, abs(max_drawdown)),
        "exposure": float(result.position.mean()),
        "one_way_trades": int((result.turnover > 0).sum()),
        "observations": len(returns),
    }
