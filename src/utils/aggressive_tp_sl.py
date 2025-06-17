#!/usr/bin/env python3
"""
Aggressive Take Profit and Stop Loss Manager
Implements tight TP/SL for small profits (0.01-0.05 USDT) with trailing stops
"""

import time
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from threading import Thread, Lock
import logging

from .trade_logger import get_trade_logger
from .logger import setup_logger

log = setup_logger("aggressive_tp_sl")

@dataclass
class TPSLOrder:
    """Take Profit / Stop Loss order data."""
    symbol: str
    position_side: str  # "LONG" or "SHORT"
    entry_price: Decimal
    quantity: Decimal
    tp_price: Optional[Decimal] = None
    sl_price: Optional[Decimal] = None
    tp_order_id: Optional[str] = None
    sl_order_id: Optional[str] = None
    trailing_stop_price: Optional[Decimal] = None
    trailing_distance: Decimal = Decimal("0.001")  # 0.1%
    created_at: float = 0.0
    last_update: float = 0.0
    failed_attempts: int = 0  # Track failed order attempts to prevent infinite loops
    max_failed_attempts: int = 3  # Maximum failed attempts before removing position

class AggressiveTPSLManager:
    """
    Manages aggressive Take Profit and Stop Loss orders for small profits.
    Targets 0.01-0.05 USDT profits with trailing stops.
    """
    
    def __init__(self, api_client, config: Dict):
        """
        Initialize aggressive TP/SL manager.
        
        Args:
            api_client: API client for order management
            config: Configuration dictionary
        """
        self.api_client = api_client
        self.config = config
        self.trade_logger = get_trade_logger()
        
        # Configuration from config.yaml
        tp_sl_config = config['aggressive_tp_sl']
        self.min_profit_usdt = Decimal(str(tp_sl_config['min_profit_usdt']))
        self.max_profit_usdt = Decimal(str(tp_sl_config['max_profit_usdt']))
        self.default_tp_percentage = Decimal(str(tp_sl_config['default_tp_percentage']))
        self.default_sl_percentage = Decimal(str(tp_sl_config['default_sl_percentage']))
        self.trailing_distance_percentage = Decimal(str(tp_sl_config['trailing_distance_percentage']))
        self.update_interval = tp_sl_config['update_interval_seconds']
        
        # Configurações para posições perdedoras
        self.max_loss_percentage = Decimal(str(tp_sl_config['max_loss_percentage']))
        self.loss_timeout_hours = tp_sl_config['loss_timeout_hours']
        
        # State management
        self.active_orders: Dict[str, TPSLOrder] = {}  # position_id -> TPSLOrder
        self.lock = Lock()
        self.running = False
        self.monitor_thread: Optional[Thread] = None
        
        log.info(
            f"AggressiveTPSLManager initialized - SL AGRESSIVO DE 5% ATIVADO - "
            f"Target profits: ${self.min_profit_usdt}-${self.max_profit_usdt} USDT, "
            f"TP: {self.default_tp_percentage*100:.1f}%, SL: {self.default_sl_percentage*100:.1f}% (AGRESSIVO), "
            f"Trailing: {self.trailing_distance_percentage*100:.1f}%"
        )
    
    def start_monitoring(self):
        """Start the TP/SL monitoring thread."""
        if self.running:
            log.warning("TP/SL monitoring already running")
            return
            
        # Detect existing positions before starting monitoring
        self._detect_existing_positions()
            
        self.running = True
        self.monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        log.info("🎯 Aggressive TP/SL monitoring started")
    
    def stop_monitoring(self):
        """Stop the TP/SL monitoring thread."""
        self.running = False
        if self.monitor_thread:
            tp_sl_config = self.config['aggressive_tp_sl']
            shutdown_timeout = tp_sl_config['shutdown_timeout_seconds']
            self.monitor_thread.join(timeout=shutdown_timeout)
        log.info("🛑 Aggressive TP/SL monitoring stopped")
    
    def add_position(self, symbol: str, position_side: str, entry_price: Decimal, 
                    quantity: Decimal, custom_tp_percentage: Optional[Decimal] = None,
                    custom_sl_percentage: Optional[Decimal] = None) -> str:
        """
        Add a position for TP/SL monitoring.
        
        Args:
            symbol: Trading symbol
            position_side: "LONG" or "SHORT"
            entry_price: Entry price of position
            quantity: Position quantity
            custom_tp_percentage: Custom TP percentage (optional)
            custom_sl_percentage: Custom SL percentage (optional)
            
        Returns:
            Position ID for tracking
        """
        # CRITICAL: Verify position actually exists before adding to TP/SL monitoring
        if not self._is_position_open(symbol, position_side):
            log.warning(f"🚫 Cannot add TP/SL for {symbol} {position_side}: Position does not exist")
            return None
        
        # Check if position is already being monitored
        position_key = f"{symbol}_{position_side}"
        for existing_id, existing_order in self.active_orders.items():
            if existing_order.symbol == symbol and existing_order.position_side == position_side:
                log.info(f"🔄 Position {symbol} {position_side} already being monitored as {existing_id}")
                return existing_id
        
        position_id = f"{symbol}_{position_side}_{int(time.time())}"
        
        # Calculate profit target based on position size
        position_value = entry_price * quantity
        
        # Determine TP percentage based on position value
        if position_value < Decimal("50"):
            # Small positions - use higher TP percentage for faster profits
            tp_percentage = custom_tp_percentage or Decimal("0.004")  # 0.4%
            sl_percentage = custom_sl_percentage or Decimal("0.006")  # 0.6%
        elif position_value < Decimal("100"):
            # Medium positions
            tp_percentage = custom_tp_percentage or Decimal("0.003")  # 0.3%
            sl_percentage = custom_sl_percentage or Decimal("0.004")  # 0.4%
        else:
            # Larger positions - use default percentages
            tp_percentage = custom_tp_percentage or self.default_tp_percentage
            sl_percentage = custom_sl_percentage or self.default_sl_percentage
        
        # Calculate TP and SL prices
        if position_side == "LONG":
            tp_price = entry_price * (Decimal("1") + tp_percentage)
            sl_price = entry_price * (Decimal("1") - sl_percentage)
        else:  # SHORT
            tp_price = entry_price * (Decimal("1") - tp_percentage)
            sl_price = entry_price * (Decimal("1") + sl_percentage)
        
        # Calculate expected profit
        expected_profit = abs((tp_price - entry_price) * quantity)
        
        # Create TP/SL order
        tpsl_order = TPSLOrder(
            symbol=symbol,
            position_side=position_side,
            entry_price=entry_price,
            quantity=quantity,
            tp_price=tp_price,
            sl_price=sl_price,
            trailing_distance=self.trailing_distance_percentage * entry_price,
            created_at=time.time()
        )
        
        with self.lock:
            self.active_orders[position_id] = tpsl_order
        
        # Place initial TP and SL orders
        self._place_tp_sl_orders(position_id, tpsl_order)
        
        # Update pair logger with TP/SL prices
        try:
            from .pair_logger import get_pair_logger
            pair_logger = get_pair_logger(symbol)
            pair_logger.update_tp_sl(tp_price=float(tp_price), sl_price=float(sl_price))
        except Exception as e:
            log.debug(f"Could not update pair_logger with TP/SL: {e}")
        
        log.info(
            f"📈 Added position for TP/SL monitoring: {position_id} | "
            f"Entry: {entry_price} | TP: {tp_price} | SL: {sl_price} | "
            f"Expected profit: ${expected_profit:.4f} USDT"
        )
        
        self.trade_logger.log_position_update(
            symbol, position_side, str(quantity), str(entry_price),
            str(entry_price), "0.00", "10x"
        )
        
        return position_id
    
    def remove_position(self, position_id: str):
        """Remove a position from monitoring and cancel associated orders."""
        with self.lock:
            if position_id in self.active_orders:
                tpsl_order = self.active_orders[position_id]
                
                # Cancel existing orders
                if tpsl_order.tp_order_id:
                    self._cancel_order(tpsl_order.symbol, tpsl_order.tp_order_id)
                if tpsl_order.sl_order_id:
                    self._cancel_order(tpsl_order.symbol, tpsl_order.sl_order_id)
                
                del self.active_orders[position_id]
                log.info(f"🗑️ Removed position from TP/SL monitoring: {position_id}")
    
    def _monitor_loop(self):
        """Main monitoring loop for TP/SL orders."""
        log.info("🔄 TP/SL monitoring loop started")
        
        while self.running:
            try:
                current_time = time.time()
                
                with self.lock:
                    positions_to_update = list(self.active_orders.items())
                
                for position_id, tpsl_order in positions_to_update:
                    try:
                        self._update_position(position_id, tpsl_order, current_time)
                    except Exception as e:
                        log.error(f"Error updating position {position_id}: {e}")
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                log.error(f"Error in TP/SL monitor loop: {e}")
                time.sleep(self.update_interval)
    
    def _update_position(self, position_id: str, tpsl_order: TPSLOrder, current_time: float):
        """Update a single position's TP/SL orders."""
        try:
            # Check if position has too many failed attempts
            if tpsl_order.failed_attempts >= tpsl_order.max_failed_attempts:
                log.error(f"🚫 Position {position_id} has too many failed attempts ({tpsl_order.failed_attempts}), removing from monitoring")
                self.remove_position(position_id)
                return
                
            # Get current price
            current_price = self._get_current_price(tpsl_order.symbol)
            if not current_price:
                return
            
            # Check if position is still open
            if not self._is_position_open(tpsl_order.symbol, tpsl_order.position_side):
                log.info(f"Position {position_id} is closed, removing from monitoring")
                self.remove_position(position_id)
                return
            
            # NOVO: Verificar se posição deve ser fechada por perda excessiva ou timeout
            if self._should_close_losing_position(tpsl_order, current_price, current_time):
                log.warning(f"Closing losing position {position_id} due to excessive loss or timeout")
                self._force_close_position(position_id, tpsl_order, current_price)
                return
            
            # Update trailing stop for profitable positions
            if self._should_update_trailing_stop(tpsl_order, current_price):
                self._update_trailing_stop(position_id, tpsl_order, current_price)
            
            # Check if TP or SL should be triggered
            self._check_tp_sl_triggers(position_id, tpsl_order, current_price)
            
            tpsl_order.last_update = current_time
            
        except Exception as e:
            log.error(f"Error updating position {position_id}: {e}")
    
    def _should_update_trailing_stop(self, tpsl_order: TPSLOrder, current_price: Decimal) -> bool:
        """Check if trailing stop should be updated."""
        if not tpsl_order.trailing_stop_price:
            # Initialize trailing stop
            if tpsl_order.position_side == "LONG" and current_price > tpsl_order.entry_price:
                return True
            elif tpsl_order.position_side == "SHORT" and current_price < tpsl_order.entry_price:
                return True
        else:
            # Update existing trailing stop
            if tpsl_order.position_side == "LONG":
                new_stop = current_price - tpsl_order.trailing_distance
                return new_stop > tpsl_order.trailing_stop_price
            else:  # SHORT
                new_stop = current_price + tpsl_order.trailing_distance
                return new_stop < tpsl_order.trailing_stop_price
        
        return False
    
    def _update_trailing_stop(self, position_id: str, tpsl_order: TPSLOrder, current_price: Decimal):
        """Update trailing stop price and order with enhanced position verification."""
        try:
            # CRITICAL: Re-verify position exists before any operations
            current_position = self.api_client.get_futures_position(tpsl_order.symbol)
            if not current_position:
                log.warning(f"📈 Position {position_id} not found during trailing stop update")
                self.remove_position(position_id)
                return
            
            # Handle both list and dict response formats
            if isinstance(current_position, list):
                current_position = current_position[0] if current_position else None
                
            if not current_position:
                log.warning(f"📈 Position {position_id} empty response during trailing stop update")
                self.remove_position(position_id)
                return
                
            position_amt = float(current_position.get('positionAmt', 0))
            if abs(position_amt) == 0:
                log.warning(f"📈 Position {position_id} closed during trailing stop update")
                self.remove_position(position_id)
                return
            
            # Verify position side matches our tracking
            actual_side = "LONG" if position_amt > 0 else "SHORT"
            if actual_side != tpsl_order.position_side:
                log.warning(f"📈 Position {position_id} side mismatch: expected {tpsl_order.position_side}, got {actual_side}")
                self.remove_position(position_id)
                return
                
            if tpsl_order.position_side == "LONG":
                new_stop_price = current_price - tpsl_order.trailing_distance
            else:  # SHORT
                new_stop_price = current_price + tpsl_order.trailing_distance
            
            # Cancel existing SL order
            if tpsl_order.sl_order_id:
                self._cancel_order(tpsl_order.symbol, tpsl_order.sl_order_id)
            
            # Use actual current position size for trailing stop
            actual_quantity = abs(position_amt)
            
            # Place new trailing stop order
            new_sl_order_id = self._place_stop_order(
                tpsl_order.symbol, 
                "SELL" if actual_side == "LONG" else "BUY",
                str(actual_quantity),
                str(new_stop_price)
            )
            
            if new_sl_order_id:
                tpsl_order.trailing_stop_price = new_stop_price
                tpsl_order.sl_order_id = new_sl_order_id
                
                self.trade_logger.log_trailing_stop_update(
                    tpsl_order.symbol, str(new_stop_price),
                    str(tpsl_order.trailing_distance), str(current_price)
                )
                
                log.info(
                    f"📈 Updated trailing stop for {position_id}: "
                    f"New stop: {new_stop_price}, Current: {current_price}"
                )
            
        except Exception as e:
            log.error(f"Error updating trailing stop for {position_id}: {e}")
    
    def _check_tp_sl_triggers(self, position_id: str, tpsl_order: TPSLOrder, current_price: Decimal):
        """Check if TP or SL should be manually triggered with position verification."""
        try:
            # CRITICAL: Verify position still exists before triggering TP/SL
            current_position = self.api_client.get_futures_position(tpsl_order.symbol)
            if isinstance(current_position, list):
                current_position = current_position[0] if current_position else None
                
            if not current_position or abs(float(current_position.get('positionAmt', 0))) == 0:
                log.warning(f"📈 Position {position_id} closed before TP/SL trigger, removing")
                self.remove_position(position_id)
                return
                
            proximity_threshold = 0.002  # 0.2% de proximidade para TP imediato
            
            if tpsl_order.position_side == "LONG":
                # Check TP proximity for immediate execution
                tp_distance = abs(float(current_price) - float(tpsl_order.tp_price)) / float(current_price)
            
                if tp_distance <= proximity_threshold and current_price < tpsl_order.tp_price:
                    # Preço MUITO PRÓXIMO do TP - executar ordem de mercado IMEDIATA
                    log.warning(f"🎯💰 TP PRÓXIMO DETECTADO para {tpsl_order.symbol} - Executando ordem de mercado!")
                    self._execute_immediate_tp(position_id, tpsl_order, current_price)
                    
                elif current_price >= tpsl_order.tp_price:
                    # TP atingido - executar se ordem limite não executou
                    profit = (current_price - tpsl_order.entry_price) * tpsl_order.quantity
                    log.info(f"🎯 TP atingido para {tpsl_order.symbol} - Lucro: ${profit:.4f}")
                    self.trade_logger.log_take_profit_triggered(
                        tpsl_order.symbol, str(tpsl_order.tp_price),
                        str(current_price), str(profit)
                    )
                    
                # Check SL trigger (including trailing stop)
                sl_trigger_price = tpsl_order.trailing_stop_price or tpsl_order.sl_price
                if current_price <= sl_trigger_price:
                    loss = (tpsl_order.entry_price - current_price) * tpsl_order.quantity
                    self.trade_logger.log_stop_loss_triggered(
                        tpsl_order.symbol, str(sl_trigger_price),
                        str(current_price), str(-loss)
                    )
        
            else:  # SHORT position
                # Check TP proximity for immediate execution
                tp_distance = abs(float(current_price) - float(tpsl_order.tp_price)) / float(current_price)
                
                if tp_distance <= proximity_threshold and current_price > tpsl_order.tp_price:
                    # Preço MUITO PRÓXIMO do TP - executar ordem de mercado IMEDIATA
                    log.warning(f"🎯💰 TP PRÓXIMO DETECTADO para {tpsl_order.symbol} - Executando ordem de mercado!")
                    self._execute_immediate_tp(position_id, tpsl_order, current_price)
                    
                elif current_price <= tpsl_order.tp_price:
                    # TP atingido - executar se ordem limite não executou
                    profit = (tpsl_order.entry_price - current_price) * tpsl_order.quantity
                    log.info(f"🎯 TP atingido para {tpsl_order.symbol} - Lucro: ${profit:.4f}")
                    self.trade_logger.log_take_profit_triggered(
                        tpsl_order.symbol, str(tpsl_order.tp_price),
                        str(current_price), str(profit)
                    )
                    
                # Check SL trigger (including trailing stop)
                sl_trigger_price = tpsl_order.trailing_stop_price or tpsl_order.sl_price
                if current_price >= sl_trigger_price:
                    loss = (current_price - tpsl_order.entry_price) * tpsl_order.quantity
                    self.trade_logger.log_stop_loss_triggered(
                        tpsl_order.symbol, str(sl_trigger_price),
                        str(current_price), str(-loss)
                    )
        
        except Exception as e:
            log.error(f"Error checking TP/SL triggers for {position_id}: {e}")
    
    def _place_tp_sl_orders(self, position_id: str, tpsl_order: TPSLOrder):
        """Place initial TP and SL orders."""
        try:
            log.info(f"🎯 Attempting to place TP/SL orders for {position_id}")
            
            # CRITICAL: Get current actual position size before placing orders
            current_position = self.api_client.get_futures_position(tpsl_order.symbol)
            if not current_position:
                log.warning(f"🎯 Position {position_id} not found, skipping TP/SL orders")
                return
            
            # Extract current position data
            if isinstance(current_position, list):
                current_position = current_position[0] if current_position else None
            
            if not current_position:
                log.warning(f"🎯 Position {position_id} not found in API response")
                return
                
            current_position_amt = float(current_position.get("positionAmt", 0))
            if current_position_amt == 0:
                log.warning(f"🎯 Position {position_id} is already closed")
                return
            
            # Use ACTUAL current position size
            actual_quantity = abs(current_position_amt)
            actual_position_side = "LONG" if current_position_amt > 0 else "SHORT"
            
            # Verify position side matches what we're tracking
            if actual_position_side != tpsl_order.position_side:
                log.error(f"❌ Position side mismatch: tracking {tpsl_order.position_side} but actual is {actual_position_side}")
                return
            
            log.info(f"📊 Quantidade atual real para TP/SL: {actual_quantity} (era {tpsl_order.quantity} quando adicionada)")
            
            # Place Take Profit order - DINÂMICO baseado na proximidade do preço
            tp_side = "SELL" if tpsl_order.position_side == "LONG" else "BUY"
            current_price = self._get_current_price(tpsl_order.symbol)
            
            if current_price:
                # Calcular distância do TP em relação ao preço atual
                tp_distance_percentage = abs(float(tpsl_order.tp_price) - float(current_price)) / float(current_price)
                proximity_threshold = 0.002  # 0.2% de proximidade
                
                if tp_distance_percentage <= proximity_threshold:
                    # TP PRÓXIMO: Usar ordem de MERCADO para garantir lucro imediato
                    log.info(f"🎯💰 TP PRÓXIMO ({tp_distance_percentage*100:.3f}%): Executando ordem de MERCADO para {tpsl_order.symbol}")
                    tp_order_id = self._place_market_order_for_tp(
                        tpsl_order.symbol, tp_side, str(actual_quantity)
                    )
                else:
                    # TP DISTANTE: Usar ordem LIMITE tradicional
                    log.info(f"🎯📍 TP DISTANTE ({tp_distance_percentage*100:.3f}%): Colocando ordem LIMITE para {tpsl_order.symbol} @ {tpsl_order.tp_price}")
                    tp_order_id = self._place_limit_order(
                        tpsl_order.symbol, tp_side, str(actual_quantity), str(tpsl_order.tp_price)
                    )
            else:
                # Fallback: usar ordem limite se não conseguir preço atual
                log.warning(f"🎯⚠️ Não foi possível obter preço atual, usando ordem LIMITE para {tpsl_order.symbol}")
                tp_order_id = self._place_limit_order(
                    tpsl_order.symbol, tp_side, str(actual_quantity), str(tpsl_order.tp_price)
                )
            
            if tp_order_id:
                tpsl_order.tp_order_id = tp_order_id
                tpsl_order.failed_attempts = 0  # Reset failed attempts on success
                log.info(f"🎯 TP order placed for {position_id}: {tp_order_id}")
            else:
                tpsl_order.failed_attempts += 1
                log.warning(f"🎯 Failed to place TP order for {position_id} (attempt {tpsl_order.failed_attempts}/{tpsl_order.max_failed_attempts})")
            
            # Place Stop Loss order
            sl_side = "SELL" if actual_position_side == "LONG" else "BUY"
            log.info(f"🛑 Placing SL order: {tpsl_order.symbol} {sl_side} {actual_quantity} @ {tpsl_order.sl_price}")
            sl_order_id = self._place_stop_order(
                tpsl_order.symbol, sl_side, str(actual_quantity), str(tpsl_order.sl_price)
            )
            
            if sl_order_id:
                tpsl_order.sl_order_id = sl_order_id
                # Don't reset failed attempts here unless both TP and SL succeed
                log.info(f"🛑 SL order placed for {position_id}: {sl_order_id}")
            else:
                tpsl_order.failed_attempts += 1
                log.warning(f"🛑 Failed to place SL order for {position_id} (attempt {tpsl_order.failed_attempts}/{tpsl_order.max_failed_attempts})")
                
        except Exception as e:
            log.error(f"Error placing TP/SL orders for {position_id}: {e}")
    
    def _place_limit_order(self, symbol: str, side: str, quantity: str, price: str) -> Optional[str]:
        """Place a limit order."""
        try:
            # Format price to proper precision for this symbol
            formatted_price = self._format_price_for_symbol(symbol, price)
            formatted_quantity = self._format_quantity_for_symbol(symbol, quantity)
            
            if not formatted_price or not formatted_quantity:
                log.error(f"Failed to format price/quantity for {symbol}: {price}/{quantity}")
                return None
            
            result = self.api_client.place_futures_order(
                symbol=symbol,
                side=side,
                order_type="LIMIT",
                quantity=formatted_quantity,
                price=formatted_price,
                time_in_force="GTC",
                reduceOnly="true"  # Close position only (correct Binance API parameter format)
            )
            
            if result and result.get("orderId"):
                return str(result["orderId"])
                
        except Exception as e:
            log.error(f"Error placing limit order: {e}")
        
        return None
    
    def _place_stop_order(self, symbol: str, side: str, quantity: str, stop_price: str) -> Optional[str]:
        """Place a MARKET order for immediate execution (SL agressivo)."""
        try:
            # CRITICAL: Verify position exists before placing SL order
            position_side = "LONG" if side == "SELL" else "SHORT"
            if not self._is_position_open(symbol, position_side):
                log.info(f"🔄 SL AGRESSIVO: Posição {symbol} já foi fechada")
                return None
            
            # Para SL agressivo, usar ORDEM DE MERCADO para execução imediata
            # Não usar STOP_MARKET que pode não executar se preço passar muito rápido
            log.warning(f"🛑 SL AGRESSIVO: Executando ordem de MERCADO para {symbol}")
            
            # Format quantity to proper precision for this symbol
            formatted_quantity = self._format_quantity_for_symbol(symbol, quantity)
            
            if not formatted_quantity:
                log.error(f"Failed to format quantity for {symbol}: {quantity}")
                return None
            
            # ORDEM DE MERCADO para execução IMEDIATA (SL agressivo)
            result = self.api_client.place_futures_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",  # ORDEM DE MERCADO para execução IMEDIATA
                quantity=formatted_quantity,
                reduceOnly="true"  # Close position only
            )
            
            if result and result.get("orderId"):
                log.warning(f"✅ SL AGRESSIVO EXECUTADO: Ordem de mercado {result.get('orderId')} para {symbol}")
                return str(result["orderId"])
            elif result is None:
                # None indicates position already closed (normal behavior)
                log.info(f"🔄 SL AGRESSIVO: Posição {symbol} já foi fechada")
                return None
            else:
                log.error(f"❌ Falha na execução da ordem de mercado SL para {symbol}")
                
        except Exception as e:
            log.error(f"Error placing aggressive SL market order: {e}")
        
        return None
    
    def _place_market_order_for_tp(self, symbol: str, side: str, quantity: str) -> Optional[str]:
        """Place a MARKET order for immediate TP execution when close to target."""
        try:
            # CRITICAL: Verify position exists before placing TP order
            position_side = "LONG" if side == "SELL" else "SHORT"
            if not self._is_position_open(symbol, position_side):
                log.info(f"🎯 TP atingido para {symbol} - Lucro já realizado")
                return None
            
            log.warning(f"🎯💰 TP IMEDIATO: Executando ordem de MERCADO para {symbol}")
            
            # Format quantity to proper precision for this symbol
            formatted_quantity = self._format_quantity_for_symbol(symbol, quantity)
            
            if not formatted_quantity:
                log.error(f"Failed to format quantity for TP market order {symbol}: {quantity}")
                return None
            
            # ORDEM DE MERCADO para TAKE PROFIT IMEDIATO
            result = self.api_client.place_futures_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",  # ORDEM DE MERCADO para execução IMEDIATA
                quantity=formatted_quantity,
                reduceOnly="true"  # Close position only
            )
            
            if result and result.get("orderId"):
                log.info(f"✅ TP IMEDIATO EXECUTADO: Ordem de mercado {result.get('orderId')} para {symbol}")
                
                # Log no trade logger
                self.trade_logger.log_take_profit_triggered(
                    symbol, "MARKET_EXECUTION", "IMMEDIATE", "PROFIT_SECURED"
                )
                
                return str(result["orderId"])
            else:
                log.error(f"❌ Falha na execução da ordem de mercado TP para {symbol}")
                
        except Exception as e:
            log.error(f"Error placing TP market order: {e}")
        
        return None
    
    def _execute_immediate_tp(self, position_id: str, tpsl_order: TPSLOrder, current_price: Decimal):
        """Executa TP imediato quando preço está muito próximo do target."""
        try:
            log.warning(f"🎯🚀 EXECUTANDO TP IMEDIATO para {position_id}")
            
            # CRITICAL: Get current actual position size
            current_position = self.api_client.get_futures_position(tpsl_order.symbol)
            if not current_position:
                log.warning(f"🎯🚫 Position {position_id} not found during immediate TP")
                self.remove_position(position_id)
                return
            
            # Extract current position data
            if isinstance(current_position, list):
                current_position = current_position[0] if current_position else None
            
            if not current_position:
                log.warning(f"🎯🚫 Position {position_id} empty response during immediate TP")
                self.remove_position(position_id)
                return
                
            current_position_amt = float(current_position.get("positionAmt", 0))
            if current_position_amt == 0:
                log.warning(f"🎯🚫 Position {position_id} already closed during immediate TP")
                self.remove_position(position_id)
                return
            
            # Use actual current position size
            actual_quantity = abs(current_position_amt)
            actual_position_side = "LONG" if current_position_amt > 0 else "SHORT"
            
            # Verify position side matches
            if actual_position_side != tpsl_order.position_side:
                log.error(f"❌ Position side mismatch during immediate TP: tracking {tpsl_order.position_side} but actual is {actual_position_side}")
                self.remove_position(position_id)
                return
            
            # Cancelar ordem TP limite existente
            if tpsl_order.tp_order_id:
                self._cancel_order(tpsl_order.symbol, tpsl_order.tp_order_id)
                log.info(f"🎯❌ Ordem TP limite cancelada: {tpsl_order.tp_order_id}")
            
            # Executar ordem de mercado para TP imediato
            tp_side = "SELL" if actual_position_side == "LONG" else "BUY"
            market_order_id = self._place_market_order_for_tp(
                tpsl_order.symbol, tp_side, str(actual_quantity)
            )
            
            if market_order_id:
                # Calcular lucro realizado usando quantidade REAL
                if actual_position_side == "LONG":
                    profit = (current_price - tpsl_order.entry_price) * Decimal(str(actual_quantity))
                else:
                    profit = (tpsl_order.entry_price - current_price) * Decimal(str(actual_quantity))
                
                log.info(f"✅ TP IMEDIATO EXECUTADO com sucesso!")
                log.info(f"💰 Lucro realizado: ${profit:.4f} USDT")
                log.info(f"🎯 Ordem de mercado: {market_order_id}")
                
                # Atualizar TP order ID
                tpsl_order.tp_order_id = market_order_id
                
                # Remover posição do monitoramento (TP executado)
                self.remove_position(position_id)
                
            else:
                log.error(f"❌ Falha na execução do TP imediato para {position_id}")
                
        except Exception as e:
            log.error(f"Error executing immediate TP for {position_id}: {e}")
    
    def _cancel_order(self, symbol: str, order_id: str):
        """Cancel an order."""
        try:
            result = self.api_client.cancel_futures_order(symbol, order_id)
            if result:
                log.debug(f"Cancelled order {order_id} for {symbol}")
        except Exception as e:
            log.error(f"Error cancelling order {order_id}: {e}")
    
    def _get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price for symbol."""
        try:
            ticker = self.api_client.get_futures_ticker(symbol)
            if ticker and ticker.get("price"):
                return Decimal(str(ticker["price"]))
        except Exception as e:
            log.error(f"Error getting current price for {symbol}: {e}")
        
        return None
    
    def _detect_existing_positions(self):
        """Detect and add existing futures positions to TP/SL monitoring."""
        try:
            positions = self.api_client.get_futures_positions()
            if not positions:
                log.info("No existing positions found to monitor")
                return
                
            existing_count = 0
            for pos in positions:
                try:
                    position_amt = float(pos.get("positionAmt", 0))
                    if position_amt == 0:
                        continue  # No position
                    
                    symbol = pos.get("symbol")
                    entry_price = Decimal(str(pos.get("entryPrice", 0)))
                    position_side = "LONG" if position_amt > 0 else "SHORT"
                    quantity = Decimal(str(abs(position_amt)))
                    
                    if entry_price <= 0:
                        continue  # Invalid entry price
                    
                    # Add existing position to monitoring
                    position_id = self.add_position(
                        symbol=symbol,
                        position_side=position_side,
                        entry_price=entry_price,
                        quantity=quantity
                    )
                    
                    existing_count += 1
                    log.info(
                        f"📋 Added existing position to TP/SL: {symbol} {position_side} "
                        f"{quantity} @ {entry_price} (ID: {position_id})"
                    )
                    
                except Exception as e:
                    log.error(f"Error processing existing position {pos}: {e}")
                    
            log.info(f"🎯 Detected and added {existing_count} existing positions to TP/SL monitoring")
            
        except Exception as e:
            log.error(f"Error detecting existing positions: {e}")
    
    def _format_price_for_symbol(self, symbol: str, price: str) -> Optional[str]:
        """Format price according to symbol's precision requirements."""
        try:
            # Get exchange info for this symbol
            exchange_info = self.api_client.futures_exchange_info()
            if not exchange_info or 'symbols' not in exchange_info:
                return None
            
            symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    symbol_info = s
                    break
            
            if not symbol_info:
                return None
            
            # Get price precision and tick size
            price_precision = symbol_info.get('pricePrecision', 8)
            
            # Find tick size from PRICE_FILTER
            tick_size = None
            for filter_info in symbol_info.get('filters', []):
                if filter_info.get('filterType') == 'PRICE_FILTER':
                    tick_size = Decimal(filter_info.get('tickSize', '0.01'))
                    break
            
            if tick_size is None:
                tick_size = Decimal('0.01')  # Default fallback
            
            # Ajustar preço para o tick size mais próximo usando ROUND_HALF_UP
            price_decimal = Decimal(str(price))
            adjusted_price = (price_decimal / tick_size).quantize(
                Decimal("1"), rounding=ROUND_UP
            ) * tick_size
            
            # Format with correct precision
            formatted_price = f"{adjusted_price:.{price_precision}f}"
            
            # Remove trailing zeros and decimal point if not needed
            if '.' in formatted_price:
                formatted_price = formatted_price.rstrip('0').rstrip('.')
            
            return formatted_price
            
        except Exception as e:
            log.error(f"Error formatting price for {symbol}: {e}")
            # Fallback: round to 6 decimal places
            try:
                return f"{float(price):.6f}".rstrip('0').rstrip('.')
            except:
                return None
    
    def _format_quantity_for_symbol(self, symbol: str, quantity: str) -> Optional[str]:
        """Format quantity according to symbol's precision requirements."""
        try:
            # Get exchange info for this symbol
            exchange_info = self.api_client.futures_exchange_info()
            if not exchange_info or 'symbols' not in exchange_info:
                return None
            
            symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    symbol_info = s
                    break
            
            if not symbol_info:
                return None
            
            # Get quantity precision
            quantity_precision = symbol_info.get('quantityPrecision', 8)
            
            # Format quantity with correct precision
            formatted_quantity = f"{float(quantity):.{quantity_precision}f}"
            
            # Remove trailing zeros and decimal point if not needed
            if '.' in formatted_quantity:
                formatted_quantity = formatted_quantity.rstrip('0').rstrip('.')
            
            return formatted_quantity
            
        except Exception as e:
            log.error(f"Error formatting quantity for {symbol}: {e}")
            # Fallback: round to 3 decimal places  
            try:
                return f"{float(quantity):.3f}".rstrip('0').rstrip('.')
            except:
                return None
    
    def _is_position_open(self, symbol: str, position_side: str) -> bool:
        """Check if position is still open."""
        try:
            positions = self.api_client.get_futures_positions()
            if positions:
                for pos in positions:
                    position_amt = float(pos.get("positionAmt", 0))
                    if pos.get("symbol") == symbol and position_amt != 0:
                        # Determinar side baseado no positionAmt
                        actual_side = "LONG" if position_amt > 0 else "SHORT"
                        if actual_side == position_side:
                            return True
        except Exception as e:
            log.error(f"Error checking position status: {e}")
        
        return False
    
    def _should_close_losing_position(self, tpsl_order: TPSLOrder, current_price: Decimal, current_time: float) -> bool:
        """Verifica se uma posição perdedora deve ser fechada baseado no CAPITAL INVESTIDO na posição."""
        try:
            # Calcular CAPITAL INVESTIDO na posição específica (sem alavancagem)
            position_value = tpsl_order.entry_price * tpsl_order.quantity
            # CORREÇÃO: Obter alavancagem da configuração (não hardcoded)
            leverage = self.config.get('grid', {}).get('futures', {}).get('leverage', 3)
            capital_invested = position_value / leverage  # Capital real investido
            
            # Calcular perda atual em USDT
            if tpsl_order.position_side == "LONG":
                current_loss_usdt = (tpsl_order.entry_price - current_price) * tpsl_order.quantity
            else:  # SHORT
                current_loss_usdt = (current_price - tpsl_order.entry_price) * tpsl_order.quantity
            
            # Calcular percentual de perda baseado no CAPITAL INVESTIDO
            if capital_invested > 0:
                loss_percentage_on_capital = current_loss_usdt / capital_invested
            else:
                loss_percentage_on_capital = 0
            
            # SL ULTRA AGRESSIVO: 2-3% do capital investido (PROTEÇÃO CRÍTICA)
            max_loss_usdt = capital_invested * self.max_loss_percentage  # Agora 3% max
            
            # Log detalhado para debug
            log.info(f"[{tpsl_order.symbol}] SL Check - Capital: ${capital_invested:.2f} | Perda atual: ${current_loss_usdt:.2f} | Max permitida: ${max_loss_usdt:.2f} | Leverage: {leverage}x")
            
            # Verificar se perda em USDT excede 5% do capital investido
            if current_loss_usdt > max_loss_usdt:
                log.warning(f"🛑 SL AGRESSIVO TRIGGER - {tpsl_order.symbol}")
                log.warning(f"💰 Capital investido: ${capital_invested:.2f} USDT")
                log.warning(f"📉 Perda atual: ${current_loss_usdt:.2f} USDT ({loss_percentage_on_capital*100:.2f}% do capital)")
                log.warning(f"🚨 Limite de 5% (${max_loss_usdt:.2f}) ULTRAPASSADO!")
                return True
            
            # Verificar timeout (posição aberta há muito tempo)
            position_age_hours = (current_time - tpsl_order.created_at) / 3600
            if position_age_hours > self.loss_timeout_hours:
                log.warning(f"Position {tpsl_order.symbol} timeout: {position_age_hours:.1f}h old")
                return True
            
            return False
            
        except Exception as e:
            log.error(f"Error checking if should close losing position: {e}")
            return False
    
    def _force_close_position(self, position_id: str, tpsl_order: TPSLOrder, current_price: Decimal):
        """Força o fechamento de uma posição perdedora."""
        try:
            # CRITICAL: Get current actual position size before closing
            current_position = self.api_client.get_futures_position(tpsl_order.symbol)
            if not current_position:
                log.warning(f"🚫 Force close CANCELADO: Posição {tpsl_order.symbol} não encontrada")
                self.remove_position(position_id)
                return
            
            # Extract current position data
            if isinstance(current_position, list):
                current_position = current_position[0] if current_position else None
            
            if not current_position:
                log.warning(f"🚫 Force close CANCELADO: Posição {tpsl_order.symbol} já foi fechada")
                self.remove_position(position_id)
                return
                
            current_position_amt = float(current_position.get("positionAmt", 0))
            if current_position_amt == 0:
                log.warning(f"🚫 Force close CANCELADO: Posição {tpsl_order.symbol} já está zerada")
                self.remove_position(position_id)
                return
            
            # Use ACTUAL current position size, not stored quantity
            actual_quantity = abs(current_position_amt)
            actual_position_side = "LONG" if current_position_amt > 0 else "SHORT"
            
            # Verify position side matches what we're tracking
            if actual_position_side != tpsl_order.position_side:
                log.error(f"❌ Position side mismatch: tracking {tpsl_order.position_side} but actual is {actual_position_side}")
                self.remove_position(position_id)
                return
            
            log.warning(f"🛑 SL AGRESSIVO ATIVADO - Forçando fechamento de posição com perda: {position_id}")
            log.info(f"📊 Quantidade atual real: {actual_quantity} (era {tpsl_order.quantity} quando adicionada)")
            
            # Determinar side para fechar posição
            close_side = "SELL" if actual_position_side == "LONG" else "BUY"
            
            # Cancelar ordens TP/SL existentes
            if tpsl_order.tp_order_id:
                self._cancel_order(tpsl_order.symbol, tpsl_order.tp_order_id)
            if tpsl_order.sl_order_id:
                self._cancel_order(tpsl_order.symbol, tpsl_order.sl_order_id)
            
            # Fechar posição com ordem de mercado usando quantidade REAL
            result = self.api_client.place_futures_order(
                symbol=tpsl_order.symbol,
                side=close_side,
                order_type="MARKET",
                quantity=str(actual_quantity),
                reduceOnly="true"
            )
            
            if result:
                # Calcular perda final usando quantidade REAL
                if actual_position_side == "LONG":
                    loss = (tpsl_order.entry_price - current_price) * Decimal(str(actual_quantity))
                else:
                    loss = (current_price - tpsl_order.entry_price) * Decimal(str(actual_quantity))
                
                log.warning(f"🛡️ SL AGRESSIVO EXECUTADO: {position_id}")
                log.warning(f"🛑 Posição fechada para PROTEÇÃO DE CAPITAL")
                log.warning(f"📉 Perda evitada de crescer: ${abs(loss):.4f} USDT")
                
                # Log no trade logger
                self.trade_logger.log_stop_loss_triggered(
                    tpsl_order.symbol, str(current_price), str(current_price), str(abs(loss))
                )
                
                # Log específico de fechamento forçado
                self.trade_logger.log_trading_error(
                    tpsl_order.symbol, "AGGRESSIVE_SL_TRIGGERED", 
                    f"Position closed by 5% aggressive SL - Loss: ${abs(loss):.4f} USDT",
                    {"position_id": position_id, "entry_price": str(tpsl_order.entry_price), "exit_price": str(current_price)}
                )
            else:
                log.error(f"❌ Failed to close losing position: {position_id}")
            
            # Remover da monitoração
            self.remove_position(position_id)
            
        except Exception as e:
            log.error(f"Error force closing position {position_id}: {e}")
    
    def get_active_positions_count(self) -> int:
        """Get number of active positions being monitored."""
        with self.lock:
            return len(self.active_orders)
    
    def get_position_info(self, position_id: str) -> Optional[Dict]:
        """Get information about a specific position."""
        with self.lock:
            if position_id in self.active_orders:
                order = self.active_orders[position_id]
                return {
                    "symbol": order.symbol,
                    "position_side": order.position_side,
                    "entry_price": str(order.entry_price),
                    "quantity": str(order.quantity),
                    "tp_price": str(order.tp_price) if order.tp_price else None,
                    "sl_price": str(order.sl_price) if order.sl_price else None,
                    "trailing_stop_price": str(order.trailing_stop_price) if order.trailing_stop_price else None,
                    "tp_order_id": order.tp_order_id,
                    "sl_order_id": order.sl_order_id,
                    "created_at": order.created_at,
                    "last_update": order.last_update
                }
        return None