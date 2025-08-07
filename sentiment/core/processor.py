# sentiment/core/processor.py

import pandas as pd
import numpy as np

def calculate_atr(ohlc_data, period=14):
    df = pd.DataFrame(ohlc_data)
    df['H-L'] = df['high'] - df['low']
    df['H-C'] = abs(df['high'] - df['close'].shift())
    df['L-C'] = abs(df['low'] - df['close'].shift())
    df['TR'] = df[['H-L', 'H-C', 'L-C']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=period).mean()
    return df['ATR'].iloc[-1] / df['close'].iloc[-1]

def calculate_macd_histogram(ohlc_data, fast=12, slow=26, signal=9):
    df = pd.DataFrame(ohlc_data)
    df['EMA_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['EMA_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = df['EMA_fast'] - df['EMA_slow']
    df['Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    df['Histogram'] = df['MACD'] - df['Signal']
    return df['Histogram'].iloc[-1]

def calculate_volume_ratio(ohlc_data, lookback=30):
    df = pd.DataFrame(ohlc_data)
    avg_volume = df['volume'].tail(lookback).mean()
    current_volume = df['volume'].iloc[-1]
    return current_volume / avg_volume if avg_volume != 0 else 1

def calculate_market_cap_change(current_marketcap, previous_marketcap):
    if previous_marketcap == 0:
        return 0
    return ((current_marketcap - previous_marketcap) / previous_marketcap) * 100

def calculate_btc_dominance_change(current_dominance, previous_dominance):
    return current_dominance - previous_dominance

def process_all_factors(market_data):
    factors = {}

    previous_cmc_data = market_data.get("CMC", {})
    current_cmc_data = market_data.get("CMC", {})

    for symbol, data in market_data.items():
        if symbol == "CMC":
            continue

        ohlc = data['ohlc']

        factors[symbol] = {
            "volatility_raw": calculate_atr(ohlc),
            "momentum_raw": calculate_macd_histogram(ohlc),
            "volume_raw": calculate_volume_ratio(ohlc),
            "marketcap_raw": current_cmc_data.get('total_market_cap_usd', 0),
            "btcdom_raw": current_cmc_data.get('btc_dominance', 0)
        }

    return factors
