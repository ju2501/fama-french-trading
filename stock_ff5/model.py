"""FF5 OLS, as-published monthly input validation and long-only allocation."""
from dataclasses import dataclass
from pathlib import Path
import json
import re

import numpy as np
import pandas as pd

FACTORS = ["MKT_RF", "SMB", "HML", "RMW", "CMA"]


def day(value):
    result = pd.Timestamp(value)
    if pd.isna(result) or result.tzinfo is not None:
        raise ValueError("Dates must be valid timezone-free YYYY-MM-DD values")
    return result.normalize()


def monthly(frame):
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.pop("date"), errors="raise")
    if frame.index.hasnans or frame.index.has_duplicates or not frame.index.is_month_end.all():
        raise ValueError("date must contain unique calendar month ends")
    if frame.index.tz is not None or not (frame.index == frame.index.normalize()).all():
        raise ValueError("Monthly dates must be timezone-free midnight dates")
    frame = frame.sort_index()
    if frame.empty:
        raise ValueError("Empty monthly input")
    expected = pd.period_range(frame.index[0], frame.index[-1], freq="M")
    if not frame.index.to_period("M").equals(expected):
        raise ValueError("Missing months: do not forward-fill returns")
    return frame


@dataclass
class Dataset:
    factors: pd.DataFrame
    returns: pd.DataFrame
    universe: pd.DataFrame
    metadata: dict

    @classmethod
    def load(cls, directory):
        root = Path(directory)
        meta = json.loads((root / "metadata.json").read_text())
        for key, expected in {"market": "KR", "currency": "KRW", "frequency": "monthly", "units": "decimal"}.items():
            if meta.get(key) != expected:
                raise ValueError(f"metadata.{key} must be {expected!r}")
        if type(meta.get("synthetic")) is not bool or not meta.get("factor_source"):
            raise ValueError("metadata needs synthetic boolean and factor_source")
        factors = monthly(pd.read_csv(root / "factors.csv"))
        required = FACTORS + ["RF", "available_on"]
        if not set(required).issubset(factors.columns):
            raise ValueError(f"factors.csv needs {required}")
        factors = factors[required]
        for col in FACTORS + ["RF"]:
            factors[col] = pd.to_numeric(factors[col], errors="raise")
        values = factors[FACTORS + ["RF"]].to_numpy()
        if not np.isfinite(values).all() or (np.abs(values) > 1).any():
            raise ValueError("Factor returns must be finite decimals, not percentages or missing-value sentinels")
        factors["available_on"] = pd.to_datetime(factors["available_on"], errors="raise")
        available = factors["available_on"]
        if (available.isna().any() or available.dt.tz is not None
                or not (available == available.dt.normalize()).all()
                or (available < factors.index).any()):
            raise ValueError("available_on must be a date on/after its return month end")
        returns = monthly(pd.read_csv(root / "returns.csv"))
        if not all(re.fullmatch(r"\d{6}", str(s)) for s in returns.columns):
            raise ValueError("Return columns must be six-digit KRX stock codes")
        returns = returns.apply(pd.to_numeric, errors="raise")
        if np.isinf(returns.to_numpy()).any() or (returns < -1).any().any():
            raise ValueError("Invalid stock total returns")
        universe = pd.read_csv(root / "universe.csv", dtype={"symbol": str})
        if set(universe.columns) != {"symbol", "start", "end"} or universe.empty:
            raise ValueError("universe.csv needs symbol,start,end")
        if universe.symbol.duplicated().any() or not set(universe.symbol).issubset(returns.columns):
            raise ValueError("Universe must have unique symbols present in returns.csv")
        for col in ["start", "end"]:
            universe[col] = pd.to_datetime(universe[col], errors="raise")
        if universe.start.isna().any() or (universe.end < universe.start).any():
            raise ValueError("Invalid universe membership dates")
        return cls(factors, returns, universe, meta)


@dataclass(frozen=True)
class Config:
    window: int = 60
    min_observations: int = 36
    top_n: int = 5
    max_weight: float = 0.20
    invested_fraction: float = 0.90
    min_excess_return: float = 0.0
    max_staleness_days: int = 100

    def __post_init__(self):
        if not 12 <= self.min_observations <= self.window or self.top_n < 1:
            raise ValueError("Require 12 <= min_observations <= window and top_n >= 1")
        if not 0 < self.max_weight <= 1 or not 0 < self.invested_fraction <= 1:
            raise ValueError("Weight limits must be in (0,1]")
        if not np.isfinite(self.min_excess_return) or self.max_staleness_days < 1:
            raise ValueError("Invalid signal threshold or staleness limit")


def signal(dataset, as_of, config=Config()):
    """Use only prior-day published observations. Alpha is diagnostic, not a forecast."""
    as_of = day(as_of)
    eligible = dataset.factors.loc[
        (dataset.factors.index < as_of)
        & (dataset.factors.available_on < as_of)
    ]
    if len(eligible) < config.min_observations:
        raise ValueError("Insufficient published factor history")
    latest = eligible.index[-1]
    if (as_of - latest).days > config.max_staleness_days:
        raise ValueError("Published factors are stale; refresh the input dataset")
    # A calendar window, not the last N non-missing rows of a discontinued stock.
    start = latest - pd.DateOffset(months=config.window - 1)
    eligible = eligible.loc[eligible.index >= start]
    u = dataset.universe
    symbols = u.loc[(u.start <= as_of) & (u.end.isna() | (u.end >= as_of)), "symbol"]
    rows = []
    for symbol in sorted(symbols):
        aligned = eligible.join(dataset.returns[[symbol]], how="inner").dropna()
        if len(aligned) < config.min_observations or aligned.index[-1] != latest:
            continue
        x = np.column_stack([np.ones(len(aligned)), aligned[FACTORS].to_numpy()])
        y = aligned[symbol].to_numpy() - aligned.RF.to_numpy()
        beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
        if rank != 6 or np.linalg.cond(x) > 1e8:
            continue
        forecast = float(beta[1:] @ aligned[FACTORS].mean().to_numpy())
        residual = y - x @ beta
        total = float(((y - y.mean()) ** 2).sum())
        rows.append({"symbol": symbol, "alpha_monthly": float(beta[0]),
                     **{f"beta_{f}": float(b) for f, b in zip(FACTORS, beta[1:])},
                     "expected_excess_monthly": forecast,
                     "r_squared": float(1 - (residual @ residual) / total) if total > 0 else 0.0,
                     "observations": len(aligned), "last_month": latest.date().isoformat()})
    if not rows:
        raise ValueError("No stocks with sufficient recent, full-rank FF5 history")
    scores = pd.DataFrame(rows).sort_values(
        ["expected_excess_monthly", "symbol"], ascending=[False, True])
    selected = scores.loc[scores.expected_excess_monthly > config.min_excess_return].head(config.top_n)
    per_stock = min(config.max_weight, config.invested_fraction / len(selected)) if len(selected) else 0.0
    weights = {symbol: per_stock for symbol in selected.symbol}
    return {"as_of": as_of.date().isoformat(), "factor_month": latest.date().isoformat(),
            "weights": weights, "cash_weight": 1 - sum(weights.values()),
            "scores": scores.to_dict("records"), "synthetic": dataset.metadata["synthetic"]}


def backtest(dataset, config=Config(), initial_cash=10_000_000, cost_bps=20.0, sell_tax_bps=0.0):
    """Monthly research simulation: beginning-of-month rebalance; drift-aware costs.

    Fractional allocations at previous month-end prices are an explicit idealization.
    Cash earns zero; no broker orders or fill assumptions are hidden here.
    """
    if initial_cash <= 0 or not np.isfinite(initial_cash):
        raise ValueError("initial_cash must be finite and positive")
    if not 0 <= cost_bps < 1000 or not 0 <= sell_tax_bps < 1000:
        raise ValueError("Invalid cost assumptions")
    nav, holdings, started, records = float(initial_cash), {}, False, []
    for end, realized in dataset.returns.iterrows():
        as_of = end.to_period("M").start_time
        try:
            result = signal(dataset, as_of, config)
        except ValueError:
            if not started:
                continue
            raise  # Never silently liquidate or skip missing data after inception.
        started = True
        targets = result["weights"]
        symbols = set(holdings) | set(targets)
        for symbol in symbols:
            if (holdings.get(symbol, 0) > 0 or targets.get(symbol, 0) > 0) and pd.isna(realized[symbol]):
                raise ValueError(f"Missing realized/delisting return: {symbol} at {end.date()}")
        buys = sum(max(targets.get(s, 0) - holdings.get(s, 0), 0) for s in symbols)
        sells = sum(max(holdings.get(s, 0) - targets.get(s, 0), 0) for s in symbols)
        fee = (buys + sells) * cost_bps / 10000 + sells * sell_tax_bps / 10000
        gross = sum(w * float(realized[s]) for s, w in targets.items())
        multiple = (1 - fee) * (1 + gross)
        if multiple <= 0:
            raise ValueError("Portfolio exhausted")
        nav *= multiple
        holdings = {s: w * (1 + float(realized[s])) / (1 + gross) for s, w in targets.items()}
        records.append({"date": end.date().isoformat(), "nav": nav,
                        "return": multiple - 1, "turnover": buys + sells,
                        "cost_fraction": fee, "cash_weight": result["cash_weight"]})
    if not records:
        raise ValueError("Not enough history for an out-of-sample backtest")
    return pd.DataFrame(records)


def from_sorted_portfolios(frame):
    """Combine preconstructed 2x3, value-weighted KR portfolios into FF5 returns.

    Input prefixes value/profit/invest each have SL,SN,SH,BL,BN,BH.
    L/H mean low/high book-to-market, profitability, or asset growth respectively.
    """
    result = frame[["date", "available_on", "market_return", "RF"]].copy()
    result["MKT_RF"] = result.market_return - result.RF
    smb = []
    for prefix in ["value", "profit", "invest"]:
        cols = [f"{prefix}_{s}{q}" for s in "SB" for q in "LNH"]
        p = frame[cols].apply(pd.to_numeric, errors="raise")
        if not np.isfinite(p.to_numpy()).all():
            raise ValueError("All 18 portfolio returns are required for every month")
        smb.append(p[[f"{prefix}_S{q}" for q in "LNH"]].mean(axis=1)
                   - p[[f"{prefix}_B{q}" for q in "LNH"]].mean(axis=1))
        spread = (p[f"{prefix}_SH"] + p[f"{prefix}_BH"]
                  - p[f"{prefix}_SL"] - p[f"{prefix}_BL"]) / 2
        result[{"value": "HML", "profit": "RMW", "invest": "CMA"}[prefix]] = -spread if prefix == "invest" else spread
    result["SMB"] = sum(smb) / 3
    return result[["date", "available_on", *FACTORS, "RF"]]
