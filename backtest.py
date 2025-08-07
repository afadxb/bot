import sys
import os
#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from core.strategy import add_indicators, generate_signal
from core.data_loader import fetch_ohlc

# Load parameters from environment or set defaults
EMA_FAST = int(os.getenv("EMA_FAST", 8))
EMA_SLOW = int(os.getenv("EMA_SLOW", 21))
RSI_WINDOW = int(os.getenv("RSI_WINDOW", 14))
RSI_ENTRY_THRESHOLD = float(os.getenv("RSI_ENTRY_THRESHOLD", 50))
RSI_EXIT_THRESHOLD = float(os.getenv("RSI_EXIT_THRESHOLD", 45))

SYMBOL = "BTC/USD"
INTERVAL_MIN = 240
LOOKBACK = 300  # More for indicator warmup

# Fetch historical data
df = fetch_ohlc(SYMBOL, interval=INTERVAL_MIN, lookback=LOOKBACK)
df = add_indicators(df)

# Backtest logic
position = 0
entry_px = 0.0
entry_ts = None
trades = []

for i in range(2, len(df)):
    window = df.iloc[:i+1].copy()
    ts = window.index[-1]
    price = window["close"].iloc[-1]

    signal = generate_signal(window, fear_greed_score=50)  # neutral FG for backtest

    if signal == "buy" and position == 0:
        position = 1
        entry_px = price
        entry_ts = ts
        print(f"[{ts}] BUY @ {price:.2f}")

    elif signal == "sell" and position > 0:
        pnl_usd = (price - entry_px) * position
        trades.append({
            "symbol": SYMBOL,
            "entry_time": entry_ts,
            "entry_price": entry_px,
            "exit_time": ts,
            "exit_price": price,
            "qty": position,
            "pnl": pnl_usd,
            "pnl_pct": pnl_usd / (entry_px * position) * 100,
            "holding_hrs": (ts - entry_ts).total_seconds() / 3600,
        })
        print(f"[{ts}] SELL @ {price:.2f} | PnL: {pnl_usd:.2f}")
        position = 0
        entry_px = 0.0
        entry_ts = None
    else:
        #trend = "Bullish" if window["ema_fast"].iloc[-1] > window["ema_slow"].iloc[-1] else "Bearish"
        trend_val = window["trend"].iloc[-1]
        trend = "Bullish" if trend_val == 1 else "Bearish"
        print(f"[{ts}] HOLD | Price: {price:.2f} | Trend: {trend} | Signal: {signal or 'None'} | Position: {position}")

# Final report
df_trades = pd.DataFrame(trades)
if not df_trades.empty:
    print("\n===== Trade Summary =====")
    print(df_trades)
    total_pnl = df_trades["pnl"].sum()
    avg_holding = df_trades["holding_hrs"].mean()
    win_rate = (df_trades["pnl"] > 0).mean() * 100
    print(f"Total PnL: {total_pnl:.2f} USD")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Average Holding Time: {avg_holding:.2f} hrs")
else:
    print("No trades were executed.")

# Plot equity curve
if not df_trades.empty:
    df_trades["cum_pnl"] = df_trades["pnl"].cumsum()
    df_trades.set_index("exit_time")["cum_pnl"].plot(title="Equity Curve")
    plt.xlabel("Time")
    plt.ylabel("Cumulative PnL (USD)")
    plt.grid()
    plt.tight_layout()
    plt.show()
