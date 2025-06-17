#!/usr/bin/env python3
"""
Enhanced Trade Logger - Separate logging for trades vs bot operations
Creates dedicated log files for trading activities and detailed monitoring
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal

class TradeLogger:
    """Dedicated logger for trading activities separate from bot operations."""
    
    def __init__(self, base_log_dir: str = "logs"):
        """
        Initialize trade logger with separate log files.
        
        Args:
            base_log_dir: Base directory for log files
        """
        self.base_log_dir = base_log_dir
        self.ensure_log_directories()
        
        # Setup different loggers for different types of activities
        self.trade_logger = self._setup_logger("trades", "trades.log")
        self.order_logger = self._setup_logger("orders", "orders.log") 
        self.profit_logger = self._setup_logger("profits", "profits.log")
        self.error_logger = self._setup_logger("trading_errors", "trading_errors.log")
        self.position_logger = self._setup_logger("positions", "positions.log")
        
    def ensure_log_directories(self):
        """Create log directories if they don't exist."""
        os.makedirs(self.base_log_dir, exist_ok=True)
        os.makedirs(os.path.join(self.base_log_dir, "trades"), exist_ok=True)
        
    def _setup_logger(self, name: str, filename: str) -> logging.Logger:
        """Setup individual logger with file handler."""
        logger = logging.getLogger(f"trade_{name}")
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # File handler - sempre limpar arquivo existente
        file_path = os.path.join(self.base_log_dir, "trades", filename)
        
        # Remover arquivo existente para começar com logs frescos
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        
        handler = logging.FileHandler(file_path)
        handler.setLevel(logging.INFO)
        
        # Custom formatter for trade logs
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        return logger
    
    def log_trade_execution(self, symbol: str, side: str, quantity: str, 
                          price: str, realized_pnl: str = "0", commission: str = "0",
                          commission_asset: str = "USDT", order_id: str = "N/A",
                          market_type: str = "futures", order_type: str = "MARKET"):
        """Log successful trade execution with complete details."""
        notional_value = float(quantity) * float(price)
        pnl_float = float(realized_pnl)
        pnl_emoji = "💰" if pnl_float > 0 else "📉" if pnl_float < 0 else "💤"
        
        message = (
            f"🟢 TRADE EXECUTED | {symbol} | {side} | "
            f"Qty: {quantity} | Price: ${price} | "
            f"Notional: ${notional_value:.4f} | "
            f"{pnl_emoji} PnL: ${realized_pnl} | "
            f"Commission: {commission} {commission_asset} | "
            f"OrderID: {order_id} | Type: {order_type} | Market: {market_type}"
        )
        
        self.trade_logger.info(message)
        
    def log_order_placed(self, symbol: str, side: str, quantity: str,
                        price: str, order_type: str, order_id: str,
                        stop_price: Optional[str] = None,
                        time_in_force: str = "GTC"):
        """Log order placement."""
        message = (
            f"📝 ORDER PLACED | {symbol} | {side} | "
            f"Type: {order_type} | Qty: {quantity} | "
            f"Price: {price}"
        )
        
        if stop_price:
            message += f" | StopPrice: {stop_price}"
            
        message += f" | OrderID: {order_id} | TIF: {time_in_force}"
        
        self.order_logger.info(message)
        
    def log_order_filled(self, symbol: str, order_id: str, side: str,
                        executed_qty: str, avg_price: str, commission: str = "0",
                        commission_asset: str = "USDT"):
        """Log order fill."""
        notional_value = float(executed_qty) * float(avg_price)
        
        message = (
            f"✅ ORDER FILLED | {symbol} | {side} | "
            f"OrderID: {order_id} | Qty: {executed_qty} | "
            f"AvgPrice: {avg_price} | Notional: ${notional_value:.2f} | "
            f"Commission: {commission} {commission_asset}"
        )
        
        self.order_logger.info(message)
        
    def log_order_cancelled(self, symbol: str, order_id: str, reason: str = "Manual"):
        """Log order cancellation."""
        message = f"❌ ORDER CANCELLED | {symbol} | OrderID: {order_id} | Reason: {reason}"
        self.order_logger.info(message)
        
    def log_profit_realized(self, symbol: str, pnl: str, pnl_percentage: str,
                           entry_price: str, exit_price: str, 
                           quantity: str, hold_time: str = "N/A"):
        """Log realized profit/loss."""
        pnl_float = float(pnl)
        emoji = "💰" if pnl_float > 0 else "📉" if pnl_float < 0 else "💤"
        
        message = (
            f"{emoji} PROFIT REALIZED | {symbol} | "
            f"PnL: ${pnl} ({pnl_percentage}%) | "
            f"Entry: {entry_price} | Exit: {exit_price} | "
            f"Qty: {quantity} | HoldTime: {hold_time}"
        )
        
        self.profit_logger.info(message)
        
    def log_position_update(self, symbol: str, side: str, size: str,
                           entry_price: str, mark_price: str,
                           unrealized_pnl: str, leverage: str = "1x"):
        """Log position updates."""
        pnl_float = float(unrealized_pnl)
        pnl_emoji = "🟢" if pnl_float > 0 else "🔴" if pnl_float < 0 else "⚪"
        
        message = (
            f"{pnl_emoji} POSITION UPDATE | {symbol} | {side} | "
            f"Size: {size} | Entry: {entry_price} | "
            f"Mark: {mark_price} | UnrealizedPnL: ${unrealized_pnl} | "
            f"Leverage: {leverage}"
        )
        
        self.position_logger.info(message)
        
    def log_trading_error(self, symbol: str, error_type: str, error_message: str,
                         context: Dict[str, Any] = None):
        """Log trading-related errors."""
        message = f"💥 TRADING ERROR | {symbol} | {error_type} | {error_message}"
        
        if context:
            context_str = " | ".join([f"{k}: {v}" for k, v in context.items()])
            message += f" | Context: {context_str}"
            
        self.error_logger.error(message)
        
    def log_take_profit_triggered(self, symbol: str, tp_price: str, 
                                 current_price: str, profit: str):
        """Log take profit trigger."""
        message = (
            f"🎯 TAKE PROFIT TRIGGERED | {symbol} | "
            f"TP: {tp_price} | Current: {current_price} | "
            f"Profit: ${profit}"
        )
        
        self.trade_logger.info(message)
        
    def log_stop_loss_triggered(self, symbol: str, sl_price: str,
                               current_price: str, loss: str):
        """Log stop loss trigger."""
        message = (
            f"🛑 STOP LOSS TRIGGERED | {symbol} | "
            f"SL: {sl_price} | Current: {current_price} | "
            f"Loss: ${loss}"
        )
        
        self.trade_logger.info(message)
        
    def log_grid_level_hit(self, symbol: str, level_type: str, price: str,
                          quantity: str, level_number: int):
        """Log grid level execution."""
        emoji = "🟢" if level_type.lower() == "buy" else "🔴"
        
        message = (
            f"{emoji} GRID LEVEL HIT | {symbol} | "
            f"Level: {level_number} | Type: {level_type} | "
            f"Price: {price} | Qty: {quantity}"
        )
        
        self.trade_logger.info(message)
        
    def log_oco_order_placed(self, symbol: str, quantity: str, stop_price: str,
                            limit_price: str, stop_limit_price: str, order_id: str):
        """Log OCO order placement."""
        message = (
            f"🔀 OCO ORDER PLACED | {symbol} | "
            f"Qty: {quantity} | Stop: {stop_price} | "
            f"Limit: {limit_price} | StopLimit: {stop_limit_price} | "
            f"OrderID: {order_id}"
        )
        
        self.order_logger.info(message)
        
    def log_trailing_stop_update(self, symbol: str, new_stop_price: str,
                                trailing_distance: str, current_price: str):
        """Log trailing stop updates."""
        message = (
            f"📈 TRAILING STOP UPDATE | {symbol} | "
            f"NewStop: {new_stop_price} | Distance: {trailing_distance} | "
            f"Current: {current_price}"
        )
        
        self.order_logger.info(message)
        
    def log_market_analysis(self, symbol: str, analysis_type: str, 
                           result: str, confidence: float = 0.0):
        """Log market analysis results."""
        confidence_emoji = "🟢" if confidence > 0.7 else "🟡" if confidence > 0.4 else "🔴"
        
        message = (
            f"{confidence_emoji} MARKET ANALYSIS | {symbol} | "
            f"Type: {analysis_type} | Result: {result} | "
            f"Confidence: {confidence:.2%}"
        )
        
        self.trade_logger.info(message)

# Global instance
_trade_logger = None

def get_trade_logger() -> TradeLogger:
    """Get or create global trade logger instance."""
    global _trade_logger
    if _trade_logger is None:
        _trade_logger = TradeLogger()
    return _trade_logger

def log_trade(symbol: str, side: str, quantity: str, price: str, order_id: str, **kwargs):
    """Convenient function to log trade execution."""
    get_trade_logger().log_trade_execution(symbol, side, quantity, price, order_id, **kwargs)

def log_order(symbol: str, side: str, quantity: str, price: str, order_type: str, order_id: str, **kwargs):
    """Convenient function to log order placement."""
    get_trade_logger().log_order_placed(symbol, side, quantity, price, order_type, order_id, **kwargs)

def log_profit(symbol: str, pnl: str, pnl_percentage: str, entry_price: str, exit_price: str, quantity: str, **kwargs):
    """Convenient function to log profit realization."""
    get_trade_logger().log_profit_realized(symbol, pnl, pnl_percentage, entry_price, exit_price, quantity, **kwargs)

def log_error(symbol: str, error_type: str, error_message: str, context: Dict[str, Any] = None):
    """Convenient function to log trading errors."""
    get_trade_logger().log_trading_error(symbol, error_type, error_message, context)