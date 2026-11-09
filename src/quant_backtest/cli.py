"""Command-line research runner and portable output artifacts."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .data import fetch_yahoo, load_csv
from .engine import backtest, buy_and_hold
from .metrics import performance_metrics
from .strategies import mean_reversion, moving_average


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", type=Path)
    source.add_argument("--ticker")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2025-01-01", help="exclusive end date for Yahoo")
    parser.add_argument("--strategy", choices=["ma", "mean-reversion"], default="ma")
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=100)
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--entry-z", type=float, default=1.5)
    parser.add_argument("--exit-z", type=float, default=0)
    parser.add_argument("--cash", type=float, default=100_000)
    parser.add_argument("--commission-bps", type=float, default=1)
    parser.add_argument("--slippage-bps", type=float, default=4)
    parser.add_argument("--risk-free-rate", type=float, default=0)
    parser.add_argument("--periods-per-year", type=int, default=252)
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args(argv)
    try:
        prices = load_csv(args.csv) if args.csv else fetch_yahoo(args.ticker, args.start, args.end)
        signal = (moving_average(prices, args.fast, args.slow) if args.strategy == "ma"
                  else mean_reversion(prices, args.window, args.entry_z, args.exit_z))
        settings = dict(initial_cash=args.cash, commission_bps=args.commission_bps,
                        slippage_bps=args.slippage_bps)
        strategy = backtest(prices, signal, **settings)
        benchmark = buy_and_hold(prices, **settings)
        metrics_args = dict(initial_cash=args.cash, risk_free_rate=args.risk_free_rate,
                            periods_per_year=args.periods_per_year)
        summary = {"strategy": performance_metrics(strategy, **metrics_args),
                   "buy_and_hold": performance_metrics(benchmark, **metrics_args)}
    except (ValueError, OSError, ImportError) as exc:
        parser.error(str(exc))
    args.out.mkdir(parents=True, exist_ok=True)
    normalized = prices.to_frame().rename_axis("Date").to_csv()
    (args.out / "prices.csv").write_text(normalized)
    strategy.to_csv(args.out / "backtest.csv", index_label="Date")
    benchmark.to_csv(args.out / "benchmark.csv", index_label="Date")
    (args.out / "metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    metadata = {"arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                "prices_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
                "first_date": str(prices.index[0]), "last_date": str(prices.index[-1]),
                "price_count": len(prices), "execution": "signal close t; fill close t+1"}
    (args.out / "run.json").write_text(json.dumps(metadata, indent=2))
    _plot(strategy, benchmark, args.cash, args.out / "performance.png")
    print(pd.DataFrame(summary).to_string(float_format=lambda x: f"{x:.4f}"))
    print(f"\nResults: {args.out.resolve()}")


def _plot(strategy, benchmark, cash, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]})
    for frame, label, color in [(strategy, "Strategy", "#2563eb"),
                                 (benchmark, "Buy & hold", "#64748b")]:
        axes[0].plot(frame.index, frame.equity / cash, label=label, color=color)
        axes[1].plot(frame.index, frame.drawdown * 100, color=color)
    axes[0].set(ylabel="Growth of initial capital", title="Net performance after trading costs")
    axes[0].legend()
    axes[1].set(ylabel="Drawdown (%)", xlabel="Date")
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
