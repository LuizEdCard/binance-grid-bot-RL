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
ENV_PATH = os.path.join(SRC_DIR, "config", ".env")
CONFIG_PATH = os.path.join(SRC_DIR, "config", "config.yaml")

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
    """Lida com comunicação com as APIs da Binance (Spot e Futuros).
    Opera em modo Production para trading real.
    """

    def __init__(self, config: dict, operation_mode: str = "production"):
        self.client = None
        self.config = config
        self.operation_mode = operation_mode.lower()
        log.info(f"APIClient inicializado no modo {self.operation_mode.upper()}.")
        self._connect()

    def _connect(self):
        """Estabelece conexão com a API de Produção da Binance."""
        key = API_KEY
        secret = API_SECRET

        if not key or not secret:
            log.error(
                "API_KEY/SECRET não encontrada no arquivo .env. Não é possível conectar à Produção da Binance."
            )
            self.client = None
            return

        retries = 0
        while retries < MAX_RETRIES:
            try:
                log.info(
                    f"Tentando conectar à Produção da Binance (Tentativa {retries + 1}/{MAX_RETRIES})..."
                )
                # Sempre conecta à produção, testnet=False
                self.client = Client(key, secret, testnet=False)
                # Testa conexão com Futures
                self.client.futures_ping()
                server_time = self.client.futures_time()["serverTime"]
                log.info(
                    f"Conectado com sucesso à Produção da Binance. Hora do servidor: {server_time}"
                )
                return
            except (BinanceAPIException, BinanceRequestException, ConnectionError) as e:
                log.warning(f"Tentativa de conexão {retries + 1} falhou: {e}")
                retries += 1
                if retries < MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS[retries - 1]
                    log.info(f"Tentando reconectar em {delay} segundos...")
                    time.sleep(delay)
                else:
                    log.error(f"Máximo de tentativas de conexão atingido. Falha ao conectar.")
                    self.client = None
                    break
            except Exception as e:
                log.error(f"Erro inesperado durante a conexão: {e}")
                self.client = None
                break

    def _make_request(self, method, *args, **kwargs):
        """Faz uma requisição à API com tratamento de erros, tentativas e simulação no modo Shadow."""
        if not self.client:
            log.error("Cliente da API não está conectado. Tentando reconectar...")
            self._connect()
            if not self.client:
                log.error("Reconexão falhou. Não é possível fazer requisição à API.")
                return None

        # --- Modo de Produção --- #
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
        if symbol:
            # Use futures_symbol_ticker when a specific symbol is requested
            return self._make_request(self.client.futures_symbol_ticker, symbol=symbol)
        else:
            # Use futures_ticker when no symbol is specified (get all tickers)
            return self._make_request(self.client.futures_ticker)

    def get_exchange_info(self):
        log.debug(f"Getting exchange info ({self.operation_mode.upper()})")
        return self._make_request(self.client.futures_exchange_info)

    # --- Métodos para Mercado Spot --- #

    def get_spot_account_balance(self):
        """Obtém o saldo da conta Spot."""
        log.debug(f"Buscando saldo da conta Spot ({self.operation_mode.upper()})")
        return self._make_request(self.client.get_account)

    def place_spot_order(
        self, symbol, side, order_type, quantity, price=None, timeInForce=None, **kwargs
    ):
        """Coloca uma ordem no mercado Spot."""
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
        log.info(f"Colocando ordem Spot ({self.operation_mode.upper()}): {params}")
        return self._make_request(self.client.create_order, **params)

    def cancel_spot_order(self, symbol, orderId):
        """Cancela uma ordem no mercado Spot."""
        log.info(
            f"Cancelando ordem Spot ({self.operation_mode.upper()}): symbol={symbol}, orderId={orderId}"
        )
        return self._make_request(
            self.client.cancel_order, symbol=symbol, orderId=orderId
        )

    def get_spot_order_status(self, symbol, orderId):
        """Obtém o status de uma ordem no mercado Spot."""
        log.debug(
            f"Obtendo status da ordem Spot ({self.operation_mode.upper()}): symbol={symbol}, orderId={orderId}"
        )
        if self.operation_mode == "shadow":
            log.warning(
                f"[MODO SHADOW] get_spot_order_status chamado para ordem simulada {orderId}. Retornando None. GridLogic deve gerenciar estado."
            )
            return None  # Ou recuperar de cache local se implementado
        return self._make_request(
            self.client.get_order, symbol=symbol, orderId=orderId
        )

    def get_open_spot_orders(self, symbol=None):
        """Obtém ordens abertas no mercado Spot."""
        log.debug(
            f"Obtendo ordens abertas Spot ({self.operation_mode.upper()}): symbol={symbol}"
        )
        if self.operation_mode == "shadow":
            log.warning(
                "[MODO SHADOW] get_open_spot_orders chamado. Retornando lista vazia. GridLogic deve gerenciar estado."
            )
            return []  # Retorna lista vazia pois não rastreamos ordens reais
        params = {"symbol": symbol} if symbol else {}
        return self._make_request(self.client.get_open_orders, **params)

    def get_spot_klines(
        self, symbol, interval, startTime=None, endTime=None, limit=500
    ):
        """Obtém dados de klines (candlesticks) do mercado Spot."""
        log.debug(
            f"Obtendo klines Spot ({self.operation_mode.upper()}): symbol={symbol}, interval={interval}"
        )
        return self._make_request(
            self.client.get_klines,
            symbol=symbol,
            interval=interval,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
        )

    def get_spot_ticker(self, symbol=None):
        """Obtém ticker do mercado Spot."""
        log.debug(f"Obtendo ticker Spot ({self.operation_mode.upper()}): symbol={symbol}")
        if symbol:
            return self._make_request(self.client.get_symbol_ticker, symbol=symbol)
        else:
            return self._make_request(self.client.get_all_tickers)

    def get_spot_exchange_info(self):
        """Obtém informações de exchange do mercado Spot."""
        log.debug(f"Obtendo informações de exchange Spot ({self.operation_mode.upper()})")
        return self._make_request(self.client.get_exchange_info)

    def get_futures_position_info(self, symbol=None):
        """Obtém informações de posição do mercado Futuros."""
        log.debug(f"Obtendo informações de posição Futuros ({self.operation_mode.upper()}): symbol={symbol}")
        params = {"symbol": symbol} if symbol else {}
        return self._make_request(self.client.futures_position_information, **params)


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
