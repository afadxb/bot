from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


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
