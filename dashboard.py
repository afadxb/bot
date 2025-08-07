import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
from sqlalchemy import Table

from core.logger import DBLogger

# Configuration
st.set_page_config(layout="wide", page_title="Trading Bot Dashboard")
REFRESH_INTERVAL = 60  # seconds

# Connect to MySQL
db_logger = DBLogger()
engine = db_logger.engine
trades_table = db_logger.metadata.tables["trades"]
positions_table = db_logger.metadata.tables["positions"]
#fear_greed_table = db_logger.metadata.tables["fear_greed_scores"]
fear_greed_table = Table('fear_greed_scores', db_logger.metadata, autoload_with=engine)

# Data Functions
def get_open_positions():
    with engine.connect() as conn:
        result = conn.execute(
            positions_table.select().where(positions_table.c.status == "open")
        )
        df = pd.DataFrame(result.mappings().all())
    return df

def get_portfolio_allocation():
    with engine.connect() as conn:
        result = conn.execute("SELECT symbol, SUM(volume * entry_price) AS value FROM positions WHERE status='open' GROUP BY symbol")
        df = pd.DataFrame(result.mappings().all())
    if df.empty:
        return pd.DataFrame({'asset': [], 'percentage': []})
    df['percentage'] = 100 * df['value'] / df['value'].sum()
    df['asset'] = df['symbol'].str.split('/').str[0]
    return df[['asset', 'percentage']]

def get_cumulative_pnl():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT close_time, pnl FROM trades WHERE pnl IS NOT NULL ORDER BY close_time", conn)
    if df.empty:
        return pd.DataFrame({'date': [], 'pnl': []})
    df['close_time'] = pd.to_datetime(df['close_time'])
    df = df.rename(columns={'close_time': 'date'})
    df['cumulative_pnl'] = df['pnl'].cumsum()
    return df[['date', 'cumulative_pnl']].rename(columns={'cumulative_pnl': 'pnl'})

def get_today_trades():
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    with engine.connect() as conn:
        df = pd.read_sql(f"SELECT * FROM trades WHERE DATE(close_time) = '{today_str}'", conn)
    return df

def get_fear_greed_history():
    with engine.connect() as conn:
        df = pd.read_sql(
            "SELECT timestamp, final_score FROM fear_greed_scores WHERE symbol = 'TOTAL' ORDER BY timestamp ASC", conn
        )
    if df.empty:
        return pd.DataFrame()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# Dashboard Layout
def main():
    last_refresh = st.empty()

    st.title("Trading Bot Dashboard")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Kraken Trading Bot")
    with col2:
        last_refresh.text(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    st.markdown("---")

    # Load fear & greed history early
    fg_data = get_fear_greed_history()

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

    kpi1.metric("Total P&L", "$", "live")
    kpi2.metric("Unrealized P&L", "$", "live")
    kpi3.metric("Win Rate", "-", "-")
    kpi4.metric("Trades Today", "-", "-")

    # ?? Fear & Greed KPI
    if not fg_data.empty:
        latest_fg = fg_data.iloc[-1]["final_score"]
        fg_color = "green" if latest_fg > 50 else "red"
        kpi5.metric("Fear & Greed", f"{latest_fg:.1f}", delta=None, delta_color="off")
    else:
        kpi5.metric("Fear & Greed", "-", "-")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Open Positions")
        positions = get_open_positions()
        if not positions.empty:
                cols_to_show = ['symbol', 'volume', 'entry_price']
                if 'trailing_stop' in positions.columns:
                        cols_to_show.append('trailing_stop')

                st.dataframe(
                    positions[cols_to_show].style.format({
                        'entry_price': '${:,.2f}',
                        'trailing_stop': '${:,.2f}',
                        'volume': '{:,.6f}'
                    }),
                    use_container_width=True
                )
        else:
            st.info("No open positions.")

        st.subheader("Cumulative P&L")
        pnl_data = get_cumulative_pnl()
        if not pnl_data.empty:
            fig = px.line(pnl_data, x='date', y='pnl',
                          labels={'pnl': 'Profit & Loss ($)'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No PnL history yet.")

    with col2:
        st.subheader("Portfolio Allocation")
        alloc_data = get_portfolio_allocation()
        if not alloc_data.empty:
            fig = px.pie(alloc_data, values='percentage', names='asset')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No portfolio data.")

        st.subheader("Risk Metrics")
        st.metric("Max Drawdown", "-")
        st.metric("Risk/Reward Ratio", "-")
        st.metric("Sharpe Ratio", "-")

    st.subheader("Today's Trades")
    trades = get_today_trades()
    if not trades.empty:
        st.dataframe(trades[['symbol', 'side', 'entry_price', 'exit_price', 'volume', 'pnl']].style.format({
            'entry_price': '${:,.2f}',
            'exit_price': '${:,.2f}',
            'pnl': '${:,.2f}'
        }), use_container_width=True)
    else:
        st.info("No trades today.")

    # ?? Fear & Greed Score over Time
    st.subheader("Fear & Greed Score Over Time")
    if not fg_data.empty:
        fig = px.line(fg_data, x="timestamp", y="final_score",
                      labels={"final_score": "Fear & Greed Score (0-100)"},
                      title="Fear & Greed Historical Trend")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No Fear & Greed data available.")

    # ?? Price Candlestick (optional mock still)
    st.subheader("Price Action (Sample Candlestick)")
    fig = go.Figure(data=[go.Candlestick(
        x=pd.date_range(start='2023-01-01', periods=20),
        open=pd.Series(45000 + np.random.randn(20) * 500),
        high=pd.Series(45500 + np.random.randn(20) * 500),
        low=pd.Series(44500 + np.random.randn(20) * 500),
        close=pd.Series(45000 + np.random.randn(20) * 500)
    )])
    st.plotly_chart(fig, use_container_width=True)

    time.sleep(REFRESH_INTERVAL)
    st.experimental_rerun()

if __name__ == "__main__":
    main()
