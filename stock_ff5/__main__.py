"""Run from the repository root: python -m stock_ff5 --help."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import pandas as pd

from .demo import generate
from .kis import (BrokerError, Credentials, KIS, SEOUL, execute_batch,
                  plan_orders, require_session, secure_write)
from .model import Config, Dataset, backtest, from_sorted_portfolios, signal


def parser():
    p = argparse.ArgumentParser(description="KRW monthly Fama–French 5-factor research and KIS trading")
    sub = p.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Generate synthetic data; makes no API calls")
    demo.add_argument("--out", required=True)
    build = sub.add_parser("build-factors", help="Combine 18 preconstructed KR 2x3 portfolio returns")
    build.add_argument("--portfolios", required=True)
    build.add_argument("--out", required=True)
    for name in ["signal", "backtest", "rebalance"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--data", required=True, help="Directory containing the four input files")
        cmd.add_argument("--out", required=True)
        cmd.add_argument("--window", type=int, default=60)
        cmd.add_argument("--min-observations", type=int, default=36)
        cmd.add_argument("--top-n", type=int, default=5)
        cmd.add_argument("--max-weight", type=float, default=0.20)
        cmd.add_argument("--invested-fraction", type=float, default=0.90)
        if name == "signal":
            cmd.add_argument("--as-of", required=True, help="Decision date, YYYY-MM-DD")
        if name == "backtest":
            cmd.add_argument("--initial-cash", type=float, default=10_000_000)
            cmd.add_argument("--cost-bps", type=float, default=20.0, help="Illustrative one-way fees + slippage")
            cmd.add_argument("--sell-tax-bps", type=float, default=0.0, help="Set applicable sales tax explicitly")
        if name == "rebalance":
            cmd.add_argument("--budget", type=float, required=True, help="Maximum strategy capital, KRW")
            cmd.add_argument("--max-order-value", type=float, default=1_000_000)
            cmd.add_argument("--state-dir", default="stock_ff5/.state")
            cmd.add_argument("--sessions", help="CSV with valid KRX session dates; required to submit")
            cmd.add_argument("--submit", action="store_true", help="Without this flag, read/plan only")
            cmd.add_argument("--allow-live", action="store_true", help="Additional gate for live account orders")
    return p


def run(args):
    output = Path(args.out)
    if args.command == "demo":
        generate(output)
        print(f"Synthetic demo dataset created: {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.command == "build-factors":
        from_sorted_portfolios(pd.read_csv(args.portfolios)).to_csv(output, index=False)
        print(f"FF5 factor combinations written: {output}")
        return
    dataset = Dataset.load(args.data)
    config = Config(window=args.window, min_observations=args.min_observations,
                    top_n=args.top_n, max_weight=args.max_weight, invested_fraction=args.invested_fraction)
    if args.command == "signal":
        secure_write(output, signal(dataset, args.as_of, config))
    elif args.command == "backtest":
        result = backtest(dataset, config, args.initial_cash, args.cost_bps, args.sell_tax_bps)
        result.to_csv(output, index=False)
        print(f"Research simulation: {len(result)} months; synthetic={dataset.metadata['synthetic']}")
    else:
        # Preflight data/environment before issuing even a token request.
        if dataset.metadata["synthetic"]:
            raise ValueError("Synthetic input is only for signal/backtest, never broker integration")
        now = datetime.now(SEOUL)
        result = signal(dataset, now.date().isoformat(), config)
        credentials = Credentials.from_env()
        if args.submit:
            if credentials.environment == "live" and not args.allow_live:
                raise ValueError("Live submission requires both --submit and --allow-live")
            if not args.sessions:
                raise ValueError("--sessions is required to submit")
            require_session(now, args.sessions)
            journal = Path(args.state_dir) / f"rebalance-{credentials.identity}-{result['as_of'][:7]}.json"
            if journal.exists():
                raise BrokerError("Account/month already claimed; inspect journal and broker account")
        broker = KIS(credentials, args.state_dir)
        if broker.pending_orders(now.strftime("%Y%m%d")):
            raise BrokerError("Account has unfilled KRX orders; reconcile before rebalancing")
        account = broker.balance()
        known = set(dataset.universe.symbol)
        if set(account["positions"]) - known:
            raise BrokerError("Non-strategy holdings found; use a dedicated strategy account")
        symbols = set(account["positions"]) | set(result["weights"])
        quotes = {s: broker.quote(s) for s in sorted(symbols)}
        powers = {s: broker.buying_power(s) for s in sorted(symbols)}
        orders = plan_orders(result["weights"], account, quotes, powers, args.budget, args.max_order_value)
        report = {"environment": credentials.environment, "signal": result, "orders": orders,
                  "submitted": False, "note": "Limit orders at snapshot prices; acceptance is not a fill"}
        secure_write(output, report)
        if args.submit:
            # Recheck time after potentially slow paginated preflight requests.
            require_session(datetime.now(SEOUL), args.sessions)
            report["execution"] = execute_batch(broker, orders, result, args.state_dir, args.allow_live)
            report["submitted"] = True
            secure_write(output, report)
    print(f"Written: {output}")


def main():
    args = parser().parse_args()
    try:
        run(args)
    except (ValueError, BrokerError, OSError, KeyError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
