# Telegram Alerter Module

import pandas as pd  # Needed for chart generation from klines
from decimal import Decimal

# from datetime import datetime # Unused import
import logging
import io
import asyncio
import os

# Optional matplotlib import for plotting
try:
    import matplotlib
    import matplotlib.pyplot as plt
    matplotlib.use("Agg")  # Use Agg backend for non-interactive plotting
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None

import telegram
import yaml
from dotenv import load_dotenv
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
ENV_PATH = os.path.join(ROOT_DIR, "secrets", ".env")
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

TELEGRAM_ENABLED = False  # Temporariamente desabilitado para evitar erros de API
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
                log.warning(
                    "Telegram alerts enabled, but TOKEN or CHAT_ID not found in .env. Disabling Telegram."
                )
                self.enabled = False
            else:
                try:
                    # Configure telegram bot with connection pool settings
                    from telegram.ext import Application
                    import httpx
                    
                    # Create httpx client with better timeout and connection pool settings
                    http_client = httpx.AsyncClient(
                        timeout=httpx.Timeout(30.0, connect=10.0),
                        limits=httpx.Limits(max_connections=20, max_keepalive_connections=5)
                    )
                    
                    self.bot = telegram.Bot(token=TELEGRAM_TOKEN)
                    log.info(f"Telegram bot initialized with improved connection pool. Chat ID: {TELEGRAM_CHAT_ID}")
                    self.enabled = True
                    if self.api_client:
                        # Fetch info immediately if client provided
                        fetch_and_cache_symbol_info(self.api_client)
                except Exception as e:
                    log.warning(f"Failed to initialize Telegram bot: {e}")
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
    
    def escape_markdown_v2(self, text: str) -> str:
        """Escapes special characters for MarkdownV2."""
        if not text:
            return ""
        # Characters that need to be escaped in MarkdownV2
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text

    async def send_message_async(
        self, text: str, parse_mode="MarkdownV2", photo: bytes = None
    ):
        """Asynchronously sends a message (text and optional photo) to the configured Telegram chat."""
        if not self.enabled or not self.bot:
            log.debug(
                f"Telegram disabled or not initialized. Message not sent: {text[:50] if text else 'Empty'}..."
            )
            return False
            
        # Check if text is empty or None
        if not text or text.strip() == "":
            log.warning("Attempted to send empty message to Telegram. Skipping.")
            return False
            
        try:
            # If using MarkdownV2, ensure proper escaping for simple text
            if parse_mode == "MarkdownV2":
                # Always escape special characters to prevent BadRequest errors
                text = self.escape_markdown_v2(text)
            
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
            log.warning(f"Telegram BadRequest Error: {e}. Message: {text}")
            if parse_mode == "MarkdownV2":
                log.warning("Retrying Telegram message with HTML parse mode.")
                try:
                    # Convert some basic markdown to HTML
                    html_text = text.replace('\\*', '<b>').replace('\\*', '</b>').replace('\\_', '<i>').replace('\\_', '</i>')
                    html_text = html_text.replace('\\(', '(').replace('\\)', ')')
                    if photo:
                        await self.bot.send_photo(
                            chat_id=TELEGRAM_CHAT_ID, photo=photo, caption=html_text, parse_mode="HTML"
                        )
                    else:
                        await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=html_text, parse_mode="HTML")
                    return True
                except Exception as retry_e:
                    log.warning(f"Telegram HTML retry failed: {retry_e}")
                    # Final fallback - no parse mode
                    try:
                        plain_text = text.replace('\\', '').replace('*', '').replace('_', '').replace('`', '')
                        if photo:
                            await self.bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=photo, caption=plain_text)
                        else:
                            await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=plain_text)
                        return True
                    except Exception as final_e:
                        log.warning(f"Telegram final retry failed: {final_e}")
                        return False
            return False
        except Exception as e:
            log.warning(f"Failed to send Telegram message: {e}")
            return False

    def send_message(self, text: str, parse_mode="MarkdownV2", photo: bytes = None):
        """Synchronously sends a message via Telegram by running the async version."""
        if not self.enabled:
            log.debug("Telegram not enabled, skipping message")
            return False
        
        if not text or text.strip() == "":
            log.warning("Empty message, skipping")
            return False
            
        try:
            # Try to use existing event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, create a task
                    task = asyncio.create_task(self.send_message_async(text, parse_mode, photo))
                    return True
                else:
                    # If loop exists but not running, use it
                    return loop.run_until_complete(self.send_message_async(text, parse_mode, photo))
            except RuntimeError:
                # No event loop exists, create a new one
                return asyncio.run(self.send_message_async(text, parse_mode, photo))
                
        except Exception as e:
            log.warning(f"Error sending Telegram message: {e}")
            # Try simple non-async approach as fallback
            try:
                import requests
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                data = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown" if parse_mode == "MarkdownV2" else parse_mode
                }
                response = requests.post(url, data=data, timeout=10)
                if response.status_code == 200:
                    log.info("Message sent via fallback method")
                    return True
                else:
                    log.warning(f"Fallback method failed: {response.status_code}")
                    return False
            except Exception as fallback_error:
                log.warning(f"Fallback method also failed: {fallback_error}")
                return False

    def _generate_chart(
        self, klines, symbol: str, entry_price=None, tp_price=None, sl_price=None
    ):
        """Generates a professional candlestick chart with trading levels."""
        if not MATPLOTLIB_AVAILABLE:
            log.debug("Matplotlib not available, skipping chart generation")
            return None
            
        if not klines or len(klines) < 10:
            log.warning(f"Not enough kline data to generate chart for {symbol}.")
            return None
        try:
            # Prepare DataFrame from klines data
            df = pd.DataFrame(
                klines,
                columns=[
                    "Open time", "Open", "High", "Low", "Close", "Volume",
                    "Close time", "Quote asset volume", "Number of trades",
                    "Taker buy base asset volume", "Taker buy quote asset volume", "Ignore"
                ],
            )
            
            # Convert to proper data types
            df["Open time"] = pd.to_datetime(df["Open time"], unit="ms")
            df["Open"] = pd.to_numeric(df["Open"])
            df["High"] = pd.to_numeric(df["High"])
            df["Low"] = pd.to_numeric(df["Low"])
            df["Close"] = pd.to_numeric(df["Close"])
            df["Volume"] = pd.to_numeric(df["Volume"])
            
            # Take last 100 candles for better visualization
            df = df.tail(100)
            
            # Create figure with dark theme
            plt.style.use('dark_background')
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), 
                                         gridspec_kw={'height_ratios': [3, 1]}, 
                                         facecolor='#1e1e1e')
            
            # Plot candlestick chart
            for idx, row in df.iterrows():
                color = '#00ff88' if row['Close'] >= row['Open'] else '#ff4444'
                
                # Draw candlestick body
                body_height = abs(row['Close'] - row['Open'])
                body_bottom = min(row['Open'], row['Close'])
                
                ax1.bar(row['Open time'], body_height, bottom=body_bottom, 
                       color=color, alpha=0.8, width=pd.Timedelta(minutes=45))
                
                # Draw wicks
                ax1.plot([row['Open time'], row['Open time']], 
                        [row['Low'], row['High']], 
                        color=color, linewidth=1, alpha=0.7)
            
            # Add trading levels with enhanced styling
            if entry_price is not None:
                ax1.axhline(y=float(entry_price), color='#4da6ff', 
                           linestyle='-', linewidth=2, alpha=0.8,
                           label=f'Entry: ${entry_price}')
                
            if tp_price is not None:
                ax1.axhline(y=float(tp_price), color='#00ff88', 
                           linestyle='--', linewidth=2, alpha=0.8,
                           label=f'Take Profit: ${tp_price}')
                
            if sl_price is not None:
                ax1.axhline(y=float(sl_price), color='#ff4444', 
                           linestyle='--', linewidth=2, alpha=0.8,
                           label=f'Stop Loss: ${sl_price}')
            
            # Customize main chart
            ax1.set_title(f'{symbol} - Last 100 Candles', color='white', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Price (USDT)', color='white', fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.legend(loc='upper left', facecolor='#2d2d2d', edgecolor='white')
            
            # Add volume chart
            volume_colors = ['#00ff88' if df.iloc[i]['Close'] >= df.iloc[i]['Open'] 
                           else '#ff4444' for i in range(len(df))]
            ax2.bar(df['Open time'], df['Volume'], color=volume_colors, alpha=0.6)
            ax2.set_ylabel('Volume', color='white', fontweight='bold')
            ax2.set_xlabel('Time', color='white', fontweight='bold')
            ax2.grid(True, alpha=0.3)
            
            # Format time axis
            ax1.tick_params(colors='white')
            ax2.tick_params(colors='white')
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
            
            # Add timestamp
            fig.text(0.99, 0.01, f'Generated: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")} UTC', 
                    ha='right', va='bottom', color='gray', fontsize=8)
            
            plt.tight_layout()
            plt.subplots_adjust(bottom=0.1)
            
            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, facecolor='#1e1e1e', 
                       bbox_inches='tight', pad_inches=0.2)
            buf.seek(0)
            plt.close(fig)
            
            log.info(f"Generated professional candlestick chart for {symbol}.")
            return buf.getvalue()
            
        except Exception as e:
            log.error(f"Error generating chart for {symbol}: {e}")
            # Fallback to simple line chart
            try:
                plt.style.use('default')
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.plot(df["Open time"], df["Close"], label="Close Price", color='blue')
                
                if entry_price:
                    ax.axhline(y=float(entry_price), color='blue', linestyle='--', 
                              label=f'Entry: ${entry_price}')
                if tp_price:
                    ax.axhline(y=float(tp_price), color='green', linestyle='--', 
                              label=f'TP: ${tp_price}')
                if sl_price:
                    ax.axhline(y=float(sl_price), color='red', linestyle='--', 
                              label=f'SL: ${sl_price}')
                
                ax.set_title(f"{symbol} Price Chart")
                ax.legend()
                plt.tight_layout()
                
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                plt.close(fig)
                return buf.getvalue()
            except:
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
        tp1_price: Decimal = None,
        tp2_price: Decimal = None,
        sl_price: Decimal = None,
        leverage: int = None,
    ):
        """Sends a notification about a filled trade with complete trading information."""
        # Enhanced emojis for different sides
        if side.upper() == "BUY":
            side_emoji = "🟢📈"  # Green circle + chart up
            action_emoji = "🚀"  # Rocket for buy
        else:
            side_emoji = "🔴📉"  # Red circle + chart down  
            action_emoji = "🎯"  # Target for sell
            
        price_precision = self.get_price_precision(symbol)
        qty_precision = self.get_qty_precision(symbol)
        
        # Calculate position value
        position_value = float(price) * float(qty)
        
        # Format all values safely without markdown escaping initially
        price_str = f"{price:.{price_precision}f}"
        qty_str = f"{qty:.{qty_precision}f}"
        value_str = f"{position_value:.2f}"
        
        # Build message without markdown to avoid escaping issues
        text = f"{side_emoji} TRADE EXECUTED {action_emoji}\n\n"
        text += f"📊 Symbol: {symbol}\n"
        text += f"⚡ Side: {side.upper()}\n"
        text += f"💰 Entry Price: ${price_str}\n"
        text += f"📦 Quantity: {qty_str}\n"
        text += f"💵 Position Value: ${value_str} USDT\n"
        
        if leverage:
            text += f"🔥 Leverage: {leverage}x\n"
            
        if tp1_price:
            tp1_str = f"{tp1_price:.{price_precision}f}"
            text += f"🎯 TP1: ${tp1_str}\n"
            
        if tp2_price:
            tp2_str = f"{tp2_price:.{price_precision}f}"
            text += f"🎯 TP2: ${tp2_str}\n"
            
        if sl_price:
            sl_str = f"{sl_price:.{price_precision}f}"
            text += f"🛡️ Stop Loss: ${sl_str}\n"

        if pnl is not None:
            pnl_str = f"{pnl:.4f}"
            pnl_emoji = "💸" if pnl >= 0 else "💔"
            profit_emoji = "✅" if pnl >= 0 else "❌"
            text += f"\n{profit_emoji} Realized PNL: {pnl_str} USDT {pnl_emoji}\n"
            
        text += f"\n⏰ Timestamp: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"

        photo_bytes = None
        if klines_data:
            # Generate chart with all price levels
            tp_prices = [tp1_price, tp2_price] if tp1_price and tp2_price else tp1_price
            photo_bytes = self._generate_chart(
                klines_data, symbol, 
                entry_price=price, 
                tp_price=tp1_price, 
                sl_price=sl_price
            )

        # Send without markdown to avoid formatting issues
        self.send_message(text, parse_mode=None, photo=photo_bytes)

    def send_trend_recommendation(
        self,
        symbol: str,
        direction: str,
        entry_price: Decimal,
        tp_price: Decimal,
        sl_price: Decimal,
        confidence: float = None,
        klines_data=None,
        market_type: str = "SPOT",
        risk_reward_ratio: float = None,
    ):
        """Sends a comprehensive trading recommendation with all important details."""
        direction_upper = direction.upper()
        if direction_upper not in ["LONG", "SHORT"]:
            log.error(f"Invalid direction for trend recommendation: {direction}")
            return

        # Enhanced emojis based on direction
        if direction_upper == "LONG":
            direction_emoji = "🟢🚀📈"  # Green + rocket + chart up
            signal_emoji = "⬆️"
        else:
            direction_emoji = "🔴📉🎯"  # Red + chart down + target
            signal_emoji = "⬇️"
            
        price_precision = self.get_price_precision(symbol)
        
        # Calculate potential profit/loss percentages
        entry_float = float(entry_price)
        tp_float = float(tp_price)
        sl_float = float(sl_price)
        
        if direction_upper == "LONG":
            profit_pct = ((tp_float - entry_float) / entry_float) * 100
            loss_pct = ((entry_float - sl_float) / entry_float) * 100
        else:
            profit_pct = ((entry_float - tp_float) / entry_float) * 100
            loss_pct = ((sl_float - entry_float) / entry_float) * 100
            
        # Calculate risk/reward if not provided
        if not risk_reward_ratio:
            risk_reward_ratio = profit_pct / loss_pct if loss_pct > 0 else 0
        
        # Build comprehensive message
        text = f"{direction_emoji} TRADING SIGNAL {signal_emoji}\n\n"
        text += f"📊 SYMBOL: {symbol}\n"
        text += f"🎯 DIRECTION: {direction_upper}\n"
        text += f"💰 ENTRY PRICE: ${entry_price:.{price_precision}f}\n"
        text += f"🎯 TAKE PROFIT: ${tp_price:.{price_precision}f} (+{profit_pct:.2f}%)\n"
        text += f"🛡️ STOP LOSS: ${sl_price:.{price_precision}f} (-{loss_pct:.2f}%)\n"
        text += f"📊 MARKET: {market_type}\n"
        
        if risk_reward_ratio:
            rr_emoji = "🟢" if risk_reward_ratio >= 2 else "🟡" if risk_reward_ratio >= 1.5 else "🔴"
            text += f"{rr_emoji} RISK/REWARD: 1:{risk_reward_ratio:.2f}\n"
        
        if confidence is not None:
            conf_pct = confidence * 100
            conf_emoji = "🟢" if conf_pct >= 75 else "🟡" if conf_pct >= 50 else "🔴"
            text += f"{conf_emoji} CONFIDENCE: {conf_pct:.1f}%\n"
            
        text += f"\n⏰ Signal Time: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        text += "\n⚠️ DISCLAIMER: Automated analysis only. DYOR and trade responsibly!"

        photo_bytes = None
        if klines_data:
            # Generate enhanced chart with 100 candles
            photo_bytes = self._generate_chart(
                klines_data[-100:],  # Last 100 candles
                symbol, 
                entry_price=entry_price, 
                tp_price=tp_price, 
                sl_price=sl_price
            )

        self.send_message(text, parse_mode=None, photo=photo_bytes)


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
