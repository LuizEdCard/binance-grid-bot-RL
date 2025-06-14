#!/usr/bin/env python3
"""
Sistema de Ordens Condicionais para Multi-Agent Trading Bot
Implementa ordens baseadas em condições técnicas e de mercado
"""

import time
import threading
from decimal import Decimal
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import logging

log = logging.getLogger(__name__)

class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LIMIT = "STOP_LIMIT"
    STOP_MARKET = "STOP_MARKET"

class ConditionType(Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    RSI_OVERSOLD = "rsi_oversold"
    RSI_OVERBOUGHT = "rsi_overbought"
    VOLUME_SPIKE = "volume_spike"
    MA_CROSS_ABOVE = "ma_cross_above"
    MA_CROSS_BELOW = "ma_cross_below"
    ATR_BREAKOUT = "atr_breakout"
    MACD_SIGNAL = "macd_signal"
    BOLLINGER_BREAK = "bollinger_break"
    CUSTOM = "custom"

@dataclass
class ConditionalOrderConfig:
    """Configuração para ordem condicional"""
    order_id: str
    symbol: str
    side: str  # BUY ou SELL
    order_type: OrderType
    quantity: str
    price: Optional[str] = None
    stop_price: Optional[str] = None
    condition_type: ConditionType = ConditionType.PRICE_ABOVE
    condition_value: float = 0.0
    condition_params: Dict[str, Any] = None
    custom_condition: Optional[Callable] = None
    expiry_time: Optional[float] = None
    max_checks: int = 1000
    check_interval: int = 5  # segundos

@dataclass
class ConditionalOrderState:
    """Estado atual da ordem condicional"""
    config: ConditionalOrderConfig
    created_at: float
    checks_performed: int = 0
    last_check: float = 0
    is_active: bool = True
    triggered: bool = False
    executed: bool = False
    error_count: int = 0
    last_error: Optional[str] = None

class ConditionalOrderManager:
    """Gerenciador de ordens condicionais"""
    
    def __init__(self, api_client, alerter=None):
        self.api_client = api_client
        self.alerter = alerter
        self.orders: Dict[str, ConditionalOrderState] = {}
        self.stop_event = threading.Event()
        self.monitor_thread = None
        self.stats = {
            "total_orders": 0,
            "triggered_orders": 0,
            "executed_orders": 0,
            "expired_orders": 0,
            "failed_orders": 0
        }
        
        # Registrar condições padrão
        self.condition_handlers = {
            ConditionType.PRICE_ABOVE: self._check_price_above,
            ConditionType.PRICE_BELOW: self._check_price_below,
            ConditionType.RSI_OVERSOLD: self._check_rsi_oversold,
            ConditionType.RSI_OVERBOUGHT: self._check_rsi_overbought,
            ConditionType.VOLUME_SPIKE: self._check_volume_spike,
            ConditionType.MA_CROSS_ABOVE: self._check_ma_cross_above,
            ConditionType.MA_CROSS_BELOW: self._check_ma_cross_below,
            ConditionType.ATR_BREAKOUT: self._check_atr_breakout,
            ConditionType.MACD_SIGNAL: self._check_macd_signal,
            ConditionType.BOLLINGER_BREAK: self._check_bollinger_break,
            ConditionType.CUSTOM: self._check_custom_condition
        }
        
        log.info("ConditionalOrderManager inicializado")
    
    def start_monitoring(self):
        """Inicia thread de monitoramento"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
            
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="ConditionalOrderMonitor"
        )
        self.monitor_thread.start()
        log.info("Monitoramento de ordens condicionais iniciado")
    
    def stop_monitoring(self):
        """Para thread de monitoramento"""
        self.stop_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
        log.info("Monitoramento de ordens condicionais parado")
    
    def add_conditional_order(self, config: ConditionalOrderConfig) -> bool:
        """Adiciona ordem condicional"""
        try:
            if config.order_id in self.orders:
                log.warning(f"Ordem condicional {config.order_id} já existe")
                return False
            
            # Validar configuração
            if not self._validate_config(config):
                return False
            
            # Criar estado da ordem
            state = ConditionalOrderState(
                config=config,
                created_at=time.time()
            )
            
            self.orders[config.order_id] = state
            self.stats["total_orders"] += 1
            
            log.info(f"Ordem condicional adicionada: {config.order_id} - "
                    f"{config.symbol} {config.side} {config.condition_type.value}")
            
            if self.alerter:
                self.alerter.send_message(
                    f"📋 Ordem Condicional Criada\\n"
                    f"🎯 {config.symbol} {config.side}\\n"
                    f"📊 Condição: {config.condition_type.value}\\n"
                    f"💰 Quantidade: {config.quantity}\\n"
                    f"🎚️ Valor: {config.condition_value}"
                )
            
            return True
            
        except Exception as e:
            log.error(f"Erro ao adicionar ordem condicional: {e}")
            return False
    
    def remove_conditional_order(self, order_id: str) -> bool:
        """Remove ordem condicional"""
        if order_id in self.orders:
            self.orders[order_id].is_active = False
            del self.orders[order_id]
            log.info(f"Ordem condicional removida: {order_id}")
            return True
        return False
    
    def _monitoring_loop(self):
        """Loop principal de monitoramento"""
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                orders_to_remove = []
                
                for order_id, state in self.orders.items():
                    if not state.is_active:
                        continue
                    
                    # Verificar expiração
                    if (state.config.expiry_time and 
                        current_time > state.config.expiry_time):
                        log.info(f"Ordem condicional expirada: {order_id}")
                        state.is_active = False
                        orders_to_remove.append(order_id)
                        self.stats["expired_orders"] += 1
                        continue
                    
                    # Verificar limite de checks
                    if state.checks_performed >= state.config.max_checks:
                        log.info(f"Limite de verificações atingido: {order_id}")
                        state.is_active = False
                        orders_to_remove.append(order_id)
                        continue
                    
                    # Verificar intervalo
                    if (current_time - state.last_check < 
                        state.config.check_interval):
                        continue
                    
                    # Executar verificação da condição
                    self._check_order_condition(state)
                
                # Remover ordens inativas
                for order_id in orders_to_remove:
                    if order_id in self.orders:
                        del self.orders[order_id]
                
                # Aguardar próxima iteração
                self.stop_event.wait(1)
                
            except Exception as e:
                log.error(f"Erro no loop de monitoramento: {e}")
                self.stop_event.wait(5)
    
    def _check_order_condition(self, state: ConditionalOrderState):
        """Verifica condição de uma ordem"""
        try:
            state.last_check = time.time()
            state.checks_performed += 1
            
            config = state.config
            condition_met = False
            
            # Verificar condição usando handler apropriado
            if config.condition_type in self.condition_handlers:
                handler = self.condition_handlers[config.condition_type]
                condition_met = handler(config)
            else:
                log.warning(f"Tipo de condição não suportado: {config.condition_type}")
                return
            
            if condition_met and not state.triggered:
                state.triggered = True
                self.stats["triggered_orders"] += 1
                
                log.info(f"Condição atingida para ordem: {config.order_id}")
                
                # Executar ordem
                success = self._execute_order(state)
                if success:
                    state.executed = True
                    state.is_active = False
                    self.stats["executed_orders"] += 1
                else:
                    state.error_count += 1
                    self.stats["failed_orders"] += 1
                    
                    # Desativar após muitos erros
                    if state.error_count >= 3:
                        state.is_active = False
                        log.error(f"Ordem desativada após {state.error_count} erros: {config.order_id}")
        
        except Exception as e:
            log.error(f"Erro ao verificar condição da ordem {state.config.order_id}: {e}")
            state.error_count += 1
            state.last_error = str(e)
    
    def _execute_order(self, state: ConditionalOrderState) -> bool:
        """Executa ordem quando condição é atingida"""
        try:
            config = state.config
            
            log.info(f"Executando ordem condicional: {config.order_id}")
            
            # Preparar parâmetros da ordem
            order_params = {
                "symbol": config.symbol,
                "side": config.side,
                "quantity": config.quantity
            }
            
            # Adicionar parâmetros específicos por tipo
            if config.order_type == OrderType.LIMIT:
                if not config.price:
                    log.error(f"Preço obrigatório para ordem LIMIT: {config.order_id}")
                    return False
                order_params["order_type"] = "LIMIT"
                order_params["price"] = config.price
                order_params["time_in_force"] = "GTC"
                
            elif config.order_type == OrderType.MARKET:
                order_params["order_type"] = "MARKET"
                
            elif config.order_type == OrderType.STOP_LIMIT:
                if not config.stop_price or not config.price:
                    log.error(f"Stop price e price obrigatórios para STOP_LIMIT: {config.order_id}")
                    return False
                order_params["order_type"] = "STOP"
                order_params["price"] = config.price
                order_params["stop_price"] = config.stop_price
                order_params["time_in_force"] = "GTC"
                
            elif config.order_type == OrderType.STOP_MARKET:
                if not config.stop_price:
                    log.error(f"Stop price obrigatório para STOP_MARKET: {config.order_id}")
                    return False
                order_params["order_type"] = "STOP_MARKET"
                order_params["stop_price"] = config.stop_price
            
            # Executar ordem via API
            result = self.api_client.place_futures_order(**order_params)
            
            if result and "orderId" in result:
                log.info(f"Ordem condicional executada com sucesso: {config.order_id} -> Order ID: {result['orderId']}")
                
                if self.alerter:
                    self.alerter.send_message(
                        f"✅ Ordem Condicional EXECUTADA!\\n"
                        f"🎯 {config.symbol} {config.side}\\n"
                        f"📊 Tipo: {config.order_type.value}\\n"
                        f"💰 Quantidade: {config.quantity}\\n"
                        f"🆔 Order ID: {result['orderId']}"
                    )
                
                return True
            else:
                log.error(f"Falha ao executar ordem condicional: {config.order_id}")
                return False
                
        except Exception as e:
            log.error(f"Erro ao executar ordem condicional {state.config.order_id}: {e}")
            state.last_error = str(e)
            return False
    
    def _validate_config(self, config: ConditionalOrderConfig) -> bool:
        """Valida configuração da ordem condicional"""
        try:
            # Validações básicas
            if not config.symbol or not config.side or not config.quantity:
                log.error("Symbol, side e quantity são obrigatórios")
                return False
            
            if config.side not in ["BUY", "SELL"]:
                log.error("Side deve ser BUY ou SELL")
                return False
            
            if config.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and not config.price:
                log.error("Price é obrigatório para ordens LIMIT e STOP_LIMIT")
                return False
            
            if config.order_type in [OrderType.STOP_LIMIT, OrderType.STOP_MARKET] and not config.stop_price:
                log.error("Stop price é obrigatório para ordens STOP")
                return False
            
            return True
            
        except Exception as e:
            log.error(f"Erro na validação: {e}")
            return False
    
    # Handlers de condições específicas
    def _check_price_above(self, config: ConditionalOrderConfig) -> bool:
        """Verifica se preço está acima do valor"""
        try:
            ticker = self.api_client.get_futures_ticker(config.symbol)
            if ticker:
                current_price = float(ticker.get("price", 0))
                return current_price > config.condition_value
        except Exception as e:
            log.error(f"Erro ao verificar price_above: {e}")
        return False
    
    def _check_price_below(self, config: ConditionalOrderConfig) -> bool:
        """Verifica se preço está abaixo do valor"""
        try:
            ticker = self.api_client.get_futures_ticker(config.symbol)
            if ticker:
                current_price = float(ticker.get("price", 0))
                return current_price < config.condition_value
        except Exception as e:
            log.error(f"Erro ao verificar price_below: {e}")
        return False
    
    def _check_rsi_oversold(self, config: ConditionalOrderConfig) -> bool:
        """Verifica RSI oversold"""
        try:
            # Buscar dados históricos e calcular RSI
            klines = self.api_client.get_futures_klines(config.symbol, "1h", 20)
            if not klines or len(klines) < 14:
                return False
            
            closes = [float(k[4]) for k in klines]
            
            # Calcular RSI simples
            gains = []
            losses = []
            for i in range(1, len(closes)):
                change = closes[i] - closes[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            if len(gains) < 14:
                return False
            
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            
            if avg_loss == 0:
                return False
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            threshold = config.condition_params.get("rsi_threshold", 30) if config.condition_params else 30
            return rsi < threshold
            
        except Exception as e:
            log.error(f"Erro ao calcular RSI: {e}")
        return False
    
    def _check_rsi_overbought(self, config: ConditionalOrderConfig) -> bool:
        """Verifica RSI overbought"""
        # Similar ao oversold, mas threshold > 70
        try:
            # Implementação similar ao _check_rsi_oversold
            # mas verificando se RSI > threshold (default 70)
            threshold = config.condition_params.get("rsi_threshold", 70) if config.condition_params else 70
            # ... (código similar ao oversold)
            return False  # Placeholder
        except Exception as e:
            log.error(f"Erro ao verificar RSI overbought: {e}")
        return False
    
    def _check_volume_spike(self, config: ConditionalOrderConfig) -> bool:
        """Verifica spike de volume"""
        try:
            klines = self.api_client.get_futures_klines(config.symbol, "1h", 10)
            if not klines or len(klines) < 5:
                return False
            
            volumes = [float(k[5]) for k in klines]
            current_volume = volumes[-1]
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1])
            
            multiplier = config.condition_params.get("volume_multiplier", 2.0) if config.condition_params else 2.0
            return current_volume > avg_volume * multiplier
            
        except Exception as e:
            log.error(f"Erro ao verificar volume spike: {e}")
        return False
    
    def _check_ma_cross_above(self, config: ConditionalOrderConfig) -> bool:
        """Verifica cruzamento de médias móveis para cima"""
        # Implementação placeholder
        return False
    
    def _check_ma_cross_below(self, config: ConditionalOrderConfig) -> bool:
        """Verifica cruzamento de médias móveis para baixo"""
        # Implementação placeholder  
        return False
    
    def _check_atr_breakout(self, config: ConditionalOrderConfig) -> bool:
        """Verifica breakout baseado em ATR"""
        # Implementação placeholder
        return False
    
    def _check_macd_signal(self, config: ConditionalOrderConfig) -> bool:
        """Verifica sinal MACD"""
        # Implementação placeholder
        return False
    
    def _check_bollinger_break(self, config: ConditionalOrderConfig) -> bool:
        """Verifica quebra das bandas de Bollinger"""
        # Implementação placeholder
        return False
    
    def _check_custom_condition(self, config: ConditionalOrderConfig) -> bool:
        """Verifica condição customizada"""
        try:
            if config.custom_condition:
                return config.custom_condition(config, self.api_client)
        except Exception as e:
            log.error(f"Erro ao verificar condição customizada: {e}")
        return False
    
    def get_active_orders(self) -> Dict[str, Dict]:
        """Retorna ordens ativas"""
        active = {}
        for order_id, state in self.orders.items():
            if state.is_active:
                active[order_id] = {
                    "symbol": state.config.symbol,
                    "side": state.config.side,
                    "condition_type": state.config.condition_type.value,
                    "condition_value": state.config.condition_value,
                    "checks_performed": state.checks_performed,
                    "created_at": state.created_at,
                    "triggered": state.triggered,
                    "error_count": state.error_count
                }
        return active
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do sistema"""
        return {
            "total_orders": self.stats["total_orders"],
            "active_orders": len([s for s in self.orders.values() if s.is_active]),
            "triggered_orders": self.stats["triggered_orders"],
            "executed_orders": self.stats["executed_orders"],
            "expired_orders": self.stats["expired_orders"],
            "failed_orders": self.stats["failed_orders"],
            "success_rate": (self.stats["executed_orders"] / max(1, self.stats["triggered_orders"])) * 100
        }

# Exemplo de uso
if __name__ == "__main__":
    # Configuração de exemplo
    config = ConditionalOrderConfig(
        order_id="test_order_1",
        symbol="BTCUSDT",
        side="BUY",
        order_type=OrderType.LIMIT,
        quantity="0.001",
        price="45000",
        condition_type=ConditionType.PRICE_BELOW,
        condition_value=44000.0,
        expiry_time=time.time() + 3600  # 1 hora
    )
    
    # Simulação sem API real
    manager = ConditionalOrderManager(api_client=None)
    manager.add_conditional_order(config)
    
    print(f"Ordens ativas: {manager.get_active_orders()}")
    print(f"Estatísticas: {manager.get_statistics()}")