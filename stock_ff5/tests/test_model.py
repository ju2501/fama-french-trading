import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from stock_ff5.demo import generate
from stock_ff5.model import Config, Dataset, FACTORS, backtest, from_sorted_portfolios, signal


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        generate(self.root)
        self.data = Dataset.load(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_known_five_factor_loadings(self):
        expected = np.array([1.1, 0.2, -0.3, 0.4, 0.5])
        self.data.returns["000001"] = self.data.factors.RF + 0.007 + self.data.factors[FACTORS].to_numpy() @ expected
        result = signal(self.data, "2026-01-16")
        row = next(r for r in result["scores"] if r["symbol"] == "000001")
        np.testing.assert_allclose([row[f"beta_{f}"] for f in FACTORS], expected, atol=1e-10)
        self.assertAlmostEqual(row["alpha_monthly"], 0.007)
        self.assertAlmostEqual(row["r_squared"], 1)
        means = self.data.factors.iloc[-60:][FACTORS].mean().to_numpy()
        self.assertAlmostEqual(row["expected_excess_monthly"], float(expected @ means))

    def test_future_data_cannot_change_past_signal(self):
        before = signal(self.data, "2022-05-01")
        future = self.data.factors.available_on >= pd.Timestamp("2022-05-01")
        self.data.factors.loc[future, FACTORS] = 0.9
        self.data.returns.loc[self.data.returns.index >= "2022-05-01"] = 0.8
        self.assertEqual(before, signal(self.data, "2022-05-01"))

    def test_release_day_itself_is_excluded(self):
        self.assertEqual(signal(self.data, "2026-01-15")["factor_month"], "2025-11-30")
        self.assertEqual(signal(self.data, "2026-01-16")["factor_month"], "2025-12-31")

    def test_stale_data_fails(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            signal(self.data, "2026-10-06")

    def test_singular_factors_are_rejected(self):
        self.data.factors["CMA"] = self.data.factors["HML"]
        with self.assertRaisesRegex(ValueError, "full-rank"):
            signal(self.data, "2026-01-16")

    def test_weights_and_cash_cap(self):
        result = signal(self.data, "2026-01-16", Config(top_n=2, max_weight=0.2))
        self.assertLessEqual(sum(result["weights"].values()), 0.4)
        self.assertGreaterEqual(result["cash_weight"], 0.6)

    def test_universe_dates_are_respected(self):
        self.data.universe.loc[self.data.universe.symbol == "000001", "start"] = pd.Timestamp("2027-01-01")
        scores = signal(self.data, "2026-01-16")["scores"]
        self.assertNotIn("000001", [r["symbol"] for r in scores])

    def test_missing_month_is_not_filled(self):
        frame = pd.read_csv(self.root / "factors.csv").drop(10)
        frame.to_csv(self.root / "factors.csv", index=False)
        with self.assertRaisesRegex(ValueError, "Missing months"):
            Dataset.load(self.root)

    def test_percent_and_wrong_market_rejected(self):
        frame = pd.read_csv(self.root / "factors.csv")
        frame.loc[0, "MKT_RF"] = 3.5
        frame.to_csv(self.root / "factors.csv", index=False)
        with self.assertRaisesRegex(ValueError, "decimals"):
            Dataset.load(self.root)
        meta = json.loads((self.root / "metadata.json").read_text())
        meta["market"] = "US"
        (self.root / "metadata.json").write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, "market"):
            Dataset.load(self.root)

    def test_backtest_has_warmup_and_costs(self):
        result = backtest(self.data)
        no_cost = backtest(self.data, cost_bps=0)
        self.assertGreater(pd.Timestamp(result.date.iloc[0]), pd.Timestamp("2018-12-31"))
        self.assertLess(result.nav.iloc[-1], no_cost.nav.iloc[-1])
        self.assertTrue(np.isfinite(result.nav).all())

    def test_backtest_rejects_missing_held_returns(self):
        chosen = next(iter(signal(self.data, "2024-01-01")["weights"]))
        self.data.returns.loc["2024-01-31", chosen] = np.nan
        with self.assertRaisesRegex(ValueError, "Missing realized"):
            backtest(self.data)

    def test_ff5_portfolio_combinations(self):
        data = {"date": ["2025-01-31"], "available_on": ["2025-02-15"], "market_return": [0.06], "RF": [0.01]}
        for prefix in ["value", "profit", "invest"]:
            for size, offset in [("S", 0.02), ("B", 0.0)]:
                for group, amount in [("L", 0.01), ("N", 0.03), ("H", 0.05)]:
                    data[f"{prefix}_{size}{group}"] = [offset + amount]
        out = from_sorted_portfolios(pd.DataFrame(data)).iloc[0]
        np.testing.assert_allclose(out[FACTORS].to_numpy(dtype=float), [0.05, 0.02, 0.04, 0.04, -0.04])


if __name__ == "__main__":
    unittest.main()
