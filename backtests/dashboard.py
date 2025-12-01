from pathlib import Path
from typing import Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide", page_title="Backtest Dashboard")

LOG_DIR = Path(__file__).parent / "logs"
SUMMARY_CSV = LOG_DIR / "trade_summary.csv"
TICKS_CSV = LOG_DIR / "trade_ticks.csv"
DEFAULT_CAPITAL = 10_000.0


def load_trade_data(summary_path: Path, ticks_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load summary and tick-level data, returning empty DataFrames if missing."""
    summary_df = pd.DataFrame()
    ticks_df = pd.DataFrame()

    if summary_path.exists():
        summary_df = pd.read_csv(summary_path, parse_dates=["entry_time", "exit_time"])

    if ticks_path.exists():
        ticks_df = pd.read_csv(ticks_path, parse_dates=["timestamp"])

    return summary_df, ticks_df


def equity_curve(summary_df: pd.DataFrame, starting_capital: float) -> pd.DataFrame:
    """Return a DataFrame with equity and drawdown series."""
    pnl = summary_df.get("pnl", pd.Series(dtype=float)).fillna(0)
    equity = pnl.cumsum() + starting_capital
    drawdown = equity.cummax() - equity
    timeline = summary_df["exit_time"] if "exit_time" in summary_df else pd.Series(dtype="datetime64[ns]")

    return pd.DataFrame({
        "timestamp": timeline,
        "equity": equity,
        "drawdown": drawdown,
    })


def render_metrics(summary_df: pd.DataFrame, starting_capital: float) -> None:
    total_trades = len(summary_df)
    wins = (summary_df["pnl"] > 0).sum() if not summary_df.empty else 0
    win_rate = wins / total_trades if total_trades else 0
    gross_pnl = summary_df["pnl"].sum() if "pnl" in summary_df else 0
    avg_pnl = summary_df["pnl"].mean() if not summary_df.empty else 0

    durations = pd.to_datetime(summary_df["exit_time"]) - pd.to_datetime(summary_df["entry_time"]) if not summary_df.empty else pd.Series(dtype="timedelta64[ns]")
    avg_hold = durations.mean() if not durations.empty else pd.Timedelta(0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Net P&L", f"${gross_pnl:,.2f}", f"{gross_pnl / starting_capital * 100:.1f}%")
    col2.metric("Win Rate", f"{win_rate*100:.1f}%", f"{wins}/{total_trades} wins" if total_trades else "")
    col3.metric("Average P&L", f"${avg_pnl:,.2f}")
    col4.metric("Avg Holding", str(avg_hold))


def render_trades_table(summary_df: pd.DataFrame) -> None:
    st.subheader("Completed Trades")
    if summary_df.empty:
        st.info("No trades found. Run a back-test to populate logs/trade_summary.csv.")
        return

    display_cols = [
        "symbol", "entry_time", "entry_price", "exit_time", "exit_price", "qty", "pnl",
    ]
    existing_cols = [c for c in display_cols if c in summary_df.columns]
    st.dataframe(
        summary_df[existing_cols].sort_values("exit_time").style.format({
            "entry_price": "${:,.2f}",
            "exit_price": "${:,.2f}",
            "qty": "{:,.6f}",
            "pnl": "${:,.2f}",
        }),
        use_container_width=True,
    )


def render_equity_charts(eq_df: pd.DataFrame) -> None:
    st.subheader("Equity & Drawdown")
    if eq_df.empty:
        st.info("No equity curve to display.")
        return

    eq_fig = px.line(eq_df, x="timestamp", y="equity", title="Equity Curve")
    dd_fig = px.area(eq_df, x="timestamp", y="drawdown", title="Drawdown", color_discrete_sequence=["#EF553B"])

    col1, col2 = st.columns(2)
    col1.plotly_chart(eq_fig, use_container_width=True)
    col2.plotly_chart(dd_fig, use_container_width=True)


def render_distribution(summary_df: pd.DataFrame) -> None:
    st.subheader("PnL Distribution")
    if summary_df.empty:
        st.info("No distribution to plot.")
        return

    hist = px.histogram(summary_df, x="pnl", nbins=30, title="Trade PnL Histogram")
    st.plotly_chart(hist, use_container_width=True)

    grouped = summary_df.groupby("symbol")["pnl"].sum().reset_index() if "symbol" in summary_df else pd.DataFrame()
    if not grouped.empty:
        bar = px.bar(grouped, x="symbol", y="pnl", title="PnL by Symbol")
        st.plotly_chart(bar, use_container_width=True)


def render_price_marks(ticks_df: pd.DataFrame) -> None:
    st.subheader("Entry/Exit Marks")
    if ticks_df.empty:
        st.info("No tick-level markers available.")
        return

    fig = px.scatter(
        ticks_df,
        x="timestamp",
        y="price",
        color="type",
        symbol="type",
        color_discrete_map={"entry": "#2ca02c", "exit": "#d62728"},
        title="Trade Markers",
    )
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.title("Backtesting Dashboard")
    st.markdown(
        "Use the back-test scripts to refresh `backtests/logs/trade_summary.csv` and `trade_ticks.csv`, then visualize the results here."
    )

    default_capital = st.sidebar.number_input("Starting capital", value=DEFAULT_CAPITAL, step=1_000.0, min_value=0.0)
    summary_path = Path(st.sidebar.text_input("Summary CSV", value=str(SUMMARY_CSV)))
    ticks_path = Path(st.sidebar.text_input("Ticks CSV", value=str(TICKS_CSV)))

    summary_df, ticks_df = load_trade_data(summary_path, ticks_path)

    render_metrics(summary_df, default_capital)
    render_equity_charts(equity_curve(summary_df, default_capital))

    col1, col2 = st.columns([2, 1])
    with col1:
        render_trades_table(summary_df)
    with col2:
        render_distribution(summary_df)

    render_price_marks(ticks_df)


if __name__ == "__main__":
    main()
