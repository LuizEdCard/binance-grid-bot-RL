# Lógica central para Grid Trading
# Suporta mercado Spot e Futuros, com RL decidindo entre os mercados

import time
from decimal import ROUND_DOWN, ROUND_UP, ROUND_HALF_UP, Decimal

import numpy as np  # Importa numpy para TA-Lib
import pandas as pd  # Importa pandas para manipulação de dados
from binance.enums import (
    ORDER_TYPE_LIMIT,
    TIME_IN_FORCE_GTC,
    ORDER_STATUS_NEW,
    SIDE_BUY,
    SIDE_SELL,
    ORDER_STATUS_FILLED,
    ORDER_STATUS_CANCELED,
    ORDER_STATUS_EXPIRED,
    ORDER_STATUS_REJECTED,
)

from utils.api_client import APIClient
from utils.logger import setup_logger
from utils.pair_logger import get_pair_logger
from utils.trade_logger import get_trade_logger
from utils.global_tp_sl_manager import get_global_tpsl_manager, add_position_to_global_tpsl, remove_position_from_global_tpsl
from utils.trading_state_recovery import TradingStateRecovery
log = setup_logger("grid_logic")

# Tentativa de importar TA-Lib
try:
    import talib

    talib_available = True
    log.info("Biblioteca TA-Lib encontrada e importada com sucesso para GridLogic.")
except ImportError:
    talib_available = False
    log.warning(
        "Biblioteca TA-Lib não encontrada para GridLogic. Algumas funcionalidades avançadas (espaçamento dinâmico baseado em ATR, verificações de padrões) estarão indisponíveis. Por favor, instale TA-Lib para funcionalidade completa (veja talib_installation_guide.md)."
    )
    # Não é necessário fallback direto aqui, a menos que indicadores específicos sejam calculados
    # dentro do próprio GridLogic


class GridLogic:
    """Encapsula a lógica central para estratégia de grid trading.

    Pode ser controlada por um agente RL para ajustes dinâmicos.
    Suporta modos Production (trading real) e Shadow (dados reais, ordens simuladas).
    Agora suporta tanto mercado Spot quanto Futuros.
    Opcionalmente usa TA-Lib para ajustes dinâmicos.
    """

    def __init__(
        self,
        symbol: str,
        config: dict,
        api_client: APIClient,
        operation_mode: str = "production",
        market_type: str = "futures",  # "futures" ou "spot"
        ws_client=None,  # WebSocket client for real-time data
    ):
        self.symbol = symbol
        self.config = config
        self.api_client = api_client
        self.ws_client = ws_client  # WebSocket for real-time price updates
        self.operation_mode = operation_mode.lower()
        self.market_type = market_type.lower()  # "futures" ou "spot"
        self.grid_config = config.get("grid", {})
        self.risk_config = config.get("risk_management", {})
        
        # Get kline interval from config
        self.kline_interval = config.get("http_api", {}).get("default_kline_interval", "3m")
        self.exchange_info = None
        self.symbol_info = None
        self.tick_size = None
        self.step_size = None
        self.min_notional = None
        self.quantity_precision = None
        self.price_precision = None

        # Parâmetros do grid - sempre priorizar valores do frontend
        initial_levels = int(config.get("initial_levels") or self.grid_config.get("initial_levels", 25))
        self.min_levels = int(config.get("min_levels") or self.grid_config.get("min_levels", 15))
        self.max_levels = int(config.get("max_levels") or self.grid_config.get("max_levels", 50))
        
        # Ensure initial levels is within min/max bounds
        self.num_levels = max(self.min_levels, min(initial_levels, self.max_levels))
        self.base_spacing_percentage = Decimal(str(config.get("initial_spacing_perc") or self.grid_config.get("initial_spacing_perc", "0.002")))
        # Usa estado real (production mode)
        if self.market_type == "spot":
            self.position = {
                "base_balance": Decimal("0"),
                "quote_balance": Decimal("0"),
                "avg_buy_price": Decimal("0"),
                "total_bought": Decimal("0"),
                "unrealized_pnl": Decimal("0"),
                }
        else:  # futures
            self.position = {
                    "positionAmt": Decimal("0"),
                    "entryPrice": Decimal("0"),
                    "markPrice": Decimal("0"),
                    "unRealizedProfit": Decimal("0"),
                    "liquidationPrice": Decimal("0"),
                }

        self.trade_history = []
        self.total_realized_pnl = Decimal("0")
        self.fees_paid = Decimal("0")
        self.total_trades = 0  # Contador para retreinamento do RL
        
        # Inicializar atributos para recuperação de grid
        self._recovery_attempted = False
        self._grid_recovered = False
        self._stopped = False
        self.grid_direction = "neutral"
        self.current_spacing_percentage = self.base_spacing_percentage
        self.active_grid_orders = {}
        self.open_orders = {}
        self.grid_levels = []  # Initialize grid_levels

        # Inicializar parâmetros de espaçamento dinâmico
        self.use_dynamic_spacing = self.grid_config.get("use_dynamic_spacing", False)
        self.dynamic_spacing_atr_period = self.grid_config.get("dynamic_spacing_atr_period", 14)
        self.dynamic_spacing_multiplier = Decimal(str(self.grid_config.get("dynamic_spacing_multiplier", "0.5")))
        
        # Extrair base e quote assets do símbolo
        self.base_asset = symbol.replace('USDT', '').replace('BUSD', '').replace('BTC', '').replace('ETH', '')
        if symbol.endswith('BTC'):
            self.quote_asset = 'BTC'
        elif symbol.endswith('ETH'):
            self.quote_asset = 'ETH'
        elif symbol.endswith('BUSD'):
            self.quote_asset = 'BUSD'
        else:
            self.quote_asset = 'USDT'

        # Initialize pair logger for detailed metrics logging
        from utils.pair_logger import get_multi_pair_logger
        multi_pair_logger = get_multi_pair_logger()
        self.pair_logger = multi_pair_logger.get_pair_logger(self.symbol)
        
        # Initialize trade logger for separate trade logs
        self.trade_logger = get_trade_logger()
        
        # Initialize global TP/SL manager (singleton) - SEMPRE ATIVAR
        self.tpsl_manager = get_global_tpsl_manager(self.api_client, self.config)
        if self.tpsl_manager:
            # O start_monitoring será chamado apenas uma vez pelo singleton
            log.info(f"[{self.symbol}] Conectado ao Global TP/SL Manager com SL agressivo de 5%")
        else:
            log.warning(f"[{self.symbol}] Falha ao conectar com Global TP/SL Manager")
        
        # Initialize trading state recovery system
        self.state_recovery = TradingStateRecovery(self.api_client)
        self.recovered_state = None
        self.recovery_initialized = False
        
        # Initialize TP/SL position tracking to prevent duplicates
        self._active_tpsl_positions = set()
        self._last_position_amt = Decimal("0")
        
        # Initialize metrics tracking variables
        self.last_price_24h = None
        self.current_rsi = 0.0
        self.current_atr = 0.0
        self.current_adx = 0.0

        log.info(
            f"[{self.symbol}] GridLogic inicializado no modo {self.operation_mode.upper()} para mercado {self.market_type.upper()}. Espaçamento Dinâmico (ATR): {self.use_dynamic_spacing}"
        )
        
        # Initialize leverage for futures trading
        if self.market_type == "futures":
            self._initialize_leverage()
        
        if self.use_dynamic_spacing and not talib_available:
            log.warning(
                f"[{self.symbol}] Espaçamento dinâmico solicitado mas TA-Lib não encontrado. Voltando para espaçamento fixo."
            )
            self.use_dynamic_spacing = False

    def _initialize_leverage(self):
        """Initialize leverage for futures trading to ensure proper configuration."""
        try:
            # Get leverage from config
            leverage = self.config.get("grid", {}).get("futures", {}).get("leverage", 10)
            
            log.info(f"[{self.symbol}] Setting initial leverage to {leverage}x for futures trading")
            
            # Attempt to set leverage
            result = self.api_client.change_leverage(self.symbol, leverage)
            
            if result:
                actual_leverage = result.get("leverage", leverage)
                log.info(f"[{self.symbol}] ✅ Leverage successfully set to {actual_leverage}x")
                
                # Verify the leverage was applied correctly
                if int(actual_leverage) != int(leverage):
                    log.warning(
                        f"[{self.symbol}] ⚠️  Requested leverage {leverage}x but got {actual_leverage}x. "
                        f"This might be due to Binance limits for this symbol."
                    )
            else:
                log.error(f"[{self.symbol}] ❌ Failed to set leverage to {leverage}x")
                
        except Exception as e:
            log.error(f"[{self.symbol}] Error initializing leverage: {e}")

        if not self._initialize_symbol_info():
            raise ValueError(
                f"[{self.symbol}] Falha ao inicializar informações do símbolo. Não é possível iniciar GridLogic."
            )
        
        # Initialize trading state recovery (run once per symbol)
        self._initialize_state_recovery()

    def _initialize_symbol_info(self) -> bool:
        """Inicializa informações do símbolo para Spot ou Futuros com validação melhorada."""
        log.info(f"[{self.symbol}] Inicializando informações de exchange para mercado {self.market_type.upper()}...")
        
        # 1. Validação prévia do símbolo
        if not self.symbol or len(self.symbol) < 3:
            log.error(f"[{self.symbol}] Símbolo inválido ou muito curto")
            return False
        
        # 2. Busca informações de exchange baseado no tipo de mercado
        try:
            if self.market_type == "spot":
                self.exchange_info = self.api_client.get_spot_exchange_info()
            else:  # futures
                self.exchange_info = self.api_client.get_exchange_info()
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao buscar exchange info: {e}")
            return False
            
        if not self.exchange_info or 'symbols' not in self.exchange_info:
            log.error(f"[{self.symbol}] Falha ao buscar informações de exchange ou dados inválidos.")
            return False
        
        # 3. Buscar símbolo com validação de status
        for item in self.exchange_info.get("symbols", []):
            if item["symbol"] == self.symbol:
                # Verificar se o símbolo está ativo
                status = item.get("status", "").upper()
                if status != "TRADING":
                    log.error(f"[{self.symbol}] Símbolo não está em status TRADING. Status atual: {status}")
                    return False
                
                self.symbol_info = item
                log.info(f"[{self.symbol}] ✅ Símbolo encontrado e válido no mercado {self.market_type}")
                break
                
        if not self.symbol_info:
            log.error(f"[{self.symbol}] Symbol not found in {self.market_type} market. Available symbols count: {len(self.exchange_info.get('symbols', []))}")
            # Log some similar symbols for debugging
            similar_symbols = [s['symbol'] for s in self.exchange_info.get('symbols', []) 
                             if (self.symbol[:3] in s['symbol'] or self.symbol[-4:] in s['symbol']) 
                             and s.get('status', '').upper() == 'TRADING'][:5]
            if similar_symbols:
                log.info(f"[{self.symbol}] Similar active symbols found: {similar_symbols}")
            return False

        # Obter precisões dos dados do símbolo ou calcular dos filtros
        self.quantity_precision = self.symbol_info.get("quantityPrecision")
        self.price_precision = self.symbol_info.get("pricePrecision")
        
        # Se precisões não estão disponíveis, calcular dos filtros
        if self.quantity_precision is None or self.price_precision is None:
            # Calcular precision baseado no stepSize e tickSize
            if self.quantity_precision is None:
                # Usar baseAssetPrecision ou calcular do stepSize
                self.quantity_precision = self.symbol_info.get("baseAssetPrecision", 8)
                
            if self.price_precision is None:
                # Usar quoteAssetPrecision ou calcular do tickSize  
                self.price_precision = self.symbol_info.get("quoteAssetPrecision", 8)
        price_filter = next(
            (
                f
                for f in self.symbol_info["filters"]
                if f["filterType"] == "PRICE_FILTER"
            ),
            None,
        )
        lot_size_filter = next(
            (f for f in self.symbol_info["filters"] if f["filterType"] == "LOT_SIZE"),
            None,
        )
        min_notional_filter = next(
            (
                f
                for f in self.symbol_info["filters"]
                if f["filterType"] == "MIN_NOTIONAL"
            ),
            None,
        )

        if price_filter:
            self.tick_size = Decimal(price_filter["tickSize"])
        else:
            log.error(f"[{self.symbol}] Filtro de preço não encontrado.")
            return False
        if lot_size_filter:
            self.step_size = Decimal(lot_size_filter["stepSize"])
        else:
            log.error(f"[{self.symbol}] Filtro de tamanho de lote não encontrado.")
            return False
        if min_notional_filter:
            # Para Spot, usar 'minNotional', para Futuros usar 'notional'
            notional_key = "minNotional" if self.market_type == "spot" else "notional"
            self.min_notional = Decimal(
                min_notional_filter.get(notional_key, "5")
            )  # Padrão 5 se chave estiver ausente
        else:
            market_lot_filter = next(
                (
                    f
                    for f in self.symbol_info["filters"]
                    if f["filterType"] == "MARKET_LOT_SIZE"
                ),
                None,
            )
            if market_lot_filter:
                self.min_notional = Decimal("5")  # Padrão para 5 USDT
                log.warning(
                    f"[{self.symbol}] Filtro MIN_NOTIONAL ausente, usando padrão: {self.min_notional} USDT"
                )
            else:
                log.error(
                    f"[{self.symbol}] Filtro Min Notional (e fallback) não encontrado."
                )
                return False

        log.info(
            f"[{self.symbol}] Tick: {self.tick_size}, Step: {self.step_size}, MinNotional: {self.min_notional}, PricePrec: {self.price_precision}, QtyPrec: {self.quantity_precision} (Mercado: {self.market_type.upper()})"
        )
        if not all(
            [
                self.tick_size,
                self.step_size,
                self.min_notional,
                self.quantity_precision is not None,
                self.price_precision is not None,
            ]
        ):
            log.error(
                f"[{self.symbol}] Falha ao inicializar todos os filtros/precisão necessários do símbolo."
            )
            return False
        return True
    
    def _initialize_state_recovery(self):
        """
        Inicializa recuperação de estado baseada no histórico real da Binance.
        Recupera PnL, posições e capital investido das últimas 24h.
        """
        if self.recovery_initialized:
            return  # Evitar múltiplas inicializações
            
        try:
            log.info(f"[{self.symbol}] 🔄 Iniciando recuperação de estado do trading...")
            
            # Recuperar estado das últimas 24 horas
            self.recovered_state = self.state_recovery.recover_trading_state(hours_back=24)
            
            if self.recovered_state and not self.recovered_state.get('fallback', False):
                # Estado recuperado com sucesso
                summary = self.recovered_state['trading_summary']
                
                log.info(f"[{self.symbol}] ✅ Estado recuperado com sucesso!")
                log.info(f"[{self.symbol}] 💰 PnL Total: ${summary['total_pnl']:.2f} USDT")
                log.info(f"[{self.symbol}] 💵 Capital Investido: ${summary['total_invested']:.2f} USDT")
                log.info(f"[{self.symbol}] 📊 ROI: {summary['roi_percentage']:.2f}%")
                log.info(f"[{self.symbol}] 📈 Posições: {summary['profitable_positions']} lucrativas, {summary['losing_positions']} com perda")
                
                # Atualizar métricas do pair_logger com dados reais
                if self.symbol in self.recovered_state['positions']:
                    position_metrics = self.state_recovery.update_position_metrics(
                        self.symbol, self.recovered_state
                    )
                    
                    # Atualizar pair_logger com dados reais recuperados
                    self.pair_logger.update_metrics(
                        realized_pnl=position_metrics.get('realized_pnl', 0.0),
                        total_invested=position_metrics.get('total_invested', 0.0),
                        total_orders=position_metrics.get('orders_count', 0),
                        roi_percentage=position_metrics.get('roi_percentage', 0.0)
                    )
                    
                    # Atualizar TP/SL se disponível
                    tp_price = position_metrics.get('tp_price')
                    sl_price = position_metrics.get('sl_price')
                    if tp_price or sl_price:
                        self.pair_logger.update_tp_sl(
                            tp_price=tp_price,
                            sl_price=sl_price
                        )
                    
                    log.info(f"[{self.symbol}] 📋 Métricas atualizadas com dados reais da Binance")
                
            else:
                log.warning(f"[{self.symbol}] ⚠️ Recuperação de estado falhou, usando dados padrão")
                
            self.recovery_initialized = True
            
        except Exception as e:
            log.error(f"[{self.symbol}] ❌ Erro na recuperação de estado: {e}")
            self.recovery_initialized = True  # Marcar como tentado

    def _format_price(self, price):
        """Formata preço de acordo com as regras do símbolo com validação de precisão."""
        if self.tick_size is None or self.price_precision is None:
            return None
        try:
            # Use ROUND_HALF_UP para arredondar corretamente para o tick size mais próximo
            price_decimal = Decimal(str(price))
            adjusted_price = (price_decimal / self.tick_size).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            ) * self.tick_size
            
            # Use ONLY the price_precision from exchange info - never exceed it
            # This prevents "Precision is over the maximum defined" errors
            formatted_price = f"{adjusted_price:.{int(self.price_precision)}f}"
            
            # Only remove trailing zeros if it doesn't reduce precision below minimum
            if '.' in formatted_price:
                # Count decimal places after removing trailing zeros
                test_format = formatted_price.rstrip('0').rstrip('.')
                decimal_places = 0 if '.' not in test_format else len(test_format.split('.')[1])
                
                # Only use trimmed format if it maintains minimum precision for tick_size
                tick_decimal_places = max(0, -self.tick_size.as_tuple().exponent)
                if decimal_places >= tick_decimal_places:
                    formatted_price = test_format
            
            return formatted_price
            
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao formatar preço {price}: {e}")
            return None

    def _format_quantity(self, quantity, current_price=None):
        """Formata quantidade de acordo com as regras do símbolo com verificação de notional."""
        if self.step_size is None or self.quantity_precision is None:
            return None
        try:
            # Calculate proper precision based on step_size
            step_size_decimal = Decimal(str(self.step_size))
            quantity_decimal = Decimal(str(quantity))
            
            # Calculate how many decimal places we need based on step_size
            step_decimal_places = max(0, -step_size_decimal.as_tuple().exponent)
            effective_precision = min(int(step_decimal_places), int(self.quantity_precision))
            
            # Adjust quantity to step_size (round down to avoid exceeding balance)
            steps = (quantity_decimal / step_size_decimal).quantize(Decimal("1"), rounding=ROUND_DOWN)
            adjusted_quantity = steps * step_size_decimal
            
            # Ensure minimum quantity
            if adjusted_quantity == Decimal("0") and quantity_decimal > Decimal("0"):
                adjusted_quantity = step_size_decimal
            
            # Check minimum notional if price provided
            if current_price and adjusted_quantity > 0:
                min_notional = self.min_notional if self.min_notional else Decimal("5")
                notional_value = adjusted_quantity * Decimal(str(current_price))
                
                if notional_value < min_notional:
                    # Calculate minimum quantity needed
                    min_quantity_needed = (min_notional / Decimal(str(current_price)))
                    min_steps = (min_quantity_needed / step_size_decimal).quantize(Decimal("1"), rounding=ROUND_UP)
                    adjusted_quantity = min_steps * step_size_decimal
                    
                    log.info(f"[{self.symbol}] Adjusted quantity from {quantity} to {adjusted_quantity} to meet min_notional {min_notional}")
            
            # Use ONLY the quantity_precision from exchange info - never exceed it
            formatted_quantity = f"{adjusted_quantity:.{int(self.quantity_precision)}f}"
            
            # Only remove trailing zeros if it doesn't reduce precision below minimum  
            if '.' in formatted_quantity:
                # Count decimal places after removing trailing zeros
                test_format = formatted_quantity.rstrip('0').rstrip('.')
                decimal_places = 0 if '.' not in test_format else len(test_format.split('.')[1])
                
                # Only use trimmed format if it maintains minimum precision for step_size
                if decimal_places >= step_decimal_places:
                    formatted_quantity = test_format
            
            return formatted_quantity
            
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao formatar quantidade {quantity}: {e}")
            return None

    def _check_min_notional(self, price, quantity):
        """Verifica se a ordem atende ao valor nocional mínimo com logs detalhados."""
        min_notional = self.min_notional if self.min_notional else Decimal("5")
        try:
            price_decimal = Decimal(str(price))
            quantity_decimal = Decimal(str(quantity))
            notional_value = price_decimal * quantity_decimal
            meets = notional_value >= min_notional
            
            if not meets:
                log.warning(
                    f"[{self.symbol}] FAILED min_notional check: {notional_value:.8f} USDT < {min_notional} USDT "
                    f"(Price: {price}, Qty: {quantity}, StepSize: {self.step_size})"
                )
            else:
                log.debug(
                    f"[{self.symbol}] PASSED min_notional check: {notional_value:.8f} USDT >= {min_notional} USDT"
                )
            return meets
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao verificar nocional mínimo: {e}")
            return False

    def _get_ticker(self):
        """Obtém ticker baseado no tipo de mercado."""
        if self.market_type == "spot":
            return self.api_client.get_spot_ticker(symbol=self.symbol)
        else:  # futures
            return self.api_client.get_futures_ticker(symbol=self.symbol)
    
    def _get_current_price_from_ticker(self, ticker):
        """Extrai preço atual do ticker, lidando com diferentes formatos (spot vs futures)."""
        if not ticker:
            return None
        
        # Para futures: usa 'price'
        if self.market_type == "futures" and "price" in ticker:
            return float(ticker["price"])
        
        # Para spot: usa 'lastPrice'
        if self.market_type == "spot" and "lastPrice" in ticker:
            return float(ticker["lastPrice"])
        
        # Fallback: tenta ambos os campos
        if "lastPrice" in ticker:
            return float(ticker["lastPrice"])
        elif "price" in ticker:
            return float(ticker["price"])
        
        return None

    def _get_real_time_price(self):
        """Get real-time price from WebSocket if available, otherwise fallback to API."""
        if self.ws_client:
            # Try to get real-time price from simple WebSocket
            price = self.ws_client.get_price(self.symbol)
            if price is not None:
                log.debug(f"[{self.symbol}] Using WebSocket real-time price: ${price}")
                return price
        
        # Fallback to API ticker
        ticker = self._get_ticker()
        if ticker:
            return self._get_current_price_from_ticker(ticker)
        
        return None

    def _get_klines(self, interval="1h", limit=50):
        """Obtém klines baseado no tipo de mercado."""
        if self.market_type == "spot":
            return self.api_client.get_spot_klines(symbol=self.symbol, interval=interval, limit=limit)
        else:  # futures
            return self.api_client.get_futures_klines(symbol=self.symbol, interval=interval, limit=limit)

    def _place_order_unified(self, side, price_str, qty_str):
        """Coloca ordem baseado no tipo de mercado com proteção contra margem insuficiente."""
        log.info(
            f"[{self.symbol} - {self.operation_mode.upper()}] Colocando ordem {side} LIMIT no mercado {self.market_type.upper()} em {price_str}, Qtd: {qty_str}"
        )
        try:
            # NOVO: Verificar saldo antes de tentar colocar ordem
            if self.market_type == "futures":
                try:
                    futures_balance = self.api_client.get_futures_balance()
                    if futures_balance:
                        for asset in futures_balance:
                            if asset.get("asset") == "USDT":
                                available = float(asset.get("availableBalance", "0"))
                                if available < 1.0:  # Menos de $1 disponível
                                    log.warning(f"[{self.symbol}] 🚨 MARGEM INSUFICIENTE: Apenas ${available:.2f} disponível - PAUSANDO colocação de ordens")
                                    self.pair_logger.log_error(f"⚠️ Margem insuficiente: ${available:.2f} - Ordem cancelada")
                                    return None
                                break
                except Exception as e:
                    log.debug(f"[{self.symbol}] Erro ao verificar saldo futures: {e}")
            
            if self.market_type == "spot":
                # Ordem no mercado Spot
                order = self.api_client.place_spot_order(
                    symbol=self.symbol,
                    side=side,
                    order_type=ORDER_TYPE_LIMIT,
                    quantity=qty_str,
                    price=price_str,
                    timeInForce=TIME_IN_FORCE_GTC,
                )
            else:  # futures
                # Ordem no mercado Futuros
                order = self.api_client.place_futures_order(
                    symbol=self.symbol,
                    side=side,
                    order_type=ORDER_TYPE_LIMIT,
                    quantity=qty_str,
                    price=price_str,
                    timeInForce=TIME_IN_FORCE_GTC,
                )
            
            if order and "orderId" in order:
                order_id = order["orderId"]
                log.info(
                    f"[{self.symbol}] Ordem {side} colocada com sucesso {order_id} em {price_str} no mercado {self.market_type.upper()}"
                )
                # Armazena detalhes da ordem
                self.open_orders[order_id] = order
                
                # Log order event to pair_logger
                try:
                    self.pair_logger.log_order_event(
                        side=side,
                        price=float(price_str),
                        quantity=float(qty_str),
                        order_type="GRID"
                    )
                except Exception as e:
                    log.debug(f"[{self.symbol}] Erro ao registrar ordem no pair_logger: {e}")
                
                return order_id
            else:
                log.error(
                    f"[{self.symbol}] Falha ao colocar ordem {side} em {price_str}. Resposta: {order}"
                )
                return None
        except Exception as e:
            # NOVO: Tratamento específico para erro de margem insuficiente
            error_str = str(e)
            if "2019" in error_str or "Margin is insufficient" in error_str:
                log.error(f"[{self.symbol}] 🚨 MARGEM INSUFICIENTE detectada - parando colocação de ordens")
                self.pair_logger.log_error("🛑 Sistema pausado: Margem insuficiente detectada")
                
                # Marcar que este par tem problemas de margem
                if not hasattr(self, '_margin_insufficient_flag'):
                    self._margin_insufficient_flag = True
                    log.error(f"[{self.symbol}] 💡 AÇÃO NECESSÁRIA: Transferir USDT para conta Futures ou fechar posições")
                
                return None
            else:
                log.error(
                    f"[{self.symbol}] Exceção ao colocar ordem {side} em {price_str}: {e}"
                )
                return None

    def _cancel_order_unified(self, order_id):
        """Cancela ordem baseado no tipo de mercado."""
        try:
            if self.market_type == "spot":
                success = self.api_client.cancel_spot_order(
                    symbol=self.symbol, orderId=order_id
                )
            else:  # futures
                success = self.api_client.cancel_futures_order(
                    symbol=self.symbol, orderId=order_id
                )
            return success
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao cancelar ordem {order_id}: {e}")
            return False

    def _get_order_status_unified(self, order_id):
        """Obtém status da ordem baseado no tipo de mercado."""
        try:
            if self.market_type == "spot":
                return self.api_client.get_spot_order_status(
                    symbol=self.symbol, orderId=order_id
                )
            else:  # futures
                return self.api_client.get_futures_order_status(
                    symbol=self.symbol, orderId=order_id
                )
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao obter status da ordem {order_id}: {e}")
            return None

    def update_grid_parameters(
        self, num_levels=None, spacing_percentage=None, direction=None
    ):
        """Atualiza parâmetros do grid (agente RL ainda controla parâmetros base)."""
        updated = False
        if num_levels is not None and num_levels != self.num_levels:
            self.num_levels = num_levels if num_levels % 2 == 0 else num_levels + 1
            log.info(
                f"[{self.symbol}] Agente RL atualizou num_levels para: {self.num_levels}"
            )
            updated = True
        if (
            spacing_percentage is not None
            and spacing_percentage != self.base_spacing_percentage
        ):
            self.base_spacing_percentage = Decimal(str(spacing_percentage))
            log.info(
                f"[{self.symbol}] Agente RL atualizou base_spacing_percentage para: {self.base_spacing_percentage}"
            )
            # Recalcula espaçamento atual se dinâmico estiver desligado
            if not self.use_dynamic_spacing:
                self.current_spacing_percentage = self.base_spacing_percentage
            updated = True
        if (
            direction is not None
            and direction in ["long", "short", "neutral"]
            and direction != self.grid_direction
        ):
            self.grid_direction = direction
            log.info(
                f"[{self.symbol}] Agente RL atualizou grid_direction para: {self.grid_direction}"
            )
            updated = True
        if updated:
            # Redefine grid no próximo ciclo se parâmetros mudaram
            self.grid_levels = []
            self.cancel_active_grid_orders()
            log.info(
                f"[{self.symbol}] Parâmetros do grid atualizados pelo agente RL. Grid será redefinido."
            )

    def _update_dynamic_spacing(self):
        """Atualiza current_spacing_percentage baseado no ATR se espaçamento dinâmico estiver habilitado."""
        if not self.use_dynamic_spacing or not talib_available:
            self.current_spacing_percentage = self.base_spacing_percentage
            return

        try:
            # Busca klines recentes (ex: 1h, suficiente para cálculo de ATR)
            # Precisa de pelo menos atr_period + 1 candles
            limit = self.dynamic_spacing_atr_period + 5  # Adiciona buffer
            # Use configured interval from config
            interval = getattr(self, 'kline_interval', '3m')
            klines = self._get_klines(interval=interval, limit=limit)
            if not klines or len(klines) < self.dynamic_spacing_atr_period:
                log.warning(
                    f"[{self.symbol}] Dados de kline insuficientes ({len(klines) if klines else 0}) para espaçamento ATR dinâmico. Usando espaçamento base."
                )
                self.current_spacing_percentage = self.base_spacing_percentage
                return

            # Prepara dados para TA-Lib
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
            high_prices = pd.to_numeric(df["High"]).values
            low_prices = pd.to_numeric(df["Low"]).values
            close_prices = pd.to_numeric(df["Close"]).values

            # Calcula ATR
            atr_series = talib.ATR(
                high_prices,
                low_prices,
                close_prices,
                timeperiod=self.dynamic_spacing_atr_period,
            )
            latest_atr = (
                atr_series[~np.isnan(atr_series)][-1]
                if not np.all(np.isnan(atr_series))
                else None
            )
            last_close_price = close_prices[-1]

            if latest_atr is not None and last_close_price > 0:
                atr_percentage = Decimal(str(latest_atr)) / Decimal(
                    str(last_close_price)
                )
                # Combina espaçamento base com componente ATR
                # Exemplo: spacing = base + atr_perc * multiplicador
                dynamic_spacing = self.base_spacing_percentage + (
                    atr_percentage * self.dynamic_spacing_multiplier
                )
                # Adiciona limites para prevenir espaçamento extremo
                min_spacing = self.base_spacing_percentage / Decimal("2")
                max_spacing = self.base_spacing_percentage * Decimal("3")
                self.current_spacing_percentage = max(
                    min_spacing, min(max_spacing, dynamic_spacing)
                )
                log.info(
                    f"[{self.symbol}] Espaçamento dinâmico atualizado: ATR={latest_atr:.4f}, ATR%={atr_percentage*100:.3f}%, Novo Espaçamento%={self.current_spacing_percentage*100:.3f}%"
                )
            else:
                log.warning(
                    f"[{self.symbol}] Não foi possível calcular ATR válido ou preço para espaçamento dinâmico. Usando espaçamento base."
                )
                self.current_spacing_percentage = self.base_spacing_percentage

        except Exception as e:
            log.error(
                f"[{self.symbol}] Erro ao atualizar espaçamento dinâmico: {e}", exc_info=True
            )
            self.current_spacing_percentage = self.base_spacing_percentage

    def _get_hft_grid_range(self, current_price: float):
        """Get optimal grid range using Bollinger Bands, Keltner Channels e VWAP para HFT."""
        try:
            upper_bound = current_price * 1.02  # Default fallback 2%
            lower_bound = current_price * 0.98
            center_price = current_price
            
            # 1. BOLLINGER BANDS como range primário
            if hasattr(self, 'bb_upper') and hasattr(self, 'bb_lower') and hasattr(self, 'bb_middle'):
                # Usar BB como range do grid se disponível
                bb_range = (self.bb_upper - self.bb_lower) / self.bb_middle
                
                # Se BB width < 2%, expandir um pouco para HFT
                if bb_range < 0.02:
                    expansion_factor = 1.2
                    bb_center = self.bb_middle
                    bb_half_range = (self.bb_upper - self.bb_lower) / 2 * expansion_factor
                    upper_bound = bb_center + bb_half_range
                    lower_bound = bb_center - bb_half_range
                else:
                    upper_bound = self.bb_upper
                    lower_bound = self.bb_lower
                
                center_price = self.bb_middle
                log.debug(f"[{self.symbol}] BB Range: {lower_bound:.6f} - {upper_bound:.6f} (width: {bb_range:.1%})")
            
            # 2. KELTNER CHANNELS como confirmação/expansão
            if hasattr(self, 'kc_upper') and hasattr(self, 'kc_lower'):
                # Se KC é mais amplo que BB, usar KC para capture mais movimentos
                kc_range = (self.kc_upper - self.kc_lower) / current_price
                bb_range_calc = (upper_bound - lower_bound) / current_price
                
                if kc_range > bb_range_calc * 1.1:  # KC 10% maior que BB range
                    upper_bound = self.kc_upper
                    lower_bound = self.kc_lower
                    log.debug(f"[{self.symbol}] Usando KC range (mais amplo): {lower_bound:.6f} - {upper_bound:.6f}")
            
            # 3. VWAP como referência de centro
            if hasattr(self, 'vwap') and self.vwap > 0:
                # Usar VWAP como centro se próximo do preço atual (dentro de 1%)
                vwap_distance = abs(self.vwap - current_price) / current_price
                if vwap_distance < 0.01:  # VWAP dentro de 1%
                    center_price = self.vwap
                    log.debug(f"[{self.symbol}] Using VWAP as center: {self.vwap:.6f}")
            
            # 4. ATR-based adjustment para spacing mais dinâmico
            if hasattr(self, 'current_atr') and self.current_atr > 0:
                atr_perc = self.current_atr / current_price
                # Se ATR é alto, grid mais espaçado; se baixo, mais apertado
                if atr_perc > 0.01:  # ATR > 1%
                    # High volatility - expand range but keep levels
                    range_expansion = 1.0 + (atr_perc - 0.01) * 2  # Scale expansion
                    current_range = upper_bound - lower_bound
                    range_center = (upper_bound + lower_bound) / 2
                    half_expanded_range = (current_range * range_expansion) / 2
                    upper_bound = range_center + half_expanded_range
                    lower_bound = range_center - half_expanded_range
                    log.debug(f"[{self.symbol}] ATR expansion: {atr_perc:.1%} -> range expanded by {range_expansion:.1f}x")
            
            # 5. Safety checks
            max_range = current_price * 0.05  # Max 5% range
            min_range = current_price * 0.004  # Min 0.4% range for HFT
            
            current_range = upper_bound - lower_bound
            if current_range > max_range:
                # Range too wide - compress
                range_center = (upper_bound + lower_bound) / 2
                upper_bound = range_center + max_range / 2
                lower_bound = range_center - max_range / 2
            elif current_range < min_range:
                # Range too narrow - expand for HFT
                range_center = (upper_bound + lower_bound) / 2
                upper_bound = range_center + min_range / 2
                lower_bound = range_center - min_range / 2
            
            return {
                'upper_bound': upper_bound,
                'lower_bound': lower_bound,
                'center_price': center_price,
                'range_percent': (upper_bound - lower_bound) / current_price * 100
            }
            
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao calcular HFT grid range: {e}")
            # Fallback para range básico
            return {
                'upper_bound': current_price * 1.015,  # 1.5% up
                'lower_bound': current_price * 0.985,  # 1.5% down
                'center_price': current_price,
                'range_percent': 3.0
            }

    def _adjust_dynamic_levels(self, current_price: float):
        """Adjust grid levels dynamically based on volatility and market conditions."""
        try:
            # Calculate current volatility from price history
            volatility = 0.01  # Default volatility
            if len(self.price_history) >= 20:
                volatility = float(np.std(self.price_history[-20:]) / np.mean(self.price_history[-20:]))
            
            # Calculate number of orders currently active
            active_orders = len([order for order in self.orders if order.get("status") == "NEW"])
            
            # Dynamic level calculation based on:
            # 1. Volatility (higher volatility = more levels)
            # 2. Performance (profitable pairs get more levels)
            # 3. Available capital
            
            # Base calculation: volatility factor
            volatility_factor = min(2.0, max(0.5, volatility * 50))  # Scale volatility to 0.5-2.0 range
            
            # Performance factor
            performance_factor = 1.0
            if hasattr(self, 'total_profit') and self.total_profit:
                if float(self.total_profit) > 0:
                    performance_factor = 1.3  # Increase levels for profitable pairs
                elif float(self.total_profit) < -1:
                    performance_factor = 0.8  # Decrease levels for losing pairs
            
            # Calculate new levels
            base_levels = (self.min_levels + self.max_levels) // 2  # Start with middle value
            adjusted_levels = int(base_levels * volatility_factor * performance_factor)
            
            # Ensure within bounds
            new_levels = max(self.min_levels, min(adjusted_levels, self.max_levels))
            
            # Only update if significantly different (avoid constant changes)
            if abs(new_levels - self.num_levels) >= 3:
                old_levels = self.num_levels
                self.num_levels = new_levels
                log.info(
                    f"[{self.symbol}] 📊 Grid dinâmico: {old_levels} → {new_levels} níveis "
                    f"(vol: {volatility:.3f}, perf: {performance_factor:.1f})"
                )
            
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao ajustar níveis dinâmicos: {e}")

    def define_grid_levels(self, current_price: float):
        """Define níveis do grid baseado no preço atual usando HFT com Bollinger Bands."""
        # Adjust grid levels dynamically based on volatility and market conditions
        self._adjust_dynamic_levels(current_price)
        
        # 1. Obter range HFT usando Bollinger Bands, Keltner Channels e VWAP
        hft_range = self._get_hft_grid_range(current_price)
        
        # 2. Atualiza espaçamento dinâmico primeiro se habilitado
        if self.use_dynamic_spacing:
            self._update_dynamic_spacing()
        else:
            self.current_spacing_percentage = self.base_spacing_percentage

        # 3. Log do range HFT
        upper_bound = hft_range['upper_bound']
        lower_bound = hft_range['lower_bound']
        center_price_hft = hft_range['center_price']
        range_percent = hft_range['range_percent']
        
        log.info(
            f"[{self.symbol}] 🎯 HFT Grid Range: {lower_bound:.6f} - {upper_bound:.6f} ({range_percent:.2f}%) | Níveis: {self.num_levels}, Espaçamento: {self.current_spacing_percentage*100:.3f}%"
            + (" (Dinâmico)" if self.use_dynamic_spacing else " (Fixo)")
        )
        
        if self.num_levels <= 0:
            log.error(f"[{self.symbol}] Número de níveis <= 0. Não é possível definir grid.")
            self.grid_levels = []
            return
        
        self.grid_levels = []
        center_price_str = self._format_price(center_price_hft)
        if not center_price_str:
            log.error(f"[{self.symbol}] Não foi possível formatar preço central {center_price_hft}.")
            return
        center_price = Decimal(center_price_str)

        levels_above = self.num_levels // 2
        levels_below = self.num_levels // 2
        if self.grid_direction == "long":
            levels_above, levels_below = self.num_levels // 3, self.num_levels - (
                self.num_levels // 3
            )
        elif self.grid_direction == "short":
            levels_below, levels_above = self.num_levels // 3, self.num_levels - (
                self.num_levels // 3
            )

        # Usa current_spacing_percentage que pode ser dinâmico
        spacing = self.current_spacing_percentage

        last_price = center_price
        for i in range(levels_below):
            # Usa espaçamento geométrico: Price_n = Price_n-1 * (1 - spacing)
            level_price_raw = last_price * (Decimal("1") - spacing)
            level_price_str = self._format_price(level_price_raw)
            if level_price_str:
                level_price = Decimal(level_price_str)
                self.grid_levels.append({"price": level_price, "type": "buy"})
                last_price = level_price  # Atualiza último preço para próximo cálculo
            else:
                log.warning(
                    f"[{self.symbol}] Não foi possível formatar nível de grid inferior próximo a {level_price_raw}. Parando definição de grid inferior."
                )
                break

        last_price = center_price
        for i in range(levels_above):
            # Usa espaçamento geométrico: Price_n = Price_n-1 * (1 + spacing)
            level_price_raw = last_price * (Decimal("1") + spacing)
            level_price_str = self._format_price(level_price_raw)
            if level_price_str:
                level_price = Decimal(level_price_str)
                self.grid_levels.append({"price": level_price, "type": "sell"})
                last_price = level_price  # Atualiza último preço para próximo cálculo
            else:
                log.warning(
                    f"[{self.symbol}] Não foi possível formatar nível de grid superior próximo a {level_price_raw}. Parando definição de grid superior."
                )
                break

        self.grid_levels.sort(key=lambda x: x["price"])
        log.info(f"[{self.symbol}] Definidos {len(self.grid_levels)} níveis de grid.")

    def _calculate_quantity_per_order(self, current_price: Decimal) -> Decimal:
        # ... (no changes) ...
        total_capital_usd = Decimal(
            self.config.get("trading", {}).get("capital_per_pair_usd", "100")
        )
        leverage = Decimal(self.grid_config.get("leverage", "10"))
        num_grids = len(self.grid_levels) if self.grid_levels else self.num_levels
        if num_grids <= 0:
            log.error(f"[{self.symbol}] Num grids is zero.")
            return Decimal("0")
        capital_per_grid = total_capital_usd / Decimal(str(num_grids))
        exposure_per_grid = capital_per_grid * leverage
        quantity = exposure_per_grid / current_price
        
        # Ensure minimum notional value is met (minimum $5 per order)
        min_notional = self.min_notional if self.min_notional else Decimal("5")
        min_quantity = min_notional / current_price
        if quantity < min_quantity:
            log.info(f"[{self.symbol}] Adjusting quantity from {quantity} to {min_quantity} to meet minimum notional ${min_notional}")
            quantity = min_quantity
        formatted_qty_str = self._format_quantity(quantity, current_price)
        if not formatted_qty_str:
            log.error(f"[{self.symbol}] Failed to format quantity {quantity}.")
            return Decimal("0")
        log.info(f"[{self.symbol}] Calculated quantity per order: {formatted_qty_str}")
        return Decimal(formatted_qty_str)

    def _place_order(self, side, price_str, qty_str):
        """Método legado que chama o método unificado."""
        return self._place_order_unified(side, price_str, qty_str)

    def place_initial_grid_orders(self):
        # ... (no changes) ...
        log.info(f"[{self.symbol}] Placing initial grid orders...")
        if not self.grid_levels:
            log.warning(f"[{self.symbol}] No grid levels defined.")
            return
        if self.active_grid_orders:
            log.warning(f"[{self.symbol}] Initial grid orders seem active. Skipping.")
            return

        # Try real-time price first, fallback to API
        current_price_float = self._get_real_time_price()
        if current_price_float is None:
            ticker = self._get_ticker()
            current_price_float = self._get_current_price_from_ticker(ticker)
        if current_price_float is None:
            log.error(f"[{self.symbol}] Não foi possível obter preço atual.")
            return
        current_price = Decimal(str(current_price_float))
        quantity_per_order = self._calculate_quantity_per_order(current_price)
        if quantity_per_order <= Decimal("0"):
            log.error(f"[{self.symbol}] Quantity is zero.")
            return

        placed_count = 0
        for level in self.grid_levels:
            level_price = level["price"]
            order_type = level["type"]
            if level_price in self.active_grid_orders:
                continue

            formatted_price_str = self._format_price(level_price)
            formatted_qty_str = self._format_quantity(quantity_per_order, current_price)
            if not formatted_price_str or not formatted_qty_str:
                continue
            if not self._check_min_notional(formatted_price_str, formatted_qty_str):
                continue

            side = SIDE_BUY if order_type == "buy" else SIDE_SELL
            order_id = self._place_order(side, formatted_price_str, formatted_qty_str)
            if order_id:
                self.active_grid_orders[level_price] = order_id
                placed_count += 1
            time.sleep(0.1)
        log.info(f"[{self.symbol}] Placed {placed_count} initial grid orders.")
        
        # Save state after placing initial orders
        if placed_count > 0:
            self._save_grid_state()

    def check_and_handle_fills(self):
        # ... (rest of the file remains unchanged for now) ...
        # Add TA-Lib pattern checks here later if needed
        self._check_fills_production()

    def _check_fills_production(self):
        if not self.open_orders:
            return
        log.info(
            f"[{self.symbol}] Checking status of {len(self.open_orders)} open orders via API..."
        )
        order_ids_to_check = list(self.open_orders.keys())
        filled_orders_data = []
        still_open_orders = {}

        for order_id in order_ids_to_check:
            try:
                status = self._get_order_status_unified(order_id)
                time.sleep(0.05)  # Small delay
                if status:
                    log.debug(f"[{self.symbol}] Order {order_id} status: {status['status']} - Price: {status.get('price', 'N/A')}")
                    if status["status"] == ORDER_STATUS_FILLED:
                        log.info(f"[{self.symbol}] Order {order_id} FILLED.")
                        filled_orders_data.append(status)
                        # Remove from open orders immediately
                        if order_id in self.open_orders:
                            del self.open_orders[order_id]
                        # Find which grid level this corresponds to
                        filled_level_price = None
                        for price, oid in list(self.active_grid_orders.items()):
                            if oid == order_id:
                                filled_level_price = price
                                del self.active_grid_orders[price]
                                break
                        if filled_level_price:
                            self._handle_filled_order(status, filled_level_price)
                        else:
                            log.warning(
                                f"[{self.symbol}] Filled order {order_id} not found in active grid levels."
                            )
                    elif status["status"] in [
                        ORDER_STATUS_CANCELED,
                        ORDER_STATUS_EXPIRED,
                        ORDER_STATUS_REJECTED,
                    ]:
                        log.warning(
                            f"[{self.symbol}] Order {order_id} has status {status['status']}. Removing from tracking and recreating if needed."
                        )
                        if order_id in self.open_orders:
                            del self.open_orders[order_id]
                        
                        # Find and remove from active grid orders, then recreate
                        canceled_price = None
                        for price, oid in list(self.active_grid_orders.items()):
                            if oid == order_id:
                                canceled_price = price
                                del self.active_grid_orders[price]
                                break
                        
                        # Recreate the canceled order if it was part of our grid
                        if canceled_price and not self._stopped:
                            try:
                                log.info(f"[{self.symbol}] Recreating canceled order at price {canceled_price}")
                                # Determine order side based on current price
                                current_price = self.current_price
                                if current_price and canceled_price < current_price:
                                    # Buy order
                                    self._place_grid_order_at_level(canceled_price, "buy")
                                elif current_price and canceled_price > current_price:
                                    # Sell order
                                    self._place_grid_order_at_level(canceled_price, "sell")
                            except Exception as e:
                                log.error(f"[{self.symbol}] Failed to recreate canceled order at {canceled_price}: {e}")
                    else:  # Still open (NEW, PARTIALLY_FILLED)
                        still_open_orders[order_id] = status
                else:
                    log.warning(
                        f"[{self.symbol}] Could not get status for order {order_id}. Assuming still open."
                    )
                    # Keep old data se existir
                    if order_id in self.open_orders:
                        still_open_orders[order_id] = self.open_orders[order_id]
            except Exception as e:
                log.error(
                    f"[{self.symbol}] Error checking status for order {order_id}: {e}"
                )
                # Keep old data on error se existir
                if order_id in self.open_orders:
                    still_open_orders[order_id] = self.open_orders[order_id]

        self.open_orders = still_open_orders  # Update open orders list
        log.info(
            f"[{self.symbol}] Finished checking orders. {len(filled_orders_data)} filled, {len(self.open_orders)} still open."
        )
        
        # Auto-save state if there were changes
        if filled_orders_data:
            self._save_grid_state()


    def _handle_filled_order(self, fill_data, filled_level_price):
        """Handles logic after an order is filled: update position, place TP order, record trade."""
        side = fill_data["side"]
        filled_qty = Decimal(fill_data["executedQty"])
        avg_price = Decimal(fill_data["avgPrice"])
        # Need to fetch this properly if possible
        commission = Decimal(fill_data.get("commission", "0"))
        commission_asset = fill_data.get("commissionAsset", self.quote_asset)

        log.info(
            f"[{self.symbol}] Handling filled {side} order {fill_data['orderId']} at {avg_price}, Qty: {filled_qty}"
        )

        # --- Update Position (Simplified) ---
        # This needs a more robust position tracking mechanism, especially for
        # futures
        current_pos_amt = self.position["positionAmt"]
        current_entry_price = self.position["entryPrice"]

        if side == SIDE_BUY:
            new_pos_amt = current_pos_amt + filled_qty
            if current_pos_amt >= 0:  # Adding to long or opening long
                new_entry_price = (
                    ((current_entry_price * current_pos_amt) + (avg_price * filled_qty))
                    / new_pos_amt
                    if new_pos_amt != 0
                    else Decimal("0")
                )
            else:  # Reducing short position
                # Entry price doesn't change when reducing short
                new_entry_price = current_entry_price
        else:  # SIDE_SELL
            new_pos_amt = current_pos_amt - filled_qty
            if current_pos_amt <= 0:  # Adding to short or opening short
                # Use absolute values for calculation, entry price is positive
                new_entry_price = (
                    (
                        (current_entry_price * abs(current_pos_amt))
                        + (avg_price * filled_qty)
                    )
                    / abs(new_pos_amt)
                    if new_pos_amt != 0
                    else Decimal("0")
                )
            else:  # Reducing long position
                # Entry price doesn't change when reducing long
                new_entry_price = current_entry_price

        self.position["positionAmt"] = new_pos_amt
        self.position["entryPrice"] = new_entry_price
        log.info(
            f"[{self.symbol}] Updated Position: Amt={self.position['positionAmt']}, Entry={self.position['entryPrice']:.{self.price_precision}f}"
        )
        
        # Log position update to pair_logger
        try:
            position_side = "LONG" if float(new_pos_amt) > 0 else "SHORT" if float(new_pos_amt) < 0 else "NONE"
            unrealized_pnl = self.position.get("unRealizedProfit", 0)
            self.pair_logger.log_position_update(
                side=position_side,
                entry_price=float(new_entry_price),
                size=abs(float(new_pos_amt)),
                pnl=float(unrealized_pnl) if unrealized_pnl else 0.0
            )
        except Exception as e:
            log.debug(f"[{self.symbol}] Erro ao registrar atualização de posição no pair_logger: {e}")
        # -------------------------------------

        # --- Calculate PnL for this fill (if closing part of a position) ---
        realized_pnl = Decimal("0")
        if (side == SIDE_SELL and current_pos_amt > 0) or (
            side == SIDE_BUY and current_pos_amt < 0
        ):
            qty_closed = min(abs(current_pos_amt), filled_qty)
            if side == SIDE_SELL:  # Closed long
                realized_pnl = (avg_price - current_entry_price) * qty_closed
            else:  # Closed short
                realized_pnl = (current_entry_price - avg_price) * qty_closed
            # Adjust PnL for fees (assuming commission is in quote asset)
            # This is simplified, real fee calculation depends on taker/maker,
            # asset etc.
            fee_estimate = (
                avg_price * filled_qty * Decimal("0.0004")
            )  # Rough estimate (0.04%)
            realized_pnl -= fee_estimate
            self.total_realized_pnl += realized_pnl
            self.fees_paid += fee_estimate
            log.info(
                f"[{self.symbol}] Realized PnL from this fill: {realized_pnl:.4f} {self.quote_asset}"
            )

        # --- Place Corresponding Take Profit Order --- #
        tp_price = None
        tp_side = None
        tp_qty = filled_qty  # TP order matches the filled quantity

        # Find the next grid level in the opposite direction
        self.grid_levels.sort(key=lambda x: x["price"])  # Ensure sorted
        try:
            current_level_index = next(
                i
                for i, level in enumerate(self.grid_levels)
                if level["price"] == filled_level_price
            )

            if side == SIDE_BUY:
                # Find next sell level above
                if current_level_index + 1 < len(self.grid_levels):
                    tp_level = self.grid_levels[current_level_index + 1]
                    if tp_level["type"] == "sell":
                        tp_price = tp_level["price"]
                        tp_side = SIDE_SELL
            else:  # Filled Sell
                # Find next buy level below
                if current_level_index - 1 >= 0:
                    tp_level = self.grid_levels[current_level_index - 1]
                    if tp_level["type"] == "buy":
                        tp_price = tp_level["price"]
                        tp_side = SIDE_BUY

        except StopIteration:
            log.warning(
                f"[{self.symbol}] Could not find filled level price {filled_level_price} in current grid definition."
            )
        except Exception as e:
            log.error(f"[{self.symbol}] Error finding TP level: {e}")

        if tp_price and tp_side:
            formatted_tp_price_str = self._format_price(tp_price)
            formatted_tp_qty_str = self._format_quantity(tp_qty, current_price)
            if (
                formatted_tp_price_str
                and formatted_tp_qty_str
                and self._check_min_notional(
                    formatted_tp_price_str, formatted_tp_qty_str
                )
            ):
                log.info(
                    f"[{self.symbol}] Placing corresponding TP ({tp_side}) order at {formatted_tp_price_str}, Qty: {formatted_tp_qty_str}"
                )
                tp_order_id = self._place_order(
                    tp_side, formatted_tp_price_str, formatted_tp_qty_str
                )
                if tp_order_id:
                    # Add this TP order to the grid tracking
                    self.active_grid_orders[tp_price] = tp_order_id
            else:
                log.warning(
                    f"[{self.symbol}] Could not place TP order for fill {fill_data['orderId']}. Price/Qty/Notional issue."
                )
        else:
            log.warning(
                f"[{self.symbol}] Could not determine TP level for filled order {fill_data['orderId']} at level {filled_level_price}. Maybe edge of grid?"
            )

        # --- Add Position to TP/SL Manager (SMART - evita duplicatas) --- #
        # Aplicar TP/SL agressivo para TODAS as posições abertas (spot e futures)
        if abs(float(new_pos_amt)) > 0:
            position_side = "LONG" if float(new_pos_amt) > 0 else "SHORT"
            position_key = f"{self.symbol}_{position_side}_{float(new_entry_price):.6f}"
            
            # Only add if position size changed significantly (>1%) to avoid micro-changes
            size_change_threshold = 0.01  # 1%
            current_amt = float(self._last_position_amt)
            new_amt = float(new_pos_amt)
            size_change = abs(abs(new_amt) - abs(current_amt))
            size_change_percent = size_change / max(abs(current_amt), abs(new_amt), 0.01) if max(abs(current_amt), abs(new_amt)) > 0 else 0
            
            # Add position only if significant size change AND not already tracked
            if (size_change_percent > size_change_threshold and 
                position_key not in self._active_tpsl_positions):
                
                try:
                    position_id = add_position_to_global_tpsl(
                        symbol=self.symbol,
                        position_side=position_side,
                        entry_price=new_entry_price,
                        quantity=abs(new_pos_amt)
                    )
                    
                    if position_id:  # Only proceed if position was successfully added
                        self._active_tpsl_positions.add(position_key)
                        log.info(f"[{self.symbol}] 🎯 Position added to TP/SL manager: {position_id} (size change: {size_change_percent:.1%})")
                        log.info(f"[{self.symbol}] 🛡️ SL AGRESSIVO ATIVADO - Proteção de capital em 5%")
                    else:
                        log.warning(f"[{self.symbol}] 🚫 Could not add position to TP/SL: position does not exist on exchange")
                    
                except Exception as e:
                    log.error(f"[{self.symbol}] Error adding position to TP/SL manager: {e}")
            elif position_key in self._active_tpsl_positions:
                log.debug(f"[{self.symbol}] Position {position_key} already tracked in TP/SL manager")
        
        # Record trade activity for rotation tracking
        trade_volume = float(fill_data.get("cummulativeQuoteQty", 0))
        trade_profit = float(realized_pnl) if realized_pnl else 0.0
        
        self._record_trade_activity({
            "volume_usdt": trade_volume,
            "profit": trade_profit,
            "trade_type": "grid_fill",
            "timestamp": time.time()
        })
        
        # Clean up closed positions from tracking
        if abs(float(new_pos_amt)) == 0 and len(self._active_tpsl_positions) > 0:
            log.info(f"[{self.symbol}] Position closed, cleaning up TP/SL tracking")
            self._active_tpsl_positions.clear()
        
        # Update last position amount for comparison
        self._last_position_amt = Decimal(str(new_pos_amt))
    
    def _calculate_trade_profit(self, fill_data: dict, filled_level_price: float) -> float:
        """Calcula lucro estimado de um trade de grid."""
        try:
            # Para grid trading, o lucro é a diferença entre preços de níveis
            current_price = self._get_current_price_from_ticker()
            if not current_price:
                return 0.0
            
            side = fill_data.get("side", "")
            exec_qty = float(fill_data.get("executedQty", 0))
            avg_price = float(fill_data.get("avgPrice", 0))
            
            # Lucro estimado baseado na direção do trade
            if side == "SELL":
                # Venda: lucro = (preço_venda - preço_compra) * quantidade
                estimated_profit = (avg_price - filled_level_price * 0.995) * exec_qty  # 0.5% spread estimado
            else:  # BUY
                # Compra: aguardando venda futura, lucro = 0 por enquanto
                estimated_profit = 0.0
            
            return estimated_profit
            
        except Exception as e:
            log.debug(f"[{self.symbol}] Erro ao calcular lucro do trade: {e}")
            return 0.0
    
        
        # Continue with trade record processing
        self._handle_filled_order_continuation(fill_data, filled_level_price, 
                                             side, avg_price, filled_qty, realized_pnl, 
                                             commission, commission_asset)
    
    def _handle_filled_order_continuation(self, fill_data: dict, filled_level_price: float,
                                        side: str, avg_price: float, filled_qty: float, 
                                        realized_pnl: float, commission: float, commission_asset: str):
        """Continuação do processamento após atualização de posição."""
        # --- Record Trade --- #
        trade_record = {
            "timestamp": fill_data.get("updateTime", int(time.time() * 1000)),
            "orderId": fill_data["orderId"],
            "side": side,
            "price": avg_price,
            "quantity": filled_qty,
            "realizedPnl": realized_pnl,
            "commission": commission,
            "commissionAsset": commission_asset,
            "positionAmtAfter": self.position["positionAmt"],
        }
        self.trade_history.append(trade_record)
        self.total_trades += 1
        
        # LOG DETALHADO da ordem executada
        log.info(f"[{self.symbol}] 📊 ORDEM EXECUTADA:")
        log.info(f"[{self.symbol}] 🆔 Order ID: {fill_data['orderId']}")
        log.info(f"[{self.symbol}] 📈 Side: {side} | Qty: {filled_qty} | Price: ${avg_price}")
        log.info(f"[{self.symbol}] 💰 PnL: {realized_pnl} USDT | Comissão: {commission} {commission_asset}")
        log.info(f"[{self.symbol}] 📊 Nova Posição: {self.position['positionAmt']} | Total Trades: {self.total_trades}")
        
        # Log no trade logger para arquivo separado
        self.trade_logger.log_trade_execution(
            self.symbol, side, str(filled_qty), str(avg_price), 
            str(realized_pnl), str(commission), commission_asset
        )

        # --- Check for RL Retraining Trigger --- #
        retrain_threshold = self.config.get("rl", {}).get("retrain_after_trades", 0)
        if retrain_threshold > 0 and self.total_trades % retrain_threshold == 0:
            log.info(
                f"[{self.symbol}] Reached {self.total_trades} trades. Triggering RL retraining signal (implementation needed in main loop)."
            )
            # The main loop should check a flag or queue to start the training process
            # self.trigger_rl_retraining_flag = True # Example flag

    def cancel_active_grid_orders(self):
        # ... (no changes) ...
        log.warning(
            f"[{self.symbol}] Cancelling all active grid orders ({len(self.active_grid_orders)})..."
        )
        orders_to_cancel = list(self.active_grid_orders.values())
        cancelled_count = 0
        failed_count = 0
        for order_id in orders_to_cancel:
            try:
                # APIClient lida com simulação
                success = self._cancel_order_unified(order_id)
                time.sleep(0.1)
                if success:
                    log.info(f"[{self.symbol}] Cancelled order {order_id}.")
                    cancelled_count += 1
                    # Remove from tracking
                    if order_id in self.open_orders:
                        del self.open_orders[order_id]
                    # Remove from active_grid_orders by value
                    for price, oid in list(self.active_grid_orders.items()):
                        if oid == order_id:
                            del self.active_grid_orders[price]
                            break
                else:
                    log.error(f"[{self.symbol}] Failed to cancel order {order_id}.")
                    failed_count += 1
            except Exception as e:
                log.error(f"[{self.symbol}] Exception cancelling order {order_id}: {e}")
                failed_count += 1
        log.warning(
            f"[{self.symbol}] Order cancellation finished. Cancelled: {cancelled_count}, Failed: {failed_count}. Remaining active: {len(self.active_grid_orders)}"
        )
        # Clear remaining just in case, though ideally they should be removed
        # above
        self.active_grid_orders.clear()
        self.open_orders.clear()

    def get_state(self):
        """Returns the current state of the grid for the RL agent or monitoring."""
        # Update position info before returning state
        self._update_position_info()

        return {
            "symbol": self.symbol,
            "operation_mode": self.operation_mode,
            "num_levels": self.num_levels,
            "base_spacing_percentage": float(self.base_spacing_percentage),
            "current_spacing_percentage": float(self.current_spacing_percentage),
            "use_dynamic_spacing": self.use_dynamic_spacing,
            "grid_direction": self.grid_direction,
            "grid_levels_count": len(self.grid_levels),
            "active_grid_orders_count": len(self.active_grid_orders),
            "open_orders_count": len(self.open_orders),
            "position_amount": float(self.position.get("positionAmt", 0)),
            "entry_price": float(self.position.get("entryPrice", 0)),
            "mark_price": float(self.position.get("markPrice", 0)),
            "unrealized_pnl": float(self.position.get("unRealizedProfit", 0)),
            "total_realized_pnl": float(self.total_realized_pnl),
            "total_trades": self.total_trades,
            "talib_available": talib_available,  # Expose TA-Lib status
        }

    def _update_market_data(self):
        """Atualiza dados de mercado (preços, klines, volume) e métricas do pair_logger."""
        try:
            # 1. Atualizar preço atual e extrair métricas do ticker
            ticker = self._get_ticker()
            price_change_24h = 0.0
            volume_24h = 0.0
            
            if ticker:
                if "price" in ticker:
                    new_price = float(ticker["price"])
                    self.current_price = new_price
                    
                    # Atualizar histórico de preços
                    if not hasattr(self, "price_history"):
                        self.price_history = []
                    
                    self.price_history.insert(0, new_price)
                    # Manter apenas últimos 100 preços
                    if len(self.price_history) > 100:
                        self.price_history = self.price_history[:100]
                        
                    log.debug(f"[{self.symbol}] Preço atualizado: {new_price}")
                
                # Extrair mudança de preço 24h do ticker
                if "priceChangePercent" in ticker:
                    price_change_24h = float(ticker["priceChangePercent"])
                elif "priceChange" in ticker and "prevClosePrice" in ticker:
                    # Calcular porcentagem manualmente se não disponível diretamente
                    prev_price = float(ticker["prevClosePrice"])
                    if prev_price > 0:
                        price_change_24h = ((float(ticker["price"]) - prev_price) / prev_price) * 100
                
                # Extrair volume 24h do ticker
                if "volume" in ticker:
                    volume_24h = float(ticker["volume"])
                elif "quoteVolume" in ticker:
                    volume_24h = float(ticker["quoteVolume"])
                    
            else:
                log.warning(f"[{self.symbol}] Falha ao obter ticker")
            
            # 2. Atualizar dados de klines para indicadores técnicos
            # Use configured interval from config
            interval = getattr(self, 'kline_interval', '3m')
            klines = self._get_klines(interval=interval, limit=100)
            if klines and len(klines) > 0:
                # Extrair preços de fechamento para indicadores
                close_prices = []
                high_prices = []
                low_prices = []
                
                for kline in klines:
                    close_price = float(kline[4])  # Close price é o índice 4
                    high_price = float(kline[2])   # High price é o índice 2
                    low_price = float(kline[3])    # Low price é o índice 3
                    
                    close_prices.append(close_price)
                    high_prices.append(high_price)
                    low_prices.append(low_price)
                
                # Reverter para ordem cronológica (mais antigo primeiro)
                close_prices.reverse()
                high_prices.reverse()
                low_prices.reverse()
                
                self.kline_closes = close_prices
                
                # Calcular volume recente se não obtido do ticker
                if volume_24h == 0.0 and len(klines) >= 24:  # Últimas 24 horas
                    volumes = [float(kline[5]) for kline in klines[:24]]
                    self.recent_volume = sum(volumes)
                    volume_24h = self.recent_volume
                else:
                    self.recent_volume = volume_24h
                
                # 3. Calcular indicadores técnicos se TA-Lib disponível
                if talib_available and len(close_prices) >= 20:
                    # RSI
                    try:
                        rsi_values = talib.RSI(np.array(close_prices), timeperiod=14)
                        if not np.isnan(rsi_values[-1]):
                            self.current_rsi = float(rsi_values[-1])
                    except Exception as e:
                        log.debug(f"[{self.symbol}] Erro ao calcular RSI: {e}")
                    
                    # ATR (Average True Range) - Com precisão melhorada para tokens de baixo valor
                    try:
                        atr_values = talib.ATR(
                            np.array(high_prices), 
                            np.array(low_prices), 
                            np.array(close_prices), 
                            timeperiod=14
                        )
                        if len(atr_values) > 0 and not np.isnan(atr_values[-1]):
                            new_atr = float(atr_values[-1])
                            
                            # Verificar se ATR é extremamente baixo para o preço atual
                            current_price = close_prices[-1] if close_prices else 1.0
                            atr_percentage = (new_atr / current_price) * 100 if current_price > 0 else 0
                            
                            # Log para debug quando ATR é muito baixo
                            if atr_percentage < 0.1:  # Menos de 0.1% de volatilidade
                                log.warning(f"[{self.symbol}] ATR extremamente baixo: {new_atr:.6f} ({atr_percentage:.3f}%) - Preço: ${current_price:.6f}")
                            
                            # Só atualizar se ATR for válido e não zero
                            if new_atr > 0:
                                self.current_atr = new_atr
                                log.debug(f"[{self.symbol}] ATR atualizado: {new_atr:.6f} ({atr_percentage:.3f}% do preço)")
                            else:
                                log.warning(f"[{self.symbol}] ATR calculado é zero, mantendo valor anterior: {self.current_atr:.6f}")
                        else:
                            log.warning(f"[{self.symbol}] ATR inválido ou NaN, mantendo valor anterior: {self.current_atr:.6f}")
                    except Exception as e:
                        log.error(f"[{self.symbol}] Erro ao calcular ATR: {e}")
                    
                    # ADX (Average Directional Index)
                    try:
                        adx_values = talib.ADX(
                            np.array(high_prices), 
                            np.array(low_prices), 
                            np.array(close_prices), 
                            timeperiod=14
                        )
                        if not np.isnan(adx_values[-1]):
                            self.current_adx = float(adx_values[-1])
                    except Exception as e:
                        log.debug(f"[{self.symbol}] Erro ao calcular ADX: {e}")
                    
                    # BOLLINGER BANDS - Para HFT Range Trading
                    try:
                        bb_upper, bb_middle, bb_lower = talib.BBANDS(
                            np.array(close_prices), 
                            timeperiod=20, 
                            nbdevup=2, 
                            nbdevdn=2, 
                            matype=0
                        )
                        if not (np.isnan(bb_upper[-1]) or np.isnan(bb_lower[-1]) or np.isnan(bb_middle[-1])):
                            self.bb_upper = float(bb_upper[-1])
                            self.bb_lower = float(bb_lower[-1])
                            self.bb_middle = float(bb_middle[-1])
                            # BB Width para medir volatilidade
                            self.bb_width = (self.bb_upper - self.bb_lower) / self.bb_middle * 100
                    except Exception as e:
                        log.debug(f"[{self.symbol}] Erro ao calcular Bollinger Bands: {e}")
                    
                    # KELTNER CHANNELS - Para canais de volatilidade
                    try:
                        # EMA e ATR para Keltner Channels
                        ema_values = talib.EMA(np.array(close_prices), timeperiod=20)
                        keltner_atr = talib.ATR(
                            np.array(high_prices), 
                            np.array(low_prices), 
                            np.array(close_prices), 
                            timeperiod=10
                        )
                        if not (np.isnan(ema_values[-1]) or np.isnan(keltner_atr[-1])):
                            kc_multiplier = 2.0
                            self.kc_upper = float(ema_values[-1] + (keltner_atr[-1] * kc_multiplier))
                            self.kc_lower = float(ema_values[-1] - (keltner_atr[-1] * kc_multiplier))
                            self.kc_middle = float(ema_values[-1])
                    except Exception as e:
                        log.debug(f"[{self.symbol}] Erro ao calcular Keltner Channels: {e}")
                    
                    # VWAP - Para intraday anchor price
                    try:
                        # Simplified VWAP calculation
                        volumes = np.array([float(k[5]) for k in klines])
                        typical_prices = (np.array(high_prices) + np.array(low_prices) + np.array(close_prices)) / 3
                        cumulative_volume = np.cumsum(volumes)
                        cumulative_pv = np.cumsum(typical_prices * volumes)
                        vwap_values = cumulative_pv / cumulative_volume
                        if len(vwap_values) > 0 and not np.isnan(vwap_values[-1]):
                            self.vwap = float(vwap_values[-1])
                    except Exception as e:
                        log.debug(f"[{self.symbol}] Erro ao calcular VWAP: {e}")
                
                log.debug(f"[{self.symbol}] Klines atualizados: {len(close_prices)} preços, volume 24h: {volume_24h:.2f}")
            else:
                log.warning(f"[{self.symbol}] Falha ao obter klines")
            
            # 4. Verificar e atualizar TP/SL ativos
            self._update_active_tp_sl()
            
            # 5. Atualizar métricas do pair_logger
            self._update_pair_logger_metrics(price_change_24h, volume_24h)
                
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao atualizar dados de mercado: {e}", exc_info=True)
    
    def _update_active_tp_sl(self):
        """
        Verifica e atualiza ordens TP/SL ativas da Binance.
        Executado a cada ciclo para manter dados atualizados.
        """
        try:
            # Verificar se há posição ativa
            if self.market_type == "futures":
                position = self.api_client.get_futures_position(self.symbol)
                if not position:
                    return
                    
                # Extrair dados da posição
                if isinstance(position, list):
                    position = position[0] if position else None
                if not position:
                    return
                    
                position_amt = float(position.get('positionAmt', 0))
                if position_amt == 0:
                    # Sem posição ativa, limpar TP/SL
                    self.pair_logger.update_tp_sl(tp_price=None, sl_price=None)
                    return
                
                # Buscar ordens TP/SL ativas
                orders = self.api_client.get_open_futures_orders(symbol=self.symbol)
                tp_price = None
                sl_price = None
                
                for order in orders:
                    order_type = order.get('type', '')
                    price = float(order.get('price', 0))
                    
                    if order_type in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT'] and price > 0:
                        tp_price = price
                    elif order_type in ['STOP_MARKET', 'STOP'] and price > 0:
                        sl_price = price
                
                # Atualizar pair_logger se houver mudanças
                current_tp = self.pair_logger.metrics.tp_price
                current_sl = self.pair_logger.metrics.sl_price
                
                if tp_price != current_tp or sl_price != current_sl:
                    self.pair_logger.update_tp_sl(tp_price=tp_price, sl_price=sl_price)
                    
                    if tp_price or sl_price:
                        log.debug(f"[{self.symbol}] TP/SL atualizado: TP={tp_price}, SL={sl_price}")
                
        except Exception as e:
            log.debug(f"[{self.symbol}] Erro ao verificar TP/SL ativos: {e}")
    
    def _update_pair_logger_metrics(self, price_change_24h: float, volume_24h: float):
        """Atualiza métricas no pair_logger com dados de mercado atualizados."""
        try:
            # Obter dados de posição atual
            position_side = "NONE"
            position_size = 0.0
            entry_price = 0.0
            unrealized_pnl = 0.0
            leverage = 10
            
            if self.market_type == "futures":
                if hasattr(self, 'position') and self.position:
                    position_amt = float(self.position.get("positionAmt", 0))
                    if position_amt > 0:
                        position_side = "LONG"
                        position_size = position_amt
                    elif position_amt < 0:
                        position_side = "SHORT"
                        position_size = abs(position_amt)
                    
                    entry_price = float(self.position.get("entryPrice", 0))
                    unrealized_pnl = float(self.position.get("unRealizedProfit", 0))
                    leverage = self.config.get("futures", {}).get("leverage", 10)
            else:  # spot
                if hasattr(self, 'position') and self.position:
                    base_balance = float(self.position.get("base_balance", 0))
                    if base_balance > 0:
                        position_side = "LONG"
                        position_size = base_balance
                        entry_price = float(self.position.get("avg_buy_price", 0))
                        unrealized_pnl = float(self.position.get("unrealized_pnl", 0))
            
            # Contar ordens ativas do grid
            active_orders = len(self.active_grid_orders)
            filled_orders = self.total_trades
            grid_profit = float(self.total_realized_pnl)
            
            # Atualizar métricas no pair_logger
            self.pair_logger.update_metrics(
                current_price=self.current_price,
                entry_price=entry_price,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=grid_profit,
                position_size=position_size,
                position_side=position_side,
                leverage=leverage,
                rsi=self.current_rsi,
                atr=self.current_atr,
                adx=self.current_adx,
                volume_24h=volume_24h,
                price_change_24h=price_change_24h,
                grid_levels=self.num_levels,
                active_orders=active_orders,
                filled_orders=filled_orders,
                grid_profit=grid_profit,
                market_type=self.market_type.upper()
            )
            
            log.debug(f"[{self.symbol}] Métricas do pair_logger atualizadas: RSI={self.current_rsi:.1f}, ATR={self.current_atr:.4f}, Volume={volume_24h:.0f}")
            
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao atualizar métricas do pair_logger: {e}", exc_info=True)
    
    def _check_balance_for_trading(self):
        """Verifica se há saldo suficiente para operar."""
        try:
            if self.market_type == "futures":
                # Para futuros, verificar saldo USDT
                account_balance = self.api_client.get_futures_account_balance()
                if account_balance:
                    usdt_balance = None
                    for balance in account_balance:
                        if balance.get("asset") == "USDT":
                            usdt_balance = float(balance.get("balance", 0))
                            break
                    
                    if usdt_balance is None or usdt_balance < 10:  # Mínimo 10 USDT
                        log.warning(f"[{self.symbol}] Saldo USDT insuficiente: {usdt_balance}")
                        return False
                        
                    log.debug(f"[{self.symbol}] Saldo USDT: {usdt_balance:.2f}")
                    return True
                    
            else:
                # Para spot, verificar saldos dos ativos
                account_info = self.api_client.get_spot_account_balance()
                if account_info and "balances" in account_info:
                    usdt_balance = 0
                    base_balance = 0
                    
                    base_asset = self.symbol.replace("USDT", "").replace("BUSD", "").replace("USDC", "")
                    
                    for balance in account_info["balances"]:
                        asset = balance["asset"]
                        free_balance = float(balance["free"])
                        
                        if asset == "USDT":
                            usdt_balance = free_balance
                        elif asset == base_asset:
                            base_balance = free_balance
                    
                    # Verificar se há pelo menos 10 USDT ou algum saldo do ativo base
                    if usdt_balance < 10 and base_balance == 0:
                        log.warning(f"[{self.symbol}] Saldos insuficientes - USDT: {usdt_balance:.2f}, {base_asset}: {base_balance:.6f}")
                        return False
                        
                    log.debug(f"[{self.symbol}] Saldos - USDT: {usdt_balance:.2f}, {base_asset}: {base_balance:.6f}")
                    return True
                    
            return False
            
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao verificar saldo: {e}")
            return False
    
    def _update_position_info(self):
        """Updates the position details (mark price, PnL) from the API or ticker."""
        try:
            if self.operation_mode == "production":
                pos_data = self.api_client.get_futures_position_info(symbol=self.symbol)
                if pos_data:
                    # Binance API returns a list, find the specific symbol
                    symbol_pos = next(
                        (p for p in pos_data if p.get("symbol") == self.symbol), None
                    )
                    if symbol_pos:
                        self.position["positionAmt"] = Decimal(
                            symbol_pos.get("positionAmt", "0")
                        )
                        self.position["entryPrice"] = Decimal(
                            symbol_pos.get("entryPrice", "0")
                        )
                        self.position["markPrice"] = Decimal(
                            symbol_pos.get("markPrice", "0")
                        )
                        self.position["unRealizedProfit"] = Decimal(
                            symbol_pos.get("unRealizedProfit", "0")
                        )
                        self.position["liquidationPrice"] = Decimal(
                            symbol_pos.get("liquidationPrice", "0")
                        )
                    else:
                        # No position exists, reset
                        self.position = {
                            "positionAmt": Decimal("0"),
                            "entryPrice": Decimal("0"),
                            "markPrice": Decimal("0"),
                            "unRealizedProfit": Decimal("0"),
                            "liquidationPrice": Decimal("0"),
                        }
                else:
                    log.debug(
                        f"[{self.symbol}] Could not fetch production position info."
                    )
                    # Fetch ticker as fallback for mark price
                    ticker = self._get_ticker()
                    current_price_float = self._get_current_price_from_ticker(ticker)
                    if current_price_float is not None:
                        self.position["markPrice"] = Decimal(str(current_price_float))


        except Exception as e:
            log.error(
                f"[{self.symbol}] Error updating position info: {e}", exc_info=True
            )

    def get_market_state(self):
        """Gets the current market state for RL agent.

        Returns:
            numpy.ndarray: State vector containing market and grid features
        """
        # Ensure we have latest market data
        self._update_market_data()

        # Create state vector
        state_features = []

        # 1. Price features
        current_price = self.current_price
        if hasattr(self, "price_history") and len(self.price_history) > 0:
            # Normalized price changes
            price_changes = []
            for i in range(1, min(10, len(self.price_history))):
                if self.price_history[0] > 0:
                    change = (self.price_history[i - 1] / self.price_history[0]) - 1.0
                    price_changes.append(change)

            # Add recent price changes to state
            state_features.extend(price_changes)

            # Add volatility estimate
            if len(self.price_history) >= 20:
                volatility = np.std(self.price_history[:20]) / np.mean(
                    self.price_history[:20]
                )
                state_features.append(volatility)
            else:
                state_features.append(0.01)  # Default volatility
        else:
            # If no price history, add placeholders
            state_features.extend([0.0] * 10)  # Price changes
            state_features.append(0.01)  # Volatility

        # 2. Grid features
        # Normalized grid parameters
        state_features.append(self.num_levels / 20.0)  # Normalize by max levels
        state_features.append(
            float(self.current_spacing_percentage) / 0.02
        )  # Normalize by max spacing

        # Grid position relative to current price
        if hasattr(self, "grid_levels") and len(self.grid_levels) > 0:
            buy_levels_below = sum(
                1 for level in self.grid_levels if level["price"] < current_price
            )
            sell_levels_above = sum(
                1 for level in self.grid_levels if level["price"] > current_price
            )
            grid_balance = (buy_levels_below - sell_levels_above) / max(
                1, len(self.grid_levels)
            )
            state_features.append(grid_balance)
        else:
            state_features.append(0.0)  # Balanced grid

        # 3. Position features
        # Current position size
        position_size = (
            self.current_position_size
            if hasattr(self, "current_position_size")
            else 0.0
        )
        max_position = self.risk_config.get("max_position_size", 1.0)
        state_features.append(position_size / max_position)  # Normalized position size

        # Unrealized PnL
        unrealized_pnl = self.unrealized_pnl if hasattr(self, "unrealized_pnl") else 0.0
        state_features.append(
            min(1.0, max(-1.0, unrealized_pnl / 0.1))
        )  # Clip to [-1, 1]

        # 4. Technical indicators (if TA-Lib available)
        if talib_available:
            # Usar dados de klines se disponíveis, senão price_history
            prices_data = None
            if hasattr(self, "kline_closes") and len(self.kline_closes) >= 30:
                prices_data = np.array(self.kline_closes[-30:])  # Últimos 30 preços
            elif hasattr(self, "price_history") and len(self.price_history) >= 30:
                prices_data = np.array(self.price_history[:30])  # Primeiros 30 (mais recentes)
                
            if prices_data is not None and len(prices_data) >= 14:
                # RSI
                try:
                    rsi = talib.RSI(prices_data, timeperiod=14)[-1] / 100.0
                    state_features.append(rsi)
                except BaseException:
                    state_features.append(0.5)  # Neutral RSI

                # MACD
                try:
                    macd, signal, hist = talib.MACD(prices_data)
                    if len(hist) > 0 and not np.isnan(hist[-1]):
                        # Normalize histogram
                        norm_hist = np.clip(
                            (hist[-1] / (prices_data.mean() * 0.01)) / 2.0 + 0.5, 0, 1
                        )
                        state_features.append(norm_hist)
                    else:
                        state_features.append(0.5)
                except BaseException:
                    state_features.append(0.5)  # Neutral MACD
            else:
                # Dados insuficientes para indicadores
                state_features.extend([0.5, 0.5])  # Neutral RSI and MACD
        else:
            # Add placeholders if TA-Lib not available
            state_features.extend([0.5, 0.5])  # Neutral RSI and MACD

        # 5. Market activity features
        # Recent trades count/volume
        if hasattr(self, "recent_trades_count"):
            # Normalize trades count
            state_features.append(min(1.0, self.recent_trades_count / 1000.0))
        else:
            state_features.append(0.5)  # Average activity

        # Convert to numpy array and ensure all values are valid
        state_array = np.array(state_features, dtype=np.float32)
        # Replace NaN with neutral value
        state_array = np.nan_to_num(state_array, nan=0.5)

        # TEMPORARY FIX: Ensure we have exactly 28 features (RL will add sentiment separately)
        target_size = 28
        current_size = len(state_array)
        
        if current_size < target_size:
            # Add dummy features to reach target size
            padding = np.full(target_size - current_size, 0.5, dtype=np.float32)
            state_array = np.concatenate([state_array, padding])
            log.debug(f"[{self.symbol}] Padded state from {current_size} to {target_size} features")
        elif current_size > target_size:
            # Truncate if too many features
            state_array = state_array[:target_size]
            log.debug(f"[{self.symbol}] Truncated state from {current_size} to {target_size} features")

        return state_array

    def _apply_discrete_rl_action(self, action):
        """Applies a discrete action from the RL agent to modify grid parameters.

        Args:
            action (int): Discrete action index from the RL agent
                0: No change (maintain current parameters)
                1: Increase number of levels
                2: Decrease number of levels
                3: Increase spacing percentage
                4: Decrease spacing percentage
                5: Shift grid direction bullish (long)
                6: Shift grid direction bearish (short)
                7: Reset to balanced grid (neutral)
                8: Aggressive bullish setup (more levels, tighter spacing, long direction)
                9: Aggressive bearish setup (more levels, tighter spacing, short direction)
        """
        log.info(f"[{self.symbol}] Applying RL discrete action: {action}")
        
        # NOVO: Capturar estado antes da ação para logging
        previous_state = self.get_market_state() if hasattr(self, 'get_market_state') else None

        # Current parameters
        current_levels = self.num_levels
        current_spacing = self.base_spacing_percentage
        current_direction = (
            self.grid_direction if hasattr(self, "grid_direction") else "neutral"
        )

        # Parameter change amounts
        # 20% change, ensure even number
        level_change = max(2, int(current_levels * 0.2))
        if level_change % 2 != 0:
            level_change += 1  # Make it even

        spacing_change = Decimal(str(float(current_spacing) * 0.2))  # 20% change

        # Apply action
        if action == 0:  # No change
            log.info(f"[{self.symbol}] RL action: No change to grid parameters")
            return

        elif action == 1:  # Increase levels
            new_levels = current_levels + level_change
            self.update_grid_parameters(num_levels=new_levels)
            log.info(
                f"[{self.symbol}] RL action: Increased levels from {current_levels} to {new_levels}"
            )

        elif action == 2:  # Decrease levels
            new_levels = max(4, current_levels - level_change)  # Minimum 4 levels
            if new_levels % 2 != 0:
                new_levels += 1  # Ensure even number
            self.update_grid_parameters(num_levels=new_levels)
            log.info(
                f"[{self.symbol}] RL action: Decreased levels from {current_levels} to {new_levels}"
            )

        elif action == 3:  # Increase spacing
            new_spacing = Decimal(str(current_spacing)) + spacing_change
            self.update_grid_parameters(spacing_percentage=float(new_spacing))
            log.info(
                f"[{self.symbol}] RL action: Increased spacing from {current_spacing} to {new_spacing}"
            )

        elif action == 4:  # Decrease spacing
            new_spacing = max(Decimal("0.001"), Decimal(str(current_spacing)) - spacing_change)
            self.update_grid_parameters(spacing_percentage=float(new_spacing))
            log.info(
                f"[{self.symbol}] RL action: Decreased spacing from {current_spacing} to {new_spacing}"
            )

        elif action == 5:  # More bullish
            self.update_grid_parameters(direction="long")
            log.info(
                f"[{self.symbol}] RL action: Shifted direction bullish from {current_direction} to long"
            )

        elif action == 6:  # More bearish
            self.update_grid_parameters(direction="short")
            log.info(
                f"[{self.symbol}] RL action: Shifted direction bearish from {current_direction} to short"
            )

        elif action == 7:  # Reset to balanced
            self.update_grid_parameters(direction="neutral")
            log.info(
                f"[{self.symbol}] RL action: Reset to balanced grid (direction=neutral)"
            )

        elif action == 8:  # Aggressive bullish
            new_levels = min(20, current_levels + level_change)
            new_spacing = max(Decimal("0.001"), Decimal(str(current_spacing)) - spacing_change)
            self.update_grid_parameters(
                num_levels=new_levels,
                spacing_percentage=float(new_spacing),
                direction="long",
            )
            log.info(
                f"[{self.symbol}] RL action: Aggressive bullish setup (levels={new_levels}, spacing={new_spacing}, direction=long)"
            )

        elif action == 9:  # Aggressive bearish
            new_levels = min(20, current_levels + level_change)
            new_spacing = max(Decimal("0.001"), Decimal(str(current_spacing)) - spacing_change)
            self.update_grid_parameters(
                num_levels=new_levels,
                spacing_percentage=float(new_spacing),
                direction="short",
            )
            log.info(
                f"[{self.symbol}] RL action: Aggressive bearish setup (levels={new_levels}, spacing={new_spacing}, direction=short)"
            )

        else:
            log.warning(f"[{self.symbol}] Unknown RL action: {action}")
            
    
    def _calculate_rl_reward(self, previous_state, next_state):
        """Calcula reward simples para ação RL baseado na mudança de estado."""
        try:
            # Reward baseado em múltiplos fatores
            reward = 0.0
            
            # 1. Reward baseado na posição (índices 15-16 do estado)
            if len(previous_state) > 16 and len(next_state) > 16:
                position_change = next_state[15] - previous_state[15]  # Mudança na posição normalizada
                pnl_change = next_state[16] - previous_state[16]       # Mudança no PnL normalizado
                
                # Recompensar melhoria no PnL
                reward += pnl_change * 10.0
                
                # Penalizar posições extremas
                if abs(next_state[15]) > 0.8:  # Posição muito grande
                    reward -= 1.0
            
            # 2. Reward baseado na volatilidade (índice 11)
            if len(previous_state) > 11 and len(next_state) > 11:
                volatility = next_state[11]
                # Recompensar baixa volatilidade (mais estável)
                reward += (1.0 - volatility) * 0.5
            
            # 3. Reward baseado no balanceamento do grid (índice 14)
            if len(next_state) > 14:
                grid_balance = abs(next_state[14])  # Quão balanceado está o grid
                # Recompensar grid balanceado
                reward += (1.0 - grid_balance) * 0.5
            
            # Garantir que reward está em range razoável
            reward = max(-5.0, min(5.0, reward))
            
            return reward
            
        except Exception as e:
            log.warning(f"[{self.symbol}] Erro ao calcular reward RL: {e}")
            return 0.0

    def run_cycle(self, rl_action=None, ai_decision=None):
        """Main execution cycle for the grid logic."""
        log.info(f"[{self.symbol}] Running grid cycle...")

        # Track if there's significant activity during this cycle
        has_trading_activity = False

        # 0. First run: Try to recover existing grid
        if not self._recovery_attempted:
            log.info(f"[{self.symbol}] 🔄 Primeira execução - verificando existência de grid ativo na Binance...")
            grid_recovered = self.recover_active_grid()
            
            if grid_recovered:
                log.info(f"[{self.symbol}] ✅ Grid ativo recuperado com sucesso da Binance!")
                has_trading_activity = True  # Recovery is significant activity
                
                # Pular para monitoramento direto das ordens recuperadas
                self.check_and_handle_fills()
                log.info(f"[{self.symbol}] ✅ Ciclo de recuperação concluído - monitorando ordens da Binance")
                
                # Log trading cycle for recovery activity
                try:
                    self.pair_logger.log_trading_cycle(force_terminal=True)
                except Exception as e:
                    log.error(f"[{self.symbol}] Erro ao registrar ciclo de recuperação: {e}")
                return
            else:
                log.info(f"[{self.symbol}] ❌ Nenhum grid ativo encontrado na Binance - iniciando novo grid")

        # 1. Update market data first (prices, klines, volume)
        self._update_market_data()
        
        # 2. Update position/balance info
        self._update_position_info()
        
        # 2. Verificar se há saldo suficiente antes de operar
        balance_ok = self._check_balance_for_trading()
        log.debug(f"[{self.symbol}] Balance check result: {balance_ok}")
        if not balance_ok:
            log.warning(f"[{self.symbol}] Saldo insuficiente para trading. Pulando ciclo.")
            return

        # Apply RL agent actions if provided
        if rl_action is not None:
            # Process RL action based on the action type
            if isinstance(rl_action, (int, np.integer)):
                # Discrete action space (0: no change, 1: increase levels, 2:
                # decrease levels, etc.)
                self._apply_discrete_rl_action(rl_action)
                has_trading_activity = True  # RL action is significant
            elif isinstance(rl_action, dict):
                # Dictionary with explicit parameters
                self.update_grid_parameters(
                    num_levels=rl_action.get("num_levels"),
                    spacing_percentage=rl_action.get("spacing_percentage"),
                    direction=rl_action.get("direction"),
                )
                has_trading_activity = True  # RL action is significant
            else:
                log.warning(
                    f"[{self.symbol}] Unsupported RL action type: {type(rl_action)}"
                )
            
            # Registrar ação do grid no tracker de atividade
            self._record_grid_activity("rl_action_applied")

        # Apply AI decision if provided (takes priority over RL)
        if ai_decision is not None and isinstance(ai_decision, dict):
            suggested_params = ai_decision.get("suggested_params", {})
            if suggested_params and suggested_params.get("is_valid", False):
                # Apply AI suggested parameters
                if "grid_levels" in suggested_params:
                    new_levels = suggested_params["grid_levels"]
                    if 5 <= new_levels <= 30:  # Safety bounds
                        self.num_levels = new_levels
                        has_trading_activity = True  # AI parameter change is significant
                        
                if "spacing_percentage" in suggested_params:
                    new_spacing = suggested_params["spacing_percentage"]
                    if 0.001 <= new_spacing <= 0.05:  # 0.1% to 5%
                        self.base_spacing_percentage = Decimal(str(new_spacing))
                        self.current_spacing_percentage = Decimal(str(new_spacing))
                        has_trading_activity = True  # AI parameter change is significant
                
                log.debug(f"[{self.symbol}] Applied AI decision: levels={self.num_levels}, spacing={float(self.current_spacing_percentage)*100:.3f}%")
            else:
                log.debug(f"[{self.symbol}] AI decision parameters not valid, using RL/defaults")

        # 1. Check if grid needs (re)definition
        if not self.grid_levels:
            ticker = self._get_ticker()
            current_price = self._get_current_price_from_ticker(ticker)
            if current_price is None:
                log.error(
                    f"[{self.symbol}] Não é possível definir grid, falha ao obter preço atual."
                )
                return  # Aguarda próximo ciclo
            self.define_grid_levels(current_price)
            if self.grid_levels:
                self.place_initial_grid_orders()
                has_trading_activity = True  # Grid creation is significant activity
                # Registrar criação inicial do grid
                self._record_grid_activity("initial_grid_created")
            else:
                log.error(f"[{self.symbol}] Failed to define grid levels.")
                return

        # 2. Check for filled orders
        fills_before = self.total_trades
        self.check_and_handle_fills()
        fills_after = self.total_trades
        if fills_after > fills_before:
            has_trading_activity = True  # New trades are significant activity

        # 3. Check for automatic take profit opportunities
        self._check_automatic_take_profit()

        # 4. (Optional) Add other checks like risk management triggers (handled
        # externally for now)

        # 5. Log detailed trading cycle metrics to pair_logger only when there's activity
        try:
            if has_trading_activity:
                # Force terminal display for significant activity
                self.pair_logger.log_trading_cycle(force_terminal=True)
            # Always update metrics but don't force terminal display for routine cycles
            else:
                # Just update metrics without terminal display
                pass
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao registrar ciclo de trading no pair_logger: {e}")

        log.info(f"[{self.symbol}] Grid cycle finished.")
    
    def _record_grid_activity(self, activity_type: str) -> None:
        """Registra atividade do grid no tracker para monitoramento de rotação."""
        try:
            # Importar somente quando necessário para evitar import circular
            from utils.trade_activity_tracker import get_trade_activity_tracker
            
            tracker = get_trade_activity_tracker(config=self.config)
            tracker.record_grid_action(self.symbol, activity_type)
            
        except Exception as e:
            log.debug(f"[{self.symbol}] Erro ao registrar atividade do grid: {e}")
    
    def _record_trade_activity(self, trade_info: dict) -> None:
        """Registra atividade de trade no tracker para monitoramento de rotação."""
        try:
            # Importar somente quando necessário para evitar import circular
            from utils.trade_activity_tracker import get_trade_activity_tracker
            
            tracker = get_trade_activity_tracker(config=self.config)
            tracker.record_trade(self.symbol, trade_info)
            
        except Exception as e:
            log.debug(f"[{self.symbol}] Erro ao registrar atividade de trade: {e}")

    def _check_automatic_take_profit(self):
        """Verifica e cria take profit automático inteligente para lucros pequenos e consistentes."""
        try:
            # Só para mercado futures
            if self.market_type != "futures":
                return
            
            # Atualizar informações da posição
            self._update_position_info()
            
            # Verificar se há posição ativa
            position_amt = float(self.position.get("positionAmt", 0))
            if position_amt == 0:
                return
            
            unrealized_pnl = float(self.position.get("unRealizedProfit", 0))
            
            # Sistema de take profit inteligente para lucros pequenos (0.01-0.05 USDT)
            small_profit_threshold = 0.008  # $0.008 para capturar lucros menores
            medium_profit_threshold = 0.02   # $0.02 para lucros médios
            large_profit_threshold = 0.05    # $0.05 para lucros maiores
            
            # Verificar se há lucro suficiente
            if unrealized_pnl <= small_profit_threshold:
                return
            
            # Verificar se já tem ordens ativas (take profit)
            open_orders = self.api_client.get_open_futures_orders(self.symbol)
            existing_tp_orders = []
            if open_orders:
                for order in open_orders:
                    order_side = order.get('side')
                    if (position_amt > 0 and order_side == 'SELL') or (position_amt < 0 and order_side == 'BUY'):
                        if order.get('auto_take_profit') or 'TP' in order.get('clientOrderId', ''):
                            existing_tp_orders.append(order)
                
                # Se já tem take profit e PnL não mudou significativamente, retornar
                if existing_tp_orders and unrealized_pnl < medium_profit_threshold:
                    return
            
            # Estratégia dinâmica baseada no tamanho do lucro
            entry_price = float(self.position.get("entryPrice", 0))
            mark_price = float(self.position.get("markPrice", 0))
            
            # Determinar estratégia baseada no lucro
            if unrealized_pnl <= medium_profit_threshold:
                # Lucros pequenos (0.008-0.02): Take profit agressivo com 90% do lucro
                profit_margin_pct = 0.90
                tp_strategy = "SMALL_PROFIT"
            elif unrealized_pnl <= large_profit_threshold:
                # Lucros médios (0.02-0.05): Take profit moderado com 85% do lucro
                profit_margin_pct = 0.85
                tp_strategy = "MEDIUM_PROFIT"
            else:
                # Lucros grandes (>0.05): Take profit conservador com 75% do lucro
                profit_margin_pct = 0.75
                tp_strategy = "LARGE_PROFIT"
            
            # Calcular preço de take profit
            if position_amt > 0:  # Long position
                side = SIDE_SELL
                profit_margin = (mark_price - entry_price) * profit_margin_pct
                take_profit_price = entry_price + profit_margin
            else:  # Short position
                side = SIDE_BUY
                profit_margin = (entry_price - mark_price) * profit_margin_pct
                take_profit_price = entry_price - profit_margin
            
            # Para lucros pequenos, usar take profit parcial (50% da posição)
            if tp_strategy == "SMALL_PROFIT":
                quantity = self._round_quantity(abs(position_amt) * 0.5)  # 50% da posição
                log.info(f"[{self.symbol}] 💰 Small profit TP - PnL: ${unrealized_pnl:.4f} (50% position)")
            else:
                quantity = self._round_quantity(abs(position_amt))  # Posição completa
                log.info(f"[{self.symbol}] 💰 Auto take profit ({tp_strategy}) - PnL: ${unrealized_pnl:.4f}")
            
            # Ajustar precisão
            take_profit_price = self._round_price(take_profit_price)
            
            # Verificar se a quantidade atende ao mínimo nocional
            if not self._check_min_notional(take_profit_price, quantity):
                log.warning(f"[{self.symbol}] Take profit abaixo do mínimo nocional, usando posição completa")
                quantity = self._round_quantity(abs(position_amt))
            
            log.info(f"[{self.symbol}] Creating {tp_strategy} take profit: {side} {quantity} @ {take_profit_price}")
            
            # Cancelar take profits existentes se for necessário atualizar
            if existing_tp_orders and unrealized_pnl >= medium_profit_threshold:
                for order in existing_tp_orders:
                    try:
                        self.api_client.cancel_futures_order(self.symbol, order.get('orderId'))
                        log.info(f"[{self.symbol}] Cancelled outdated take profit order")
                    except Exception as e:
                        log.warning(f"[{self.symbol}] Failed to cancel existing TP order: {e}")
            
            # Criar ordem de take profit
            if self.operation_mode == "shadow":
                log.info(f"[{self.symbol}] [SHADOW] {tp_strategy} take profit simulated")
                return
            
            order_result = self.api_client.place_futures_order(
                symbol=self.symbol,
                side=side,
                order_type=ORDER_TYPE_LIMIT,
                quantity=quantity,
                price=take_profit_price,
                time_in_force=TIME_IN_FORCE_GTC
            )
            
            if order_result:
                order_id = order_result.get('orderId')
                log.info(f"[{self.symbol}] ✅ {tp_strategy} take profit created: ID {order_id}")
                
                # Adicionar às ordens abertas
                self.open_orders[order_id] = {
                    'orderId': order_id,
                    'symbol': self.symbol,
                    'side': side,
                    'type': 'LIMIT',
                    'origQty': str(quantity),
                    'price': str(take_profit_price),
                    'status': 'NEW',
                    'timeInForce': 'GTC',
                    'auto_take_profit': True,
                    'tp_strategy': tp_strategy,
                    'profit_margin_pct': profit_margin_pct
                }
            else:
                log.warning(f"[{self.symbol}] Failed to create {tp_strategy} take profit")
                
        except Exception as e:
            log.error(f"[{self.symbol}] Error in automatic take profit: {e}")

    def get_status(self) -> dict:
        """Retorna status atual do bot de grid trading."""
        try:
            # Obter preço atual
            ticker = self._get_ticker()
            current_price = self._get_current_price_from_ticker(ticker)
            if current_price is None:
                current_price = 0.0

            # Calcular PnL baseado no tipo de mercado
            if self.market_type == "spot":
                unrealized_pnl = float(self.position.get("unrealized_pnl", 0))
                position_size = float(self.position.get("base_balance", 0))
            else:  # futures
                unrealized_pnl = float(self.position.get("unRealizedProfit", 0))
                position_size = float(self.position.get("positionAmt", 0))

            # Status base
            status = {
                "status": "running",
                "symbol": self.symbol,
                "market_type": self.market_type,
                "operation_mode": self.operation_mode,
                "current_price": current_price,
                "grid_levels": len(self.grid_levels),
                "active_orders": len(self.active_grid_orders),
                "total_trades": self.total_trades,
                "realized_pnl": float(self.total_realized_pnl),
                "unrealized_pnl": unrealized_pnl,
                "fees_paid": float(self.fees_paid),
                "position_size": position_size,
                "spacing_percentage": float(self.current_spacing_percentage),
                "grid_direction": getattr(self, 'grid_direction', 'neutral')
            }

            # Adicionar informações de recuperação
            if hasattr(self, '_grid_recovered'):
                status["grid_recovered"] = self._grid_recovered
                if self._grid_recovered:
                    recovered_count = sum(1 for level in self.grid_levels if level.get('recovered', False))
                    status["recovered_orders"] = recovered_count
            
            base_message = "Running in production mode (real trading)"
            
            # Adicionar status de recuperação à mensagem
            if hasattr(self, '_grid_recovered') and self._grid_recovered:
                status["message"] = f"{base_message} - Grid recuperado de sessão anterior"
            else:
                status["message"] = base_message

            return status

        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao obter status: {e}")
            return {
                "status": "error",
                "symbol": self.symbol,
                "message": f"Error getting status: {str(e)}"
            }

    def stop(self):
        """Para o bot de grid trading."""
        try:
            log.info(f"[{self.symbol}] Parando bot de grid trading...")
            
            # Cancelar todas as ordens ativas
            if self.operation_mode == "production":
                # Cancelar ordens reais
                for order_id in list(self.active_grid_orders.values()):
                    try:
                        if self.market_type == "spot":
                            self.api_client.cancel_spot_order(symbol=self.symbol, orderId=order_id)
                        else:  # futures
                            self.api_client.cancel_order(symbol=self.symbol, orderId=order_id)
                        log.info(f"[{self.symbol}] Ordem {order_id} cancelada")
                    except Exception as e:
                        log.warning(f"[{self.symbol}] Erro ao cancelar ordem {order_id}: {e}")

            # Limpar estruturas de dados
            self.active_grid_orders.clear()
            self.open_orders.clear()
            self.grid_levels.clear()
            
            # Marcar como parado
            self._stopped = True
            
            log.info(f"[{self.symbol}] Bot parado com sucesso")
            
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao parar bot: {e}")
            
    @property
    def is_stopped(self):
        """Property alias for _stopped attribute."""
        return self._stopped
        
    @is_stopped.setter
    def is_stopped(self, value):
        """Setter for is_stopped property."""
        self._stopped = value

    def recover_active_grid(self):
        """Recupera grid ativo existente após reinicialização do bot.
        
        Verifica se há ordens ativas na exchange e reconstrói o estado do grid.
        Prioriza a recuperação a partir das ordens ativas na Binance.
        Verifica ambos os mercados (spot e futures) para maior robustez.
        """
        self._recovery_attempted = True
        
        # Only production mode supported

        try:
            log.info(f"[{self.symbol}] 🔍 Verificando ordens ativas em ambos os mercados...")
            
            # Tentar mercado futures primeiro
            futures_orders = None
            try:
                futures_orders = self.api_client._make_request(
                    self.api_client.client.futures_get_open_orders,
                    symbol=self.symbol
                )
                log.info(f"[{self.symbol}] Encontradas {len(futures_orders) if futures_orders else 0} ordens FUTURES")
                if futures_orders:
                    self.market_type = "futures"
            except Exception as e:
                log.warning(f"[{self.symbol}] Erro ao verificar mercado FUTURES: {e}")
                futures_orders = None

            # Se não encontrou no futures, tentar spot
            spot_orders = None
            if not futures_orders:
                try:
                    spot_orders = self.api_client._make_request(
                        self.api_client.client.get_open_orders,
                        symbol=self.symbol
                    )
                    log.info(f"[{self.symbol}] Encontradas {len(spot_orders) if spot_orders else 0} ordens SPOT")
                    if spot_orders:
                        self.market_type = "spot"
                except Exception as e:
                    log.warning(f"[{self.symbol}] Erro ao verificar mercado SPOT: {e}")
                    spot_orders = None

            # Usar as ordens encontradas
            active_orders = futures_orders if futures_orders else spot_orders

            if not active_orders:
                log.info(f"[{self.symbol}] Nenhuma ordem ativa encontrada em nenhum mercado")
                
                # Check for existing positions (filled orders)
                existing_position = self._check_existing_position()
                if existing_position:
                    log.info(f"[{self.symbol}] ✅ Posição existente detectada - iniciando grid complementar")
                    self._grid_recovered = True
                    return True
                
                self._grid_recovered = False
                return False
            
            log.info(f"[{self.symbol}] Usando ordens do mercado {self.market_type.upper()}")

            # Filtrar apenas ordens LIMIT
            grid_orders = []
            for order in active_orders:
                if order.get('type') == 'LIMIT' and order.get('status') in ['NEW', 'PARTIALLY_FILLED']:
                    grid_orders.append({
                        'orderId': order['orderId'],
                        'price': float(order['price']),
                        'origQty': float(order['origQty']),
                        'executedQty': float(order.get('executedQty', 0)),
                        'side': order['side'],
                        'status': order['status'],
                        'time': order.get('time', 0)
                    })

            if not grid_orders:
                log.info(f"[{self.symbol}] Nenhuma ordem LIMIT ativa encontrada")
                self._grid_recovered = False
                return False

            # Analisar espaçamento entre ordens
            grid_orders.sort(key=lambda x: x['price'])
            
            # Exibir ordens encontradas para diagnóstico
            log.info(f"[{self.symbol}] 📋 Ordens encontradas para análise:")
            for i, order in enumerate(grid_orders[:5]):  # Mostrar até 5 ordens para não poluir o log
                log.info(f"  #{i+1}: {order['side']} @ {order['price']} - Qtd: {order['origQty']}")
            if len(grid_orders) > 5:
                log.info(f"  ... e mais {len(grid_orders) - 5} ordens")
                
            # Análise separada para ordens de compra e venda
            buy_orders = [o for o in grid_orders if o['side'] == 'BUY']
            sell_orders = [o for o in grid_orders if o['side'] == 'SELL']
            log.info(f"[{self.symbol}] 📊 Composição: {len(buy_orders)} ordens de compra, {len(sell_orders)} ordens de venda")
            
            # Calcular espaçamentos entre ordens consecutivas do mesmo tipo
            spacings = []
            
            # Espaçamentos entre ordens de compra
            if len(buy_orders) >= 2:
                buy_orders.sort(key=lambda x: x['price'])
                buy_spacings = []
                for i in range(1, len(buy_orders)):
                    price1 = buy_orders[i-1]['price']
                    price2 = buy_orders[i]['price']
                    spacing = abs((price2 - price1) / price1)
                    buy_spacings.append(spacing)
                    log.info(f"[{self.symbol}] BUY: Espaçamento entre {price1} e {price2}: {spacing*100:.2f}%")
                
                if buy_spacings:
                    avg_buy_spacing = sum(buy_spacings) / len(buy_spacings)
                    log.info(f"[{self.symbol}] 📏 Espaçamento médio entre ordens de COMPRA: {avg_buy_spacing*100:.2f}%")
                    spacings.extend(buy_spacings)
            
            # Espaçamentos entre ordens de venda
            if len(sell_orders) >= 2:
                sell_orders.sort(key=lambda x: x['price'])
                sell_spacings = []
                for i in range(1, len(sell_orders)):
                    price1 = sell_orders[i-1]['price']
                    price2 = sell_orders[i]['price']
                    spacing = abs((price2 - price1) / price1)
                    sell_spacings.append(spacing)
                    log.info(f"[{self.symbol}] SELL: Espaçamento entre {price1} e {price2}: {spacing*100:.2f}%")
                
                if sell_spacings:
                    avg_sell_spacing = sum(sell_spacings) / len(sell_spacings)
                    log.info(f"[{self.symbol}] 📏 Espaçamento médio entre ordens de VENDA: {avg_sell_spacing*100:.2f}%")
                    spacings.extend(sell_spacings)
            
            # Se não houver espaçamentos por tipo, calcular entre todas as ordens
            if not spacings:
                for i in range(1, len(grid_orders)):
                    price1 = grid_orders[i-1]['price']
                    price2 = grid_orders[i]['price']
                    spacing = abs((price2 - price1) / price1)
                    spacings.append(spacing)
                    log.info(f"[{self.symbol}] ALL: Espaçamento entre {price1} e {price2}: {spacing*100:.2f}%")

            if spacings:
                avg_spacing = sum(spacings) / len(spacings)
                # Verificar se os espaçamentos são consistentes (variação < 30%)
                spacing_variation = [abs(s - avg_spacing) / avg_spacing for s in spacings]
                is_consistent = all(v < 0.30 for v in spacing_variation)
                
                log.info(f"[{self.symbol}] 📏 Espaçamento médio geral: {avg_spacing*100:.2f}%")
                
                if is_consistent:
                    log.info(f"[{self.symbol}] ✅ Grid detectado! Espaçamento consistente ({avg_spacing*100:.2f}%)")
                    
                    # Atualizar parâmetros do grid
                    self.current_spacing_percentage = Decimal(str(avg_spacing))
                    self.base_spacing_percentage = Decimal(str(avg_spacing))
                    self.num_levels = max(len(grid_orders), self.num_levels)
                    
                    # Determinar direção do grid baseado na distribuição de ordens
                    if len(buy_orders) > len(sell_orders) * 1.5:
                        self.grid_direction = "long"
                        log.info(f"[{self.symbol}] 📈 Grid recuperado com viés LONG (mais ordens de compra)")
                    elif len(sell_orders) > len(buy_orders) * 1.5:
                        self.grid_direction = "short"
                        log.info(f"[{self.symbol}] 📉 Grid recuperado com viés SHORT (mais ordens de venda)")
                    else:
                        self.grid_direction = "neutral"
                        log.info(f"[{self.symbol}] ⚖️ Grid recuperado com viés NEUTRAL (balanceado)")
                    
                    # Reconstruir níveis do grid
                    self.grid_levels = []
                    for order in grid_orders:
                        level = {
                            'price': order['price'],
                            'type': 'buy' if order['side'] == 'BUY' else 'sell',
                            'quantity': order.get('origQty', 0),
                            'order_id': order['orderId'],
                            'status': 'active',
                            'recovered': True
                        }
                        self.grid_levels.append(level)
                        self.active_grid_orders[order['price']] = order['orderId']
                        self.open_orders[order['orderId']] = order
                    
                    log.info(f"[{self.symbol}] ✅ Grid recuperado com sucesso! {len(self.grid_levels)} níveis ativos")
                    
                    # Obter ticker para verificar preço atual
                    try:
                        ticker = self._get_ticker()
                        current_price = self._get_current_price_from_ticker(ticker)
                        if current_price is not None:
                            self.current_price = current_price
                            log.info(f"[{self.symbol}] 📊 Preço atual: {self.current_price}")
                            
                            # Contar quantos níveis estão acima e abaixo do preço atual
                            levels_below = sum(1 for level in self.grid_levels if level['price'] < self.current_price)
                            levels_above = sum(1 for level in self.grid_levels if level['price'] > self.current_price)
                            log.info(f"[{self.symbol}] 📊 Distribuição do grid: {levels_below} níveis abaixo e {levels_above} níveis acima do preço atual")
                    except Exception as ticker_e:
                        log.warning(f"[{self.symbol}] ⚠️ Não foi possível obter preço atual: {ticker_e}")
                    
                    self._grid_recovered = True
                    
                    # Salvar estado recuperado como backup
                    self._save_grid_state()
                    
                    # Reinicializar symbol_info para o mercado correto
                    self._initialize_symbol_info()
                    
                    return True
                else:
                    log.info(f"[{self.symbol}] ⚠️ Ordens encontradas mas espaçamento não consistente (variação > 25%)")
                    # Mostrar os espaçamentos mais discrepantes
                    for i, var in enumerate(spacing_variation):
                        if var > 0.25:
                            log.info(f"[{self.symbol}] Variação alta no espaçamento {i}: {var*100:.1f}%")
                    
                    # Verificar se temos pelo menos algumas ordens com espaçamento consistente
                    consistent_spacings = [s for i, s in enumerate(spacings) if spacing_variation[i] < 0.30]
                    if len(consistent_spacings) >= 3:  # Se tivermos pelo menos 3 espaçamentos consistentes
                        log.info(f"[{self.symbol}] 🔄 Tentando recuperação parcial com {len(consistent_spacings)} espaçamentos consistentes")
                        
                        # Usar apenas espaçamentos consistentes para calcular média
                        consistent_avg = sum(consistent_spacings) / len(consistent_spacings)
                        log.info(f"[{self.symbol}] 📏 Espaçamento médio dos valores consistentes: {consistent_avg*100:.2f}%")
                        
                        # Continuar com recuperação mesmo com alguns espaçamentos inconsistentes
                        self.current_spacing_percentage = Decimal(str(consistent_avg))
                        self.base_spacing_percentage = Decimal(str(consistent_avg))
                        
                        # Reconstruir níveis do grid
                        self.grid_levels = []
                        for order in grid_orders:
                            level = {
                                'price': order['price'],
                                'type': 'buy' if order['side'] == 'BUY' else 'sell',
                                'quantity': order.get('origQty', 0),
                                'order_id': order['orderId'],
                                'status': 'active',
                                'recovered': True
                            }
                            self.grid_levels.append(level)
                            self.active_grid_orders[order['price']] = order['orderId']
                            self.open_orders[order['orderId']] = order
                        
                        log.info(f"[{self.symbol}] ⚠️ Recuperação parcial do grid (alguns espaçamentos inconsistentes)")
                        self._grid_recovered = True
                        return True
                        
                    self._grid_recovered = False
                    return False
            else:
                # Tentar recuperar mesmo se não conseguimos calcular espaçamentos
                if len(grid_orders) >= 3:
                    log.info(f"[{self.symbol}] ⚠️ Tentando recuperar grid mesmo sem calcular espaçamento")
                    
                    # Usar valor padrão de espaçamento
                    self.current_spacing_percentage = Decimal("0.005")  # 0.5%
                    self.base_spacing_percentage = Decimal("0.005")
                    
                    # Reconstruir níveis do grid de qualquer forma
                    self.grid_levels = []
                    for order in grid_orders:
                        level = {
                            'price': order['price'],
                            'type': 'buy' if order['side'] == 'BUY' else 'sell',
                            'quantity': order.get('origQty', 0),
                            'order_id': order['orderId'],
                            'status': 'active',
                            'recovered': True
                        }
                        self.grid_levels.append(level)
                        self.active_grid_orders[order['price']] = order['orderId']
                        self.open_orders[order['orderId']] = order
                    
                    log.info(f"[{self.symbol}] ✅ Grid recuperado com ordens insuficientes para calcular espaçamento")
                    self._grid_recovered = True
                    return True
                else:
                    log.info(f"[{self.symbol}] ⚠️ Impossível calcular espaçamento (ordens insuficientes)")
                    self._grid_recovered = False
                    return False
                
        except Exception as e:
            log.error(f"[{self.symbol}] ❌ Erro durante recuperação do grid: {e}", exc_info=True)
            self._grid_recovered = False
            return False

    def _get_active_orders_from_exchange(self) -> list:
        """Busca ordens ativas na exchange para o símbolo atual."""
        try:
            # Tentar múltiplas vezes em caso de falha de conexão
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    if self.market_type == "spot":
                        log.info(f"[{self.symbol}] Buscando ordens ativas no mercado SPOT (tentativa {attempt}/{max_attempts})...")
                        orders = self.api_client.get_spot_open_orders(symbol=self.symbol)
                    else:  # futures
                        log.info(f"[{self.symbol}] Buscando ordens ativas no mercado FUTURES (tentativa {attempt}/{max_attempts})...")
                        orders = self.api_client.get_futures_open_orders(symbol=self.symbol)  # Corrigido para usar método correto
                    
                    # Verificação de resposta válida
                    if orders is None:
                        log.warning(f"[{self.symbol}] API retornou None para ordens ativas (tentativa {attempt}/{max_attempts})")
                        if attempt < max_attempts:
                            time.sleep(2)  # Esperar 2 segundos antes de tentar novamente
                            continue
                        else:
                            return []
                    
                    # Filtrar apenas ordens LIMIT que são do tipo grid
                    grid_orders = []
                    for order in orders:
                        if (order.get('type') == 'LIMIT' and 
                            order.get('status') in ['NEW', 'PARTIALLY_FILLED']):
                            grid_orders.append({
                                'orderId': order['orderId'],
                                'price': float(order['price']),
                                'origQty': float(order['origQty']),
                                'executedQty': float(order.get('executedQty', 0)),
                                'side': order['side'],
                                'status': order['status'],
                                'time': order.get('time', 0),
                                'symbol': order.get('symbol', self.symbol)
                            })
                    
                    if grid_orders:
                        log.info(f"[{self.symbol}] ✅ Encontradas {len(grid_orders)} ordens LIMIT ativas")
                        # Mostrar detalhes das ordens para diagnóstico
                        for i, order in enumerate(grid_orders[:5]):  # Limitar a 5 ordens
                            log.info(f"[{self.symbol}] Ordem #{i+1}: {order['side']} @ {order['price']}, Qtd={order['origQty']}")
                        if len(grid_orders) > 5:
                            log.info(f"[{self.symbol}] ... e mais {len(grid_orders) - 5} ordens")
                    else:
                        log.info(f"[{self.symbol}] Nenhuma ordem LIMIT ativa encontrada")
                    
                    return grid_orders
                    
                except Exception as api_error:
                    log.warning(f"[{self.symbol}] Erro na tentativa {attempt}/{max_attempts} de buscar ordens: {api_error}")
                    if attempt < max_attempts:
                        time.sleep(2)  # Esperar 2 segundos antes de tentar novamente
                    else:
                        raise  # Re-levantar a exceção na última tentativa
            
            return []  # Caso todas as tentativas falhem
            
        except Exception as e:
            log.error(f"[{self.symbol}] ❌ Erro ao buscar ordens ativas: {e}", exc_info=True)
            return []

    def _reconstruct_grid_from_orders(self, active_orders: list) -> list:
        """Reconstrói níveis do grid a partir das ordens ativas."""
        try:
            if not active_orders:
                log.warning(f"[{self.symbol}] Nenhuma ordem ativa para reconstrução de grid")
                return []
            
            # Separar ordens por tipo
            buy_orders = [o for o in active_orders if o['side'] == 'BUY']
            sell_orders = [o for o in active_orders if o['side'] == 'SELL']
            
            log.info(f"[{self.symbol}] 📊 Análise das ordens - Compra: {len(buy_orders)}, Venda: {len(sell_orders)}")
            
            # Validar que temos uma estrutura de grid (pelo menos algumas ordens de compra e venda)
            if len(buy_orders) == 0 or len(sell_orders) == 0:
                log.warning(f"[{self.symbol}] ⚠️ Estrutura de grid incompleta - faltando ordens de {'compra' if len(buy_orders) == 0 else 'venda'}")
                # Continuar mesmo assim, pode ser um grid em construção ou unidirecional
            
            # Calcular espaçamento médio das ordens existentes
            recovered_spacing = self._calculate_spacing_from_orders(active_orders)
            if recovered_spacing:
                log.info(f"[{self.symbol}] 📏 Espaçamento do grid recuperado: {recovered_spacing*100:.3f}%")
                self.current_spacing_percentage = Decimal(str(recovered_spacing))
                # Atualizar também o espaçamento base para usar em novos níveis
                self.base_spacing_percentage = Decimal(str(recovered_spacing))
            else:
                log.warning(f"[{self.symbol}] ⚠️ Não foi possível calcular espaçamento do grid. Usando padrão: {self.base_spacing_percentage*100:.3f}%")
            
            # Verificar e recuperar tamanho do grid baseado no número de ordens
            self.num_levels = max(len(active_orders), self.num_levels)
            log.info(f"[{self.symbol}] 📐 Número de níveis do grid recuperado: {self.num_levels}")
            
            # Determinar direção do grid com base na proporção de ordens
            if len(buy_orders) > len(sell_orders) * 1.5:
                self.grid_direction = "long"
                log.info(f"[{self.symbol}] 📈 Direção do grid recuperada: LONG (mais ordens de compra)")
            elif len(sell_orders) > len(buy_orders) * 1.5:
                self.grid_direction = "short"
                log.info(f"[{self.symbol}] 📉 Direção do grid recuperada: SHORT (mais ordens de venda)")
            else:
                self.grid_direction = "neutral"
                log.info(f"[{self.symbol}] ⚖️ Direção do grid recuperada: NEUTRAL (equilibrado)")
            
            # Reconstruir estruturas de dados
            recovered_levels = []
            self.open_orders = {}  # Limpar antes de reconstruir
            self.active_grid_orders = {}  # Limpar antes de reconstruir
            
            for order in active_orders:
                # Adicionar às ordens abertas com formato adequado para cada tipo de mercado
                order_data = {
                    'orderId': order['orderId'],
                    'symbol': self.symbol,
                    'side': order['side'],
                    'type': 'LIMIT',
                    'origQty': str(order['origQty']),
                    'price': str(order['price']),
                    'status': order['status'],
                    'executedQty': str(order['executedQty']),
                    'time': order['time']
                }
                
                self.open_orders[order['orderId']] = order_data
                
                # Adicionar aos níveis ativos do grid
                # Chave é o preço formatado como string para evitar problemas com Decimal
                self.active_grid_orders[float(order['price'])] = order['orderId']
                
                # Criar nível do grid
                # Determinar tipo baseado no lado da ordem
                level_type = "buy" if order['side'] == 'BUY' else "sell"
                
                level = {
                    'price': float(order['price']),
                    'type': level_type,  # Formato esperado pelo grid
                    'quantity': float(order['origQty']),
                    'order_id': order['orderId'],
                    'status': 'active',
                    'recovered': True  # Marcar como recuperado
                }
                recovered_levels.append(level)
            
            # Ordenar níveis por preço
            recovered_levels.sort(key=lambda x: x['price'])
            
            # Atualizar current_price baseado nas ordens
            # Buscar o preço do mercado atual
            try:
                ticker = self._get_ticker()
                current_price = self._get_current_price_from_ticker(ticker)
                if current_price is not None:
                    self.current_price = current_price
                    log.info(f"[{self.symbol}] 📊 Preço atual do mercado: {self.current_price}")
            except Exception as price_error:
                log.warning(f"[{self.symbol}] ⚠️ Não foi possível obter preço atual: {price_error}")
                # Estimar preço atual usando a média das ordens
                if recovered_levels:
                    estimated_price = sum(level['price'] for level in recovered_levels) / len(recovered_levels)
                    self.current_price = estimated_price
                    log.info(f"[{self.symbol}] 📊 Preço atual estimado das ordens: {estimated_price}")
            
            log.info(f"[{self.symbol}] ✅ Grid reconstruído com sucesso! {len(recovered_levels)} níveis ativos")
            return recovered_levels
            
        except Exception as e:
            log.error(f"[{self.symbol}] ❌ Erro ao reconstruir grid: {e}", exc_info=True)
            return []

    def _calculate_spacing_from_orders(self, orders: list) -> float:
        """Calcula espaçamento médio das ordens, analisando ordens do mesmo tipo separadamente."""
        try:
            if len(orders) < 2:
                log.warning(f"[{self.symbol}] Ordens insuficientes para calcular espaçamento")
                return None

            # Separar ordens por tipo
            buy_orders = sorted([o for o in orders if o['side'] == 'BUY'], key=lambda x: float(x['price']))
            sell_orders = sorted([o for o in orders if o['side'] == 'SELL'], key=lambda x: float(x['price']))
            
            log.info(f"[{self.symbol}] Analisando {len(buy_orders)} ordens de compra e {len(sell_orders)} ordens de venda")
            
            spacings = []
            
            # Analisar ordens de compra
            if len(buy_orders) >= 2:
                buy_spacings = []
                for i in range(1, len(buy_orders)):
                    price1 = float(buy_orders[i-1]['price'])
                    price2 = float(buy_orders[i]['price'])
                    spacing = abs((price2 - price1) / price1)
                    buy_spacings.append(spacing)
                    log.info(f"[{self.symbol}] BUY spacing: {spacing*100:.2f}% between {price1} and {price2}")
                
                if buy_spacings:
                    avg_buy_spacing = sum(buy_spacings) / len(buy_spacings)
                    log.info(f"[{self.symbol}] Average BUY spacing: {avg_buy_spacing*100:.2f}%")
                    spacings.extend(buy_spacings)
            
            # Analisar ordens de venda
            if len(sell_orders) >= 2:
                sell_spacings = []
                for i in range(1, len(sell_orders)):
                    price1 = float(sell_orders[i-1]['price'])
                    price2 = float(sell_orders[i]['price'])
                    spacing = abs((price2 - price1) / price1)
                    sell_spacings.append(spacing)
                    log.info(f"[{self.symbol}] SELL spacing: {spacing*100:.2f}% between {price1} and {price2}")
                
                if sell_spacings:
                    avg_sell_spacing = sum(sell_spacings) / len(sell_spacings)
                    log.info(f"[{self.symbol}] Average SELL spacing: {avg_sell_spacing*100:.2f}%")
                    spacings.extend(sell_spacings)
            
            # Se temos espaçamentos válidos, calcular média
            if spacings:
                avg_spacing = sum(spacings) / len(spacings)
                log.info(f"[{self.symbol}] Overall average spacing: {avg_spacing*100:.2f}%")
                
                # Verificar consistência dentro de cada grupo (compra/venda)
                spacing_variation = [abs(s - avg_spacing) / avg_spacing for s in spacings]
                is_consistent = all(v < 0.30 for v in spacing_variation)  # Aumentado para 30%
                
                if is_consistent:
                    log.info(f"[{self.symbol}] ✅ Grid spacing is consistent")
                    return avg_spacing
                else:
                    # Se as variações são consistentes dentro de cada grupo, considerar válido
                    if (len(buy_spacings) >= 2 and all(abs(s - avg_buy_spacing) / avg_buy_spacing < 0.30 for s in buy_spacings)) or \
                       (len(sell_spacings) >= 2 and all(abs(s - avg_sell_spacing) / avg_sell_spacing < 0.30 for s in sell_spacings)):
                        log.info(f"[{self.symbol}] ✅ Grid spacing is consistent within buy/sell groups")
                        return avg_spacing
                    
                    log.info(f"[{self.symbol}] ❌ Grid spacing is not consistent")
                    return None
            
            return None
            
        except Exception as e:
            log.error(f"[{self.symbol}] Error calculating spacing: {e}")
            return None

    def _cleanup_orphaned_orders(self, orders: list):
        """Cancela ordens órfãs que não conseguimos reconstruir."""
        try:
            log.warning(f"[{self.symbol}] Cancelando {len(orders)} ordens órfãs...")
            
            for order in orders:
                try:
                    if self.market_type == "spot":
                        self.api_client.cancel_spot_order(symbol=self.symbol, orderId=order['orderId'])
                    else:  # futures
                        self.api_client.cancel_order(symbol=self.symbol, orderId=order['orderId'])
                    
                    log.info(f"[{self.symbol}] Ordem órfã {order['orderId']} cancelada")
                    time.sleep(0.1)  # Pequena pausa entre cancelamentos
                    
                except Exception as e:
                    log.warning(f"[{self.symbol}] Erro ao cancelar ordem órfã {order['orderId']}: {e}")
            
        except Exception as e:
            log.error(f"[{self.symbol}] Erro durante limpeza de ordens órfãs: {e}")

    def _save_grid_state(self):
        """Salva estado atual do grid para persistência."""
        try:
            import json
            import os
            
            state_dir = os.path.join("data", "grid_states")
            os.makedirs(state_dir, exist_ok=True)
            
            state_file = os.path.join(state_dir, f"{self.symbol}_state.json")
            
            state_data = {
                'symbol': self.symbol,
                'market_type': self.market_type,
                'num_levels': self.num_levels,
                'current_spacing_percentage': float(self.current_spacing_percentage),
                'base_spacing_percentage': float(self.base_spacing_percentage),
                'grid_levels': self.grid_levels,
                'active_grid_orders': dict(self.active_grid_orders),
                'last_updated': time.time(),
                'operation_mode': self.operation_mode
            }
            
            with open(state_file, 'w') as f:
                json.dump(state_data, f, indent=2, default=str)
            
            log.debug(f"[{self.symbol}] Estado do grid salvo em {state_file}")
            
        except Exception as e:
            log.warning(f"[{self.symbol}] Erro ao salvar estado do grid: {e}")

    def _load_grid_state(self) -> dict:
        """Carrega estado salvo do grid."""
        try:
            import json
            import os
            
            state_file = os.path.join("data", "grid_states", f"{self.symbol}_state.json")
            
            if not os.path.exists(state_file):
                return None
            
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            # Verificar se o estado não é muito antigo (máximo 24 horas)
            if time.time() - state_data.get('last_updated', 0) > 86400:
                log.info(f"[{self.symbol}] Estado salvo muito antigo - ignorando")
                return None
            
            log.info(f"[{self.symbol}] Estado do grid carregado do arquivo")
            return state_data
            
        except Exception as e:
            log.warning(f"[{self.symbol}] Erro ao carregar estado do grid: {e}")
            return None

    def diagnose_grid(self, symbol=None, market_type=None):
        """Função temporária para diagnosticar estado das ordens e recuperação do grid.
        
        Args:
            symbol (str, optional): Símbolo a ser diagnosticado. Default é o símbolo da instância.
            market_type (str, optional): Tipo de mercado a ser verificado. Default é o mercado atual.
        """
        symbol = symbol or self.symbol
        market_type = market_type or self.market_type
        
        log.info(f"[{symbol}] Iniciando diagnóstico detalhado...")
        
        # Primeiro tentar mercado spot
        try:
            orders = self.api_client.get_spot_open_orders(symbol=symbol)
            if orders:
                log.info(f"[{symbol}] Encontradas {len(orders)} ordens no mercado SPOT:")
                for order in orders:
                    log.info(f"  - Ordem {order['orderId']}: {order['side']} @ {order['price']}")
        except Exception as e:
            log.info(f"[{symbol}] Erro ao buscar ordens SPOT: {e}")
        
        # Depois tentar mercado futures
        try:
            orders = self.api_client.get_futures_open_orders(symbol=symbol)
            if orders:
                log.info(f"[{symbol}] Encontradas {len(orders)} ordens no mercado FUTURES:")
                for order in orders:
                    log.info(f"  - Ordem {order['orderId']}: {order['side']} @ {order['price']}")
        except Exception as e:
            log.info(f"[{symbol}] Erro ao buscar ordens FUTURES: {e}")

        # Verificar configuração atual
        log.info(f"""
        Configuração atual do grid:
        - Mercado: {self.market_type}
        - Número de níveis: {self.num_levels}
        - Espaçamento base: {self.base_spacing_percentage*100:.2f}%
        - Espaçamento atual: {self.current_spacing_percentage*100:.2f}%
        - Níveis ativos: {len(self.grid_levels)}
        - Ordens ativas: {len(self.active_grid_orders)}
        """)
        
        # Verificar posição atual
        try:
            # Atualizar posição para ter informações mais recentes
            self._update_position_info()
            
            if self.market_type == "futures":
                position_amt = self.position.get("positionAmt", Decimal("0"))
                entry_price = self.position.get("entryPrice", Decimal("0"))
                unrealized_pnl = self.position.get("unRealizedProfit", Decimal("0"))
                
                log.info(f"""
                Posição atual (FUTURES):
                - Quantidade: {position_amt}
                - Preço de entrada: {entry_price}
                - PnL não realizado: {unrealized_pnl}
                """)
            else:  # spot
                base_balance = self.position.get("base_balance", Decimal("0"))
                quote_balance = self.position.get("quote_balance", Decimal("0"))
                avg_buy_price = self.position.get("avg_buy_price", Decimal("0"))
                
                log.info(f"""
                Posição atual (SPOT):
                - Saldo base: {base_balance}
                - Saldo quote: {quote_balance}
                - Preço médio de compra: {avg_buy_price}
                """)
        except Exception as e:
            log.info(f"[{symbol}] Erro ao verificar posição atual: {e}")
            
        # Verificar status de recuperação
        recovery_status = "Sim" if getattr(self, '_grid_recovered', False) else "Não"
        log.info(f"[{symbol}] Grid foi recuperado: {recovery_status}")
        
        # Retornar resultado do diagnóstico para uso em outros contextos
        return {
            "symbol": symbol,
            "market_type": self.market_type,
            "spot_orders": len(self.api_client.get_spot_open_orders(symbol=symbol) or []),
            "futures_orders": len(self.api_client.get_futures_open_orders(symbol=symbol) or []),
            "grid_levels": len(self.grid_levels),
            "active_orders": len(self.active_grid_orders),
            "recovered": getattr(self, '_grid_recovered', False)
        }

    def diagnose_grid_recovery(self):
        """Diagnostica e tenta recuperar grid existente."""
        try:
            # 1. Verificar ordens spot
            log.info(f"[{self.symbol}] 🔍 Verificando ordens SPOT...")
            try:
                spot_orders = self.api_client.get_spot_open_orders(symbol=self.symbol)
                if spot_orders:
                    log.info(f"[{self.symbol}] ✅ Encontradas {len(spot_orders)} ordens SPOT:")
                    for order in spot_orders[:5]:  # Mostrar até 5 ordens
                        log.info(f"  - Ordem {order['orderId']}: {order['side']} @ {order['price']}")
            except Exception as e:
                log.error(f"[{self.symbol}] ❌ Erro ao verificar ordens SPOT: {e}")
                spot_orders = []

            # 2. Verificar ordens futures
            log.info(f"[{self.symbol}] 🔍 Verificando ordens FUTURES...")
            try:
                futures_orders = self.api_client.get_futures_open_orders(symbol=self.symbol)
                if futures_orders:
                    log.info(f"[{self.symbol}] ✅ Encontradas {len(futures_orders)} ordens FUTURES:")
                    for order in futures_orders[:5]:  # Mostrar até 5 ordens
                        log.info(f"  - Ordem {order['orderId']}: {order['side']} @ {order['price']}")
            except Exception as e:
                log.error(f"[{self.symbol}] ❌ Erro ao verificar ordens FUTURES: {e}")
                futures_orders = []

            # 3. Analisar ordens encontradas
            if spot_orders:
                log.info(f"[{self.symbol}] Tentando recuperar grid do mercado SPOT...")
                self.market_type = "spot"
                success = self._reconstruct_grid_from_orders(spot_orders)
                if success:
                    log.info(f"[{self.symbol}] ✅ Grid recuperado com sucesso do mercado SPOT")
                    return True

            if futures_orders:
                log.info(f"[{self.symbol}] Tentando recuperar grid do mercado FUTURES...")
                self.market_type = "futures"
                success = self._reconstruct_grid_from_orders(futures_orders)
                if success:
                    log.info(f"[{self.symbol}] ✅ Grid recuperado com sucesso do mercado FUTURES")
                    return True

            log.info(f"[{self.symbol}] ❌ Não foi possível recuperar grid de nenhum mercado")
            return False

        except Exception as e:
            log.error(f"[{self.symbol}] ❌ Erro durante diagnóstico: {e}")
            return False

    def diagnose_grid_state(self):
        """Diagnóstico do estado atual do grid."""
        try:
            # Verificar ordens ativas em ambos os mercados
            log.info(f"[{self.symbol}] 🔍 Verificando ordens em ambos os mercados...")

            # Verificar spot
            try:
                spot_orders = self.api_client.get_spot_open_orders(symbol=self.symbol)
                if spot_orders:
                    log.info(f"[{self.symbol}] ✅ Encontradas {len(spot_orders)} ordens SPOT:")
                    for order in spot_orders:
                        log.info(f"  - Ordem {order['orderId']}: {order['side']} @ {order['price']}")
                        
                    # Analisar espaçamento das ordens spot
                    spot_orders.sort(key=lambda x: float(x['price']))
                    for i in range(1, len(spot_orders)):
                        price1 = float(spot_orders[i-1]['price'])
                        price2 = float(spot_orders[i]['price'])
                        spacing = (price2 - price1) / price1
                        log.info(f"  - Espaçamento entre {price1} e {price2}: {spacing*100:.2f}%")
                else:
                    log.info(f"[{self.symbol}] ℹ️ Nenhuma ordem ativa no mercado SPOT")
            except Exception as e:
                log.error(f"[{self.symbol}] ❌ Erro ao verificar ordens SPOT: {e}")

            # Verificar futures
            try:
                futures_orders = self.api_client.get_futures_open_orders(symbol=self.symbol)
                if futures_orders:
                    log.info(f"[{self.symbol}] ✅ Encontradas {len(futures_orders)} ordens FUTURES:")
                    for order in futures_orders:
                        log.info(f"  - Ordem {order['orderId']}: {order['side']} @ {order['price']}")
                        
                    # Analisar espaçamento das ordens futures
                    futures_orders.sort(key=lambda x: float(x['price']))
                    for i in range(1, len(futures_orders)):
                        price1 = float(futures_orders[i-1]['price'])
                        price2 = float(futures_orders[i]['price'])
                        spacing = (price2 - price1) / price1
                        log.info(f"  - Espaçamento entre {price1} e {price2}: {spacing*100:.2f}%")
                else:
                    log.info(f"[{self.symbol}] ℹ️ Nenhuma ordem ativa no mercado FUTURES")
            except Exception as e:
                log.error(f"[{self.symbol}] ❌ Erro ao verificar ordens FUTURES: {e}")

            # Verificar estado atual do bot
            log.info(f"""
            Estado atual do bot:
            - Mercado configurado: {self.market_type}
            - Níveis no grid: {len(self.grid_levels)}
            - Ordens ativas rastreadas: {len(self.active_grid_orders)}
            - Grid recuperado: {getattr(self, '_grid_recovered', False)}
            - Tentativa de recuperação feita: {getattr(self, '_recovery_attempted', False)}
            """)

        except Exception as e:
            log.error(f"[{self.symbol}] ❌ Erro durante diagnóstico: {e}")

    def _check_existing_position(self):
        """
        Verifica se há posições existentes que indicam um grid ativo.
        Retorna informações da posição encontrada ou None.
        """
        try:
            log.info(f"[{self.symbol}] 🔍 Verificando posições existentes...")
            
            # Verificar posições futures primeiro
            if self.market_type == "futures":
                try:
                    positions = self.api_client.get_futures_positions()
                    for position in positions:
                        if position.get('symbol') == self.symbol:
                            position_amt = float(position.get('positionAmt', 0))
                            if position_amt != 0:
                                entry_price = float(position.get('entryPrice', 0))
                                mark_price = float(position.get('markPrice', 0))
                                unrealized_pnl = float(position.get('unRealizedProfit', 0))
                                
                                log.info(f"[{self.symbol}] ✅ Posição FUTURES encontrada:")
                                log.info(f"  - Quantidade: {position_amt}")
                                log.info(f"  - Preço de entrada: ${entry_price}")
                                log.info(f"  - Preço atual: ${mark_price}")
                                log.info(f"  - PnL não realizado: ${unrealized_pnl}")
                                
                                # Atualizar estado interno da posição
                                self.position = {
                                    'positionAmt': str(position_amt),
                                    'entryPrice': str(entry_price),
                                    'markPrice': str(mark_price),
                                    'unRealizedProfit': str(unrealized_pnl)
                                }
                                
                                # Se há posição, significa que o grid estava ativo
                                # Inicializar espaçamento básico para retomar o grid
                                self.current_spacing_percentage = self.base_spacing_percentage
                                
                                return {
                                    'symbol': self.symbol,
                                    'position_amt': position_amt,
                                    'entry_price': entry_price,
                                    'mark_price': mark_price,
                                    'unrealized_pnl': unrealized_pnl,
                                    'market_type': 'futures'
                                }
                except Exception as e:
                    log.warning(f"[{self.symbol}] Erro ao verificar posições FUTURES: {e}")
            
            # Verificar saldo spot se não encontrou posição futures
            if self.market_type == "spot":
                try:
                    # Extrair base asset do símbolo (ex: ADAUSDT -> ADA)
                    base_asset = self.symbol.replace('USDT', '').replace('BUSD', '').replace('BTC', '').replace('ETH', '')
                    if self.symbol.endswith('BTC'):
                        base_asset = self.symbol.replace('BTC', '')
                    elif self.symbol.endswith('ETH'):
                        base_asset = self.symbol.replace('ETH', '')
                    else:
                        base_asset = self.symbol.replace('USDT', '').replace('BUSD', '')
                    
                    account_info = self.api_client.get_spot_account()
                    if account_info and 'balances' in account_info:
                        for balance in account_info['balances']:
                            if balance['asset'] == base_asset:
                                free_balance = float(balance['free'])
                                locked_balance = float(balance['locked'])
                                total_balance = free_balance + locked_balance
                                
                                if total_balance > 0:
                                    log.info(f"[{self.symbol}] ✅ Saldo SPOT encontrado para {base_asset}:")
                                    log.info(f"  - Saldo livre: {free_balance}")
                                    log.info(f"  - Saldo bloqueado: {locked_balance}")
                                    log.info(f"  - Total: {total_balance}")
                                    
                                    # Se há saldo do ativo, pode indicar grid anterior
                                    self.current_spacing_percentage = self.base_spacing_percentage
                                    
                                    return {
                                        'symbol': self.symbol,
                                        'base_asset': base_asset,
                                        'free_balance': free_balance,
                                        'locked_balance': locked_balance,
                                        'total_balance': total_balance,
                                        'market_type': 'spot'
                                    }
                except Exception as e:
                    log.warning(f"[{self.symbol}] Erro ao verificar saldos SPOT: {e}")
            
            log.info(f"[{self.symbol}] ❌ Nenhuma posição existente encontrada")
            return None
            
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao verificar posições existentes: {e}")
            return None

    def cancel_all_orders(self):
        """Cancel all active orders for the current symbol in both markets."""
        try:
            log.info(f"[{self.symbol}] Cancelling all orders during cleanup...")
            
            # Cancel spot orders
            try:
                spot_orders = self.api_client.get_spot_open_orders(symbol=self.symbol)
                for order in spot_orders:
                    try:
                        self.api_client.cancel_spot_order(symbol=self.symbol, orderId=order['orderId'])
                        log.info(f"[{self.symbol}] Cancelled SPOT order {order['orderId']}")
                    except Exception as e:
                        log.warning(f"[{self.symbol}] Failed to cancel SPOT order {order['orderId']}: {e}")
            except Exception as e:
                log.warning(f"[{self.symbol}] Error cancelling SPOT orders: {e}")
            
            # Cancel futures orders
            try:
                futures_orders = self.api_client.get_futures_open_orders(symbol=self.symbol)
                for order in futures_orders:
                    try:
                        self.api_client.cancel_futures_order(symbol=self.symbol, orderId=order['orderId'])
                        log.info(f"[{self.symbol}] Cancelled FUTURES order {order['orderId']}")
                    except Exception as e:
                        log.warning(f"[{self.symbol}] Failed to cancel FUTURES order {order['orderId']}: {e}")
            except Exception as e:
                log.warning(f"[{self.symbol}] Error cancelling FUTURES orders: {e}")
                
            # Clear internal tracking
            self.active_grid_orders.clear()
            log.info(f"[{self.symbol}] Order cleanup completed")
            
        except Exception as e:
            log.error(f"[{self.symbol}] Error during cancel_all_orders: {e}")
    
    def _round_price(self, price: float) -> str:
        """Round price to appropriate precision for the symbol using proper formatting."""
        try:
            # Use the proper formatting function that respects exchange rules
            formatted = self._format_price(price)
            if formatted is not None:
                return formatted
            else:
                # Fallback to simple rounding if formatting fails
                return str(round(price, 8))
        except Exception as e:
            log.error(f"[{self.symbol}] Error rounding price {price}: {e}")
            return str(price)
    
    def _round_quantity(self, quantity: float) -> str:
        """Round quantity to appropriate precision for the symbol using proper formatting."""
        try:
            # Use the proper formatting function that respects exchange rules
            formatted = self._format_quantity(quantity)
            if formatted is not None:
                return formatted
            else:
                # Fallback to simple rounding if formatting fails
                return str(round(quantity, 6))
        except Exception as e:
            log.error(f"[{self.symbol}] Error rounding quantity {quantity}: {e}")
            return str(quantity)
