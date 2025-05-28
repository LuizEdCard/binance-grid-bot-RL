# Telegram Alerter Module

import pandas as pd  # Needed for chart generation from klines
import matplotlib.pyplot as plt
from decimal import Decimal

# from datetime import datetime # Unused import
import logging
import io
import asyncio
import os

import matplotlib
import telegram
import yaml
from dotenv import load_dotenv

matplotlib.use("Agg")  # Use Agg backend for non-interactive plotting
# Assuming logger is correctly set up in __init__.py or similar
# from ..utils.logger import log
# For now, use basic logging


log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables and configuration
# Determine paths relative to this file's location
UTILS_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.dirname(UTILS_DIR)
ROOT_DIR = os.path.dirname(SRC_DIR)
ENV_PATH = os.path.join(ROOT_DIR, ".env")
CONFIG_PATH = os.path.join(SRC_DIR, "config", "config.yaml")

load_dotenv(dotenv_path=ENV_PATH)


def load_config():
    """Loads the YAML configuration file."""
    try:
        with open(CONFIG_PATH, "r") as f:
            config_data = yaml.safe_load(f)
            if config_data is None:
                log.warning(f"Config file {CONFIG_PATH} is empty or invalid.")
                return {}
            return config_data
    except FileNotFoundError:
        log.error(f"Configuration file not found at {CONFIG_PATH}")
        return {}
    except Exception as e:
        log.error(f"Error loading configuration for Alerter: {e}")
        return {}


config = load_config()
alerts_config = config.get("alerts", {})

TELEGRAM_ENABLED = alerts_config.get("enabled", False)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Store symbol info globally or pass it around - simpler to store here for now
# This is not ideal, should be managed better in a real application
SYMBOL_INFO_CACHE = {}


def fetch_and_cache_symbol_info(api_client):
    """Fetches and caches exchange info if not already done."""
    # global SYMBOL_INFO_CACHE # Removed as it's not strictly needed for modifying dict contents
    if not SYMBOL_INFO_CACHE:
        log.info("Fetching exchange info for alerter precision...")
        try:
            exchange_info = api_client.get_exchange_info()
            if exchange_info and "symbols" in exchange_info:
                for item in exchange_info["symbols"]:
                    SYMBOL_INFO_CACHE[item["symbol"]] = item
                log.info(f"Cached info for {len(SYMBOL_INFO_CACHE)} symbols.")
            else:
                log.error("Failed to fetch valid exchange info for alerter.")
        except Exception as e:
            log.error(f"Error fetching exchange info for alerter: {e}")


class Alerter:
    """Handles sending alerts and messages via Telegram."""

    def __init__(self, api_client=None):
        self.bot = None
        self.api_client = api_client  # Needed for precision info
        if TELEGRAM_ENABLED:
            if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
                log.error(
                    "Telegram alerts enabled, but TOKEN or CHAT_ID not found in .env. Disabling Telegram."
                )
                self.enabled = False
            else:
                try:
                    self.bot = telegram.Bot(token=TELEGRAM_TOKEN)
                    log.info(f"Telegram bot initialized. Chat ID: {TELEGRAM_CHAT_ID}")
                    self.enabled = True
                    if self.api_client:
                        # Fetch info immediately if client provided
                        fetch_and_cache_symbol_info(self.api_client)
                except Exception as e:
                    log.error(f"Failed to initialize Telegram bot: {e}")
                    self.enabled = False
        else:
            self.enabled = False
            log.info("Telegram alerts are disabled in config.")

    def _get_symbol_precision(self, symbol: str, precision_type: str):
        """Gets price or quantity precision for a symbol from cache."""
        # Ensure cache is populated if api_client exists but cache is empty
        if not SYMBOL_INFO_CACHE and self.api_client:
            fetch_and_cache_symbol_info(self.api_client)

        if symbol in SYMBOL_INFO_CACHE:
            info = SYMBOL_INFO_CACHE[symbol]
            if precision_type == "price":
                return info.get("pricePrecision")
            elif precision_type == "quantity":
                return info.get("quantityPrecision")
        log.warning(
            f"Precision info for {symbol} not found in cache. Using default precision 8."
        )
        return 8

    def get_price_precision(self, symbol: str) -> int:
        return self._get_symbol_precision(symbol, "price")

    def get_qty_precision(self, symbol: str) -> int:
        return self._get_symbol_precision(symbol, "quantity")

    async def send_message_async(
        self, text: str, parse_mode="MarkdownV2", photo: bytes = None
    ):
        """Asynchronously sends a message (text and optional photo) to the configured Telegram chat."""
        if not self.enabled or not self.bot:
            log.debug(
                f"Telegram disabled or not initialized. Message not sent: {text[:50]}..."
            )
            return False
        try:
            if photo:
                await self.bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=photo,
                    caption=text,
                    parse_mode=parse_mode,
                )
                log.info(f"Sent Telegram photo message to {TELEGRAM_CHAT_ID}.")
            else:
                await self.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode=parse_mode
                )
                log.info(f"Sent Telegram text message to {TELEGRAM_CHAT_ID}.")
            return True
        except telegram.error.BadRequest as e:
            log.error(f"Telegram BadRequest Error: {e}. Message: {text}")
            if parse_mode == "MarkdownV2":
                log.warning("Retrying Telegram message with default parse mode.")
                try:
                    if photo:
                        await self.bot.send_photo(
                            chat_id=TELEGRAM_CHAT_ID, photo=photo, caption=text
                        )
                    else:
                        await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
                    return True
                except Exception as retry_e:
                    log.error(f"Telegram retry failed: {retry_e}")
                    return False
            return False
        except Exception as e:
            log.error(f"Failed to send Telegram message: {e}")
            return False

    def send_message(self, text: str, parse_mode="MarkdownV2", photo: bytes = None):
        """Synchronously sends a message via Telegram by running the async version."""
        if not self.enabled:
            return False
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.send_message_async(text, parse_mode, photo))
                return True
            else:
                return loop.run_until_complete(
                    self.send_message_async(text, parse_mode, photo)
                )
        except RuntimeError:
            return asyncio.run(self.send_message_async(text, parse_mode, photo))
        except Exception as e:
            log.error(f"Error running async send_message: {e}")
            return False

    def _generate_chart(
        self, klines, symbol: str, entry_price=None, tp_price=None, sl_price=None
    ):
        """Generates a simple price chart using Matplotlib from kline data."""
        if not klines or len(klines) < 2:
            log.warning(f"Not enough kline data to generate chart for {symbol}.")
            return None
        try:
            # Assuming klines format: [open_time, open, high, low, close,
            # volume, close_time, ...]
            df = pd.DataFrame(
                klines,
                columns=[
                    "Open time",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume",
                    "Close time",
                    "Quote asset volume",
                    "Number of trades",
                    "Taker buy base asset volume",
                    "Taker buy quote asset volume",
                    "Ignore",
                ],
            )
            df["Close time"] = pd.to_datetime(df["Close time"], unit="ms")
            df["Close"] = pd.to_numeric(df["Close"])

            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(df["Close time"], df["Close"], label="Close Price")

            # Add horizontal lines for entry, TP, SL if provided
            if entry_price is not None:
                ax.axhline(
                    y=float(entry_price),
                    color="blue",
                    linestyle="--",
                    linewidth=0.8,
                    label=f"Entry: {entry_price}",
                )
            if tp_price is not None:
                ax.axhline(
                    y=float(tp_price),
                    color="green",
                    linestyle="--",
                    linewidth=0.8,
                    label=f"TP: {tp_price}",
                )
            if sl_price is not None:
                ax.axhline(
                    y=float(sl_price),
                    color="red",
                    linestyle="--",
                    linewidth=0.8,
                    label=f"SL: {sl_price}",
                )

            ax.set_title(f"{symbol} Price Chart")
            ax.set_ylabel("Price")
            ax.set_xlabel("Time")
            ax.legend()
            plt.xticks(rotation=45)
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png")
            buf.seek(0)
            plt.close(fig)  # Close the figure to free memory
            log.info(f"Generated chart for {symbol}.")
            return buf.getvalue()
        except Exception as e:
            log.error(f"Error generating chart for {symbol}: {e}")
            return None

    # --- Specific Alert Types --- #

    def send_critical_alert(self, message: str):
        """Sends a high-priority critical alert message."""
        safe_message = telegram.helpers.escape_markdown(message, version=2)
        text = f"\U0001f170 **CRITICAL ALERT** \U0001f170\n\n{safe_message}"
        self.send_message(text)

    def send_trade_notification(
        self,
        symbol: str,
        side: str,
        price: Decimal,
        qty: Decimal,
        pnl: Decimal = None,
        klines_data=None,
    ):
        """Sends a notification about a filled trade, optionally with a chart."""
        side_emoji = (
            "\U0001f7e2" if side.upper() == "BUY" else "\U0001f534"
        )  # Green/Red circle
        price_precision = self.get_price_precision(symbol)
        qty_precision = self.get_qty_precision(symbol)
        price_str = f"{price:.{price_precision}f}"
        qty_str = f"{qty:.{qty_precision}f}"

        symbol_safe = telegram.helpers.escape_markdown(symbol, version=2)
        side_safe = telegram.helpers.escape_markdown(side.upper(), version=2)
        price_safe = telegram.helpers.escape_markdown(price_str, version=2)
        qty_safe = telegram.helpers.escape_markdown(qty_str, version=2)

        text = f"{side_emoji} *Trade Filled* {side_emoji}\n\n`{symbol_safe}`\n*Side:* {side_safe}\n*Price:* {price_safe}\n*Quantity:* {qty_safe}"

        if pnl is not None:
            pnl_str = f"{pnl:.4f}"
            pnl_safe = telegram.helpers.escape_markdown(pnl_str, version=2)
            # Money bag / Chart decreasing
            pnl_emoji = "\U0001f4b0" if pnl >= 0 else "\U0001f4c9"
            text += f"\n*Realized PNL:* {pnl_safe} USDT {pnl_emoji}"

        photo_bytes = None
        if klines_data:
            photo_bytes = self._generate_chart(klines_data, symbol, entry_price=price)

        self.send_message(text, photo=photo_bytes)

    def send_trend_recommendation(
        self,
        symbol: str,
        direction: str,
        entry_price: Decimal,
        tp_price: Decimal,
        sl_price: Decimal,
        confidence: float = None,
        klines_data=None,
    ):
        """Sends a recommendation for a Long/Short entry based on trend analysis."""
        direction_upper = direction.upper()
        if direction_upper not in ["LONG", "SHORT"]:
            log.error(f"Invalid direction for trend recommendation: {direction}")
            return

        # Arrow up-right / down-right
        arrow = "\U00002197" if direction_upper == "LONG" else "\U00002198"
        price_precision = self.get_price_precision(symbol)

        symbol_safe = telegram.helpers.escape_markdown(symbol, version=2)
        direction_safe = telegram.helpers.escape_markdown(direction_upper, version=2)
        entry_safe = telegram.helpers.escape_markdown(
            f"{entry_price:.{price_precision}f}", version=2
        )
        tp_safe = telegram.helpers.escape_markdown(
            f"{tp_price:.{price_precision}f}", version=2
        )
        sl_safe = telegram.helpers.escape_markdown(
            f"{sl_price:.{price_precision}f}", version=2
        )

        text = f"{arrow} *Trend Recommendation* {arrow}\n\n`{symbol_safe}`\n*Direction:* {direction_safe}\n*Entry Suggestion:* ~{entry_safe}\n*Take Profit:* {tp_safe}\n*Stop Loss:* {sl_safe}"

        if confidence is not None:
            conf_str = f"{confidence*100:.1f}%"
            conf_safe = telegram.helpers.escape_markdown(conf_str, version=2)
            text += f"\n*Confidence:* {conf_safe}"

        text += "\n\n_Disclaimer: This is an automated suggestion, not financial advice. Trade responsibly._"

        photo_bytes = None
        if klines_data:
            # Generate chart with entry, TP, SL lines
            photo_bytes = self._generate_chart(
                klines_data, symbol, entry_price, tp_price, sl_price
            )

        self.send_message(text, photo=photo_bytes)


# Example Usage (requires valid .env and config)
# if __name__ == '__main__':
#     # Need a mock API client or real one
#     # from ..utils.api_client import APIClient
#     # mock_api = APIClient() # Replace with actual or mock
#     alerter = Alerter(api_client=None) # Pass API client if needed for precision
#     if alerter.enabled:
#         print('Alerter enabled. Sending test messages...')
#         # Test basic message
#         # alerter.send_message('Hello from the Bot!')
#         # Test critical alert
#         # alerter.send_critical_alert('Something went wrong! Need attention.')
#         # Test trade notification (requires klines data for chart)
#         # alerter.send_trade_notification('BTCUSDT', 'BUY', Decimal('40000.50'), Decimal('0.001'), pnl=Decimal('5.25'))
#         # Test trend recommendation (requires klines data for chart)
#         # alerter.send_trend_recommendation('ETHUSDT', 'LONG', Decimal('3000'), Decimal('3150'), Decimal('2950'), confidence=0.75)
#         pass
#     else:
#         print('Alerter is disabled or failed to initialize.')
