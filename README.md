# Crypto Trading Bot & Sentiment Suite

This repository combines an automated Kraken trading loop with a supporting
sentiment-analysis pipeline and dashboards. The trading bot ingests Kraken OHLC
candles, enriches them with indicators, gates entries and exits using a Fear &
Greed overlay, and logs all decisions. A separate sentiment module aggregates
funding rates, positioning, and social data, and exposes a Streamlit dashboard
backed by MySQL for visualization.

## Features
- **Exchange data ingestion:** Kraken OHLC candles are fetched with built-in
  caching and basic validation before strategies run.【F:core/data_loader.py†L7-L85】
- **Technical indicators:** Utility helpers calculate RSI and ATR and assemble
  a minimal signal frame suitable for unit tests or prototyping.【F:core/strategy.py†L6-L47】
- **Automated trading loop:** The main entrypoint coordinates configuration,
  position sync, Fear & Greed scoring, signal evaluation, and order placement
  with retry/backoff handling.【F:main.py†L25-L274】
- **Order and trade logging:** A lightweight order manager captures limit order
  requests for verification, and a CSV trade logger ensures trades are appended
  with timestamps.【F:core/order_manager.py†L7-L33】【F:core/logger.py†L9-L36】
- **Sentiment collectors:** Binance funding/positioning, Twitter keyword counts,
  and Reddit sentiment are polled with caching and retries to build emotional
  factors for the trading overlay.【F:sentiment/core/social_fetcher.py†L11-L159】
- **Dashboards:** Streamlit UI renders MySQL-backed Fear & Greed scores with
  auto-refreshing tables, metrics, and line charts for recent sentiment
  history.【F:sentiment/dashboard.py†L10-L78】

## Repository layout
- `main.py`: Orchestrates trading cycles, account syncing, and monthly reports.
- `core/`: Data loaders, indicator utilities, order manager, logging helpers,
  and reporting utilities.
- `sentiment/`: Data collectors, scoring logic, and Streamlit dashboard for the
  sentiment pipeline.
- `tests/`: Lightweight unit tests covering strategy helpers, order manager,
  and logging setup.

## Getting started
1. **Set up Python** – create and activate a virtual environment (Python 3.10+
   recommended).
2. **Install dependencies** – run `pip install -r requirements.txt` to install
   trading, sentiment, and dashboard dependencies.【F:requirements.txt†L1-L12】
3. **Create a `.env` file** – populate the environment variables shown below to
   configure the trading bot, API credentials, and databases.

## Configuration
### Trading bot
- `KRAKEN_API_KEY` / `KRAKEN_API_SECRET`: API credentials for Kraken access.【F:main.py†L51-L55】
- `SYMBOLS`: Comma-separated trading pairs (e.g., `BTC/USD,ETH/USD`).【F:main.py†L28-L35】
- Risk and signal tuning parameters: `FEE_RATE`, `ENTRY_BUFFER`,
  `ATR_MULTIPLIER`, `RSI_EXIT_THRESHOLD`, `MIN_FG_SCORE_FOR_ENTRY`,
  `DANGER_FG_SCORE_FOR_EXIT`.【F:main.py†L28-L34】
- `BOT_MODE`: `dev`, `test` (dry-run), or `prod` to toggle logging and order
  side effects.【F:main.py†L35-L37】

### Sentiment and notifications
- Social data keys: `TWITTER_BEARER_TOKEN`, `REDDIT_CLIENT_ID`,
  `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` for social sentiment collection.【F:sentiment/core/social_fetcher.py†L13-L140】
- MySQL settings for dashboards: `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`,
  `MYSQL_DB` for the Streamlit sentiment viewer.【F:sentiment/dashboard.py†L10-L35】
- Optional Pushover notification tokens can be added for alerts (see
  `utils/pushover.py`).

## Running the trading bot
1. Ensure `.env` is populated and valid Kraken credentials are available.
2. Run a trading cycle:
   ```bash
   python main.py
   ```
   The script loads any open positions, syncs Kraken orders into the local
   store, evaluates signals for configured symbols, and places limit orders (or
   simulates them when `BOT_MODE=test`).【F:main.py†L81-L313】
3. Generate a monthly performance notification without trading:
   ```bash
   python main.py --report
   ```
   This aggregates trade outcomes over the past month and emits a summary
   message.【F:main.py†L276-L305】

## Entry and exit conditions
The trading loop keeps position management simple and transparent:
- **Emotion-driven forced exit:** Any open position is closed immediately when
  the Fear & Greed score drops below `DANGER_FG_SCORE_FOR_EXIT`, regardless of
  technical signals. The bot submits a sell (or logs it in dry-run mode), marks
  the database position as closed, and sends a notification.【F:main.py†L200-L213】
- **Normal exit:** When the strategy produces a `sell` signal while a position
  is open, the bot submits a sell at the current price (or logs it in dry-run),
  records the closure, and removes the in-memory position handle.【F:main.py†L216-L230】
- **Entry on trend flip:** New positions are only opened on a `buy` signal **and**
  a Supertrend flip from bearish to bullish (`trend` value moving from -1 to 1).
  The entry limit is buffered above the latest close by `ENTRY_BUFFER * ATR`
  (rounded to two decimals), capital availability is checked, and a notification
  fires once the order is placed and stored in the DB.【F:main.py†L232-L262】

## Running the sentiment dashboard
Launch the Streamlit dashboard to explore recent Fear & Greed scores stored in
MySQL:
```bash
streamlit run sentiment/dashboard.py
```
The app will load the latest scores for the past 24 hours, highlight top coins,
and plot time-series trends.【F:sentiment/dashboard.py†L10-L78】

## Testing
Run the unit test suite with `pytest`:
```bash
pytest
```
The tests cover indicator helpers, the in-memory order manager, and creation of
CSV trade logs.【F:tests/test_strategy.py†L1-L18】【F:tests/test_order_manager.py†L1-L8】【F:tests/test_logger.py†L1-L7】

## Notes
- Data fetching and API calls rely on external services (Kraken, Binance,
  Twitter, Reddit); provide valid credentials and expect network-dependent
  latency or rate limits.【F:core/data_loader.py†L7-L85】【F:sentiment/core/social_fetcher.py†L11-L159】
- The repository contains additional experimental scripts (e.g.,
  `backtest.py`, `dashboard.py`, `Top_Gainers.py`) that can serve as starting
  points for further automation or visualization.
