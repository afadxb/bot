#!/usr/bin/env python3
import pandas as pd
import os
import sys
import time
import logging
import argparse
from datetime import datetime
from functools import wraps

import krakenex
from dotenv import load_dotenv

from core.data_loader import fetch_ohlc
from core.strategy import add_indicators, generate_signal
from core.order_manager import OrderManager
from core.logger import DBLogger, engine, positions_table
from core.report import get_monthly_performance
from utils.pushover import notify

from sentiment.core.scorer import get_fear_greed_score
from sentiment.core.emotion_logger import log_emotional_snapshot
from sentiment.core.social_fetcher import fetch_all_emotional_factors

# --- LOAD CONFIG -----------------------------------------------------------------
load_dotenv()

SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "").split(",") if s.strip()]
FEE_RATE = float(os.getenv("FEE_RATE", 0.005))
ENTRY_BUFFER = float(os.getenv("ENTRY_BUFFER", 0.001))
ATR_MULTIPLIER = float(os.getenv("ATR_MULTIPLIER", 1.6))
RSI_EXIT_THRESHOLD = float(os.getenv("RSI_EXIT_THRESHOLD", 80))
MIN_FG_SCORE_FOR_ENTRY = int(os.getenv("MIN_FG_SCORE_FOR_ENTRY", 30))
DANGER_FG_SCORE_FOR_EXIT = int(os.environ.get("DANGER_FG_SCORE_FOR_EXIT", 15))
BOT_MODE = os.getenv("BOT_MODE", "dev").lower()
DRY_RUN = BOT_MODE == "test"
DEBUG_MODE = BOT_MODE in ("dev", "test")

# --- LOGGING -----------------------------------------------------------------------
log_level = logging.DEBUG if DEBUG_MODE else logging.WARNING
logging.basicConfig(
    stream=sys.stdout,
    level=log_level,
    format="[%(asctime)s.%(msecs)06d] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

print(f"\n=== Kraken Bot STARTING in {BOT_MODE.upper()} mode ===\n")

# --- CLIENTS & MANAGERS -----------------------------------------------------------
api = krakenex.API()
api.key = os.getenv("KRAKEN_API_KEY")
api.secret = os.getenv("KRAKEN_API_SECRET")
order_mgr = OrderManager()
db_logger = DBLogger()

engine = db_logger.engine
positions_table = db_logger.metadata.tables["positions"]

open_positions = {}
last_trends = {}

# --- RETRY DECORATOR --------------------------------------------------------------
def retry(max_retries=3, backoff=5):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            delay = backoff
            for attempt in range(1, max_retries+1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"{fn.__name__} failed ({attempt}/{max_retries}): {e}")
                    if attempt == max_retries:
                        raise
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return deco

# --- SYNCHRONIZATION --------------------------------------------------------------
def sync_open_positions():
    """Load all open positions from DB into memory."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                positions_table.select().where(positions_table.c.status == "open")
            ).mappings().all()
        for r in rows:
            open_positions[r["symbol"]] = {
                "id": r["id"],
                "entry_price": float(r["entry_price"]),
                "volume": float(r["volume"]),
                "trailing_stop": float(r["entry_price"])
            }
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}] Synced {len(open_positions)} open positions")
    except Exception as e:
        logger.error(f"Failed to sync open positions: {e}")

def sync_account_state():
    """Mirror Kraken open buy orders into DB and in-memory."""
    try:
        resp = api.query_private("OpenOrders")
        opens = resp.get("result", {}).get("open", {})
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}] Kraken has {len(opens)} open orders")
        for txid, order in opens.items():
            d = order["descr"]
            pair = d["pair"]
            side = d["type"]
            price = float(d["price"])
            vol = float(order.get("vol", 0))
            if side == "buy" and pair not in open_positions:
                pos_id = db_logger.open_position(pair, price, vol, tag=os.getenv("TRADE_TAG", "swing"))
                open_positions[pair] = {
                    "id": pos_id,
                    "entry_price": price,
                    "volume": vol,
                    "trailing_stop": price
                }
                logger.info(f"Synced BUY {pair} @ {price:.2f}, vol={vol:.6f}")
        bal = api.query_private("Balance").get("result", {})
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}] Account Balances:")
        for asset, amt in bal.items():
            print(f"{asset}: {float(amt):.6f}")
    except Exception as e:
        logger.error(f"Failed to sync account state: {e}")

# --- HELPER ------------------------------------------------------------------------
def get_available_capital(symbol: str, price: float) -> float:
    try:
        resp = api.query_private("Balance")
        quote = symbol.split("/")[-1]
        asset = ("Z" + quote) if len(quote) == 3 else quote
        bal = float(resp["result"].get(asset, 0))
        usable = bal * (1 - FEE_RATE)
        logger.debug(f"Balance {symbol}: {bal:.6f}, usable {usable:.6f}")
        return usable / price if price > 0 else 0
    except Exception as e:
        logger.error(f"Failed to get available capital for {symbol}: {e}")
        return 0

# --- MAIN TRADING CYCLE ------------------------------------------------------------
@retry(max_retries=3, backoff=5)
def execute_trading_cycle():
    try:
        fear_greed_score = get_fear_greed_score()
        emotionals = fetch_all_emotional_factors()
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')}] Fear & Greed Score: {fear_greed_score:.2f}")

        log_emotional_snapshot(
            timestamp=datetime.utcnow(),
            funding_rate=emotionals['funding_rate'],
            long_short_ratio=emotionals['long_short_ratio'],
            taker_volume_ratio=emotionals['taker_volume_ratio'],
            fg_score=fear_greed_score
        )

        # --- Remove Phantom Positions ---
        balances = api.query_private("Balance").get("result", {})
        positions = db_logger.get_open_positions()
        for pos in positions:
            base = pos["symbol"].split("/")[0]
            kraken_asset = "X" + base if base in ["BTC", "ETH", "XRP", "LTC"] else base
            bal = float(balances.get(kraken_asset, 0))
            if bal < 0.00001:
                logger.info(f"Removing phantom position: {pos['symbol']} (no balance in Kraken)")
                db_logger.close_position(pos["id"], exit_price=None)
        open_positions.clear()
        sync_open_positions()

        any_action = False

        for symbol in SYMBOLS:
            now = datetime.utcnow()
            trend_val = None
            try:
                df4 = fetch_ohlc(symbol, interval=240, lookback=60)
                if df4.empty:
                    logger.warning(f"No data for {symbol}")
                    continue

                df4_ind = add_indicators(df4)
                if df4_ind.empty:
                    logger.warning(f"Indicator calculation failed for {symbol}")
                    continue

                last4 = df4_ind.iloc[-1]
                price = last4.get("close", 0.0)
                rsi = last4.get("rsi", float("nan"))
                supertrend_val = last4.get("supertrend", float("nan"))
                trend_val = last4.get("trend", 0)
                atr = last4.get("atr", 0.0)
                trend4 = "Bullish" if trend_val == 1 else "Bearish"

                prev_trend = last_trends.get(
                    symbol,
                    df4_ind["trend"].iloc[-2] if len(df4_ind) > 1 else trend_val,
                )

                signal = generate_signal(df4_ind, fear_greed_score)
                rsi_print = f"{rsi:.2f}" if pd.notna(rsi) else "NaN"
                st_print = f"{supertrend_val:.2f}" if pd.notna(supertrend_val) else "NaN"

                print(f"[{now.strftime('%Y-%m-%d %H:%M:%S.%f')}] {symbol}  ?  Close: {price:.2f} | Supertrend: {st_print} | Trend: {trend4} | RSI: {rsi_print} | Signal: {signal or 'None'}")

                # --- Forced SELL (emotion crash override)
                if symbol in open_positions and fear_greed_score < DANGER_FG_SCORE_FOR_EXIT:
                    info = open_positions[symbol]
                    exit_price = price
                    vol = info["volume"]
                    if DRY_RUN:
                        logger.info(f"[DRY-RUN] FORCE EXIT {symbol} @ {exit_price:.2f}")
                    else:
                        order_mgr.place_limit_order(symbol, "sell", exit_price, vol)
                    db_logger.close_position(info["id"], exit_price)
                    if not DRY_RUN:
                        notify("Force Exit (FG Crash)", f"{symbol} @ {exit_price:.2f}")
                    open_positions.pop(symbol)
                    any_action = True
                    continue

                # --- Normal SELL
                if signal == "sell" and symbol in open_positions:
                    info = open_positions[symbol]
                    exit_price = price
                    vol = info["volume"]
                    if DRY_RUN:
                        logger.info(f"[DRY-RUN] SELL {symbol} @ {exit_price:.2f}")
                    else:
                        order_mgr.place_limit_order(symbol, "sell", exit_price, vol)
                    db_logger.close_position(info["id"], exit_price)
                    if not DRY_RUN:
                        notify("Trade Closed", f"{symbol} @ {exit_price:.2f}")
                    open_positions.pop(symbol)
                    any_action = True
                    continue

                # --- BUY Entry (on Supertrend flip only) ---
                if signal == "buy" and symbol not in open_positions:
                    curr_trend = trend_val
                    just_flipped = (prev_trend == -1 and curr_trend == 1)

                    if just_flipped:
                        entry_price = round(price + (ENTRY_BUFFER * atr),2)
                        # Fix: Round to 2 decimal places for ETH/USD
                        limit_price = round(current_price + 0.5 * atr, 2)
                        volume = get_available_capital(symbol, entry_price)
                        if volume <= 0:
                            logger.warning(f"Insufficient capital for {symbol}")
                            continue

                        if DRY_RUN:
                            logger.info(f"[DRY-RUN] BUY {symbol} (Flip) @ {entry_price:.2f}, vol={volume:.6f}")
                        else:
                            order_mgr.place_limit_order(symbol, "buy", entry_price, volume)

                        pos_id = db_logger.open_position(symbol, entry_price, volume, tag=os.getenv("TRADE_TAG", "supertrend"))
                        open_positions[symbol] = {
                            "id": pos_id,
                            "entry_price": entry_price,
                            "volume": volume,
                            "trailing_stop": entry_price
                        }
                        if not DRY_RUN:
                            notify("Trade Executed (Flip Entry)", f"{symbol} @ {entry_price:.2f}")
                        any_action = True
                    else:
                        print(f"[{symbol}] Skipped buy - trend did not flip.")
            except Exception as e:
                logger.error(f"Trading cycle failed for {symbol}: {e}")
            finally:
                if "trend_val" in locals():
                    last_trends[symbol] = trend_val

        if not any_action:
            logger.info("No trading actions taken in this cycle.")

    except Exception as e:
        logger.error(f"Trading cycle failed: {e}")
        if not DRY_RUN:
            notify("Bot Crash", "See logs for details")
        raise

# --- MONTHLY REPORT ----------------------------------------------------------------
def run_monthly_report():
    try:
        stats = get_monthly_performance()
        msg = (
            f"Total Trades: {stats['total_trades']}\n"
            f"Win Rate: {stats['win_rate']:.2%}\n"
            f"Avg Return: {stats['avg_return']:.2%}\n"
            f"Total PnL: {stats['total_pnl']:.2f}\n"
            f"Avg Hold: {stats['avg_holding_time']}"
        )
        if DRY_RUN:
            logger.info(f"[DRY-RUN] Monthly Report:\n{msg}")
        else:
            notify("Monthly Report", msg)
    except Exception as e:
        logger.error(f"Monthly report failed: {e}")

# --- ENTRY POINT ------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true", help="Run monthly report only")
    args = parser.parse_args()

    sync_open_positions()
    sync_account_state()

    if args.report:
        run_monthly_report()
        sys.exit(0)

    try:
        execute_trading_cycle()
    except Exception:
        logger.exception("Trading cycle error")
        if not DRY_RUN:
            notify("Bot Crash", "See logs for details")
        sys.exit(1)