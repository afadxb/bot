from __future__ import annotations

import pandas as pd


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Return the Relative Strength Index for ``series``.

    The implementation follows the classic Wilder's RSI calculation and
    returns a :class:`pandas.Series` of the same length as the input.
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute the Average True Range (ATR) for the given ``df``.

    ``df`` must contain ``High``, ``Low`` and ``Close`` columns.
    """
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=period).mean()
    return atr


def generate_signals(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Generate a basic signal DataFrame.

    The function is intentionally simple: it calculates RSI and ATR using the
    provided configuration and adds an ``entry_signal`` column initialised to 0.
    """
    result = df.copy()
    rsi_period = config.get('rsi_period', 14)
    atr_period = config.get('atr_period', 14)
    result['rsi'] = calculate_rsi(result['Close'], rsi_period)
    result['atr'] = calculate_atr(result, atr_period)
    result['entry_signal'] = 0
    return result
