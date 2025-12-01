#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capital-aware back-test that outputs clean dashboard-compatible ticks
• dashboard_ticks: logs/trade_ticks.csv (timestamp, price, type)
• full summary:    logs/trade_summary.csv (entry_time, exit_time, pnl, etc.)
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

# ensure project root is importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)

from core.data_loader import fetch_ohlc
from core.strategy import add_indicators, generate_signal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run capital-aware backtest")
    parser.add_argument("--symbol", default=os.getenv("BACKTEST_SYMBOL", "BTC/USD"))
    parser.add_argument("--interval-min", type=int, default=int(os.getenv("BACKTEST_INTERVAL_MIN", 240)))
    parser.add_argument("--start-date", help="ISO date for start of backtest window")
    parser.add_argument("--end-date", help="ISO date for end of backtest window; defaults to now")
    parser.add_argument("--capital", type=float, default=float(os.getenv("INIT_CAPITAL", 10_000.0)))
    parser.add_argument("--fee-rate", type=float, default=float(os.getenv("FEE_RATE", 0.005)))
    parser.add_argument(
        "--supertrend-multiplier",
        type=float,
        default=float(os.getenv("ATR_MULTIPLIER", 1.6)),
        help="Multiplier passed to Supertrend/ATR calculation",
    )

    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> tuple[datetime, datetime]:
    end = datetime.fromisoformat(args.end_date) if args.end_date else datetime.utcnow()
    start = datetime.fromisoformat(args.start_date) if args.start_date else end - timedelta(days=180)

    if start > end:
        raise ValueError("Start date must be before end date")

    return start, end


def main() -> None:
    args = parse_args()
    start_dt, end_dt = resolve_dates(args)

    os.makedirs("logs", exist_ok=True)
    tick_csv = "logs/trade_ticks.csv"
    summary_csv = "logs/trade_summary.csv"

    candle_span_minutes = args.interval_min
    candles_needed = max(1, math.ceil((end_dt - start_dt).total_seconds() / (candle_span_minutes * 60)))

    df = fetch_ohlc(
        args.symbol,
        interval=candle_span_minutes,
        lookback=candles_needed + 10,  # small buffer for indicators
        start_time=start_dt,
    )

    if df.empty:
        raise RuntimeError("No OHLC data returned for requested window")

    # ``fetch_ohlc`` returns a timestamp index; normalize to a ``time`` column for
    # the downstream logic and make sure it is a datetime dtype.
    if "time" not in df.columns:
        df = df.reset_index().rename(columns={df.index.name or "index": "time"})

    df["time"] = pd.to_datetime(df["time"])
    df = df[(df["time"] >= start_dt) & (df["time"] <= end_dt)].reset_index(drop=True)
    df = add_indicators(df, supertrend_multiplier=args.supertrend_multiplier)

    # ─── SIM LOOP ───────────────────────────────────────────────────────────────
    capital = args.capital
    position = 0.0
    entry_px = None
    entry_ts = None

    tick_rows = []  # for Streamlit (timestamp, price, type)
    summary = []  # full trade log

    print(
        f"Back-testing {args.symbol} from {start_dt.isoformat()} to {end_dt.isoformat()} "
        f"(interval={candle_span_minutes}m)"
    )

    for i in range(1, len(df)):
        window = df.iloc[: i + 1]
        price = window["close"].iat[-1]
        ts = window["time"].iat[-1]
        signal = generate_signal(window)

        # BUY full capital
        if signal == "buy" and position == 0:
            qty = (capital * (1 - args.fee_rate)) / price
            position, entry_px, entry_ts = qty, price, ts
            capital -= capital * args.fee_rate
            tick_rows.append({"timestamp": ts, "price": price, "type": "entry"})
            print(f"[ENTRY] {ts} @ {price:.2f} qty={qty:.6f}")

        # SELL and realize PnL
        elif signal == "sell" and position > 0 and price > entry_px:
            proceeds = position * price * (1 - args.fee_rate)
            pnl = proceeds - (position * entry_px)
            capital += proceeds

            tick_rows.append({"timestamp": ts, "price": price, "type": "exit"})
            summary.append(
                {
                    "symbol": args.symbol,
                    "entry_time": entry_ts,
                    "entry_price": entry_px,
                    "exit_time": ts,
                    "exit_price": price,
                    "qty": position,
                    "pnl": pnl,
                }
            )

            print(f"[EXIT ] {ts} @ {price:.2f} pnl={pnl:.2f}")
            position = 0.0

    # ─── RESULTS ───────────────────────────────────────────────────────────────
    eq = args.capital
    curve = [eq]
    for tr in summary:
        eq += tr["pnl"]
        curve.append(eq)

    dd = pd.Series(curve).cummax() - curve

    print("\n=== SUMMARY ===")
    print(f"Trades      : {len(summary)}")
    print(f"Net Profit  : {curve[-1] - args.capital:.2f} USD")
    print(f"Max Drawdown: {dd.max():.2f} USD")
    print(f"Final Equity: {curve[-1]:.2f} USD")

    # ─── EXPORT ───────────────────────────────────────────────────────────────
    pd.DataFrame(tick_rows).to_csv(tick_csv, index=False)
    pd.DataFrame(summary).to_csv(summary_csv, index=False)

    print(f"✓ Exported dashboard ticks → {tick_csv}")
    print(f"✓ Exported trade summary   → {summary_csv}")


if __name__ == "__main__":
    main()
