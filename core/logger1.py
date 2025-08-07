import os
from datetime import datetime
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String,
    DECIMAL, DateTime, Enum
)
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv('DATABASE_URL')
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)
metadata = MetaData()

# trades table
trades_table = Table(
    'trades', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('symbol', String(20), nullable=False),
    Column('side', Enum('buy','sell'), nullable=False),
    Column('price', DECIMAL(18,8), nullable=False),
    Column('volume', DECIMAL(18,8), nullable=False),
    Column('tag', String(32)),
    Column('timestamp', DateTime, default=datetime.utcnow)
)

# positions table
positions_table = Table(
    'positions', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('symbol', String(20), nullable=False),
    Column('entry_price', DECIMAL(18,8), nullable=False),
    Column('entry_time', DateTime, default=datetime.utcnow),
    Column('exit_price', DECIMAL(18,8)),
    Column('exit_time', DateTime),
    Column('volume', DECIMAL(18,8), nullable=False),
    Column('tag', String(32)),
    Column('pnl', DECIMAL(18,8)),
    Column('status', Enum('open','closed'), default='open')
)

# new: account_snapshots table
account_snapshots = Table(
    'account_snapshots', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('asset', String(10), nullable=False),
    Column('balance', DECIMAL(28,8), nullable=False),
    Column('timestamp', DateTime, default=datetime.utcnow)
)

# create all tables if not exist
metadata.create_all(engine)

class DBLogger:
    def __init__(self):
        self.engine = create_engine("sqlite:///trading.db")  # Change this to your DB setup
        self.metadata = MetaData()
        self.positions_table = Table("positions", self.metadata, autoload_with=self.engine)
        self.trades_table = Table("trades", self.metadata, autoload_with=self.engine)

    def get_positions(self):
        """Fetch all open positions from the DB."""
        with self.engine.connect() as conn:
            result = conn.execute(self.positions_table.select().where(self.positions_table.c.status == "open"))
            positions = result.fetchall()
        return positions

    def get_trade_logs(self):
        """Fetch trade logs from the DB."""
        with self.engine.connect() as conn:
            result = conn.execute(self.trades_table.select())
            trades = result.fetchall()
        return trades

    def get_monthly_performance(self):
        """Fetch the performance of the bot over the last month."""
        # Example query to get monthly performance stats
        with self.engine.connect() as conn:
            query = """
                SELECT COUNT(*) AS total_trades, 
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                       AVG(pnl) AS avg_return
                FROM trades
                WHERE timestamp >= date('now', 'start of month')
            """
            result = conn.execute(query)
            performance = result.fetchone()
        
        # Calculate win rate
        win_rate = performance['wins'] / performance['total_trades'] if performance['total_trades'] else 0
        
        # Build and return performance data
        return {
            "total_trades": performance['total_trades'],
            "win_rate": win_rate,
            "avg_return": performance['avg_return'],
            "total_pnl": sum([row['pnl'] for row in self.get_trade_logs()]),
            "avg_holding_time": "N/A"  # This would be calculated if needed
        }

    def open_position(self, symbol, entry_price, volume, tag=""):
        """Open a position in the database."""
        with self.engine.connect() as conn:
            insert_query = self.positions_table.insert().values(
                symbol=symbol,
                entry_price=entry_price,
                volume=volume,
                status="open",
                tag=tag,
                timestamp=datetime.utcnow()
            )
            conn.execute(insert_query)
        return symbol  # Return the symbol or other identifier

    def close_position(self, position_id, exit_price):
        """Close a position in the database."""
        with self.engine.connect() as conn:
            update_query = self.positions_table.update().where(
                self.positions_table.c.id == position_id
            ).values(
                status="closed",
                exit_price=exit_price,
                timestamp=datetime.utcnow()
            )
            conn.execute(update_query)

    def log_balance(self, asset: str, balance: float):
        """
        Record the given asset balance into account_snapshots.
        """
        ins = account_snapshots.insert().values(
            asset=asset,
            balance=balance,
            timestamp=datetime.utcnow()
        )
        self.session.execute(ins)
        self.session.commit()

# alias for tests
TradeLogger = DBLogger
