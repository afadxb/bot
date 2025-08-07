import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import requests
import pytz
from functools import lru_cache
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import hmac
import hashlib
import base64
import urllib.parse

# Load environment variables
load_dotenv()

# Configuration
st.set_page_config(layout="wide", page_title="Trading Bot Dashboard")
REFRESH_INTERVAL = 60  # seconds
CACHE_TTL = 300  # 5 minutes cache for database queries

# Database and API Configuration
DATABASE_URL = os.getenv('DATABASE_URL')
KRAKEN_API_KEY = os.getenv('KRAKEN_API_KEY')
KRAKEN_API_SECRET = os.getenv('KRAKEN_API_SECRET').encode()

# Symbol mapping (adjust based on your trading pairs)
SYMBOLS_MAPPING = {
    'BTC/USD': 'XXBTZUSD',
    'ETH/USD': 'XETHZUSD',
    'DOGE/USD': 'XDGUSD'
}

# Database Connection Helper
def create_db_connection():
    try:
        engine = create_engine(DATABASE_URL)
        return engine
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

# Kraken API Authentication
def get_kraken_signature(urlpath, data, secret):
    postdata = urllib.parse.urlencode(data)
    encoded = (str(data['nonce']) + postdata).encode()
    message = urlpath.encode() + hashlib.sha256(encoded).digest()
    mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
    sigdigest = base64.b64encode(mac.digest())
    return sigdigest.decode()

def kraken_request(uri_path, data):
    headers = {
        'API-Key': KRAKEN_API_KEY,
        'API-Sign': get_kraken_signature(uri_path, data, KRAKEN_API_SECRET)
    }
    response = requests.post(f"https://api.kraken.com{uri_path}", headers=headers, data=data)
    return response.json()

# Data Fetching Functions with Caching
@lru_cache(maxsize=32, typed=False)
def get_cached_data(query_name, *args):
    """Generic caching function for database queries"""
    if query_name == "open_positions":
        return fetch_open_positions()
    elif query_name == "portfolio_allocation":
        return fetch_portfolio_allocation()
    elif query_name == "cumulative_pnl":
        return fetch_cumulative_pnl()
    elif query_name == "todays_trades":
        return fetch_todays_trades()
    return None

def fetch_open_positions():
    engine = create_db_connection()
    if not engine:
        return pd.DataFrame()
    
    query = text("""
    SELECT 
        symbol, volume, entry_price, entry_time
    FROM positions
    WHERE status = 'open'
    """)
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        
        # Get current prices from Kraken
        df['current_price'] = df['symbol'].apply(get_current_price)
        df['unrealized_pnl'] = (df['current_price'] - df['entry_price']) * df['volume']
        return df
    except Exception as e:
        st.error(f"Error fetching open positions: {e}")
        return pd.DataFrame()

def fetch_portfolio_allocation():
    engine = create_db_connection()
    if not engine:
        return pd.DataFrame()
    
    query = text("""
    SELECT 
        asset, 
        SUM(value_usd) as value
    FROM portfolio_allocation
    GROUP BY asset
    """)
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        
        # Calculate percentages
        total_value = df['value'].sum()
        df['percentage'] = (df['value'] / total_value) * 100
        return df
    except Exception as e:
        st.error(f"Error fetching portfolio allocation: {e}")
        return pd.DataFrame()

def fetch_cumulative_pnl():
    engine = create_db_connection()
    if not engine:
        return pd.DataFrame()
    
    query = text("""
    SELECT 
        date, 
        SUM(pnl) as pnl
    FROM trades
    GROUP BY date
    ORDER BY date
    """)
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        df['cumulative_pnl'] = df['pnl'].cumsum()
        return df
    except Exception as e:
        st.error(f"Error fetching cumulative PnL: {e}")
        return pd.DataFrame()

def fetch_todays_trades():
    engine = create_db_connection()
    if not engine:
        return pd.DataFrame()
    
    today = datetime.now().strftime('%Y-%m-%d')
    query = text(f"""
    SELECT 
        time, symbol, side, price, quantity, pnl
    FROM trades
    WHERE date = :today
    ORDER BY time DESC
    LIMIT 20
    """)
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection, params={'today': today})
        return df
    except Exception as e:
        st.error(f"Error fetching today's trades: {e}")
        return pd.DataFrame()

def get_current_price(symbol):
    """Fetch current price from Kraken API"""
    kraken_symbol = SYMBOLS_MAPPING.get(symbol)
    if not kraken_symbol:
        return 0
    
    try:
        # Using authenticated request for more reliable data
        nonce = str(int(time.time() * 1000))
        data = {
            'nonce': nonce,
            'pair': kraken_symbol
        }
        response = kraken_request('/0/public/Ticker', data)
        
        if 'result' in response and kraken_symbol in response['result']:
            return float(response['result'][kraken_symbol]['c'][0])
        return 0
    except Exception as e:
        st.error(f"Error fetching price for {symbol}: {e}")
        return 0

def fetch_ohlc_data(symbol='BTC/USD', interval=15, since=None):
    """Fetch OHLC data from Kraken API"""
    kraken_symbol = SYMBOLS_MAPPING.get(symbol)
    if not kraken_symbol:
        return pd.DataFrame()
    
    try:
        nonce = str(int(time.time() * 1000))
        data = {
            'nonce': nonce,
            'pair': kraken_symbol,
            'interval': interval
        }
        if since:
            data['since'] = since
            
        response = kraken_request('/0/public/OHLC', data)
        
        if 'result' in response and kraken_symbol in response['result']:
            ohlc_data = response['result'][kraken_symbol]
            df = pd.DataFrame(ohlc_data, columns=[
                'time', 'open', 'high', 'low', 'close', 
                'vwap', 'volume', 'count'
            ])
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df['symbol'] = symbol
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching OHLC data for {symbol}: {e}")
        return pd.DataFrame()

def calculate_risk_metrics():
    """Calculate risk metrics from trade data"""
    engine = create_db_connection()
    if not engine:
        return {}
    
    query = text("""
    SELECT 
        pnl, 
        entry_time,
        exit_time
    FROM trades
    WHERE pnl IS NOT NULL
    """)
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        
        if df.empty:
            return {}
        
        # Calculate max drawdown
        df['cumulative_pnl'] = df['pnl'].cumsum()
        df['peak'] = df['cumulative_pnl'].cummax()
        df['drawdown'] = df['cumulative_pnl'] - df['peak']
        max_drawdown = df['drawdown'].min()
        
        # Calculate risk/reward ratio
        avg_win = df[df['pnl'] > 0]['pnl'].mean()
        avg_loss = abs(df[df['pnl'] < 0]['pnl'].mean())
        risk_reward = avg_win / avg_loss if avg_loss != 0 else 0
        
        # Calculate win rate
        win_rate = len(df[df['pnl'] > 0]) / len(df)
        
        return {
            'max_drawdown': max_drawdown,
            'risk_reward': risk_reward,
            'win_rate': win_rate
        }
    except Exception as e:
        st.error(f"Error calculating risk metrics: {e}")
        return {}

# Dashboard Layout
def main():
    # Auto-refresh logic
    last_refresh = st.empty()
    
    # Header
    st.title("Trading Bot Dashboard")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("AI Trading Bot v2.1")
    with col2:
        last_refresh.text(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # KPI Strip
    st.markdown("---")
    
    # Calculate KPIs
    risk_metrics = calculate_risk_metrics()
    cumulative_pnl = get_cached_data("cumulative_pnl")
    total_pnl = cumulative_pnl['cumulative_pnl'].iloc[-1] if not cumulative_pnl.empty else 0
    open_positions = get_cached_data("open_positions")
    unrealized_pnl = open_positions['unrealized_pnl'].sum() if not open_positions.empty else 0
    win_rate = risk_metrics.get('win_rate', 0)
    todays_trades = get_cached_data("todays_trades")
    trades_today = len(todays_trades) if todays_trades is not None else 0
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total P&L", f"${total_pnl:,.2f}", 
               f"{(unrealized_pnl/total_pnl*100 if total_pnl !=0 else 0):.1f}%" if unrealized_pnl !=0 else "")
    kpi2.metric("Unrealized P&L", f"${unrealized_pnl:,.2f}", 
               f"{(unrealized_pnl/total_pnl*100 if total_pnl !=0 else 0):.1f}%" if unrealized_pnl !=0 else "")
    kpi3.metric("Win Rate", f"{win_rate*100:.1f}%")
    kpi4.metric("Trades Today", trades_today)
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Open Positions Grid
        st.subheader("Open Positions")
        if not open_positions.empty:
            st.dataframe(open_positions.style.format({
                'entry_price': '${:,.2f}',
                'current_price': '${:,.2f}',
                'unrealized_pnl': '${:,.2f}'
            }), use_container_width=True)
        else:
            st.info("No open positions currently")
        
        # Cumulative PnL Chart
        st.subheader("Cumulative P&L")
        if not cumulative_pnl.empty:
            fig = px.line(cumulative_pnl, x='date', y='cumulative_pnl', 
                         labels={'cumulative_pnl': 'Profit & Loss ($)'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No P&L data available")
        
    with col2:
        # Portfolio Allocation Pie
        st.subheader("Portfolio Allocation")
        portfolio_data = get_cached_data("portfolio_allocation")
        if not portfolio_data.empty:
            fig = px.pie(portfolio_data, values='percentage', names='asset')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No portfolio allocation data available")
        
        # Risk Panel
        st.subheader("Risk Metrics")
        if risk_metrics:
            col1, col2 = st.columns(2)
            col1.metric("Max Drawdown", f"${risk_metrics['max_drawdown']:,.2f}")
            col2.metric("Risk/Reward Ratio", f"{risk_metrics['risk_reward']:.2f}:1")
            st.metric("Win Rate", f"{risk_metrics['win_rate']*100:.1f}%")
        else:
            st.info("No risk metrics available")
    
    # Today's Trades Table
    st.subheader("Today's Trades")
    if todays_trades is not None and not todays_trades.empty:
        st.dataframe(todays_trades.style.format({
            'price': '${:,.2f}',
            'pnl': '${:,.2f}'
        }), use_container_width=True)
    else:
        st.info("No trades today")
    
    # Candlestick Chart
    st.subheader("Price Action")
    symbol_to_display = st.selectbox("Select Symbol", list(SYMBOLS_MAPPING.keys()))
    ohlc_data = fetch_ohlc_data(symbol=symbol_to_display)
    if not ohlc_data.empty:
        fig = go.Figure(data=[go.Candlestick(
            x=ohlc_data['time'],
            open=ohlc_data['open'].astype(float),
            high=ohlc_data['high'].astype(float),
            low=ohlc_data['low'].astype(float),
            close=ohlc_data['close'].astype(float)
        )])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No price data available")
    
    # Alert Banner
    if unrealized_pnl < -1000:  # Example threshold
        st.error("?? Warning: Significant unrealized losses detected!")
    elif unrealized_pnl > 2000:  # Example threshold
        st.success("?? Strong unrealized gains!")
    
    # Footer
    st.markdown("---")
    st.caption(f"Dashboard v2.1 | Data as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Auto-refresh
    time.sleep(REFRESH_INTERVAL)
    st.experimental_rerun()

if __name__ == "__main__":
    main()