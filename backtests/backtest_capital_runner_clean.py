
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capital-aware back-test that outputs clean dashboard-compatible ticks
• dashboard_ticks: logs/trade_ticks.csv (timestamp, price, type)
• full summary:    logs/trade_summary.csv (entry_time, exit_time, pnl, etc.)
"""

import os, sys
from datetime import datetime
import pandas as pd

# ensure project root is importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)

from core.data_loader import fetch_ohlc
from core.strategy     import add_indicators, generate_signal

# ─── CONFIG ────────────────────────────────────────────────────────────────
SYMBOL        = "BTC/USD"
INTERVAL_MIN  = 240
MONTHS_BACK   = 6
INIT_CAPITAL  = 10_000.0
FEE_RATE      = 0.005

os.makedirs("logs", exist_ok=True)
TICK_CSV     = "logs/trade_ticks.csv"
SUMMARY_CSV  = "logs/trade_summary.csv"

# ─── DATA ───────────────────────────────────────────────────────────────────
df = fetch_ohlc(SYMBOL, interval=INTERVAL_MIN)

# ``fetch_ohlc`` returns a timestamp index; normalize to a ``time`` column for
# the downstream logic and make sure it is a datetime dtype.
if "time" not in df.columns:
    df = df.reset_index().rename(columns={df.index.name or "index": "time"})

df["time"] = pd.to_datetime(df["time"])
needed = int(MONTHS_BACK * 30 * 24 / (INTERVAL_MIN / 60))
df = df.tail(needed).reset_index(drop=True)
df = add_indicators(df)

# ─── SIM LOOP ───────────────────────────────────────────────────────────────
capital    = INIT_CAPITAL
position   = 0.0
entry_px   = None
entry_ts   = None

tick_rows  = []  # for Streamlit (timestamp, price, type)
summary    = []  # full trade log

print(f"Back-testing {SYMBOL} over last {MONTHS_BACK} months...")

for i in range(1, len(df)):
    window = df.iloc[: i + 1]
    price  = window["close"].iat[-1]
    ts     = window["time"].iat[-1]
    signal = generate_signal(window)

    # BUY full capital
    if signal == "buy" and position == 0:
        qty = (capital * (1 - FEE_RATE)) / price
        position, entry_px, entry_ts = qty, price, ts
        capital -= capital * FEE_RATE
        tick_rows.append({"timestamp": ts, "price": price, "type": "entry"})
        print(f"[ENTRY] {ts} @ {price:.2f} qty={qty:.6f}")

    # SELL and realize PnL
    elif signal == "sell" and position > 0 and price > entry_px:
        proceeds = position * price * (1 - FEE_RATE)
        pnl = proceeds - (position * entry_px)
        capital += proceeds

        tick_rows.append({"timestamp": ts, "price": price, "type": "exit"})
        summary.append({
            "symbol": SYMBOL,
            "entry_time": entry_ts,
            "entry_price": entry_px,
            "exit_time": ts,
            "exit_price": price,
            "qty": position,
            "pnl": pnl
        })

        print(f"[EXIT ] {ts} @ {price:.2f} pnl={pnl:.2f}")
        position = 0.0

# ─── RESULTS ───────────────────────────────────────────────────────────────
eq = INIT_CAPITAL
curve = [eq]
for tr in summary:
    eq += tr["pnl"]
    curve.append(eq)

dd = pd.Series(curve).cummax() - curve

print("\n=== SUMMARY ===")
print(f"Trades      : {len(summary)}")
print(f"Net Profit  : {curve[-1] - INIT_CAPITAL:.2f} USD")
print(f"Max Drawdown: {dd.max():.2f} USD")
print(f"Final Equity: {curve[-1]:.2f} USD")

# ─── EXPORT ────────────────────────────────────────────────────────────────
pd.DataFrame(tick_rows).to_csv(TICK_CSV, index=False)
pd.DataFrame(summary).to_csv(SUMMARY_CSV, index=False)

print(f"✓ Exported dashboard ticks → {TICK_CSV}")
print(f"✓ Exported trade summary   → {SUMMARY_CSV}")
