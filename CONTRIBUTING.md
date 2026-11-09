# Contributing

Install with `python -m pip install -e '.[yahoo]'` and run `python -m unittest discover -s tests -v`.
Open an issue describing the research or accounting problem before proposing a
large feature. Include a small reproducible example and tests for timing,
transaction costs, and data validation where relevant. Keep tests offline;
mock external providers. Never commit credentials or downloaded market data
without redistribution rights. State modeling assumptions and avoid performance
claims based only on an optimized historical sample.

Optional browser tests (requires Node.js and a Chromium download):

```bash
npm install --no-save --package-lock=false playwright
npx playwright install chromium
# In a separate terminal, from this repository root:
# PYTHONPATH=src python -m quant_backtest.web
node tests/browser/dashboard.cjs
```

These checks exercise both strategies, changing trading costs, chart rendering,
CSV download, invalid settings and recovery, mobile layout, and uncaught script
errors. `BACKTEST_URL` overrides the default `http://127.0.0.1:8000` test URL.
The browser checks require the default synthetic fixture. They are optional and
are not part of the Python-only CI job. This workspace verified all 16 Python
and HTTP tests; browser execution was blocked by unavailable Chromium and a
network policy preventing its download.
