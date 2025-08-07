import os, sys
from   datetime import datetime
import pandas as pd

# make project root importable no matter where we run from
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)

from core.data_loader import fetch_ohlc
from core.strategy     import add_indicators, generate_signal

# -- CONFIG ---------------------------------------------------------------
SYMBOL        = "BTC/USD"
INTERVAL_MIN  = 240   # 4-hour candles
MONTHS_BACK   = 6
INIT_CAPITAL  = 10_000.0
FEE_RATE      = 0.005
CSV_PATH      = "logs/trade_log.csv"
os.makedirs("logs", exist_ok=True)

# -- HISTORY --------------------------------------------------------------
df = fetch_ohlc(SYMBOL, interval=INTERVAL_MIN)
df["time"] = pd.to_datetime(df["time"])
needed = int(MONTHS_BACK * 30 * 24 / (INTERVAL_MIN / 60))
df = df.tail(needed).reset_index(drop=True)
df = add_indicators(df)

# -- SIM LOOP -------------------------------------------------------------
capital = INIT_CAPITAL
position = 0.0
entry_px = entry_ts = None

rows_dashboard = []   # for type=entry/exit
trades_summary = []   # one row per completed trade

print(f"Back-test {SYMBOL} | {MONTHS_BACK} mo | start_cap=${INIT_CAPITAL:,.0f}")

for i in range(1, len(df)):
    window  = df.iloc[: i + 1]
    price   = window["close"].iat[-1]
    ts      = window["time"].iat[-1]
    signal  = generate_signal(window)

    # BUY
    if signal == "buy" and position == 0:
        qty = (capital * (1 - FEE_RATE)) / price
        position, entry_px, entry_ts = qty, price, ts
        capital -= capital * FEE_RATE
        rows_dashboard.append({"timestamp": ts, "price": price, "type": "entry"})
        print(f"[ENTRY] {ts} | qty={qty:.6f} @ {price:.2f} | cash={capital:.2f}")

    # SELL
    elif signal == "sell" and position > 0 and price > entry_px:
        proceeds = position * price * (1 - FEE_RATE)
        pnl_usd  = proceeds - (entry_px * position)
        capital += proceeds

        rows_dashboard.append({"timestamp": ts, "price": price, "type": "exit"})
        trades_summary.append({
            "symbol": SYMBOL,
            "entry_time": entry_ts,
            "entry_price": entry_px,
            "exit_time": ts,
            "exit_price": price,
            "qty": position,
            "pnl": pnl_usd,
        })
        print(f"[EXIT ] {ts} | pnl={pnl_usd:.2f} | equity={capital:.2f}")
        position = 0.0

# -- RESULTS --------------------------------------------------------------
eq_curve = [INIT_CAPITAL]
for tr in trades_summary:
    eq_curve.append(eq_curve[-1] + tr["pnl"])
drawdown = pd.Series(eq_curve).cummax() - eq_curve

print("\n=== BACK-TEST SUMMARY ===")
print(f"Trades      : {len(trades_summary)}")
print(f"Net PnL USD : {eq_curve[-1] - INIT_CAPITAL:.2f}")
print(f"Max DD USD  : {drawdown.max():.2f}")
print(f"Final Equity: {eq_curve[-1]:.2f}")

# -- EXPORT CSV (dashboard compatible) ------------------------------------
df_out = pd.DataFrame(rows_dashboard + trades_summary)
df_out.to_csv(CSV_PATH, index=False)
print(f"Trades & ticks exported ? {CSV_PATH}")