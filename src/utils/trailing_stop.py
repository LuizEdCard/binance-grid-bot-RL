#!/usr/bin/env python3
"""
Sistema de Trailing Stop para Multi-Agent Trading Bot
Implementa trailing stop dinâmico que se ajusta conforme o preço se move favoravelmente
"""

import time
from decimal import Decimal
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

log = logging.getLogger(__name__)

class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"

@dataclass
class TrailingStopConfig:
    """Configuração do trailing stop"""
    trail_amount: float  # Distância do trailing em USDT ou %
    trail_type: str = "percentage"  # "percentage" ou "fixed"
    activation_threshold: float = 0.5  # % de lucro para ativar trailing
    min_trail_distance: float = 0.001  # Distância mínima do trailing (1 tick)
    max_trail_distance: float = 0.05   # Distância máxima do trailing (5%)
    update_frequency: int = 5  # Atualizar a cada X segundos

@dataclass
class TrailingStopState:
    """Estado atual do trailing stop para uma posição"""
    symbol: str
    position_side: PositionSide
    entry_price: float
    current_stop_price: float
    highest_profitable_price: float  # Para LONG
    lowest_profitable_price: float   # Para SHORT
    is_active: bool = False
    last_update: float = 0
    profit_threshold_reached: bool = False
    total_adjustments: int = 0

class TrailingStopManager:
    """Gerenciador de trailing stops para múltiplas posições"""
    
    def __init__(self, api_client, alerter=None):
        self.api_client = api_client
        self.alerter = alerter
        self.trailing_stops: Dict[str, TrailingStopState] = {}
        self.configs: Dict[str, TrailingStopConfig] = {}
        self.stats = {
            "total_adjustments": 0,
            "successful_trailing_exits": 0,
            "profit_protected": 0.0
        }
    
    def add_trailing_stop(self, symbol: str, config: TrailingStopConfig, 
                         position_side: PositionSide, entry_price: float, 
                         initial_stop_price: float) -> bool:
        """Adiciona um trailing stop para uma posição"""
        try:
            current_time = time.time()
            
            # Determinar preços iniciais baseado na direção da posição
            if position_side == PositionSide.LONG:
                highest_price = entry_price
                lowest_price = 0
            elif position_side == PositionSide.SHORT:
                highest_price = 0
                lowest_price = entry_price
            else:
                log.warning(f"[{symbol}] Cannot add trailing stop for NONE position")
                return False
            
            # Criar estado do trailing stop
            trailing_state = TrailingStopState(
                symbol=symbol,
                position_side=position_side,
                entry_price=entry_price,
                current_stop_price=initial_stop_price,
                highest_profitable_price=highest_price,
                lowest_profitable_price=lowest_price,
                is_active=False,  # Será ativado quando atingir threshold
                last_update=current_time,
                profit_threshold_reached=False,
                total_adjustments=0
            )
            
            self.trailing_stops[symbol] = trailing_state
            self.configs[symbol] = config
            
            log.info(f"[{symbol}] Trailing stop adicionado - "
                    f"Side: {position_side.value}, Entry: ${entry_price:.4f}, "
                    f"Initial Stop: ${initial_stop_price:.4f}, "
                    f"Trail: {config.trail_amount}{'%' if config.trail_type == 'percentage' else ' USDT'}")
            
            if self.alerter:
                self.alerter.send_message(
                    f"🎯 Trailing Stop ativado para {symbol}\n"
                    f"📍 Entry: ${entry_price:.4f}\n"
                    f"🛡️ Stop inicial: ${initial_stop_price:.4f}\n"
                    f"📏 Trail: {config.trail_amount}{'%' if config.trail_type == 'percentage' else ' USDT'}"
                )
            
            return True
            
        except Exception as e:
            log.error(f"[{symbol}] Erro ao adicionar trailing stop: {e}")
            return False
    
    def update_trailing_stop(self, symbol: str, current_price: float) -> Optional[float]:
        """Atualiza trailing stop baseado no preço atual"""
        if symbol not in self.trailing_stops:
            return None
        
        try:
            state = self.trailing_stops[symbol]
            config = self.configs[symbol]
            current_time = time.time()
            
            # Verificar se é hora de atualizar
            if current_time - state.last_update < config.update_frequency:
                return None
            
            state.last_update = current_time
            old_stop_price = state.current_stop_price
            new_stop_price = None
            
            if state.position_side == PositionSide.LONG:
                new_stop_price = self._update_long_trailing_stop(state, config, current_price)
            elif state.position_side == PositionSide.SHORT:
                new_stop_price = self._update_short_trailing_stop(state, config, current_price)
            
            # Verificar se houve atualização
            if new_stop_price and new_stop_price != old_stop_price:
                state.current_stop_price = new_stop_price
                state.total_adjustments += 1
                self.stats["total_adjustments"] += 1
                
                log.info(f"[{symbol}] Trailing stop ajustado - "
                        f"${old_stop_price:.4f} → ${new_stop_price:.4f} "
                        f"(Price: ${current_price:.4f})")
                
                if self.alerter:
                    profit = self._calculate_current_profit(state, current_price)
                    self.alerter.send_message(
                        f"📈 {symbol} Trailing Stop ajustado\n"
                        f"🔄 ${old_stop_price:.4f} → ${new_stop_price:.4f}\n"
                        f"💰 Lucro atual: ${profit:.2f}\n"
                        f"📊 Preço: ${current_price:.4f}"
                    )
                
                return new_stop_price
            
            return None
            
        except Exception as e:
            log.error(f"[{symbol}] Erro ao atualizar trailing stop: {e}")
            return None
    
    def _update_long_trailing_stop(self, state: TrailingStopState, 
                                  config: TrailingStopConfig, current_price: float) -> Optional[float]:
        """Atualiza trailing stop para posição LONG"""
        
        # Verificar se atingiu threshold de ativação
        if not state.profit_threshold_reached:
            profit_pct = (current_price - state.entry_price) / state.entry_price * 100
            if profit_pct >= config.activation_threshold:
                state.profit_threshold_reached = True
                state.is_active = True
                log.info(f"[{state.symbol}] Trailing stop ATIVADO - Lucro: {profit_pct:.2f}%")
        
        if not state.is_active:
            return None
        
        # Atualizar maior preço alcançado
        if current_price > state.highest_profitable_price:
            state.highest_profitable_price = current_price
            
            # Calcular novo stop price
            if config.trail_type == "percentage":
                trail_distance = current_price * (config.trail_amount / 100)
            else:
                trail_distance = config.trail_amount
            
            # Aplicar limites mínimos e máximos
            min_distance = current_price * config.min_trail_distance
            max_distance = current_price * config.max_trail_distance
            trail_distance = max(min_distance, min(trail_distance, max_distance))
            
            new_stop = current_price - trail_distance
            
            # Só atualizar se o novo stop for maior que o atual (para LONG)
            if new_stop > state.current_stop_price:
                return new_stop
        
        return None
    
    def _update_short_trailing_stop(self, state: TrailingStopState, 
                                   config: TrailingStopConfig, current_price: float) -> Optional[float]:
        """Atualiza trailing stop para posição SHORT"""
        
        # Verificar se atingiu threshold de ativação
        if not state.profit_threshold_reached:
            profit_pct = (state.entry_price - current_price) / state.entry_price * 100
            if profit_pct >= config.activation_threshold:
                state.profit_threshold_reached = True
                state.is_active = True
                log.info(f"[{state.symbol}] Trailing stop ATIVADO - Lucro: {profit_pct:.2f}%")
        
        if not state.is_active:
            return None
        
        # Atualizar menor preço alcançado
        if state.lowest_profitable_price == 0 or current_price < state.lowest_profitable_price:
            state.lowest_profitable_price = current_price
            
            # Calcular novo stop price
            if config.trail_type == "percentage":
                trail_distance = current_price * (config.trail_amount / 100)
            else:
                trail_distance = config.trail_amount
            
            # Aplicar limites mínimos e máximos
            min_distance = current_price * config.min_trail_distance
            max_distance = current_price * config.max_trail_distance
            trail_distance = max(min_distance, min(trail_distance, max_distance))
            
            new_stop = current_price + trail_distance
            
            # Só atualizar se o novo stop for menor que o atual (para SHORT)
            if new_stop < state.current_stop_price:
                return new_stop
        
        return None
    
    def _calculate_current_profit(self, state: TrailingStopState, current_price: float) -> float:
        """Calcula lucro atual da posição"""
        if state.position_side == PositionSide.LONG:
            return current_price - state.entry_price
        elif state.position_side == PositionSide.SHORT:
            return state.entry_price - current_price
        return 0.0
    
    def check_stop_triggered(self, symbol: str, current_price: float) -> bool:
        """Verifica se o stop foi atingido"""
        if symbol not in self.trailing_stops:
            return False
        
        state = self.trailing_stops[symbol]
        
        if state.position_side == PositionSide.LONG:
            triggered = current_price <= state.current_stop_price
        elif state.position_side == PositionSide.SHORT:
            triggered = current_price >= state.current_stop_price
        else:
            return False
        
        if triggered:
            profit = self._calculate_current_profit(state, current_price)
            self.stats["successful_trailing_exits"] += 1
            self.stats["profit_protected"] += profit
            
            log.info(f"[{symbol}] Trailing stop ACIONADO - "
                    f"Preço: ${current_price:.4f}, Stop: ${state.current_stop_price:.4f}, "
                    f"Lucro protegido: ${profit:.2f}")
            
            if self.alerter:
                self.alerter.send_message(
                    f"🛑 {symbol} Trailing Stop ACIONADO!\n"
                    f"💲 Preço: ${current_price:.4f}\n"
                    f"🛡️ Stop: ${state.current_stop_price:.4f}\n"
                    f"💰 Lucro protegido: ${profit:.2f}\n"
                    f"📊 Ajustes realizados: {state.total_adjustments}"
                )
        
        return triggered
    
    def remove_trailing_stop(self, symbol: str) -> bool:
        """Remove trailing stop de uma posição"""
        if symbol in self.trailing_stops:
            state = self.trailing_stops[symbol]
            del self.trailing_stops[symbol]
            del self.configs[symbol]
            
            log.info(f"[{symbol}] Trailing stop removido - Total ajustes: {state.total_adjustments}")
            return True
        return False
    
    def get_trailing_stop_info(self, symbol: str) -> Optional[Dict]:
        """Retorna informações do trailing stop"""
        if symbol not in self.trailing_stops:
            return None
        
        state = self.trailing_stops[symbol]
        config = self.configs[symbol]
        
        return {
            "symbol": symbol,
            "position_side": state.position_side.value,
            "entry_price": state.entry_price,
            "current_stop_price": state.current_stop_price,
            "is_active": state.is_active,
            "profit_threshold_reached": state.profit_threshold_reached,
            "total_adjustments": state.total_adjustments,
            "trail_amount": config.trail_amount,
            "trail_type": config.trail_type,
            "activation_threshold": config.activation_threshold
        }
    
    def get_all_trailing_stops(self) -> Dict[str, Dict]:
        """Retorna informações de todos os trailing stops"""
        return {symbol: self.get_trailing_stop_info(symbol) 
                for symbol in self.trailing_stops.keys()}
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do trailing stop manager"""
        active_stops = len([s for s in self.trailing_stops.values() if s.is_active])
        return {
            "total_trailing_stops": len(self.trailing_stops),
            "active_trailing_stops": active_stops,
            "total_adjustments": self.stats["total_adjustments"],
            "successful_exits": self.stats["successful_trailing_exits"],
            "profit_protected": self.stats["profit_protected"]
        }

# Exemplo de uso
if __name__ == "__main__":
    # Configuração de exemplo
    config = TrailingStopConfig(
        trail_amount=1.0,  # 1% de trailing
        trail_type="percentage",
        activation_threshold=0.5,  # Ativar com 0.5% de lucro
        min_trail_distance=0.001,
        max_trail_distance=0.05,
        update_frequency=5
    )
    
    # Simulação básica
    manager = TrailingStopManager(api_client=None)
    
    # Adicionar trailing stop para posição LONG
    manager.add_trailing_stop(
        symbol="BTCUSDT",
        config=config,
        position_side=PositionSide.LONG,
        entry_price=50000.0,
        initial_stop_price=49500.0
    )
    
    # Simular movimento de preços
    prices = [50000, 50200, 50500, 50800, 50600, 50300, 50100]
    
    for price in prices:
        print(f"\nPreço: ${price}")
        new_stop = manager.update_trailing_stop("BTCUSDT", price)
        if new_stop:
            print(f"Stop atualizado para: ${new_stop:.2f}")
        
        if manager.check_stop_triggered("BTCUSDT", price):
            print("STOP ACIONADO!")
            break
    
    print(f"\nEstatísticas: {manager.get_stats()}")
    print(f"Info do stop: {manager.get_trailing_stop_info('BTCUSDT')}")