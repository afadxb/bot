import os

def get_fear_greed_score():
    """
    Fetch live emotional factors, normalize them, adjust Fear & Greed based on market regime.
    """
    from sentiment.core.social_fetcher import fetch_all_emotional_factors
    from sentiment.core.normalizer import normalize_emotional_factors
    from sentiment.core.regime_detector import detect_market_regime
    from sentiment.core.fetcher import fetch_all_data

    # Fetch raw emotional data
    raw_emotions = fetch_all_emotional_factors()
    normalized = normalize_emotional_factors(raw_emotions)

    funding_score = normalized.get('funding_rate_score', 50)
    long_short_score = normalized.get('long_short_score', 50)
    taker_volume_score = normalized.get('taker_volume_score', 50)

    # Detect overall market regime (bullish / bearish / sideways)
    market_data = fetch_all_data()
    regime = detect_market_regime(market_data)

    # Base final score from emotions
    base_emotional_score = (
        funding_score * 0.05 +
        long_short_score * 0.05 +
        taker_volume_score * 0.05 +
        50 * 0.85
    )

    # Adjust based on regime
    if regime == "bullish":
        adjustment = +5  # Slight optimism boost
    elif regime == "bearish":
        adjustment = -5  # Slight fear penalty
    else:
        adjustment = 0  # Neutral

    final_score = max(0, min(100, base_emotional_score + adjustment))  # Clamp to 0-100

    return final_score

def calculate_final_score(normalized_factors, regime, emotional_factors=None):
    final_scores = {}
    
    weight_volatility = float(os.getenv("WEIGHT_VOLATILITY", 0.25))
    weight_momentum = float(os.getenv("WEIGHT_MOMENTUM", 0.20))
    weight_volume = float(os.getenv("WEIGHT_VOLUME_SURGE", 0.20))
    weight_marketcap = float(os.getenv("WEIGHT_MARKET_CAP_TREND", 0.20))
    weight_btcdom = float(os.getenv("WEIGHT_BTC_DOMINANCE", 0.15))

    weight_funding = float(os.getenv("WEIGHT_FUNDING_RATE", 0.05))
    weight_longshort = float(os.getenv("WEIGHT_LONG_SHORT_RATIO", 0.05))
    weight_taker_volume = float(os.getenv("WEIGHT_TAKER_VOLUME_RATIO", 0.05))

    for symbol, scores in normalized_factors.items():
        final = (
            scores["volatility_score"] * weight_volatility +
            scores["momentum_score"] * weight_momentum +
            scores["volume_score"] * weight_volume +
            scores["marketcap_score"] * weight_marketcap +
            scores["btcdom_score"] * weight_btcdom
        )

        if emotional_factors:
            final += (
                emotional_factors["funding_rate_score"] * weight_funding +
                emotional_factors["long_short_score"] * weight_longshort +
                emotional_factors["taker_volume_score"] * weight_taker_volume
            )

        final_scores[symbol] = final

    return final_scores
