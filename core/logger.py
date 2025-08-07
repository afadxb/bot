# core/logger.py
import os
from datetime import datetime, timedelta
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, DECIMAL,
    DateTime, Enum, select, func, inspect
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:pass@localhost/bot")

# ------------------------------------------------------------------------------
# helper for decimal precision: 18 total digits, 8 after decimal
DEC = lambda: DECIMAL(18, 8)

STATUS_ENUM = Enum("open", "closed", name="status_enum")

metadata = MetaData()

positions_table = Table(
    "positions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", String(15), nullable=False),
    Column("entry_price", DEC(), nullable=False),
    Column("volume",      DEC(), nullable=False),
    Column("status",      STATUS_ENUM, nullable=False, default="open"),
    Column("tag",         String(30)),
    Column("entry_time",  DateTime, nullable=False, default=datetime.utcnow),
    Column("exit_price",  DEC()),
    Column("exit_time",   DateTime),
    Column("pnl",         DEC()),
    Column("kraken_txid", String(64), nullable=True),
    mysql_engine="InnoDB",
)

trades_table = Table(
    "trades",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", String(15), nullable=False),
    Column("entry_price", DEC(), nullable=False),
    Column("exit_price",  DEC(), nullable=False),
    Column("pnl",         DEC(), nullable=False),
    Column("volume",      DEC(), nullable=False),
    Column("timestamp",   DateTime, nullable=False, default=datetime.utcnow),
    Column("tag",         String(30)),
    mysql_engine="InnoDB",
)

class DBLogger:
    """Lightweight wrapper around SQLAlchemy insert/select helpers."""

    def __init__(self, url: str = DB_URL):
        self.engine: Engine = create_engine(url, pool_pre_ping=True, future=True)
        self.metadata = metadata
        self._ensure_schema()

    # ------------------------------------------------------------------ schema
    def _ensure_schema(self):
        insp = inspect(self.engine)
        missing = [t for t in ("positions", "trades") if t not in insp.get_table_names()]
        if missing:
            print(f"[DBLogger] creating tables: {', '.join(missing)}")
            self.metadata.create_all(self.engine)

    # ---------------------------------------------------------------- positions
    def open_position(self, symbol: str, entry_price: float, volume: float, tag: str = "", kraken_txid: str = None) -> int:
        with self.engine.begin() as conn:
            res = conn.execute(
                positions_table.insert().values(
                    symbol=symbol,
                    entry_price=Decimal(str(entry_price)),
                    volume=Decimal(str(volume)),
                    status="open",
                    tag=tag,
                    entry_time=datetime.utcnow(),
                    kraken_txid=kraken_txid,
                )
            )
            return res.inserted_primary_key[0]

    def close_position(self, position_id: int, exit_price: float):
        with self.engine.begin() as conn:
            # pull current row to compute PnL
            row = conn.execute(
                select(
                    positions_table.c.entry_price,
                    positions_table.c.volume
                ).where(positions_table.c.id == position_id)
            ).fetchone()

            if not row:
                raise ValueError(f"position id {position_id} not found")

            entry_price, volume = row
            if exit_price is None:
                exit_price = entry_price  # or Decimal("0.0")
            pnl = (Decimal(str(exit_price)) - entry_price) * volume

            conn.execute(
                positions_table.update()
                .where(positions_table.c.id == position_id)
                .values(
                    status="closed",
                    exit_price=Decimal(str(exit_price)),
                    exit_time=datetime.utcnow(),
                    pnl=pnl,
                )
            )

            # log a trade row
            conn.execute(
                trades_table.insert().values(
                    symbol=conn.execute(
                        select(positions_table.c.symbol).where(positions_table.c.id == position_id)
                    ).scalar_one(),
                    entry_price=entry_price,
                    exit_price=Decimal(str(exit_price)),
                    pnl=pnl,
                    volume=volume,
                    timestamp=datetime.utcnow(),
                    tag=conn.execute(
                        select(positions_table.c.tag).where(positions_table.c.id == position_id)
                    ).scalar_one(),
                )
            )

    # ----------------------------------------------------------- read helpers
    def get_positions(self, include_closed: bool = True):
        stmt = select(positions_table)
        if not include_closed:
            stmt = stmt.where(positions_table.c.status == "open")
        with self.engine.begin() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings()]

    def get_trade_logs(self):
        with self.engine.begin() as conn:
            return [dict(r) for r in conn.execute(select(trades_table)).mappings()]

    def get_monthly_performance(self):
        start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        with self.engine.begin() as conn:
            total_trades = conn.execute(
                select(func.count()).select_from(trades_table).where(trades_table.c.timestamp >= start)
            ).scalar_one()
            wins = conn.execute(
                select(func.count()).select_from(trades_table)
                .where(trades_table.c.timestamp >= start, trades_table.c.pnl > 0)
            ).scalar_one()
            total_pnl = conn.execute(
                select(func.sum(trades_table.c.pnl)).where(trades_table.c.timestamp >= start)
            ).scalar()
            avg_return = total_pnl / total_trades if total_trades else Decimal(0)
            return {
                "total_trades": total_trades,
                "win_rate": wins / total_trades if total_trades else 0,
                "total_pnl": float(total_pnl or 0),
                "avg_return": float(avg_return),
                "avg_holding_time": "n/a",  # placeholder if you later track holding time
            }

    # ---------------------------------------------------- optional signal feed
    def get_signals(self, limit: int = 20):
        # adjust to your own signal storage; here we just echo recent trades for demo
        stmt = (
            select(trades_table)
            .order_by(trades_table.c.timestamp.desc())
            .limit(limit)
        )
        with self.engine.begin() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings()]


    def get_open_positions(self):
        """Returns only open positions as a list of dicts."""
        stmt = select(positions_table).where(positions_table.c.status == "open")
        with self.engine.begin() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings()]

# --- keep everything above as-is --------------------------------------------

# expose shared metadata objects for callers that still import them directly
engine = create_engine(DB_URL, pool_pre_ping=True, future=True)
metadata.create_all(engine, tables=[positions_table, trades_table])


# quick self-test
if __name__ == "__main__":
    logger = DBLogger()
    print("existing open positions:", logger.get_positions(include_closed=False))
