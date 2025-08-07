# sentiment/core/regime_detector.py

def detect_market_regime(market_data):
    marketcap = market_data.get('CMC', {}).get('total_market_cap_usd', 0)
    btcdom = market_data.get('CMC', {}).get('btc_dominance', 0)

    # Dummy baseline values for now
    previous_marketcap = marketcap * 0.98
    previous_btcdom = btcdom * 1.02

    marketcap_change = ((marketcap - previous_marketcap) / previous_marketcap) * 100
    btcdom_change = btcdom - previous_btcdom

    if marketcap_change > 3 and btcdom_change < -0.5:
        return "bullish"
    elif marketcap_change < -3 and btcdom_change > 0.5:
        return "bearish"
    else:
        return "sideways"
