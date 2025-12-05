from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy import (
    DECIMAL,
    Column,
    DateTime,
    Enum,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import sessionmaker

# --- File-based logger -----------------------------------------------------------


@dataclass
class TradeLogger:
    """Simple CSV trade logger.

    Creating an instance ensures the target file exists and contains a
    header row. The :meth:`log` method appends trade information.
    """

    file_path: str
    headers: tuple[str, ...] = field(
        default=("timestamp", "symbol", "side", "price", "volume"),
        init=False,
    )

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        path = Path(self.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("w", newline="") as f:
                csv.writer(f).writerow(self.headers)
        self._path = path

    def log(self, symbol: str, side: str, price: float, volume: float) -> None:
        """Append a trade entry to the log file."""
        with self._path.open("a", newline="") as f:
            csv.writer(f).writerow(
                [datetime.utcnow().isoformat(), symbol, side, price, volume]
            )


# --- Database logger -------------------------------------------------------------


class DBLogger:
    """Utility wrapper around SQLAlchemy tables and common queries."""

    def __init__(self, db_url: Optional[str] = None) -> None:
        url = db_url or os.getenv("DATABASE_URL", "sqlite:///trading.db")
        self.engine = create_engine(url)
        self.metadata = MetaData()

        # Define core tables with ``extend_existing`` to avoid conflicts if they
        # already exist in the target database.
        self.positions_table = Table(
            "positions",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("symbol", String(20), nullable=False),
            Column("entry_price", DECIMAL(18, 8), nullable=False),
            Column("entry_time", DateTime, default=datetime.utcnow),
            Column("exit_price", DECIMAL(18, 8)),
            Column("exit_time", DateTime),
            Column("volume", DECIMAL(18, 8), nullable=False),
            Column("tag", String(32)),
            Column("pnl", DECIMAL(18, 8)),
            Column("status", Enum("open", "closed"), default="open"),
            Column("trailing_stop", DECIMAL(18, 8)),
            extend_existing=True,
        )

        self.trades_table = Table(
            "trades",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("symbol", String(20), nullable=False),
            Column("side", Enum("buy", "sell"), nullable=False),
            Column("price", DECIMAL(18, 8), nullable=False),
            Column("volume", DECIMAL(18, 8), nullable=False),
            Column("tag", String(32)),
            Column("timestamp", DateTime, default=datetime.utcnow),
            Column("pnl", DECIMAL(18, 8)),
            Column("close_time", DateTime),
            extend_existing=True,
        )

        self.account_snapshots = Table(
            "account_snapshots",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("asset", String(10), nullable=False),
            Column("balance", DECIMAL(28, 8), nullable=False),
            Column("timestamp", DateTime, default=datetime.utcnow),
            extend_existing=True,
        )

        self.market_data = Table(
            "market_data",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("symbol", String(20), nullable=False),
            Column("interval", Integer, nullable=False),
            Column("timestamp", DateTime, nullable=False),
            Column("open", DECIMAL(18, 8), nullable=False),
            Column("high", DECIMAL(18, 8), nullable=False),
            Column("low", DECIMAL(18, 8), nullable=False),
            Column("close", DECIMAL(18, 8), nullable=False),
            Column("volume", DECIMAL(28, 8), nullable=False),
            Column("rsi", DECIMAL(18, 8)),
            Column("atr", DECIMAL(18, 8)),
            Column("supertrend", DECIMAL(18, 8)),
            Column("trend", Integer),
            Column("signal", String(16)),
            UniqueConstraint("symbol", "interval", "timestamp", name="uq_market_data"),
            extend_existing=True,
        )

        self.metadata.create_all(self.engine)
        # Reflect in case additional tables exist outside the ones defined
        self.metadata.reflect(bind=self.engine, extend_existing=True)

        self.Session = sessionmaker(bind=self.engine)
        self._ensure_indicator_columns()

    # --- Query helpers ---------------------------------------------------------
    def get_open_positions(self) -> list[dict[str, Any]]:
        """Return open positions as a list of mappings."""
        stmt = select(self.positions_table).where(self.positions_table.c.status == "open")
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(stmt).mappings().all()]

    def get_trade_logs(self) -> list[dict[str, Any]]:
        """Return all trades."""
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(select(self.trades_table)).mappings().all()]

    def get_monthly_performance(self) -> dict[str, Any]:
        """Compute high-level stats for the current month."""
        query = """
            SELECT COUNT(*) AS total_trades,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                   AVG(pnl) AS avg_return
            FROM trades
            WHERE timestamp >= date('now', 'start of month')
        """
        with self.engine.connect() as conn:
            performance = conn.execute(query).mappings().first()

        wins = performance.get("wins", 0) or 0
        total = performance.get("total_trades", 0) or 0
        win_rate = wins / total if total else 0
        avg_return = performance.get("avg_return", 0) or 0

        return {
            "total_trades": total,
            "win_rate": win_rate,
            "avg_return": avg_return,
            "total_pnl": sum(row.get("pnl", 0) or 0 for row in self.get_trade_logs()),
            "avg_holding_time": "N/A",
        }

    # --- Mutation helpers ------------------------------------------------------
    def open_position(self, symbol: str, entry_price: float, volume: float, tag: str = "", trailing_stop: Optional[float] = None) -> int:
        """Insert a new open position and return its ID."""
        with self.engine.begin() as conn:
            result = conn.execute(
                self.positions_table.insert().values(
                    symbol=symbol,
                    entry_price=entry_price,
                    entry_time=datetime.utcnow(),
                    volume=volume,
                    status="open",
                    tag=tag,
                    trailing_stop=trailing_stop,
                )
            )
            return int(result.inserted_primary_key[0])

    def close_position(self, position_id: int, exit_price: Optional[float]) -> None:
        """Mark a position as closed with an exit price."""
        with self.engine.begin() as conn:
            conn.execute(
                self.positions_table.update()
                .where(self.positions_table.c.id == position_id)
                .values(
                    status="closed",
                    exit_price=exit_price,
                    exit_time=datetime.utcnow(),
                )
            )

    def log_balance(self, asset: str, balance: float) -> None:
        """Record a balance snapshot."""
        with self.engine.begin() as conn:
            conn.execute(
                self.account_snapshots.insert().values(
                    asset=asset,
                    balance=balance,
                    timestamp=datetime.utcnow(),
                )
            )

    # --- Market data cache helpers -------------------------------------------
    def get_market_data(self, symbol: str, interval: int, start_time: datetime) -> pd.DataFrame:
        """Return cached OHLC rows newer than ``start_time``."""

        query = (
            select(self.market_data)
            .where(
                (self.market_data.c.symbol == symbol)
                & (self.market_data.c.interval == interval)
                & (self.market_data.c.timestamp >= start_time)
            )
            .order_by(self.market_data.c.timestamp)
        )

        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df.set_index("timestamp", inplace=True)

        # SQLAlchemy returns ``Decimal`` objects for ``DECIMAL`` columns. Cast
        # them to native floats so downstream indicator math (which mixes
        # numpy/pandas float dtypes) does not trigger ``Decimal`` type errors.
        numeric_cols = [col for col in ["open", "high", "low", "close", "volume", "rsi", "atr", "supertrend"] if col in df.columns]
        if numeric_cols:
            df[numeric_cols] = df[numeric_cols].astype(float)

        if "trend" in df.columns:
            df["trend"] = df["trend"].astype("Int64")

        ordered_cols = [col for col in [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "rsi",
            "atr",
            "supertrend",
            "trend",
            "signal",
        ] if col in df.columns]

        return df[ordered_cols].sort_index()

    def cache_market_data(self, symbol: str, interval: int, df: pd.DataFrame) -> None:
        """Persist OHLC data and prune any cache older than two years."""

        if df.empty:
            return

        cutoff = datetime.utcnow() - timedelta(days=365 * 2)
        df = df.sort_index()

        def _safe_number(value: Any) -> Any:
            if value is None:
                return None
            try:
                if pd.isna(value):
                    return None
            except TypeError:
                pass
            return float(value)

        def _safe_int(value: Any) -> Any:
            numeric = _safe_number(value)
            return int(numeric) if numeric is not None else None

        records = []
        for ts, row in df.iterrows():
            record = {
                "symbol": symbol,
                "interval": interval,
                "timestamp": ts.to_pydatetime(),
                "open": _safe_number(row.get("open")),
                "high": _safe_number(row.get("high")),
                "low": _safe_number(row.get("low")),
                "close": _safe_number(row.get("close")),
                "volume": _safe_number(row.get("volume")),
                "rsi": _safe_number(row.get("rsi")),
                "atr": _safe_number(row.get("atr")),
                "supertrend": _safe_number(row.get("supertrend")),
                "trend": _safe_int(row.get("trend")),
                "signal": row.get("signal"),
            }
            records.append(record)

        with self.engine.begin() as conn:
            conn.execute(
                self.market_data.delete().where(self.market_data.c.timestamp < cutoff)
            )

            conn.execute(
                self.market_data.delete().where(
                    (self.market_data.c.symbol == symbol)
                    & (self.market_data.c.interval == interval)
                    & (self.market_data.c.timestamp >= records[0]["timestamp"])
                    & (self.market_data.c.timestamp <= records[-1]["timestamp"])
                )
            )

            conn.execute(self.market_data.insert(), records)

    def _ensure_indicator_columns(self) -> None:
        """Add indicator columns to ``market_data`` if the table already exists."""

        inspector = inspect(self.engine)
        existing_columns = {col["name"] for col in inspector.get_columns("market_data")}

        column_defs = {
            "rsi": "REAL",
            "atr": "REAL",
            "supertrend": "REAL",
            "trend": "INTEGER",
            "signal": "TEXT",
        }

        missing_columns = [name for name in column_defs if name not in existing_columns]
        if not missing_columns:
            return

        with self.engine.begin() as conn:
            for name in missing_columns:
                conn.execute(text(f"ALTER TABLE market_data ADD COLUMN {name} {column_defs[name]}"))


# Convenience exports for modules that import the engine/table directly
_default_db_logger = DBLogger()
engine = _default_db_logger.engine
positions_table = _default_db_logger.positions_table
