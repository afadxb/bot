import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv('DATABASE_URL')
engine = create_engine(DB_URL)

def get_monthly_performance():
    """
    Aggregate performance over the past month.
    Returns: dict with total_trades, win_rate, avg_return, total_pnl, avg_holding_time
    """
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    sql = text("""
        SELECT
          COUNT(*) AS total_trades,
          AVG(CASE WHEN status='closed' THEN (exit_price-entry_price)/entry_price END) AS avg_return,
          SUM(CASE WHEN status='closed' THEN exit_price-entry_price END) AS total_pnl,
          SUM(CASE WHEN status='closed' AND exit_price>entry_price THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END),0) AS win_rate,
          AVG(TIMESTAMPDIFF(SECOND, entry_time, exit_time)) AS avg_holding_secs
        FROM positions
        WHERE exit_time >= :since
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {'since': one_month_ago}).first()
    return {
        'total_trades': int(result.total_trades or 0),
        'win_rate': float(result.win_rate or 0),
        'avg_return': float(result.avg_return or 0),
        'total_pnl': float(result.total_pnl or 0),
        'avg_holding_time': timedelta(seconds=int(result.avg_holding_secs or 0))
    }
