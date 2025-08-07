# sentiment/healthcheck.py

import mysql.connector
import os
from datetime import datetime, timedelta
from utils.env_loader import load_env
from utils.alerts import send_alert

def check_recent_sentiment():
    load_env()

    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor()

    query = """
    SELECT MAX(timestamp) 
    FROM fear_greed_scores
    """
    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        latest_timestamp = result[0]
        now = datetime.utcnow()
        delay = now - latest_timestamp

        if delay > timedelta(minutes=30):
            message = f"[WARNING] Sentiment data is OLD! Last update: {latest_timestamp}"
            print(message)
            send_alert(message, priority=1)
        else:
            message = f"[OK] Sentiment updated at {latest_timestamp}"
            print(message)

    else:
        message = "[ERROR] No sentiment data found!"
        print(message)
        send_alert(message, priority=1)

if __name__ == "__main__":
    check_recent_sentiment()
