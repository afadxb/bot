import os
import pandas as pd
import pandas_ta as ta

# --- Load from .env or default fallback
RSI_WINDOW = int(os.getenv("RSI_WINDOW", 14))
RSI_ENTRY_THRESHOLD = float(os.getenv("RSI_ENTRY_THRESHOLD", 50))
RSI_EXIT_THRESHOLD = float(os.getenv("RSI_EXIT_THRESHOLD", 45))
EMA_FAST = int(os.getenv("EMA_FAST", 8))
EMA_SLOW = int(os.getenv("EMA_SLOW", 21))
ATR_WINDOW = int(os.getenv("ATR_WINDOW", 14))

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Validate OHLC data
    if df[["high", "low", "close"]].isnull().any().any() or len(df) < 30:
        raise ValueError("OHLC data is incomplete or too short for indicators")

    # Apply Supertrend
    df.ta.supertrend(length=10, multiplier=3.0, append=True)

    # Correct dynamic column references
    st_col = "SUPERT_10_3.0"
    dir_col = "SUPERTd_10_3.0"

    if st_col not in df.columns or dir_col not in df.columns:
        raise ValueError("Supertrend columns not found")

    # Add ATR
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=ATR_WINDOW)

    # Normalize names for bot logic
    df["supertrend"] = df[st_col]
    df["trend"] = df[dir_col]
    df["rsi"] = ta.rsi(df["close"], length=RSI_WINDOW)

    df.dropna(subset=["supertrend", "trend", "rsi", "atr"], inplace=True)
    return df

def generate_signal(df: pd.DataFrame, fear_greed_score: float = None) -> str:
    if len(df) < 2:
        return None

    curr = df.iloc[-1]
    trend = curr["trend"]
    rsi = curr["rsi"]

    if trend == 1 and rsi > RSI_ENTRY_THRESHOLD:
        if fear_greed_score is None or fear_greed_score >= float(os.getenv("MIN_FG_SCORE_FOR_ENTRY", 30)):
            return "buy"

    if trend == -1 or rsi < RSI_EXIT_THRESHOLD:
        return "sell"

    return None