"""Deterministic synthetic fixture; not historical Korean stock performance."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .model import FACTORS


def generate(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("Demo destination must be empty to protect existing market data")
    rng = np.random.default_rng(42)
    dates = pd.date_range("2016-01-31", periods=120, freq="ME")
    f = rng.normal([0.006, 0.002, 0.002, 0.003, 0.002], [0.035, 0.02, 0.025, 0.018, 0.018], (len(dates), 5))
    factors = pd.DataFrame(f, columns=FACTORS)
    factors.insert(0, "date", dates.strftime("%Y-%m-%d"))
    factors.insert(1, "available_on", (dates + pd.Timedelta(days=15)).strftime("%Y-%m-%d"))
    factors["RF"] = 0.001
    # Six-digit identifiers are artificial, not a recommended investment universe.
    symbols = [f"{i:06d}" for i in range(1, 9)]
    betas = rng.uniform(0.1, 1.2, (5, len(symbols)))
    returns = pd.DataFrame(0.001 + f @ betas + rng.normal(0, 0.025, (len(dates), len(symbols))), columns=symbols)
    returns.insert(0, "date", dates.strftime("%Y-%m-%d"))
    factors.to_csv(root / "factors.csv", index=False)
    returns.to_csv(root / "returns.csv", index=False)
    pd.DataFrame({"symbol": symbols, "start": "2016-01-01", "end": ""}).to_csv(root / "universe.csv", index=False)
    (root / "metadata.json").write_text(json.dumps({
        "market": "KR", "currency": "KRW", "frequency": "monthly", "units": "decimal",
        "synthetic": True, "factor_source": "seed=42 synthetic demonstration; NOT observed market data",
        "vintage_note": "No real securities, financial statements, or performance claims"}, indent=2))

