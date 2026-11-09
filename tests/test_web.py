"""Verify the local dashboard calls the actual backtest engine over HTTP."""
import json
from pathlib import Path
import threading
import unittest
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from quant_backtest.data import load_csv
from quant_backtest.engine import backtest
from quant_backtest.metrics import performance_metrics
from quant_backtest.strategies import moving_average
from quant_backtest.web import make_handler


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prices = load_csv(Path(__file__).resolve().parents[1] / 'data/synthetic.csv')
        cls.server = HTTPServer(('127.0.0.1', 0), make_handler(cls.prices, 'synthetic.csv'))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def post(self, config, **headers):
        request = Request(self.url + '/api/backtest', data=json.dumps(config).encode(),
                          headers={'Content-Type': 'application/json', **headers})
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    def test_page_and_info(self):
        with urlopen(self.url, timeout=10) as response:
            self.assertIn('Quant Backtest Lab', response.read().decode())
        with urlopen(self.url + '/api/info', timeout=10) as response:
            self.assertEqual(json.load(response)['rows'], 1000)

    def test_http_results_equal_direct_python(self):
        actual = self.post({'strategy': 'ma'})
        expected = performance_metrics(backtest(self.prices, moving_average(self.prices)))
        self.assertEqual(actual['metrics']['strategy'], expected)
        self.assertEqual(len(actual['equity']['strategy']), 999)
        self.assertEqual(len(actual['csv'].strip().splitlines()), 1000)
        other = self.post({'strategy': 'mean-reversion'})
        self.assertNotEqual(actual['metrics'], other['metrics'])

    def test_bad_parameters_and_recovery(self):
        for config in [{'strategy': 'ma', 'fast': 200, 'slow': 100},
                       {'strategy': 'unknown'}, {'cash': 'invalid'}, [],
                       {'commission_bps': -1}]:
            with self.subTest(config=config), self.assertRaises(HTTPError) as caught:
                self.post(config)
            self.assertEqual(caught.exception.code, 400)
        self.assertIn('metrics', self.post({}))

    def test_cross_origin_and_content_type_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            self.post({}, Origin='http://other.example')
        self.assertEqual(caught.exception.code, 403)
        request = Request(self.url + '/api/backtest', data=b'{}',
                          headers={'Content-Type': 'text/plain'})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 415)
