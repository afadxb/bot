import matplotlib.pyplot as plt
from backtests.backtest_runner import run_backtest
from core.data_loader import fetch_ohlc

def plot_backtest(symbol: str, start: str, end: str):
    df = fetch_ohlc(symbol)
    df['time'] = pd.to_datetime(df['time'])
    trades = run_backtest(symbol, start, end)
    plt.figure()
    plt.plot(df['time'], df['close'], label='Price')
    for trade in trades:
        plt.scatter(trade['entry_time'], trade['entry_price'], marker='^', label='Entry')
        plt.scatter(trade['exit_time'], trade['exit_price'], marker='v', label='Exit')
    plt.title(f"Backtest: {symbol}")
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.legend()
    plt.show()
