from __future__ import annotations

import pandas as pd


def add_indicators(
    df: pd.DataFrame,
    rsi_period: int = 14,
    atr_period: int = 14,
    supertrend_multiplier: float = 1.6,
) -> pd.DataFrame:
    """Return a copy of ``df`` with common trading indicators attached.

    The returned frame always contains ``rsi`` and ``atr``. When ``df`` has
    ``high``/``low``/``close`` columns a lightweight Supertrend is also
    produced along with a ``trend`` flag (``1`` bullish, ``-1`` bearish).
    """

    result = df.copy()

    if "Close" in result.columns:
        close_col = "Close"
    else:
        close_col = "close"

    if close_col not in result:
        return result

    result["rsi"] = calculate_rsi(result[close_col], period=rsi_period)

    if {"High", "Low", close_col}.issubset(result.columns):
        high_col = "High" if "High" in result.columns else "high"
        low_col = "Low" if "Low" in result.columns else "low"

        price_df = result.rename(columns={
            high_col: "high",
            low_col: "low",
            close_col: "close",
        })
        result["atr"] = calculate_atr(price_df, period=atr_period)

        hl2 = (price_df["high"] + price_df["low"]) / 2
        basic_ub = hl2 + supertrend_multiplier * result["atr"]
        basic_lb = hl2 - supertrend_multiplier * result["atr"]

        final_ub = basic_ub.copy()
        final_lb = basic_lb.copy()

        for i in range(1, len(price_df)):
            final_ub.iat[i] = min(basic_ub.iat[i], final_ub.iat[i - 1])
            final_lb.iat[i] = max(basic_lb.iat[i], final_lb.iat[i - 1])

        supertrend = pd.Series(index=price_df.index, dtype=float)
        trend = pd.Series(index=price_df.index, dtype=int)

        for i in range(len(price_df)):
            if i == 0:
                supertrend.iat[i] = final_ub.iat[i]
                trend.iat[i] = -1
                continue

            prev_supertrend = supertrend.iat[i - 1]
            close_price = price_df["close"].iat[i]

            if prev_supertrend == final_ub.iat[i - 1]:
                supertrend.iat[i] = (
                    final_lb.iat[i]
                    if close_price > final_ub.iat[i]
                    else final_ub.iat[i]
                )
            else:
                supertrend.iat[i] = (
                    final_ub.iat[i]
                    if close_price < final_lb.iat[i]
                    else final_lb.iat[i]
                )

            trend.iat[i] = 1 if close_price >= supertrend.iat[i] else -1

        result["supertrend"] = supertrend
        result["trend"] = trend
    else:
        result["atr"] = calculate_atr(result, period=atr_period)

    return result


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
    high_col = "High" if "High" in df.columns else "high"
    low_col = "Low" if "Low" in df.columns else "low"
    close_col = "Close" if "Close" in df.columns else "close"

    high_low = df[high_col] - df[low_col]
    high_close = (df[high_col] - df[close_col].shift()).abs()
    low_close = (df[low_col] - df[close_col].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    # Use a rolling ATR that starts immediately (``min_periods=1``) so early
    # candles still receive a finite Supertrend value instead of propagating
    # NaNs through the trend calculation.
    atr = tr.rolling(window=period, min_periods=1).mean()
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


def generate_signal(df: pd.DataFrame, fear_greed_score: float | None = None) -> str | None:
    """Generate a simple trade signal from the most recent *closed* candle.

    - Buy when the latest close is above Supertrend and RSI is below 70.
    - Sell when the latest close is below Supertrend or RSI rises above 70.
    ``fear_greed_score`` can optionally dampen entries: if provided and below
    20, no buy signal is emitted.
    """

    if df.empty:
        return None

    close_col = "close" if "close" in df.columns else "Close"

    # Require Supertrend to be present before filtering for full candles to
    # avoid KeyErrors when upstream indicator calculations are incomplete.
    if "supertrend" not in df.columns:
        return None

    # Require a fully-populated candle (close, supertrend) to avoid emitting
    # signals on the still-forming bar. This also sidesteps transient NaNs in
    # live feeds where the most recent row lacks indicator values.
    valid_rows = df.dropna(subset=[close_col, "supertrend"])
    if valid_rows.empty:
        return None

    last = valid_rows.iloc[-1]
    price = last[close_col]
    supertrend = last["supertrend"]
    rsi = last.get("rsi")

    if rsi is None or pd.isna(rsi):
        rsi = 50

    if fear_greed_score is not None and fear_greed_score < 20:
        return None

    if price > supertrend and rsi < 70:
        return "buy"
    if price < supertrend or rsi > 70:
        return "sell"

    return None
