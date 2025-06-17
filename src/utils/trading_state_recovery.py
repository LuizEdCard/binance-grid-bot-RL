#!/usr/bin/env python3
"""
Trading State Recovery Module
Recupera estado real do trading baseado no histórico da Binance API
Resolve problema de cache/histórico interno perdido após restart
"""

import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from .logger import setup_logger

log = setup_logger("trading_state_recovery")

@dataclass
class TradingPosition:
    """Posição de trading reconstruída do histórico."""
    symbol: str
    side: str  # "LONG" or "SHORT"
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    total_invested: float  # Capital real investido (considerando alavancagem)
    leverage: int
    orders_count: int
    first_order_time: int
    last_order_time: int
    tp_price: Optional[float] = None  # Take Profit ativo
    sl_price: Optional[float] = None  # Stop Loss ativo
    
class TradingStateRecovery:
    """
    Recupera estado completo do trading usando histórico real da Binance.
    Usado na inicialização do sistema para restaurar estado após restart.
    """
    
    def __init__(self, api_client):
        self.api_client = api_client
        
    def recover_trading_state(self, hours_back: int = 24) -> Dict[str, Dict]:
        """
        Recupera estado completo do trading das últimas N horas.
        
        Returns:
            Dict com:
            - positions: Posições ativas reconstruídas
            - realized_pnl: PnL realizado por símbolo 
            - total_invested: Capital investido por símbolo
            - trading_summary: Resumo geral
        """
        log.info(f"🔄 Iniciando recuperação de estado de trading (últimas {hours_back}h)...")
        
        try:
            # 1. Buscar posições atuais
            current_positions = self._get_current_positions()
            
            # 2. Buscar histórico de trades
            trade_history = self._get_trade_history(hours_back)
            
            # 3. Buscar histórico de PnL realizado
            income_history = self._get_income_history(hours_back)
            
            # 4. Reconstruir estado das posições
            reconstructed_positions = self._reconstruct_positions(
                current_positions, trade_history
            )
            
            # 5. Calcular PnL realizado por símbolo
            realized_pnl_by_symbol = self._calculate_realized_pnl(income_history)
            
            # 6. Calcular capital investido por símbolo
            invested_capital_by_symbol = self._calculate_invested_capital(trade_history)
            
            # 7. Gerar resumo
            trading_summary = self._generate_summary(
                reconstructed_positions, realized_pnl_by_symbol, invested_capital_by_symbol
            )
            
            log.info(f"✅ Estado de trading recuperado com sucesso!")
            log.info(f"📊 Posições ativas: {len(reconstructed_positions)}")
            log.info(f"💰 PnL realizado total: ${trading_summary['total_realized_pnl']:.2f}")
            log.info(f"💵 Capital total investido: ${trading_summary['total_invested']:.2f}")
            
            return {
                'positions': reconstructed_positions,
                'realized_pnl': realized_pnl_by_symbol,
                'total_invested': invested_capital_by_symbol,
                'trading_summary': trading_summary,
                'recovery_timestamp': time.time()
            }
            
        except Exception as e:
            log.error(f"❌ Erro na recuperação de estado: {e}")
            return self._get_fallback_state()
    
    def _get_current_positions(self) -> List[Dict]:
        """Busca posições atuais da conta."""
        try:
            positions = self.api_client.get_futures_positions()
            # Filtrar apenas posições ativas
            active_positions = [
                pos for pos in positions 
                if float(pos.get('positionAmt', 0)) != 0
            ]
            log.info(f"📊 Posições ativas encontradas: {len(active_positions)}")
            return active_positions
        except Exception as e:
            log.error(f"Erro ao buscar posições atuais: {e}")
            return []
    
    def _get_trade_history(self, hours_back: int) -> List[Dict]:
        """Busca histórico de trades das últimas N horas."""
        try:
            start_time = int((datetime.now() - timedelta(hours=hours_back)).timestamp() * 1000)
            trades = self.api_client.get_futures_trade_history(start_time=start_time)
            log.info(f"📈 Trades encontrados: {len(trades) if trades else 0}")
            return trades or []
        except Exception as e:
            log.error(f"Erro ao buscar histórico de trades: {e}")
            return []
    
    def _get_income_history(self, hours_back: int) -> List[Dict]:
        """Busca histórico de PnL realizado."""
        try:
            start_time = int((datetime.now() - timedelta(hours=hours_back)).timestamp() * 1000)
            income = self.api_client.get_futures_income_history(
                income_type="REALIZED_PNL",
                start_time=start_time
            )
            log.info(f"💰 Registros de PnL encontrados: {len(income) if income else 0}")
            return income or []
        except Exception as e:
            log.error(f"Erro ao buscar histórico de income: {e}")
            return []
    
    def _get_active_tp_sl_orders(self, symbol: str) -> Dict[str, float]:
        """Busca ordens TP/SL ativas para um símbolo."""
        try:
            orders = self.api_client.get_open_futures_orders(symbol=symbol)
            tp_price = None
            sl_price = None
            
            for order in orders:
                order_type = order.get('type', '')
                price = float(order.get('price', 0))
                
                if order_type in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT'] and price > 0:
                    tp_price = price
                elif order_type in ['STOP_MARKET', 'STOP'] and price > 0:
                    sl_price = price
            
            return {"tp_price": tp_price, "sl_price": sl_price}
            
        except Exception as e:
            log.debug(f"Erro ao buscar ordens TP/SL para {symbol}: {e}")
            return {"tp_price": None, "sl_price": None}
    
    def _reconstruct_positions(self, current_positions: List[Dict], trade_history: List[Dict]) -> Dict[str, TradingPosition]:
        """Reconstroi posições detalhadas usando histórico de trades."""
        reconstructed = {}
        
        for pos in current_positions:
            symbol = pos['symbol']
            position_amt = float(pos['positionAmt'])
            entry_price = float(pos['entryPrice'])
            mark_price = float(pos['markPrice'])
            unrealized_pnl = float(pos['unRealizedProfit'])
            
            # Buscar trades deste símbolo
            symbol_trades = [t for t in trade_history if t['symbol'] == symbol]
            
            # Calcular dados baseados no histórico
            total_invested = self._calculate_symbol_invested_capital(symbol_trades)
            orders_count = len(symbol_trades)
            
            # Tempos da primeira e última ordem
            if symbol_trades:
                times = [int(t['time']) for t in symbol_trades]
                first_order_time = min(times)
                last_order_time = max(times)
            else:
                first_order_time = last_order_time = int(time.time() * 1000)
            
            # Buscar ordens TP/SL ativas para este símbolo
            tp_sl_orders = self._get_active_tp_sl_orders(symbol)
            
            position = TradingPosition(
                symbol=symbol,
                side="LONG" if position_amt > 0 else "SHORT",
                size=abs(position_amt),
                entry_price=entry_price,
                current_price=mark_price,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=0.0,  # Será calculado separadamente
                total_invested=total_invested,
                leverage=int(pos.get('leverage', 10)),
                orders_count=orders_count,
                first_order_time=first_order_time,
                last_order_time=last_order_time,
                tp_price=tp_sl_orders.get("tp_price"),
                sl_price=tp_sl_orders.get("sl_price")
            )
            
            reconstructed[symbol] = position
            
            # Log com TP/SL se disponíveis
            tp_sl_info = ""
            if position.tp_price:
                tp_sl_info += f" | TP: ${position.tp_price:.4f}"
            if position.sl_price:
                tp_sl_info += f" | SL: ${position.sl_price:.4f}"
            
            log.info(f"🔧 {symbol}: {position.side} {position.size} @ ${position.entry_price:.4f} | "
                    f"Capital: ${total_invested:.2f} | PnL: ${unrealized_pnl:.2f}{tp_sl_info}")
        
        return reconstructed
    
    def _calculate_realized_pnl(self, income_history: List[Dict]) -> Dict[str, float]:
        """Calcula PnL realizado por símbolo."""
        pnl_by_symbol = {}
        
        for income in income_history:
            symbol = income['symbol']
            income_amount = float(income['income'])
            
            if symbol not in pnl_by_symbol:
                pnl_by_symbol[symbol] = 0.0
            
            pnl_by_symbol[symbol] += income_amount
        
        return pnl_by_symbol
    
    def _calculate_invested_capital(self, trade_history: List[Dict]) -> Dict[str, float]:
        """Calcula capital investido real por símbolo (considerando alavancagem)."""
        invested_by_symbol = {}
        
        # Agrupar trades por símbolo
        trades_by_symbol = {}
        for trade in trade_history:
            symbol = trade['symbol']
            if symbol not in trades_by_symbol:
                trades_by_symbol[symbol] = []
            trades_by_symbol[symbol].append(trade)
        
        # Calcular capital investido para cada símbolo
        for symbol, trades in trades_by_symbol.items():
            invested_by_symbol[symbol] = self._calculate_symbol_invested_capital(trades)
        
        return invested_by_symbol
    
    def _calculate_symbol_invested_capital(self, symbol_trades: List[Dict]) -> float:
        """Calcula capital real investido em um símbolo específico."""
        total_invested = 0.0
        
        for trade in symbol_trades:
            if trade['side'] == 'BUY':  # Apenas compras (entradas)
                qty = float(trade['qty'])
                price = float(trade['price'])
                notional = qty * price
                
                # Assumir alavancagem 10x por padrão
                # Capital real = valor nocional / alavancagem
                real_capital = notional / 10
                total_invested += real_capital
        
        return total_invested
    
    def _generate_summary(self, positions: Dict, realized_pnl: Dict, invested_capital: Dict) -> Dict:
        """Gera resumo geral do estado de trading."""
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions.values())
        total_realized_pnl = sum(realized_pnl.values())
        total_invested = sum(invested_capital.values())
        
        active_symbols = list(positions.keys())
        profitable_positions = len([pos for pos in positions.values() if pos.unrealized_pnl > 0])
        losing_positions = len([pos for pos in positions.values() if pos.unrealized_pnl < 0])
        
        return {
            'total_unrealized_pnl': total_unrealized_pnl,
            'total_realized_pnl': total_realized_pnl,
            'total_invested': total_invested,
            'total_pnl': total_unrealized_pnl + total_realized_pnl,
            'active_positions': len(positions),
            'active_symbols': active_symbols,
            'profitable_positions': profitable_positions,
            'losing_positions': losing_positions,
            'roi_percentage': ((total_unrealized_pnl + total_realized_pnl) / total_invested * 100) if total_invested > 0 else 0
        }
    
    def _get_fallback_state(self) -> Dict:
        """Estado de fallback quando recuperação falha."""
        return {
            'positions': {},
            'realized_pnl': {},
            'total_invested': {},
            'trading_summary': {
                'total_unrealized_pnl': 0.0,
                'total_realized_pnl': 0.0,
                'total_invested': 0.0,
                'total_pnl': 0.0,
                'active_positions': 0,
                'active_symbols': [],
                'profitable_positions': 0,
                'losing_positions': 0,
                'roi_percentage': 0.0
            },
            'recovery_timestamp': time.time(),
            'fallback': True
        }
    
    def update_position_metrics(self, symbol: str, recovered_state: Dict) -> Dict:
        """
        Atualiza métricas de uma posição específica com dados recuperados.
        Usado pelo pair_logger para mostrar dados reais.
        """
        if symbol not in recovered_state['positions']:
            return {}
        
        position = recovered_state['positions'][symbol]
        realized_pnl = recovered_state['realized_pnl'].get(symbol, 0.0)
        
        return {
            'realized_pnl': realized_pnl,
            'total_invested': position.total_invested,
            'orders_count': position.orders_count,
            'entry_price': position.entry_price,
            'unrealized_pnl': position.unrealized_pnl,
            'total_pnl': position.unrealized_pnl + realized_pnl,
            'roi_percentage': ((position.unrealized_pnl + realized_pnl) / position.total_invested * 100) if position.total_invested > 0 else 0,
            'tp_price': position.tp_price,
            'sl_price': position.sl_price
        }