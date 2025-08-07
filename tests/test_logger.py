from core.logger import TradeLogger
import os

def test_logger_creates_file():
    test_path = "logs/test_log.csv"
    logger = TradeLogger(test_path)
    assert os.path.exists(test_path)