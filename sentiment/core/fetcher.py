# sentiment/core/fetcher.py

import os
import requests
import time
import logging
from utils.retry import retry
from utils.cache import cache_result

KRAKEN_API_URL = "https://api.kraken.com/0/public/OHLC"
CMC_API_URL = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
CMC_API_KEY = os.getenv("CMC_API_KEY")

# Retry decorator will automatically retry failed calls
@retry(times=3, backoff=5)
@cache_result(ttl_minutes=5)
def fetch_kraken_ohlcv(pair, interval=240):
    params = {
        "pair": pair.replace("/", ""),  # Kraken uses no slash in symbol
        "interval": interval
    }
    response = requests.get(KRAKEN_API_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if 'error' in data and data['error']:
        raise Exception(f"Kraken API error: {data['error']}")

    # Kraken returns results under pair name key
    results = list(data['result'].values())[0]
    ohlc_data = []
    for candle in results:
        ohlc_data.append({
            "timestamp": int(candle[0]),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[6])
        })
    return ohlc_data

@retry(times=3, backoff=10)
@cache_result(ttl_minutes=15)
def fetch_cmc_global_data1111111111111():
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": CMC_API_KEY,
    }
    response = requests.get(CMC_API_URL, headers=headers)
    response.raise_for_status()
    data = response.json()
    if 'data' not in data:
        raise Exception("Invalid CMC API response.")

    return {
        "total_market_cap_usd": data['data']['quote']['USD']['total_market_cap'],
        "btc_dominance": data['data']['btc_dominance']
    }
@retry(times=3, backoff=10)
@cache_result(ttl_minutes=15)
def fetch_cmc_global_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

    parameters = {
        'start': '1',
        'limit': '2',
        'convert': 'USD'
    }

    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': os.getenv('CMC_API_KEY').strip()
    }

    session = requests.Session()
    session.headers.update(headers)

    response = session.get(url, params=parameters)
    response.raise_for_status()
    data = response.json()

    if 'data' not in data:
        raise Exception("Invalid CMC API response.")

    total_market_cap = 0
    btc_market_cap = 0

    for coin in data['data']:
        total_market_cap += coin['quote']['USD']['market_cap']
        if coin['symbol'] == 'BTC':
            btc_market_cap = coin['quote']['USD']['market_cap']

    btc_dominance = (btc_market_cap / total_market_cap) * 100 if total_market_cap != 0 else 0

    return {
        "total_market_cap_usd": total_market_cap,
        "btc_dominance": btc_dominance
    }

def fetch_all_data():
    symbols = os.getenv("SYMBOLS", "BTC/USD,ETH/USD").split(",")

    market_data = {}

    for symbol in symbols:
        symbol = symbol.strip()
        try:
            ohlc_data = fetch_kraken_ohlcv(symbol)
            market_data[symbol] = {
                "ohlc": ohlc_data
            }
        except Exception as e:
            logging.error(f"Failed to fetch Kraken OHLCV for {symbol}: {str(e)}")

    try:
        cmc_data = fetch_cmc_global_data()
        market_data["CMC"] = cmc_data
    except Exception as e:
        logging.error(f"Failed to fetch CMC Global Data: {str(e)}")

    return market_data

