import os
import mysql.connector
from datetime import datetime

def to_float(value):
    try:
        return float(value)
    except:
        return None

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )

def save_sentiment_data(final_scores, normalized_factors, raw_factors, regime):
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.utcnow()

    for symbol, final_score in final_scores.items():
        norm = normalized_factors[symbol]
        raw = raw_factors[symbol]

        query = """
        INSERT INTO sentiment_factors
        (symbol, timeframe, timestamp, volatility_raw, momentum_raw, volume_raw,
         marketcap_raw, btcdom_raw, volatility_score, momentum_score, volume_score,
         marketcap_score, btcdom_score, final_score, regime)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            symbol,
            '4h',
            now,
            to_float(raw["volatility_raw"]),
            to_float(raw["momentum_raw"]),
            to_float(raw["volume_raw"]),
            to_float(raw["marketcap_raw"]),
            to_float(raw["btcdom_raw"]),
            to_float(norm["volatility_score"]),
            to_float(norm["momentum_score"]),
            to_float(norm["volume_score"]),
            to_float(norm["marketcap_score"]),
            to_float(norm["btcdom_score"]),
            to_float(final_score),
            regime
        )
        cursor.execute(query, values)

        # Also update latest simple table
        cursor.execute("""
        INSERT INTO fear_greed_scores (symbol, timestamp, volatility_score, momentum_score, volume_score,
            marketcap_score, btcdom_score, final_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            symbol,
            now,
            to_float(norm["volatility_score"]),
            to_float(norm["momentum_score"]),
            to_float(norm["volume_score"]),
            to_float(norm["marketcap_score"]),
            to_float(norm["btcdom_score"]),
            to_float(final_score)
        ))

    conn.commit()
    cursor.close()
    conn.close()
