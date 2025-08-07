import pandas as pd
from core.data_loader import fetch_ohlc
from core.strategy     import add_indicators, generate_signal

def backtest(symbol: str, interval=240, months=6):
    # 1) historical candles
    df = fetch_ohlc(symbol, interval=interval)
    df = df.tail(months * 30 * (60//interval) * 24)  # rough 6-month slice

    # 2) indicators
    df = add_indicators(df)

    # 3) walk forward
    in_pos = False
    entry = 0
    trades = []
    for i in range(1, len(df)):
        sig = generate_signal(df.iloc[: i + 1])

        if sig == "buy" and not in_pos:
            in_pos, entry = True, df.close.iat[i]

        elif sig == "sell" and in_pos and df.close.iat[i] > entry:
            trades.append(df.close.iat[i] - entry)
            in_pos = False

    return trades


if __name__ == "__main__":
    pnl = backtest("BTC/USD")
    print(f"trades: {len(pnl)} | total PnL: {sum(pnl):.2f} | win-rate: {(pd.Series(pnl)>0).mean():.1%}")
