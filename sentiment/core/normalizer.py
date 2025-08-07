# sentiment/core/normalizer.py

def normalize(value, min_val, max_val):
    if value is None:
        return 50
    if max_val == min_val:
        return 50
    return max(0, min(100, (value - min_val) / (max_val - min_val) * 100))

def normalize_factors(factors):
    normalized = {}
    for symbol, raw in factors.items():
        normalized[symbol] = {
            "volatility_score": normalize(raw["volatility_raw"], 0, 0.05),
            "momentum_score": normalize(raw["momentum_raw"], -0.01, 0.01),
            "volume_score": normalize(raw["volume_raw"], 0.8, 1.5),
            "marketcap_score": normalize(raw["marketcap_raw"], 500000000000, 3000000000000),
            "btcdom_score": normalize(raw["btcdom_raw"], 35, 70),
        }
    return normalized

def normalize_funding_rate(value):
    # Funding Rate: positive = greed, negative = fear
    return normalize(value, -0.01, 0.01)

def normalize_long_short_ratio(value):
    # Long/Short Ratio: 1 = neutral, >1 = greed, <1 = fear
    return normalize(value, 0.8, 1.2)

def normalize_taker_volume_ratio(value):
    # Taker Volume Ratio: 1 = neutral, >1 = greed
    return normalize(value, 0.8, 1.2)

def normalize_emotional_factors(raw_factors):
    return {
        "funding_rate_score": normalize_funding_rate(raw_factors.get("funding_rate", 0)),
        "long_short_score": normalize_long_short_ratio(raw_factors.get("long_short_ratio", 1)),
        "taker_volume_score": normalize_taker_volume_ratio(raw_factors.get("taker_volume_ratio", 1)),
    }

