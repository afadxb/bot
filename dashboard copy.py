import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv

# ─── Config ────────────────────────────────────────────────────────────────────
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")  # e.g. mysql+pymysql://user:pass@host/db
engine = create_engine(DB_URL, future=True)

# ─── UI ────────────────────────────────────────────────────────────────────────
st.title("📈 Live Kraken Swing‐Bot Dashboard")

# Filters
all_symbols = [s.strip() for s in os.getenv("SYMBOLS", "").split(",") if s.strip()]
all_tags    = ["breakout", "pullback", "swing"]  # you can also fetch DISTINCT(tag) from DB
symbols     = st.multiselect("Signal Symbols", all_symbols, default=all_symbols)
tags        = st.multiselect("Trade Tags",      all_tags,    default=all_tags)
start_date  = st.date_input("Start Date",  value=pd.to_datetime("2025-01-01"))
end_date    = st.date_input("End Date",    value=pd.to_datetime("today"))

if st.button("🔄 Refresh Dashboard"):
    # ─── Load Positions ─────────────────────────────────────────────
    df_pos = pd.read_sql(
        "SELECT * FROM positions",
        engine,
        parse_dates=["entry_time", "exit_time"]
    )
    # Time & filter masks
    mask = (df_pos["entry_time"] >= pd.Timestamp(start_date)) & (df_pos["entry_time"] <= pd.Timestamp(end_date))
    if symbols: mask &= df_pos["symbol"].isin(symbols)
    if tags:    mask &= df_pos["tag"].isin(tags)
    df_pos = df_pos.loc[mask].sort_values("entry_time")

    # ─── Performance Summary ─────────────────────────────────────────
    df_closed = df_pos[df_pos["status"] == "closed"].copy()
    def avg_ret(x):
        return ((x["exit_price"] - x["entry_price"]) / x["entry_price"]).mean()
    def win_rate(x):
        return (x["exit_price"] > x["entry_price"]).mean()
    def avg_hold(x):
        return (x["exit_time"] - x["entry_time"]).mean()

    summary = (
        df_closed
        .groupby(["symbol","tag"])
        .agg(
            total_trades=("id","count"),
            total_pnl=("pnl","sum"),
            avg_return=lambda x: avg_ret(df_closed.loc[x.index]),
            win_rate=lambda x: win_rate(df_closed.loc[x.index]),
            avg_holding_time=lambda x: avg_hold(df_closed.loc[x.index])
        )
        .reset_index()
    )
    st.subheader("📊 Performance by Symbol / Tag")
    st.dataframe(summary)

    # ─── Equity Curve & Drawdown ───────────────────────────────────────
    df_closed["equity"] = df_closed["pnl"].cumsum()
    equity = df_closed.set_index("exit_time")["equity"]
    st.subheader("📈 Equity Curve")
    st.line_chart(equity)
    st.subheader("📉 Drawdown")
    drawdown = equity - equity.cummax()
    st.line_chart(drawdown)

    # ─── Trades Ledger ─────────────────────────────────────────────────
    df_trades = pd.read_sql(
        "SELECT * FROM trades",
        engine,
        parse_dates=["timestamp"]
    )
    tmask = (df_trades["timestamp"] >= pd.Timestamp(start_date)) & (df_trades["timestamp"] <= pd.Timestamp(end_date))
    if symbols: tmask &= df_trades["symbol"].isin(symbols)
    if tags:    tmask &= df_trades["tag"].isin(tags)
    df_trades = df_trades.loc[tmask]
    st.subheader("📝 All Trade Records")
    st.dataframe(df_trades)

