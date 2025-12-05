import math
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

from core.logger import DBLogger
from core.strategy import add_indicators, generate_signal

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
SYMBOL_LOOKUP = {
    "BTC/USD": "XXBTZUSD",
    "ETH/USD": "XETHZUSD",
    "USD/CAD": "ZUSDZCAD",
    "ETH/BTC": "ETHXBT"
}

_db_logger = DBLogger()

@lru_cache(maxsize=32)
def fetch_ohlc(
    symbol: str,
    interval: int = 240,
    lookback: int = 100,
    start_time: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Fetch OHLC data from Kraken for the given symbol with caching.

    Args:
        symbol (str): Standard symbol format (e.g., BTC/USD)
        interval (int): Timeframe in minutes (default: 4h = 240)
        lookback (int): Minimum number of candles to return
        start_time (datetime | None): Optional explicit start time for the
            query. When provided, the Kraken ``since`` parameter is derived
            from this value so specific historical windows can be requested.

    Returns:
        pd.DataFrame: Clean OHLC dataframe with timestamp index
    """
    kraken_symbol = SYMBOL_LOOKUP.get(symbol)
    if not kraken_symbol:
        print(f"[ERROR] Unknown Kraken symbol for {symbol}")
        return pd.DataFrame()

    base_interval = 60  # Always pull 1h candles from Kraken
    target_interval = max(interval, base_interval)
    resample_rule = f"{target_interval}T" if target_interval != base_interval else None

    multiplier = max(1, math.ceil(target_interval / base_interval))
    base_lookback = lookback * multiplier

    cache_start = start_time or datetime.utcnow() - timedelta(minutes=target_interval * lookback * 2)
    cached_df = _db_logger.get_market_data(symbol, target_interval, cache_start)
    if not cached_df.empty and len(cached_df) >= lookback:
        return cached_df.tail(lookback)

    if start_time:
        since = int(start_time.timestamp())
    else:
        since = int(time.time()) - (base_lookback * base_interval * 60 * 2)  # 2x buffer

    params = {
        "pair": kraken_symbol,
        "interval": base_interval,
        "since": since
    }

    try:
        response = requests.get(KRAKEN_OHLC_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("error"):
            print(f"[ERROR] Kraken API returned error for {symbol}: {data['error']}")
            return pd.DataFrame()

        raw = data["result"].get(kraken_symbol)
        if not raw:
            print(f"[ERROR] No OHLC data returned for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(raw, columns=[
            "timestamp", "open", "high", "low", "close",
            "vwap", "volume", "count"
        ])

        df = df.astype({
            "timestamp": int,
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "volume": float
        })

        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        df = df[["open", "high", "low", "close", "volume"]]

        if resample_rule:
            df = (
                df.resample(resample_rule)
                .agg({
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                })
                .dropna()
            )

        if len(df) < lookback:
            print(f"[WARNING] Only {len(df)} candles returned for {symbol} (expected {lookback})")
            raise ValueError(f"Insufficient data for {symbol}")

        trimmed = df.tail(lookback)

        enriched = add_indicators(trimmed.reset_index())
        enriched.set_index("timestamp", inplace=True)

        signals = []
        for i in range(len(enriched)):
            window = enriched.iloc[: i + 1]
            signals.append(generate_signal(window, on_bar_close=False))
        enriched["signal"] = signals

        _db_logger.cache_market_data(symbol, target_interval, enriched)
        return enriched

    except requests.exceptions.RequestException as e:
        print(f"[NETWORK ERROR] Failed to fetch OHLC for {symbol}: {str(e)}")
        return pd.DataFrame()
    except ValueError as e:
        print(f"[DATA ERROR] {str(e)}")
        return pd.DataFrame()