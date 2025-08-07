import pandas as pd
import os
from datetime import datetime

LOG_FILE = "logs/emotional_factors.csv"

def log_emotional_snapshot(timestamp, funding_rate, long_short_ratio, taker_volume_ratio, fg_score):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    df = pd.DataFrame([{
        "timestamp": timestamp,
        "funding_rate": funding_rate,
        "long_short_ratio": long_short_ratio,
        "taker_volume_ratio": taker_volume_ratio,
        "fear_greed_score": fg_score
    }])
    if os.path.exists(LOG_FILE):
        df.to_csv(LOG_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(LOG_FILE, index=False)
