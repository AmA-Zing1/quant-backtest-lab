import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from quant_backtest.cli import main
from quant_backtest.data import fetch_yahoo, validate_prices
from quant_backtest.engine import backtest, buy_and_hold
from quant_backtest.metrics import performance_metrics
from quant_backtest.strategies import mean_reversion, moving_average


def prices(values):
    return pd.Series(values, index=pd.bdate_range("2020-01-01", periods=len(values)), dtype=float)


class ResearchTests(unittest.TestCase):
    def test_execution_delay(self):
        p = prices([100, 100, 200, 400, 800])
        r = backtest(p, pd.Series([0, 1, 1, 1, 1], index=p.index),
                     commission_bps=0, slippage_bps=0)
        np.testing.assert_allclose(r.net_return, [0, 0, 1, 1])

    def test_entry_exit_costs(self):
        p = prices([100] * 6)
        r = backtest(p, pd.Series([1, 0, 0, 0, 0, 0], index=p.index),
                     initial_cash=100, commission_bps=100, slippage_bps=0)
        np.testing.assert_allclose(r.net_return, [0, -.01, -.01, 0, 0])
        self.assertAlmostEqual(r.equity.iloc[-1], 98.01)
        self.assertAlmostEqual(r.drawdown.min(), -.0199)

    def test_benchmark_first_loss(self):
        r = buy_and_hold(prices([100, 90, 81]), initial_cash=100,
                         commission_bps=100, slippage_bps=0)
        self.assertAlmostEqual(r.equity.iloc[-1], 80.19)
        self.assertAlmostEqual(r.drawdown.iloc[0], -.109)
        self.assertEqual(r.turnover.sum(), 1)

    def test_metrics_by_hand(self):
        r = buy_and_hold(prices([100, 110, 99, 103]), commission_bps=0, slippage_bps=0)
        daily = np.array([.1, -.1, 103 / 99 - 1])
        m = performance_metrics(r)
        self.assertAlmostEqual(m['sharpe_ratio'], daily.mean() / daily.std(ddof=1) * np.sqrt(252))
        self.assertAlmostEqual(m['sortino_ratio'], daily.mean() / np.sqrt(np.mean(np.minimum(daily, 0)**2)) * np.sqrt(252))
        self.assertAlmostEqual(m['total_return'], .03)

    def test_flat_metrics_json_safe(self):
        p = prices([100] * 10)
        m = performance_metrics(backtest(p, pd.Series(0, index=p.index)))
        self.assertIsNone(m['sharpe_ratio'])
        self.assertIsNone(m['sortino_ratio'])
        json.dumps(m, allow_nan=False)

    def test_bad_prices(self):
        for values in [[100, np.nan, 101], [100, 0, 101], [100, np.inf, 101]]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_prices(prices(values))
        p = prices([100, 101, 102])
        p.index = pd.DatetimeIndex([p.index[0]] * 3)
        with self.assertRaises(ValueError):
            validate_prices(p)

    def test_bad_signals_and_costs(self):
        p = prices([100, 101, 102])
        for s in [pd.Series([0, np.nan, 1], index=p.index), pd.Series([0, 1, 1])]:
            with self.assertRaises(ValueError):
                backtest(p, s)
        with self.assertRaises(ValueError):
            backtest(p, pd.Series(0, index=p.index), commission_bps=-1)

    def test_causal_signals(self):
        p = prices(100 + np.sin(np.arange(60)) * 10)
        changed = p.copy()
        changed.iloc[40:] *= 5
        for strategy in [lambda x: moving_average(x, 3, 8), lambda x: mean_reversion(x, 8)]:
            pd.testing.assert_series_equal(strategy(p).iloc[:40], strategy(changed).iloc[:40])

    def test_mean_reversion_state(self):
        s = mean_reversion(prices([100, 100, 100, 80, 80, 100, 100]), 3, 1, 0)
        self.assertEqual(s.iloc[3], 1)
        self.assertEqual(s.iloc[5], 0)

    def test_invalid_parameters(self):
        p = prices([100] * 30)
        for operation in [lambda: moving_average(p, 10, 5),
                          lambda: mean_reversion(p, 5, 0, 1),
                          lambda: performance_metrics(buy_and_hold(p), risk_free_rate=-1)]:
            with self.assertRaises(ValueError):
                operation()

    def test_yahoo_adapter(self):
        p = prices([100, 101, 102])
        yf = Mock()
        yf.download.return_value = p.to_frame('Close')
        with patch.dict('sys.modules', {'yfinance': yf}):
            pd.testing.assert_series_equal(fetch_yahoo('SPY', '2020-01-01', '2021-01-01'), p.rename('close'))
        self.assertTrue(yf.download.call_args.kwargs['auto_adjust'])
        self.assertFalse(yf.download.call_args.kwargs['multi_level_index'])

    def test_cli_offline_both_strategies(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            p = prices(100 + np.sin(np.arange(150)) * 10)
            source = root / 'input.csv'
            p.rename('Close').to_frame().rename_axis('Date').to_csv(source)
            for name in ['ma', 'mean-reversion']:
                out = root / name
                main(['--csv', str(source), '--strategy', name, '--out', str(out)])
                self.assertEqual(set(json.loads((out / 'metrics.json').read_text())), {'strategy', 'buy_and_hold'})
                self.assertGreater((out / 'performance.png').stat().st_size, 1000)
                self.assertEqual(json.loads((out / 'run.json').read_text())['price_count'], 150)


if __name__ == '__main__':
    unittest.main()
