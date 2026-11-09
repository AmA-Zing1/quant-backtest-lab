"""Regenerate the redistributable fixture; these are not historical market prices."""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
steps = np.arange(1000)
returns = .0002 + .008 * rng.standard_normal(1000) + .0015 * np.sin(steps / 35)
frame = pd.DataFrame({"Date": pd.bdate_range("2021-01-01", periods=1000),
                      "Close": 100 * np.exp(np.cumsum(returns))})
path = Path(__file__).resolve().parents[1] / "data" / "synthetic.csv"
frame.to_csv(path, index=False, float_format="%.6f")
print(path)
