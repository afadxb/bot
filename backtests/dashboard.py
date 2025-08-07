import streamlit as st
import pandas as pd
from backtests.backtest_runner import run_backtest

st.title('Backtest Dashboard')
symbol = st.selectbox('Symbol', options=['BTC/USD', 'ETH/USD', 'XRP/USD'])
start_date = st.date_input('Start Date')
end_date = st.date_input('End Date')
if st.button('Run Backtest'):
    df_trades = run_backtest(symbol, str(start_date), str(end_date))
    df_trades = pd.DataFrame(df_trades)
    st.subheader('Trades')
    st.dataframe(df_trades)
    eq_curve = df_trades['pnl'].cumsum()
    st.line_chart(eq_curve.rename('Equity Curve'))
    drawdown = eq_curve - eq_curve.cummax()
    st.line_chart(drawdown.rename('Drawdown'))
    profit_by_symbol = df_trades.groupby('entry_price')['pnl'].sum()
    st.bar_chart(profit_by_symbol)
    st.write('Win Rate:', f"{(df_trades['pnl'] > 0).mean():.2%}")
    st.write('Average PnL:', df_trades['pnl'].mean())
    st.write('Average Holding Time:', (pd.to_datetime(df_trades['exit_time']) - pd.to_datetime(df_trades['entry_time'])).mean())
