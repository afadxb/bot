# sentiment/sentiment.py

import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.data_loader import fetch_ohlc
from core.order_manager import OrderManager
from core.logger import DBLogger
import krakenex

# Setup local imports
from utils.env_loader import load_env
from core.fetcher import fetch_all_data
from core.processor import process_all_factors
from core.normalizer import normalize_factors
from core.regime_detector import detect_market_regime
from core.scorer import calculate_final_score
from core.db_manager import save_sentiment_data
from utils.alerts import send_alert
from core.social_fetcher import fetch_all_emotional_factors
from core.normalizer import normalize_emotional_factors

# --- Setup
api = krakenex.API()
api.key = os.getenv("KRAKEN_API_KEY")
api.secret = os.getenv("KRAKEN_API_SECRET")
order_mgr = OrderManager()
db_logger = DBLogger()

engine = db_logger.engine
positions_table = db_logger.metadata.tables["positions"]

DANGER_FG_SCORE_FOR_EXIT = int(os.getenv("DANGER_FG_SCORE_FOR_EXIT", "15"))

def main():
    try:
        # 1. Load environment variables
        load_env()

        # 2. Fetch Emotional Factors
        emotional_raw = fetch_all_emotional_factors()
        emotional_normalized = normalize_emotional_factors(emotional_raw)

        print("\n==== Live Emotional Factors ====")
        for key, value in emotional_raw.items():
            print(f"RAW {key}: {value}")

        print("\n==== Normalized Emotional Scores (0-100) ====")
        for key, value in emotional_normalized.items():
            print(f"NORMALIZED {key}: {value:.2f}")
        print("=================================\n")

        # 3. Fetch Market Data
        market_data = fetch_all_data()

        # 4. Process Factors
        factors = process_all_factors(market_data)
        normalized_factors = normalize_factors(factors)

        # 5. Detect Market Regime
        regime = detect_market_regime(market_data)

        # 6. Calculate Final Fear & Greed Score
        final_scores = calculate_final_score(normalized_factors, regime)

        # 7. Save Results into MySQL
        save_sentiment_data(final_scores, normalized_factors, factors, regime)

        # 8. Alerts on Extreme Sentiment
        for symbol, score in final_scores.items():
            if score < int(os.getenv("ALERT_THRESHOLD_FEAR", 20)) or score > int(os.getenv("ALERT_THRESHOLD_GREED", 80)):
                send_alert(f"Sentiment Alert: {symbol} score = {score:.2f}")

        # 9. Fetch latest TOTAL Fear & Greed Score
        latest_fear_greed_score = final_scores.get('TOTAL', 50)

        if latest_fear_greed_score < DANGER_FG_SCORE_FOR_EXIT:
            print("?? Fear & Greed CRASH detected. Force exiting all open positions...")
            with engine.connect() as conn:
                result = conn.execute(
                    positions_table.select().where(positions_table.c.status == "open")
                )
                open_positions = pd.DataFrame(result.mappings().all())

            for idx, pos in open_positions.iterrows():
                symbol = pos['symbol']
                volume = pos['volume']

                # Fetch latest OHLC to calculate ATR
                df = fetch_ohlc(symbol, interval=240)  # 4h candles
                if df.empty:
                    print(f"Failed to fetch OHLC for {symbol}. Skipping...")
                    continue

                # Calculate ATR
                df['H-L'] = df['high'] - df['low']
                df['H-C'] = abs(df['high'] - df['close'].shift())
                df['L-C'] = abs(df['low'] - df['close'].shift())
                df['TR'] = df[['H-L', 'H-C', 'L-C']].max(axis=1)
                atr = df['TR'].rolling(window=14).mean().iloc[-1]

                current_price = df['close'].iloc[-1]
                exit_price = max(current_price - atr, 0.01)  # Avoid negative price

                print(f"Placing LIMIT SELL for {symbol} @ {exit_price:.2f} (ATR buffer)")

                try:
                    # Place sell limit order
                    order_mgr.place_limit_order(symbol, "sell", exit_price, volume)

                    # Update DB
                    db_logger.close_position(pos['id'], exit_price)
                except Exception as e:
                    print(f"Error placing forced exit for {symbol}: {str(e)}")

    except Exception as e:
        send_alert(f"Sentiment Engine Critical Failure: {str(e)}", priority=1)
        raise

if __name__ == "__main__":
    main()
