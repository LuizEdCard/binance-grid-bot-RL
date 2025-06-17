# API Client Module

# Assuming logger is correctly set up in __init__.py or similar
# from ..utils.logger import log
# For now, use basic logging
import logging
import os
import random
import time
from datetime import datetime, timedelta

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
exchange_config = config["exchange"]

# API Credentials
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# Testnet credentials (optional)
TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", API_KEY)
TESTNET_API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", API_SECRET)

# Constants - will be overridden by config
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
        
        # Rate limiting cache with timestamps - configurable
        self._cache = {}
        api_config = config['api_client']
        cache_ttl_config = api_config['cache_ttl']
        self._cache_ttl = {
            'account': cache_ttl_config['account'],
            'balance': cache_ttl_config['balance'],
            'ticker': cache_ttl_config['ticker'],
            'positions': cache_ttl_config['positions'],
            'orders': cache_ttl_config['orders'],
        }
        
        # API client configuration
        self.max_retries = api_config['max_retries']
        self.retry_delays = api_config['retry_delays']
        self.timeout_seconds = api_config['timeout_seconds']
        
        # Time synchronization
        self._server_time_offset = 0
        
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
                
                # Sincronizar tempo automaticamente após conexão
                self._sync_time()
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

    def _get_cache_key(self, method, *args, **kwargs):
        """Generate a cache key for the API request."""
        method_name = getattr(method, '__name__', str(method))
        return f"{method_name}_{hash(str(args) + str(sorted(kwargs.items())))}"
    
    def _is_cache_valid(self, cache_key, cache_type='default'):
        """Check if cached data is still valid."""
        if cache_key not in self._cache:
            return False
        
        cached_time, _ = self._cache[cache_key]
        ttl = self._cache_ttl[cache_type]
        
        return datetime.now() - cached_time < timedelta(seconds=ttl)
    
    def _get_cached_response(self, cache_key):
        """Get cached response if valid."""
        if cache_key in self._cache:
            _, response = self._cache[cache_key]
            return response
        return None
    
    def _cache_response(self, cache_key, response):
        """Cache API response with timestamp."""
        self._cache[cache_key] = (datetime.now(), response)
        
        # Clean old cache entries (keep only last configured amount)
        api_config = self.config['api_client']
        max_cache_entries = api_config['max_cache_entries']
        if len(self._cache) > max_cache_entries:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]
    
    def _sync_time(self):
        """Synchronize local time with Binance server time to fix signature issues."""
        try:
            if not self.client:
                log.warning("Cannot sync time - no client connection")
                return False
            
            # Get server time from Binance - try multiple times for accuracy
            server_times = []
            local_times = []
            
            for i in range(3):  # Sample 3 times for better accuracy
                try:
                    local_before = int(time.time() * 1000)
                    server_time_response = self.client.futures_time()
                    local_after = int(time.time() * 1000)
                    
                    server_time = server_time_response['serverTime']
                    # Use average of local times to account for request latency
                    local_time = (local_before + local_after) // 2
                    
                    server_times.append(server_time)
                    local_times.append(local_time)
                    
                    if i < 2:  # Small delay between samples
                        time.sleep(0.1)
                        
                except Exception as e:
                    log.warning(f"Time sync attempt {i+1} failed: {e}")
                    continue
            
            if not server_times:
                log.error("Failed to get server time for synchronization")
                return False
            
            # Calculate average time difference
            time_diffs = [server - local for server, local in zip(server_times, local_times)]
            avg_time_diff = sum(time_diffs) // len(time_diffs)
            
            log.info(f"Time sync - Server avg: {sum(server_times)//len(server_times)}, "
                    f"Local avg: {sum(local_times)//len(local_times)}, "
                    f"Avg diff: {avg_time_diff}ms (samples: {time_diffs})")
            
            # If difference is significant, warn user  
            api_config = self.config['api_client']
            warning_threshold = api_config['time_sync_warning_threshold_ms']
            critical_threshold = api_config['time_sync_critical_threshold_ms']
            
            if abs(avg_time_diff) > warning_threshold:
                log.warning(f"⚠️  Large time difference detected: {avg_time_diff}ms")
                log.warning("Consider synchronizing your system clock for better API performance")
                
                # For very large differences, force immediate time sync
                if abs(avg_time_diff) > critical_threshold:
                    log.error(f"🚨 CRITICAL: Time difference is {avg_time_diff/1000:.1f} seconds!")
                    log.error("This will cause all API signatures to fail.")
                    log.error("Attempting to force system time synchronization...")
                    
                    import subprocess
                    try:
                        # Try to sync system time (requires appropriate permissions)
                        result = subprocess.run(['sudo', 'ntpdate', '-s', 'time.nist.gov'], 
                                              capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            log.info("✅ System time synchronized successfully")
                        else:
                            log.warning("⚠️  Could not sync system time automatically")
                            log.warning("Please run: sudo ntpdate -s time.nist.gov")
                    except Exception as e:
                        log.warning(f"Time sync attempt failed: {e}")
                        log.warning("Please manually sync your system time")
            
            # Force timestamp synchronization by manually setting timestamp on client
            # This is more reliable than relying on client.timestamp_offset
            try:
                # Store the time offset for manual timestamp calculation
                self._server_time_offset = avg_time_diff
                
                # Try to set timestamp_offset if available - use MORE aggressive offset
                if hasattr(self.client, 'timestamp_offset'):
                    # Add extra buffer for network latency
                    timestamp_buffer = api_config['timestamp_buffer_ms']
                    adjusted_offset = avg_time_diff + timestamp_buffer
                    self.client.timestamp_offset = adjusted_offset
                    log.info(f"Set client.timestamp_offset = {adjusted_offset}ms (original: {avg_time_diff}ms + {timestamp_buffer}ms buffer)")
                
                # Alternative: patch the client's _get_request_kwargs method if needed
                # This ensures timestamp is correctly calculated for all requests
                original_get_request_kwargs = getattr(self.client, '_get_request_kwargs', None)
                if original_get_request_kwargs and not hasattr(self.client, '_timestamp_patched'):
                    # Store original method for potential restoration
                    self.client._original_get_request_kwargs = original_get_request_kwargs
                    
                    def patched_get_request_kwargs(*args, **kwargs):
                        result = original_get_request_kwargs(*args, **kwargs)
                        # Only patch if result is a dictionary with params
                        if isinstance(result, dict) and 'params' in result and isinstance(result['params'], dict):
                            if 'timestamp' in result['params']:
                                # Adjust timestamp with our calculated offset + buffer for large diffs
                                current_timestamp = result['params']['timestamp']
                                large_diff_buffer = api_config['timestamp_large_diff_buffer_ms']
                                normal_buffer = api_config['timestamp_buffer_ms']
                                buffer = large_diff_buffer if abs(self._server_time_offset) > critical_threshold else normal_buffer
                                adjusted_timestamp = current_timestamp + self._server_time_offset + buffer
                                result['params']['timestamp'] = adjusted_timestamp
                                log.debug(f"Adjusted timestamp: {current_timestamp} + {self._server_time_offset} + {buffer}ms buffer = {adjusted_timestamp}")
                        return result
                    
                    self.client._get_request_kwargs = patched_get_request_kwargs
                    self.client._timestamp_patched = True
                    log.debug("Patched client timestamp calculation")
                
                return True
                
            except Exception as e:
                log.error(f"Error applying time offset: {e}")
                return False
            
        except Exception as e:
            log.error(f"Error syncing time with Binance server: {e}")
            return False

    def _validate_and_normalize_params(self, params: dict) -> dict:
        """
        Validate and normalize API parameters to ensure proper signature generation.
        
        Args:
            params: Dictionary of API parameters
            
        Returns:
            Normalized parameters dictionary or None if validation fails
        """
        try:
            normalized_params = {}
            
            for key, value in params.items():
                # Ensure all values are strings (required for signature generation)
                if value is None:
                    continue  # Skip None values
                elif isinstance(value, bool):
                    # Convert boolean to lowercase string
                    normalized_params[key] = "true" if value else "false"
                elif isinstance(value, (int, float)):
                    # Convert numbers to strings
                    normalized_params[key] = str(value)
                elif isinstance(value, str):
                    # Keep strings as-is, but strip whitespace
                    normalized_params[key] = value.strip()
                else:
                    # Convert other types to string
                    normalized_params[key] = str(value)
            
            # Validate critical parameters
            if 'symbol' in normalized_params and not normalized_params['symbol']:
                log.error("Invalid symbol parameter: empty or None")
                return None
                
            if 'side' in normalized_params and normalized_params['side'] not in ['BUY', 'SELL']:
                log.error(f"Invalid side parameter: {normalized_params['side']}")
                return None
                
            if 'type' in normalized_params and not normalized_params['type']:
                log.error("Invalid type parameter: empty or None")
                return None
                
            # Validate quantity is positive
            if 'quantity' in normalized_params:
                try:
                    qty = float(normalized_params['quantity'])
                    if qty <= 0:
                        log.error(f"Invalid quantity: {qty} (must be positive)")
                        return None
                except ValueError:
                    log.error(f"Invalid quantity format: {normalized_params['quantity']}")
                    return None
            
            # Validate reduceOnly parameter format
            if 'reduceOnly' in normalized_params:
                reduce_only_val = normalized_params['reduceOnly'].lower()
                if reduce_only_val not in ['true', 'false']:
                    log.error(f"Invalid reduceOnly value: {normalized_params['reduceOnly']}")
                    return None
                normalized_params['reduceOnly'] = reduce_only_val
            
            log.debug(f"Parameter validation successful. Normalized {len(params)} parameters.")
            return normalized_params
            
        except Exception as e:
            log.error(f"Error validating/normalizing parameters: {e}")
            return None

    def _make_request(self, method, *args, **kwargs):
        """Faz uma requisição à API com tratamento de erros, tentativas e simulação no modo Shadow."""
        if not self.client:
            log.error("Cliente da API não está conectado. Tentando reconectar...")
            self._connect()
            if not self.client:
                log.error("Reconexão falhou. Não é possível fazer requisição à API.")
                return None

        # Check for cacheable endpoints to reduce rate limiting
        method_name = method.__name__ if hasattr(method, '__name__') else str(method)
        cache_key = self._get_cache_key(method, *args, **kwargs)
        
        # Determine cache type based on method name
        cache_type = 'default'
        if 'account' in method_name or 'balance' in method_name:
            cache_type = 'account'
        elif 'position' in method_name:
            cache_type = 'positions'
        elif 'ticker' in method_name:
            cache_type = 'ticker'
        
        # Return cached response if valid and for read-only operations
        if (cache_type in ['account', 'positions', 'ticker'] and 
            self._is_cache_valid(cache_key, cache_type)):
            log.debug(f"Returning cached response for {method_name}")
            return self._get_cached_response(cache_key)

        # --- Modo de Produção --- #
        retries = 0
        while retries < MAX_RETRIES:
            try:
                # Debug logging before making the request
                if log.getEffectiveLevel() <= logging.DEBUG:
                    method_name = getattr(method, '__name__', str(method))
                    log.debug(f"Making API request: {method_name}")
                    log.debug(f"  Args: {args}")
                    log.debug(f"  Kwargs: {kwargs}")
                    if hasattr(self, '_server_time_offset'):
                        log.debug(f"  Server time offset: {self._server_time_offset}ms")
                
                response = method(*args, **kwargs)
                method_name = getattr(method, '__name__', str(method))
                log.debug(
                    f"API call successful: {method_name} args={args} kwargs={kwargs}"
                )
                
                # Cache response for read-only operations
                if cache_type in ['account', 'positions', 'ticker']:
                    self._cache_response(cache_key, response)
                
                return response
            except (BinanceAPIException, BinanceRequestException) as e:
                # Handle specific error codes
                error_code = getattr(e, 'code', None)
                
                if error_code == -2022:
                    method_name = getattr(method, '__name__', str(method))
                    
                    # Check if this is a reduceOnly order rejection due to no position
                    if ('reduceOnly' in str(kwargs) and 
                        'ReduceOnly Order is rejected' in str(e.message)):
                        log.warning(
                            f"REDUCE_ONLY REJECTED (Code -2022): No position to close for {kwargs.get('symbol', 'unknown')} - "
                            f"This is normal when trying to close non-existent positions"
                        )
                        return None  # Don't retry, this is expected behavior
                    
                    log.error(
                        f"INVALID SIGNATURE (Code -2022): {e.message} - "
                        f"Signature verification failed. Method: {method_name}, Args: {args}, Kwargs: {kwargs}"
                    )
                    
                    # Enhanced retry logic for signature errors
                    if retries < 3:  # Allow up to 3 retries for signature issues
                        if retries == 0:
                            # First retry: sync time
                            log.warning("First signature retry: syncing time with server...")
                            sync_success = self._sync_time()
                            if sync_success:
                                log.info("Time sync successful, retrying request...")
                            else:
                                log.warning("Time sync failed, but retrying request anyway...")
                        elif retries == 1:
                            # Second retry: force re-sync with longer delay
                            log.warning("Second signature retry: force re-sync with delay...")
                            time.sleep(2)  # Longer delay
                            self._sync_time()
                        else:  # retries == 2
                            # Third retry: try without timestamp patching
                            log.warning("Third signature retry: removing timestamp patches...")
                            if hasattr(self.client, '_timestamp_patched'):
                                # Restore original method if patched
                                if hasattr(self.client, '_original_get_request_kwargs'):
                                    self.client._get_request_kwargs = self.client._original_get_request_kwargs
                                    delattr(self.client, '_timestamp_patched')
                                    log.debug("Restored original timestamp calculation")
                        
                        retries += 1
                        delay = min(2 ** retries, 8)  # Exponential backoff, max 8 seconds
                        log.info(f"Retrying signature request in {delay} seconds (attempt {retries}/3)...")
                        time.sleep(delay)
                        continue
                    else:
                        log.error("Signature still invalid after 3 retries. Possible causes:")
                        log.error("1. API credentials may be incorrect or expired")
                        log.error("2. System clock may be severely out of sync")
                        log.error("3. API parameters may be malformed")
                        method_name = getattr(method, '__name__', str(method))
                        log.error(f"Request details - Method: {method_name}, Args: {args}, Kwargs: {kwargs}")
                        return None
                elif error_code == -2011:
                    method_name = getattr(method, '__name__', str(method))
                    log.error(
                        f"UNKNOWN ORDER TYPE (Code -2011): {e.message} - "
                        f"Invalid order type or parameters. Method: {method_name}, Args: {args}, Kwargs: {kwargs}"
                    )
                    return None  # Don't retry invalid order type errors
                elif error_code == -1111:
                    log.error(
                        f"PRECISION ERROR (Code -1111): {e.message} - "
                        f"Invalid precision in order parameters. Check price/quantity formatting."
                    )
                    return None  # Don't retry precision errors
                elif error_code == -2010:
                    log.error(
                        f"INSUFFICIENT BALANCE (Code -2010): {e.message}"
                    )
                    return None  # Don't retry insufficient balance
                elif error_code == -1013:
                    log.error(
                        f"MIN_NOTIONAL ERROR (Code -1013): {e.message} - "
                        f"Order value too small. Increase quantity or check minimum notional requirements."
                    )
                    return None  # Don't retry min notional errors
                elif error_code == -1003:
                    # Rate limiting error - wait longer and use cached data if available
                    log.warning(
                        f"RATE LIMIT ERROR (Code -1003): {e.message} - "
                        f"Too many requests. Using cached data if available."
                    )
                    # For rate limits, try to return cached data even if slightly stale
                    if cache_key in self._cache:
                        cached_time, cached_response = self._cache[cache_key]
                        # Accept cache up to configured time old for rate limited requests
                        api_config = self.config['api_client']
                        cache_tolerance_minutes = api_config['rate_limit_cache_tolerance_minutes']
                        if datetime.now() - cached_time < timedelta(minutes=cache_tolerance_minutes):
                            log.info("Returning stale cached data due to rate limiting")
                            return cached_response
                    
                    # If no cache, wait longer for rate limits
                    if retries < MAX_RETRIES:
                        max_delay = api_config['rate_limit_max_delay_seconds']
                        delay = min(max_delay, RETRY_DELAY_SECONDS[retries - 1] * 3)  # 3x longer delay, max configured seconds
                        log.info(f"Rate limited. Waiting {delay} seconds before retry...")
                        time.sleep(delay)
                        retries += 1
                        continue
                    else:
                        log.error("Max retries reached for rate limited request")
                        return None
                
                log.warning(
                    f"API Error on attempt {retries + 1}: {e} (Code: {error_code}, Message: {e.message})"
                )
                retries += 1
                if retries < MAX_RETRIES:
                    delay = RETRY_DELAY_SECONDS[retries - 1]
                    log.info(f"Retrying API call in {delay} seconds...")
                    time.sleep(delay)
                else:
                    method_name = getattr(method, '__name__', str(method))
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
                    method_name = getattr(method, '__name__', str(method))
                    log.error(
                        f"Max retries reached after ConnectionError for API call {method_name}."
                    )
                    return None
            except Exception as e:
                method_name = getattr(method, '__name__', str(method))
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
        self, symbol, side, order_type, quantity, price=None, time_in_force=None, **kwargs
    ):
        # Validate required parameters
        if not symbol or not side or not order_type or not quantity:
            log.error(f"Missing required parameters: symbol={symbol}, side={side}, type={order_type}, quantity={quantity}")
            return None
        
        # Validate order types
        valid_order_types = ["MARKET", "LIMIT", "STOP_MARKET", "STOP", "TAKE_PROFIT_MARKET", "TAKE_PROFIT"]
        if order_type not in valid_order_types:
            log.error(f"Invalid order type: {order_type}. Valid types: {valid_order_types}")
            return None
        
        # Validate sides
        valid_sides = ["BUY", "SELL"]
        if side not in valid_sides:
            log.error(f"Invalid side: {side}. Valid sides: {valid_sides}")
            return None
        
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),  # Ensure quantity is string
        }
        
        # Handle price for price-based orders
        if price and order_type in ["LIMIT", "STOP", "TAKE_PROFIT"]:
            params["price"] = str(price)
        
        # Handle stopPrice for stop orders
        if "stopPrice" in kwargs:
            params["stopPrice"] = str(kwargs["stopPrice"])
            del kwargs["stopPrice"]  # Remove from kwargs to avoid duplication
        
        # Handle timeInForce for applicable orders
        if order_type in ["LIMIT", "STOP", "TAKE_PROFIT"]:
            if time_in_force:
                params["timeInForce"] = time_in_force
            elif "timeInForce" not in kwargs:
                params["timeInForce"] = "GTC"  # Default for orders that require timeInForce
        
        # Add any additional parameters first
        params.update(kwargs)
        
        # Handle reduce-only orders - Convert to string format for Binance API
        # This must happen AFTER params.update(kwargs) to ensure proper conversion
        if "reduceOnly" in params:
            reduce_only_value = params["reduceOnly"]
            if isinstance(reduce_only_value, bool):
                params["reduceOnly"] = "true" if reduce_only_value else "false"
            else:
                # Ensure string values are lowercase
                params["reduceOnly"] = str(reduce_only_value).lower()
        
        # Validate and normalize all parameters for signature generation
        params = self._validate_and_normalize_params(params)
        if params is None:
            log.error("Parameter validation failed")
            return None
        
        # Debug logging for signature generation (after parameter processing)
        log.info(f"Placing order ({self.operation_mode.upper()}): {params}")
        
        # Log detailed parameter information for debugging signature issues
        if log.getEffectiveLevel() <= logging.DEBUG:
            log.debug(f"Order parameters for signature generation:")
            for key, value in sorted(params.items()):
                log.debug(f"  {key}: {value} (type: {type(value).__name__})")
            
            # Log current timestamp info
            current_time = int(time.time() * 1000)
            offset = getattr(self, '_server_time_offset', 0)
            log.debug(f"Timestamp info - Local: {current_time}, Offset: {offset}, Adjusted: {current_time + offset}")
        
        return self._make_request(self.client.futures_create_order, **params)

    def cancel_futures_order(self, symbol, orderId):
        log.info(
            f"Cancelling order ({self.operation_mode.upper()}): symbol={symbol}, orderId={orderId}"
        )
        try:
            return self._make_request(
                self.client.futures_cancel_order, symbol=symbol, orderId=orderId
            )
        except BinanceAPIException as e:
            if e.code == -2011:
                log.warning(f"Order {orderId} for {symbol} not found or already executed - Code: {e.code}")
                return None
            else:
                raise e
    
    def cancel_order(self, symbol, orderId):
        """Alias for cancel_futures_order for compatibility."""
        return self.cancel_futures_order(symbol=symbol, orderId=orderId)

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
            return []  # Return empty list as we don't track real orders
        params = {"symbol": symbol} if symbol else {}
        return self._make_request(self.client.futures_get_open_orders, **params)

    def get_futures_open_orders(self, symbol=None):
        """Alias for get_open_futures_orders for compatibility."""
        return self.get_open_futures_orders(symbol=symbol)

    def get_spot_open_orders(self, symbol=None):
        """Get open orders in the spot market."""
        log.debug(
            f"Getting spot open orders ({self.operation_mode.upper()}): symbol={symbol}"
        )
        if self.operation_mode == "shadow":
            log.warning(
                "[SHADOW MODE] get_spot_open_orders called. Returning empty list. GridLogic should manage state."
            )
            return []  # Return empty list as we don't track real orders
        params = {"symbol": symbol} if symbol else {}
        return self._make_request(self.client.get_open_orders, **params)

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
    
    def get_futures_order_history(self, symbol=None, start_time=None, end_time=None, limit=1000):
        """
        Busca histórico de ordens de futuros das últimas 24h ou período especificado.
        Essencial para recuperar estado real após restart do sistema.
        """
        log.debug(f"Getting futures order history ({self.operation_mode.upper()}): symbol={symbol}")
        
        # Se não especificado, buscar últimas 24 horas
        if start_time is None:
            start_time = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
        if end_time is None:
            end_time = int(datetime.now().timestamp() * 1000)
        
        params = {
            'startTime': start_time,
            'endTime': end_time,
            'limit': limit
        }
        
        if symbol:
            params['symbol'] = symbol
            
        return self._make_request(self.client.futures_get_all_orders, **params)
    
    def get_futures_trade_history(self, symbol=None, start_time=None, end_time=None, limit=1000):
        """
        Busca histórico de trades executados de futuros.
        Usado para calcular PnL real e estado das posições.
        """
        log.debug(f"Getting futures trade history ({self.operation_mode.upper()}): symbol={symbol}")
        
        # Se não especificado, buscar últimas 24 horas
        if start_time is None:
            start_time = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
        if end_time is None:
            end_time = int(datetime.now().timestamp() * 1000)
        
        if not symbol:
            # Se não especificar símbolo, buscar para todos os símbolos com posições
            try:
                positions = self.get_futures_positions()
                all_trades = []
                
                for pos in positions:
                    if float(pos.get('positionAmt', 0)) != 0:  # Apenas posições ativas
                        symbol_trades = self._make_request(
                            self.client.futures_account_trades,
                            symbol=pos['symbol'],
                            startTime=start_time,
                            endTime=end_time,
                            limit=limit
                        )
                        if symbol_trades:
                            all_trades.extend(symbol_trades)
                
                return all_trades
            except Exception as e:
                log.error(f"Error getting trade history for all symbols: {e}")
                return []
        else:
            # Buscar para símbolo específico
            return self._make_request(
                self.client.futures_account_trades,
                symbol=symbol,
                startTime=start_time,
                endTime=end_time,
                limit=limit
            )
    
    def get_futures_income_history(self, symbol=None, income_type="REALIZED_PNL", start_time=None, end_time=None, limit=1000):
        """
        Busca histórico de income (PnL realizado, funding fees, etc.).
        Usado para calcular lucros/perdas reais do período.
        """
        log.debug(f"Getting futures income history ({self.operation_mode.upper()}): symbol={symbol}, type={income_type}")
        
        # Se não especificado, buscar últimas 24 horas
        if start_time is None:
            start_time = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
        if end_time is None:
            end_time = int(datetime.now().timestamp() * 1000)
        
        params = {
            'incomeType': income_type,
            'startTime': start_time,
            'endTime': end_time,
            'limit': limit
        }
        
        if symbol:
            params['symbol'] = symbol
            
        return self._make_request(self.client.futures_income_history, **params)

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
                order_params["closePosition"] = "true"
            
            if reduce_only:
                order_params["reduceOnly"] = "true"
            
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
