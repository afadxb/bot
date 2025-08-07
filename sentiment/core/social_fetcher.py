# sentiment/core/social_fetcher.py

import os
import requests
import tweepy
import praw
from datetime import datetime, timedelta
from utils.retry import retry
from utils.cache import cache_result

# Load ENV once at top
BINANCE_FUNDING_RATE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

# --- FUNDING RATE FETCHER ---

@retry(times=3, backoff=5)
@cache_result(ttl_minutes=5)
def fetch_binance_funding_rate(symbol="BTCUSDT"):
    params = {
        "symbol": symbol,
        "limit": 5  # Get last few funding rates
    }
    response = requests.get(BINANCE_FUNDING_RATE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    funding_rates = [float(item['fundingRate']) for item in data]
    avg_funding_rate = sum(funding_rates) / len(funding_rates) if funding_rates else 0
    return avg_funding_rate

# --- GLOBAL LONG/SHORT RATIO ---
@retry(times=3, backoff=5)
@cache_result(ttl_minutes=5)
def fetch_binance_long_short_ratio(symbol="BTCUSDT"):
    params = {
        "symbol": symbol,
        "period": "5m",
        "limit": 5
    }
    url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    ratios = [float(item['longShortRatio']) for item in data]
    avg_ratio = sum(ratios) / len(ratios) if ratios else 1
    return avg_ratio

# --- TAKER BUY/SELL VOLUME RATIO ---
@retry(times=3, backoff=5)
@cache_result(ttl_minutes=5)
def fetch_binance_taker_volume_ratio(symbol="BTCUSDT"):
    params = {
        "symbol": symbol,
        "period": "5m",
        "limit": 5
    }
    url = "https://fapi.binance.com/futures/data/takerlongshortRatio"
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    buy_sell_ratios = []
    for item in data:
        buy_vol = float(item.get('takerBuyVolume', 0))
        sell_vol = float(item.get('takerSellVolume', 0))
        if sell_vol > 0:
            buy_sell_ratios.append(buy_vol / sell_vol)

    avg_ratio = sum(buy_sell_ratios) / len(buy_sell_ratios) if buy_sell_ratios else 1
    return avg_ratio

# --- TWITTER KEYWORD VOLUME ---

@retry(times=3, backoff=5)
@cache_result(ttl_minutes=5)
def fetch_twitter_keyword_count(keyword="bitcoin"):
    if not TWITTER_BEARER_TOKEN:
        return 0

    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"
    }

    now = datetime.utcnow()
    start_time = (now - timedelta(minutes=15)).isoformat("T") + "Z"

    query = {
        'query': keyword,
        'start_time': start_time,
        'max_results': 100
    }

    url = "https://api.twitter.com/2/tweets/counts/recent"
    response = requests.get(url, headers=headers, params=query)
    response.raise_for_status()
    data = response.json()

    total_count = sum(item['tweet_count'] for item in data.get('data', []))
    return total_count

# --- REDDIT SENTIMENT FETCHER ---

@retry(times=3, backoff=5)
@cache_result(ttl_minutes=5)
def fetch_reddit_sentiment(subreddit_name="cryptocurrency"):
    if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET and REDDIT_USER_AGENT):
        return 0

    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )

    posts = reddit.subreddit(subreddit_name).new(limit=50)

    bullish_keywords = ["buy", "bullish", "pump", "moon", "ath"]
    bearish_keywords = ["sell", "bearish", "crash", "panic", "rekt"]

    bullish_score = 0
    bearish_score = 0

    for post in posts:
        text = (post.title + " " + post.selftext).lower()
        if any(word in text for word in bullish_keywords):
            bullish_score += 1
        if any(word in text for word in bearish_keywords):
            bearish_score += 1

    total = bullish_score + bearish_score
    if total == 0:
        return 50  # Neutral

    sentiment_score = (bullish_score / total) * 100
    return sentiment_score

# --- MAIN FETCHER TO COMBINE ALL ---

def fetch_all_emotional_factors():
    results = {}

    # Funding Rate
    funding_rate = fetch_binance_funding_rate("BTCUSDT")
    results['funding_rate'] = funding_rate

    # Long/Short Ratio
    long_short_ratio = fetch_binance_long_short_ratio("BTCUSDT")
    results['long_short_ratio'] = long_short_ratio

    # Taker Buy/Sell Volume Ratio
    taker_volume_ratio = fetch_binance_taker_volume_ratio("BTCUSDT")
    results['taker_volume_ratio'] = taker_volume_ratio

    return results
