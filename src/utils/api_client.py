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
ENV_PATH = os.path.join(ROOT_DIR, "secrets", ".env")
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

# API Credentials
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# Testnet credentials (optional)
TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", API_KEY)
TESTNET_API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", API_SECRET)

# Constants
MAX_RETRIES = 5
RETRY_DELAY_SECONDS = [1, 2, 4, 8, 16]  # Exponential backoff


class APIClient:
    """Lida com comunicação com as APIs da Binance (Spot e Futuros).
    Opera em modo Production para trading real ou Shadow para testnet.
    """

    def __init__(self, config: dict, operation_mode: str = "production"):
        self.client = None
        self.config = config
        self.operation_mode = operation_mode.lower()
        self.use_testnet = self.operation_mode == "shadow"
        log.info(f"APIClient inicializado no modo {self.operation_mode.upper()}" + 
                 (" (TESTNET)" if self.use_testnet else " (PRODUCTION)"))
        self._connect()

    def _connect(self):
        """Estabelece conexão com a API da Binance (Produção ou Testnet)."""
        if self.use_testnet:
            key = TESTNET_API_KEY
            secret = TESTNET_API_SECRET
            environment = "Testnet"
        else:
            key = API_KEY
            secret = API_SECRET
            environment = "Produção"

        if not key or not secret:
            log.error(
                f"API_KEY/SECRET não encontrada no arquivo .env. Não é possível conectar à {environment} da Binance."
            )
            self.client = None
            return

        retries = 0
        while retries < MAX_RETRIES:
            try:
                log.info(
                    f"Tentando conectar à {environment} da Binance (Tentativa {retries + 1}/{MAX_RETRIES})..."
                )
                # Conecta baseado no modo
                self.client = Client(key, secret, testnet=self.use_testnet)
                
                # Testa conexão com Futures
                self.client.futures_ping()
                server_time = self.client.futures_time()["serverTime"]
                log.info(
                    f"Conectado com sucesso à {environment} da Binance. Hora do servidor: {server_time}"
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
                    f"API call successful: {method.__name__} args={args} kwargs={kwargs}"
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
                        f"Max retries reached for API call {method.__name__}. Error: {e}"
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
                        f"Max retries reached after ConnectionError for API call {method.__name__}."
                    )
                    return None
            except Exception as e:
                log.error(
                    f"An unexpected error occurred during API call {method.__name__}: {e}"
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
        self, symbol, side, order_type, quantity, price=None, time_in_force=None, **kwargs
    ):
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if price and order_type == "LIMIT":
            params["price"] = price
        if time_in_force and order_type == "LIMIT":
            params["timeInForce"] = time_in_force  # Binance API espera timeInForce (camelCase)
        elif order_type == "LIMIT" and not time_in_force:
            params["timeInForce"] = "GTC"  # Default para LIMIT orders
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

    def futures_exchange_info(self):
        """Alias para get_exchange_info() - compatibilidade com DynamicOrderSizer."""
        return self.get_exchange_info()

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

    def get_account_balance(self):
        """Obtém saldo da conta Spot."""
        log.debug(f"Obtendo saldo da conta Spot ({self.operation_mode.upper()})")
        return self._make_request(self.client.get_account)

    def get_spot_exchange_info(self):
        """Obtém informações de exchange do mercado Spot."""
        log.debug(f"Obtendo informações de exchange Spot ({self.operation_mode.upper()})")
        return self._make_request(self.client.get_exchange_info)

    def spot_exchange_info(self):
        """Alias para get_spot_exchange_info() - compatibilidade com DynamicOrderSizer."""
        return self.get_spot_exchange_info()

    def get_futures_position_info(self, symbol=None):
        """Obtém informações de posição do mercado Futuros."""
        log.debug(f"Obtendo informações de posição Futuros ({self.operation_mode.upper()}): symbol={symbol}")
        params = {"symbol": symbol} if symbol else {}
        return self._make_request(self.client.futures_position_information, **params)

    def get_futures_balance(self):
        """Alias for get_futures_account_balance for compatibility."""
        return self.get_futures_account_balance()

    def get_futures_position(self, symbol=None):
        """Get specific futures position for a symbol."""
        if symbol is None:
            return self.get_futures_positions()
        
        positions = self.get_futures_positions()
        if positions and isinstance(positions, list):
            for position in positions:
                if isinstance(position, dict) and position.get('symbol') == symbol:
                    return position
        return None
    
    def transfer_between_markets(self, asset: str, amount: float, transfer_type: str):
        """
        Transfere saldo entre mercados Spot e Futures.
        
        Args:
            asset: Ativo a ser transferido (ex: 'USDT')
            amount: Quantidade a transferir
            transfer_type: '1' (Spot para Futures) ou '2' (Futures para Spot)
        """
        log.info(f"Transferring {amount} {asset} - Type: {'Spot->Futures' if transfer_type == '1' else 'Futures->Spot'} ({self.operation_mode.upper()})")
        
        if self.operation_mode == "shadow":
            # Em modo shadow, simular transferência
            log.info(f"[SHADOW MODE] Simulated transfer: {amount} {asset} ({'Spot->Futures' if transfer_type == '1' else 'Futures->Spot'})")
            return {
                "tranId": f"shadow_{int(time.time())}",
                "status": "CONFIRMED"
            }
        
        # Modo production - transferência real
        try:
            result = self._make_request(
                self.client.futures_account_transfer,
                asset=asset,
                amount=amount,
                type=transfer_type
            )
            
            if result and result.get("tranId"):
                log.info(f"Transfer successful. Transaction ID: {result['tranId']}")
                return result
            else:
                log.error(f"Transfer failed: {result}")
                return None
                
        except Exception as e:
            log.error(f"Error during transfer: {e}")
            return None
    
    def change_leverage(self, symbol: str, leverage: int):
        """
        Altera a alavancagem para um símbolo no mercado de futuros.
        
        Args:
            symbol: Símbolo (ex: 'ADAUSDT')
            leverage: Nova alavancagem (ex: 10)
        """
        log.info(f"Changing leverage for {symbol} to {leverage}x ({self.operation_mode.upper()})")
        
        if self.operation_mode == "shadow":
            log.info(f"[SHADOW MODE] Simulated leverage change: {symbol} -> {leverage}x")
            return {
                "leverage": leverage,
                "symbol": symbol,
                "maxNotionalValue": "1000000"
            }
        
        try:
            result = self._make_request(
                self.client.futures_change_leverage,
                symbol=symbol,
                leverage=leverage
            )
            
            if result and result.get("leverage"):
                log.info(f"Leverage changed successfully: {symbol} -> {leverage}x")
                return result
            else:
                log.error(f"Failed to change leverage: {result}")
                return None
                
        except Exception as e:
            log.error(f"Error changing leverage for {symbol}: {e}")
            return None

    def place_stop_limit_order(self, symbol: str, side: str, quantity: str, 
                              stop_price: str, price: str, time_in_force: str = "GTC",
                              close_position: bool = False, reduce_only: bool = False):
        """
        Coloca ordem STOP_LIMIT para melhor controle de slippage.
        
        Args:
            symbol: Par de trading (ex: 'BTCUSDT')
            side: 'BUY' ou 'SELL'
            quantity: Quantidade da ordem
            stop_price: Preço de ativação do stop
            price: Preço limite da ordem
            time_in_force: 'GTC', 'IOC', 'FOK'
            close_position: Se deve fechar a posição inteira
            reduce_only: Se a ordem deve apenas reduzir posição
        """
        log.info(f"Placing STOP_LIMIT order: {symbol} {side} {quantity} @ stop:{stop_price} limit:{price} ({self.operation_mode.upper()})")
        
        if self.operation_mode == "shadow":
            shadow_order = {
                "orderId": f"SHADOW_STOP_LIMIT_{int(time.time())}",
                "symbol": symbol,
                "status": "NEW",
                "type": "STOP",
                "side": side,
                "origQty": quantity,
                "stopPrice": stop_price,
                "price": price,
                "timeInForce": time_in_force,
                "closePosition": close_position,
                "reduceOnly": reduce_only
            }
            log.info(f"[SHADOW MODE] Simulated STOP_LIMIT order: {shadow_order}")
            return shadow_order
        
        try:
            order_params = {
                "symbol": symbol,
                "side": side,
                "type": "STOP",  # STOP_LIMIT no Binance é type="STOP"
                "quantity": quantity,
                "stopPrice": stop_price,
                "price": price,
                "timeInForce": time_in_force
            }
            
            if close_position:
                order_params["closePosition"] = True
            
            if reduce_only:
                order_params["reduceOnly"] = True
            
            result = self._make_request(
                self.client.futures_create_order,
                **order_params
            )
            
            if result and result.get("orderId"):
                log.info(f"STOP_LIMIT order placed successfully: {result['orderId']}")
                return result
            else:
                log.error(f"Failed to place STOP_LIMIT order: {result}")
                return None
                
        except Exception as e:
            log.error(f"Error placing STOP_LIMIT order for {symbol}: {e}")
            return None

    def place_conditional_order(self, symbol: str, side: str, order_type: str,
                               quantity: str, price: str = None, stop_price: str = None,
                               activation_price: str = None, callback_rate: str = None,
                               time_in_force: str = "GTC", working_type: str = "MARK_PRICE"):
        """
        Coloca ordem condicional (TAKE_PROFIT, STOP_MARKET, TRAILING_STOP).
        
        Args:
            symbol: Par de trading
            side: 'BUY' ou 'SELL'
            order_type: 'TAKE_PROFIT', 'STOP_MARKET', 'TRAILING_STOP_MARKET'
            quantity: Quantidade da ordem
            price: Preço limite (para TAKE_PROFIT)
            stop_price: Preço de ativação
            activation_price: Preço de ativação para trailing stop
            callback_rate: Taxa de callback para trailing stop (0.1 = 0.1%)
            time_in_force: 'GTC', 'IOC', 'FOK'
            working_type: 'MARK_PRICE' ou 'CONTRACT_PRICE'
        """
        log.info(f"Placing conditional order: {symbol} {side} {order_type} {quantity} ({self.operation_mode.upper()})")
        
        if self.operation_mode == "shadow":
            shadow_order = {
                "orderId": f"SHADOW_CONDITIONAL_{int(time.time())}",
                "symbol": symbol,
                "status": "NEW",
                "type": order_type,
                "side": side,
                "origQty": quantity,
                "stopPrice": stop_price,
                "price": price,
                "activationPrice": activation_price,
                "callbackRate": callback_rate,
                "timeInForce": time_in_force,
                "workingType": working_type
            }
            log.info(f"[SHADOW MODE] Simulated conditional order: {shadow_order}")
            return shadow_order
        
        try:
            order_params = {
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "quantity": quantity,
                "timeInForce": time_in_force,
                "workingType": working_type
            }
            
            # Adicionar parâmetros específicos por tipo
            if price:
                order_params["price"] = price
            if stop_price:
                order_params["stopPrice"] = stop_price
            if activation_price:
                order_params["activationPrice"] = activation_price
            if callback_rate:
                order_params["callbackRate"] = callback_rate
            
            result = self._make_request(
                self.client.futures_create_order,
                **order_params
            )
            
            if result and result.get("orderId"):
                log.info(f"Conditional order placed successfully: {result['orderId']}")
                return result
            else:
                log.error(f"Failed to place conditional order: {result}")
                return None
                
        except Exception as e:
            log.error(f"Error placing conditional order for {symbol}: {e}")
            return None

    def get_order_book_depth(self, symbol: str, limit: int = 20):
        """
        Obtém profundidade do order book para análise de liquidez.
        
        Args:
            symbol: Par de trading
            limit: Número de níveis (5, 10, 20, 50, 100, 500, 1000)
        """
        try:
            result = self._make_request(
                self.client.futures_order_book,
                symbol=symbol,
                limit=limit
            )
            
            if result:
                # Calcular estatísticas úteis
                bids = result.get("bids", [])
                asks = result.get("asks", [])
                
                if bids and asks:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    spread = best_ask - best_bid
                    spread_pct = (spread / best_ask) * 100
                    
                    # Calcular liquidez total nos primeiros 5 níveis
                    bid_liquidity = sum(float(bid[1]) * float(bid[0]) for bid in bids[:5])
                    ask_liquidity = sum(float(ask[1]) * float(ask[0]) for ask in asks[:5])
                    
                    result["analysis"] = {
                        "best_bid": best_bid,
                        "best_ask": best_ask,
                        "spread": spread,
                        "spread_percentage": spread_pct,
                        "bid_liquidity_usdt": bid_liquidity,
                        "ask_liquidity_usdt": ask_liquidity,
                        "total_liquidity_usdt": bid_liquidity + ask_liquidity,
                        "liquidity_imbalance": (bid_liquidity - ask_liquidity) / (bid_liquidity + ask_liquidity)
                    }
                
                return result
            
        except Exception as e:
            log.error(f"Error getting order book depth for {symbol}: {e}")
            return None


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
