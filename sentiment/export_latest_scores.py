# sentiment/export_latest_scores.py

import mysql.connector
import pandas as pd
import os
from datetime import datetime
from utils.env_loader import load_env

def export_latest_scores():
    load_env()

    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT symbol, timestamp, final_score
    FROM fear_greed_scores
    WHERE timestamp = (SELECT MAX(timestamp) FROM fear_greed_scores WHERE symbol = fgs.symbol)
    ORDER BY symbol ASC
    """
    query = query.replace('fgs', 'fear_greed_scores')  # aliasing fix
    cursor.execute(query)
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    if results:
        df = pd.DataFrame(results)
        output_path = os.path.join(os.path.dirname(__file__), "logs", "latest_scores.csv")
        df.to_csv(output_path, index=False)
        print(f"[OK] Exported latest scores to {output_path}")
    else:
        print("[WARNING] No scores available to export.")

if __name__ == "__main__":
    export_latest_scores()
