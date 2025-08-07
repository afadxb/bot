# sentiment/dashboard_streamlit.py

import mysql.connector
import pandas as pd
import os
import streamlit as st
from utils.env_loader import load_env
from datetime import datetime, timedelta

def load_data():
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
    WHERE timestamp >= NOW() - INTERVAL 1 DAY
    ORDER BY timestamp ASC
    """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    conn.close()

    if results:
        return pd.DataFrame(results)
    else:
        return pd.DataFrame()

def main():
    st.set_page_config(page_title="Crypto Sentiment Dashboard", layout="wide")
    st.title("?? Real-Time Crypto Fear & Greed Index")

    data = load_data()

    if data.empty:
        st.warning("No sentiment data available.")
        return

    # Show Market Regime (optional enhancement)
    latest_timestamp = data['timestamp'].max()
    now = datetime.utcnow()
    last_update_minutes = (now - latest_timestamp).total_seconds() / 60

    st.markdown(f"#### Last Updated: {latest_timestamp} UTC ({last_update_minutes:.1f} min ago)")

    # Current scores (latest only)
    latest_data = data[data['timestamp'] == data['timestamp'].max()]

    st.subheader("?? Current Fear & Greed Levels")
    st.dataframe(
        latest_data[['symbol', 'final_score']].sort_values(by='final_score', ascending=False)
        .style
        .background_gradient(cmap='RdYlGn')
        .format({"final_score": "{:.2f}"})
    )

    # Top 3 Coins
    st.subheader("?? Top 3 Coins by Sentiment")
    top3 = latest_data.sort_values('final_score', ascending=False).head(3)
    for idx, row in top3.iterrows():
        st.metric(label=f"{row['symbol']}", value=f"{row['final_score']:.2f}")

    # Line Chart
    st.subheader("?? Sentiment Trend Over Last 24 Hours")
    chart_data = data.pivot(index='timestamp', columns='symbol', values='final_score')
    st.line_chart(chart_data)

    st.caption("Auto-refresh every 5 minutes. Built with ?? by yourbot.")

if __name__ == "__main__":
    main()
