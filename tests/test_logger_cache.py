import pandas as pd

from core.logger import DBLogger


def test_market_data_cache_roundtrip():
    logger = DBLogger("sqlite:///:memory:")
    df = pd.DataFrame(
        {
            "time": [1, 2, 3],
            "open": [10.0, 11.0, 12.0],
            "high": [10.5, 11.5, 12.5],
            "low": [9.5, 10.5, 11.5],
            "close": [10.2, 11.2, 12.2],
        }
    )

    logger.upsert_market_data_cache("BTC/USD", 240, 60, df)

    cached_df = logger.get_cached_market_data("BTC/USD", 240, 60)

    pd.testing.assert_frame_equal(cached_df.reset_index(drop=True), df)


def test_market_data_cache_overwrites_previous_entries():
    logger = DBLogger("sqlite:///:memory:")

    first = pd.DataFrame({"close": [1.0, 2.0]})
    updated = pd.DataFrame({"close": [3.0, 4.0]})

    logger.upsert_market_data_cache("ETH/USD", 60, 15, first)
    logger.upsert_market_data_cache("ETH/USD", 60, 15, updated)

    cached_df = logger.get_cached_market_data("ETH/USD", 60, 15)

    pd.testing.assert_frame_equal(cached_df.reset_index(drop=True), updated)
