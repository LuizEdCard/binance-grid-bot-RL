# API Client Module

# Assuming logger is correctly set up in __init__.py or similar
# from ..utils.logger import log
# For now, use basic logging
import logging
import os
import random
import time

# from decimal import Decimal # Unused import

import yaml
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables and configuration
UTILS_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.dirname(UTILS_DIR)
ROOT_DIR = os.path.dirname(SRC_DIR)
ENV_PATH = os.path.join(ROOT_DIR, "config", ".env")
CONFIG_PATH = os.path.join(ROOT_DIR, "config", "config.yaml")

load_dotenv(dotenv_path=ENV_PATH)


def load_config():
    """Loads the YAML configuration file."""
    try:
        with open(CONFIG_PATH, "r") as f:
            config_data = yaml.safe_load(f)
            if config_data is None:
                return {}
            return config_data
    except FileNotFoundError:
        log.error(f"Config file not found at {CONFIG_PATH}")
        return {}
    except Exception as e:
        log.error(f"Error loading configuration for APIClient: {e}")
        return {}


config = load_config()
exchange_config = config.get("exchange", {})

# API Credentials (Only Production keys needed now)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# Constants
MAX_RETRIES = 5
RETRY_DELAY_SECONDS = [1, 2, 4, 8, 16]  # Exponential backoff


class APIClient:
    """Handles communication with the Binance Futures API.
    Supports Production mode(real trading) and Shadow mode(real data, simulated orders).
    """

    def __init__(self, config: dict, operation_mode: str = "shadow"):
        self.client = None
        self.config = config
        self.operation_mode = operation_mode.lower()
        # Shadow mode now uses Production API for data, simulates orders
        log.info(f"APIClient initialized in {self.operation_mode.upper()} mode.")
        self._connect()

    def _connect(self):
        """Establishes connection to the Binance Production API."""
        key = API_KEY
        secret = API_SECRET

        if not key or not secret:
            log.error(
                "API_KEY/SECRET not found in .env file. Cannot connect to Binance Production."
            )
            self.client = None
            return

        retries = 0
        while retries < MAX_RETRIES:
            try:
                log.info(
                    f"Attempting to connect to Binance Futures Production (Attempt {retries + 1}/{MAX_RETRIES})..."
                )
                # Always connect to production, testnet=False
                self.client = Client(key, secret, testnet=False)
                # Test connection
                self.client.futures_ping()
                server_time = self.client.futures_time()["serverTime"]
                log.info(
                    f"Successfully connected to Binance Futures Production. Server time: {server_time}"
                )
                return
            except (BinanceAPIException, BinanceRequestException, ConnectionError) as e:
                log.warning(f"Connection attempt {retries + 1} failed: {e}")
                retries += 1
                if retries < MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS[retries - 1]
                    log.info(f"Retrying connection in {delay} seconds...")
                    time.sleep(delay)
                else:
                    log.error(f"Max connection retries reached. Failed to connect.")
                    self.client = None
                    break
            except Exception as e:
                log.error(f"An unexpected error occurred during connection: {e}")
                self.client = None
                break

    def _make_request(self, method, *args, **kwargs):
        """Makes an API request with error handling, retries, and Shadow mode simulation."""
        if not self.client:
            log.error("API client is not connected. Attempting to reconnect...")
            self._connect()
            if not self.client:
                log.error("Reconnection failed. Cannot make API request.")
                return None

        # --- Shadow Mode Simulation (for write operations) --- #
        method_name = method.__name__
        is_write_operation = method_name in [
            "futures_create_order",
            "futures_cancel_order",
            "futures_cancel_all_open_orders",
            # Add other write methods if
            # needed (e.g., adjusting
            # leverage, margin type)
        ]

        if self.operation_mode == "shadow" and is_write_operation:
            log.info(
                f"[SHADOW MODE] Simulating API call: {method_name} args={args} kwargs={kwargs}"
            )
            # Simulate responses for write operations
            if method_name == "futures_create_order":
                # Return a realistic-looking fake order response
                # Use timestamp and random element for unique ID
                simulated_order_id = int(time.time() * 1000) + random.randint(0, 999)
                return {
                    "orderId": simulated_order_id,
                    "symbol": kwargs.get("symbol"),
                    "status": "NEW",  # Assume it gets accepted immediately
                    "clientOrderId": f"shadow_{simulated_order_id}",
                    "price": kwargs.get("price"),
                    "avgPrice": "0.00000",  # Not filled yet
                    "origQty": kwargs.get("quantity"),
                    "executedQty": "0.000",
                    "cumQuote": "0",
                    "timeInForce": kwargs.get("timeInForce"),
                    "type": kwargs.get("type"),
                    "side": kwargs.get("side"),
                    "stopPrice": "0",
                    "time": int(time.time() * 1000),
                    "updateTime": int(time.time() * 1000),
                    "workingType": "CONTRACT_PRICE",
                    "activatePrice": "0",
                    "priceRate": "0",
                    "origType": kwargs.get("type"),
                    "positionSide": kwargs.get("positionSide", "BOTH"),
                    "closePosition": False,
                    "priceProtect": False,
                    "reduceOnly": kwargs.get("reduceOnly", False),
                }
            elif method_name == "futures_cancel_order":
                # Return a fake cancellation response
                # Note: We don"t have the state here to know if it *was* NEW
                # Assume cancellation is successful if requested
                return {
                    "orderId": kwargs.get("orderId"),
                    "symbol": kwargs.get("symbol"),
                    "status": "CANCELED",
                    "clientOrderId": f"shadow_{kwargs.get('orderId')}",
                    "price": "0",  # Values might not be accurate for cancelled order
                    "avgPrice": "0.00000",
                    "origQty": "0",
                    "executedQty": "0",
                    "cumQuote": "0",
                    "timeInForce": "GTC",
                    "type": "LIMIT",
                    "side": "BUY",  # Side might not be known here
                    "stopPrice": "0",
                    "time": int(time.time() * 1000),
                    "updateTime": int(time.time() * 1000),
                    "workingType": "CONTRACT_PRICE",
                    "origType": "LIMIT",
                    "positionSide": "BOTH",
                    "closePosition": False,
                    "priceProtect": False,
                    "reduceOnly": False,
                }
            elif method_name == "futures_cancel_all_open_orders":
                # Simulate success, though no orders were actually cancelled
                return {
                    "code": "200",
                    "msg": "[SHADOW MODE] Simulated cancellation of all orders for symbol.",
                }

            # Generic simulation for other write ops
            return {"status": "simulated_success"}
        # --- End Shadow Mode Simulation --- #

        # --- Production Mode or Read Operation --- #
        retries = 0
        while retries < MAX_RETRIES:
            try:
                response = method(*args, **kwargs)
                log.debug(
                    f"API call successful: {method_name} args={args} kwargs={kwargs}"
                )
                return response
            except (BinanceAPIException, BinanceRequestException) as e:
                log.warning(
                    f"API Error on attempt {retries + 1}: {e} (Code: {e.code}, Message: {e.message})"
                )
                retries += 1
                if retries < MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS[retries - 1]
                    log.info(f"Retrying API call in {delay} seconds...")
                    time.sleep(delay)
                else:
                    log.error(
                        f"Max retries reached for API call {method_name}. Error: {e}"
                    )
                    return None
            except ConnectionError as e:
                log.warning(
                    f"Connection Error on attempt {retries + 1}: {e}. Attempting reconnect..."
                )
                self._connect()
                if not self.client:
                    log.error(
                        "Reconnection failed after ConnectionError. Cannot retry API call."
                    )
                    return None
                retries += 1
                if retries >= MAX_RETRIES:
                    log.error(
                        f"Max retries reached after ConnectionError for API call {method_name}."
                    )
                    return None
            except Exception as e:
                log.error(
                    f"An unexpected error occurred during API call {method_name}: {e}"
                )
                return None

    # --- API Methods (no change needed here, _make_request handles mode) --- #

    def get_futures_account_balance(self):
        # Note: In Shadow mode, this will return the PRODUCTION balance.
        # A true simulation might require faking this based on simulated trades.
        # For now, we accept this limitation.
        log.debug(f"Fetching account balance ({self.operation_mode.upper()})")
        return self._make_request(self.client.futures_account_balance)

    def get_futures_positions(self):
        # Note: In Shadow mode, this will return PRODUCTION positions.
        # GridLogic needs to maintain its own simulated position state.
        log.debug(f"Fetching positions ({self.operation_mode.upper()})")
        return self._make_request(self.client.futures_position_information)

    def place_futures_order(
        self, symbol, side, order_type, quantity, price=None, timeInForce=None, **kwargs
    ):
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if price and order_type == "LIMIT":
            params["price"] = price
        if timeInForce and order_type == "LIMIT":
            params["timeInForce"] = timeInForce
        params.update(kwargs)
        log.info(f"Placing order ({self.operation_mode.upper()}): {params}")
        return self._make_request(self.client.futures_create_order, **params)

    def cancel_futures_order(self, symbol, orderId):
        log.info(
            f"Cancelling order ({self.operation_mode.upper()}): symbol={symbol}, orderId={orderId}"
        )
        return self._make_request(
            self.client.futures_cancel_order, symbol=symbol, orderId=orderId
        )

    def get_futures_order_status(self, symbol, orderId):
        # In Shadow mode, this won"t work for simulated orders unless we cache them.
        # GridLogic will need to manage simulated order state.
        log.debug(
            f"Getting order status ({self.operation_mode.upper()}): symbol={symbol}, orderId={orderId}"
        )
        if self.operation_mode == "shadow":
            log.warning(
                f"[SHADOW MODE] get_futures_order_status called for simulated order {orderId}. Returning None. GridLogic should manage state."
            )
            return None  # Or retrieve from a local cache if implemented
        return self._make_request(
            self.client.futures_get_order, symbol=symbol, orderId=orderId
        )

    def get_open_futures_orders(self, symbol=None):
        # In Shadow mode, this will return PRODUCTION open orders.
        # GridLogic needs to manage its own simulated open orders.
        log.debug(
            f"Getting open orders ({self.operation_mode.upper()}): symbol={symbol}"
        )
        if self.operation_mode == "shadow":
            log.warning(
                "[SHADOW MODE] get_open_futures_orders called. Returning empty list. GridLogic should manage state."
            )
            return []  # Return empty list as we don"t track real orders
        params = {"symbol": symbol} if symbol else {}
        return self._make_request(self.client.futures_get_open_orders, **params)

    def get_futures_klines(
        self, symbol, interval, startTime=None, endTime=None, limit=500
    ):
        log.debug(
            f"Getting klines ({self.operation_mode.upper()}): symbol={symbol}, interval={interval}"
        )
        return self._make_request(
            self.client.futures_klines,
            symbol=symbol,
            interval=interval,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
        )

    def get_futures_ticker(self, symbol=None):
        log.debug(f"Getting ticker ({self.operation_mode.upper()}): symbol={symbol}")
        params = {"symbol": symbol} if symbol else {}
        return self._make_request(self.client.futures_ticker, **params)

    def get_exchange_info(self):
        log.debug(f"Getting exchange info ({self.operation_mode.upper()})")
        return self._make_request(self.client.futures_exchange_info)


# Example usage
# if __name__ == '__main__':
#     # Test Production
#     # prod_api = APIClient(config, operation_mode=\"production\")
#     # if prod_api.client:
#     #     print('Production Balance:', prod_api.get_futures_account_balance())

#     # Test Shadow (Simulated)
#     shadow_api = APIClient(config, operation_mode='shadow')
#     if shadow_api.client:
#         print('Shadow (Prod Data) Balance:', shadow_api.get_futures_account_balance()) # Shows real balance
#         print('Shadow (Prod Data) Ticker BTCUSDT:', shadow_api.get_futures_ticker('BTCUSDT'))
#         # Example place/cancel simulation
#         sim_order = shadow_api.place_futures_order('BTCUSDT', 'BUY', 'LIMIT', quantity=0.001, price=20000, timeInForce='GTC')
#         if sim_order:
#             print('Shadow Order Placed (Simulated):', sim_order)
#             sim_cancel = shadow_api.cancel_futures_order('BTCUSDT', sim_order['orderId'])
#             print('Shadow Order Cancelled (Simulated):', sim_cancel)
#             # Getting status will return None in shadow mode
#             print('Shadow Order Status (Simulated):', shadow_api.get_futures_order_status('BTCUSDT', sim_order['orderId']))
#     else:
#         print('Failed to initialize Shadow API Client.')
