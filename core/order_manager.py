from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class OrderManager:
    """Minimal order manager used for unit tests.

    The real project integrates with the Kraken API, but the tests only need a
    lightweight object that stores the provided configuration and exposes a
    ``place_limit_order`` method. The configuration is optional so production
    scripts can instantiate the manager without parameters.
    """

    config: Dict[str, Any] | None = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        self.config = self.config or {}
        self.last_order: Dict[str, Any] | None = None

    def place_limit_order(self, symbol: str, side: str, price: float, volume: float) -> Dict[str, Any]:
        """Record the details of a limit order and return them.

        In the production code this would send the order to an exchange; here
        we simply capture the parameters for verification.
        """
        self.last_order = {
            "symbol": symbol,
            "side": side,
            "price": price,
            "volume": volume,
        }
        return self.last_order
