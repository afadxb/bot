import os
import krakenex
from utils.pushover import notify
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('KRAKEN_API_KEY')
API_SECRET = os.getenv('KRAKEN_API_SECRET')

class OrderManager:
    def __init__(self):
        self.api = krakenex.API()
        self.api.key = API_KEY
        self.api.secret = API_SECRET

    def place_limit_order(self, symbol: str, side: str, price: float, volume: float) -> str | None:
        pair = symbol.replace('/', '')
        order = {
            'pair': pair,
            'type': side,
            'ordertype': 'limit',
            'price': str(price),
            'volume': str(volume),
            'validate': os.getenv("KRAKEN_VALIDATE_ONLY", "false") == "true"
        }

        try:
            response = self.api.query_private('AddOrder', order)
        except Exception as e:
            notify("Order Failed", f"{symbol} {side.upper()} @ {price:.2f} FAILED\n{e}")
            print(f"[ERROR] Kraken API call failed: {e}")
            return None

        if response.get("error"):
            notify("Order Rejected", f"{symbol} {side.upper()} @ {price:.2f}\nError: {response['error']}")
            print(f"[ERROR] Kraken returned error: {response['error']}")
            return None

        txid_list = response.get("result", {}).get("txid", [])
        if not txid_list:
            notify("Order Warning", f"{symbol} {side.upper()} @ {price:.2f} submitted but no txid returned.")
            print("[WARN] No txid returned from Kraken.")
            return None

        txid = txid_list[0]
        notify("Trade Executed", f"{symbol} {side.upper()} placed @ {price:.2f} [txid: {txid}]")
        print(f"[ORDER PLACED] {symbol} {side.upper()} @ {price:.2f} [txid: {txid}]")
        return txid

    def cancel_order(self, order_txid: str) -> dict:
        return self.api.query_private('CancelOrder', {'txid': order_txid})

    def get_open_orders(self) -> dict:
        try:
            response = self.api.query_private('OpenOrders')
            return response.get("result", {}).get("open", {})
        except Exception as e:
            print(f"[ERROR] Failed to fetch open orders: {e}")
            return {}
