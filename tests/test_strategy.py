import pandas as pd

from core.strategy import (
    add_indicators,
    calculate_atr,
    calculate_rsi,
    generate_signal,
    generate_signals,
)


def test_rsi_returns_series():
    data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    rsi = calculate_rsi(data)
    assert isinstance(rsi, pd.Series)


def test_generate_signals_output():
    df = pd.DataFrame({
        'Open': [1]*100,
        'High': [2]*100,
        'Low': [0.5]*100,
        'Close': [1.5]*100,
        'Volume': [100]*100
    })
    config = {'rsi_period': 14, 'atr_period': 14, 'supertrend': {'factor': 3}}
    signals = generate_signals(df, config)
    assert 'entry_signal' in signals.columns


def test_generate_signal_handles_missing_supertrend():
    df = pd.DataFrame(
        {
            "close": [1.0, 1.1, 1.2],
            "rsi": [50, 55, 60],
        }
    )

    assert generate_signal(df) is None


def test_add_indicators_accepts_lowercase_ohlc_columns():
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0],
            "high": [1.2, 2.2, 3.2],
            "low": [0.8, 1.8, 2.8],
            "close": [1.1, 2.1, 3.1],
        }
    )

    result = add_indicators(df)

    assert "supertrend" in result.columns
    assert result["supertrend"].notna().any()
