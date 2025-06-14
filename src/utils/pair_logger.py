#!/usr/bin/env python3
"""
Sistema de Logging Separado por Par com Interface Rica
Exibe logs detalhados com métricas, indicadores, PNL, TP/SL e emojis
"""

import os
import sys
import threading
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, Any
from dataclasses import dataclass
import logging

# Cores ANSI para terminal
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Cores básicas
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Cores de fundo
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    
    # Cores mais vivas
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'

@dataclass
class TradingMetrics:
    """Métricas de trading para um par"""
    current_price: float = 0.0
    entry_price: float = 0.0
    tp_price: float = 0.0
    sl_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    position_size: float = 0.0
    leverage: int = 10
    
    # Indicadores técnicos
    rsi: float = 0.0
    atr: float = 0.0
    adx: float = 0.0
    volume_24h: float = 0.0
    price_change_24h: float = 0.0
    
    # Grid específico
    grid_levels: int = 0
    active_orders: int = 0
    filled_orders: int = 0
    grid_profit: float = 0.0
    
    # Status
    position_side: str = "NONE"
    market_type: str = "FUTURES"
    last_update: datetime = None

class PairLogger:
    """Logger individual para cada par de trading"""
    
    def __init__(self, symbol: str, log_dir: str = "logs/pairs"):
        self.symbol = symbol
        self.log_dir = log_dir
        self.metrics = TradingMetrics()
        self.lock = threading.Lock()
        
        # Criar diretório se não existir
        os.makedirs(log_dir, exist_ok=True)
        
        # Arquivo de log individual
        self.log_file = os.path.join(log_dir, f"{symbol.lower()}.log")
        
        # Configurar logger
        self.logger = logging.getLogger(f"pair_{symbol}")
        self.logger.setLevel(logging.INFO)
        
        # Remover handlers existentes
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Handler para arquivo
        file_handler = logging.FileHandler(self.log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        self.logger.info(f"🚀 {symbol} Logger initialized")
    
    def get_emoji_for_side(self, side: str) -> str:
        """Retorna emoji para posição"""
        side_upper = side.upper()
        if side_upper == "LONG":
            return "🟢📈"
        elif side_upper == "SHORT":
            return "🔴📉"
        elif side_upper == "BUY":
            return "💚⬆️"
        elif side_upper == "SELL":
            return "❤️⬇️"
        else:
            return "⚪"
    
    def get_pnl_emoji(self, pnl: float) -> str:
        """Retorna emoji para PNL"""
        if pnl > 0:
            return "💰✅"
        elif pnl < 0:
            return "📉❌"
        else:
            return "⚪"
    
    def format_price(self, price: float, decimals: int = 4) -> str:
        """Formata preço com precisão"""
        return f"${price:.{decimals}f}"
    
    def format_percentage(self, percentage: float) -> str:
        """Formata porcentagem com cor"""
        color = Colors.BRIGHT_GREEN if percentage >= 0 else Colors.BRIGHT_RED
        emoji = "📈" if percentage >= 0 else "📉"
        return f"{color}{percentage:+.2f}%{Colors.RESET} {emoji}"
    
    def update_metrics(self, **kwargs):
        """Atualiza métricas do par"""
        with self.lock:
            for key, value in kwargs.items():
                if hasattr(self.metrics, key):
                    setattr(self.metrics, key, value)
            self.metrics.last_update = datetime.now()
    
    def log_trading_cycle(self):
        """Log do ciclo de trading com métricas completas"""
        m = self.metrics
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Header colorido
        header = f"{Colors.BOLD}{Colors.BG_BLUE} {self.symbol} TRADING CYCLE {Colors.RESET}"
        
        # Preço atual com mudança
        price_color = Colors.BRIGHT_GREEN if m.price_change_24h >= 0 else Colors.BRIGHT_RED
        price_section = (
            f"{Colors.CYAN}💲 PREÇO:{Colors.RESET} {price_color}{self.format_price(m.current_price)}{Colors.RESET} "
            f"{self.format_percentage(m.price_change_24h)}"
        )
        
        # Posição
        pos_emoji = self.get_emoji_for_side(m.position_side)
        position_section = (
            f"{Colors.YELLOW}📊 POSIÇÃO:{Colors.RESET} {pos_emoji} {m.position_side} "
            f"{Colors.WHITE}{m.position_size:.4f} {self.symbol[:-4]}{Colors.RESET}"
        )
        
        # PNL
        pnl_emoji = self.get_pnl_emoji(m.unrealized_pnl)
        pnl_color = Colors.BRIGHT_GREEN if m.unrealized_pnl >= 0 else Colors.BRIGHT_RED
        pnl_section = (
            f"{Colors.MAGENTA}💰 PNL:{Colors.RESET} {pnl_color}{m.unrealized_pnl:+.4f} USDT{Colors.RESET} {pnl_emoji}"
        )
        
        # TP/SL com display sempre presente
        tp_formatted = self.format_price(m.tp_price) if m.tp_price > 0 else "N/A"
        sl_formatted = self.format_price(m.sl_price) if m.sl_price > 0 else "N/A"
        tp_sl_section = (
            f"{Colors.GREEN}🎯 TP:{Colors.RESET} {tp_formatted} | "
            f"{Colors.RED}🛡️ SL:{Colors.RESET} {sl_formatted}"
        )
        
        # Indicadores técnicos
        rsi_color = Colors.BRIGHT_RED if m.rsi > 70 else Colors.BRIGHT_GREEN if m.rsi < 30 else Colors.YELLOW
        indicators_section = (
            f"{Colors.BLUE}📊 INDICADORES:{Colors.RESET} "
            f"RSI: {rsi_color}{m.rsi:.1f}{Colors.RESET} | "
            f"ATR: {Colors.CYAN}{m.atr:.4f}{Colors.RESET} | "
            f"ADX: {Colors.MAGENTA}{m.adx:.1f}{Colors.RESET}"
        )
        
        # Grid info
        grid_section = (
            f"{Colors.CYAN}🔲 GRID:{Colors.RESET} "
            f"Níveis: {Colors.WHITE}{m.grid_levels}{Colors.RESET} | "
            f"Ordens: {Colors.YELLOW}{m.active_orders}{Colors.RESET} | "
            f"Executadas: {Colors.GREEN}{m.filled_orders}{Colors.RESET} | "
            f"Lucro: {Colors.BRIGHT_GREEN}{m.grid_profit:+.4f} USDT{Colors.RESET}"
        )
        
        # Volume e alavancagem com melhores formatações
        volume_formatted = f"{m.volume_24h:,.0f}" if m.volume_24h > 0 else "N/A"
        volume_section = (
            f"{Colors.WHITE}📈 VOLUME 24H:{Colors.RESET} {Colors.CYAN}{volume_formatted} USDT{Colors.RESET} | "
            f"{Colors.YELLOW}⚡ LEVERAGE:{Colors.RESET} {Colors.BRIGHT_YELLOW}{m.leverage}x{Colors.RESET}"
        )
        
        # Montar mensagem completa
        message_parts = [
            f"\n{header}",
            f"⏰ {timestamp}",
            price_section,
            position_section,
            pnl_section,
            tp_sl_section,
            indicators_section,
            grid_section,
            volume_section,
            f"{Colors.DIM}{'─' * 80}{Colors.RESET}\n"
        ]
        
        full_message = "\n".join(filter(None, message_parts))
        
        # Log para arquivo (sem cores)
        clean_message = self._remove_ansi_codes(full_message)
        self.logger.info(clean_message)
        
        # Print para terminal (com cores)
        print(full_message)
    
    def log_order_event(self, side: str, price: float, quantity: float, order_type: str = "GRID"):
        """Log de evento de ordem"""
        emoji = self.get_emoji_for_side(side)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message = (
            f"{Colors.BOLD}{self.symbol}{Colors.RESET} {emoji} "
            f"{Colors.BRIGHT_YELLOW}{order_type} {side.upper()}{Colors.RESET} | "
            f"💰 {self.format_price(price)} | "
            f"📦 {quantity:.4f} | "
            f"⏰ {timestamp}"
        )
        
        # Log para arquivo
        clean_message = self._remove_ansi_codes(message)
        self.logger.info(clean_message)
        
        # Print para terminal
        print(f"{Colors.BRIGHT_CYAN}🔄 ORDER:{Colors.RESET} {message}")
    
    def log_position_update(self, side: str, entry_price: float, size: float, pnl: float):
        """Log de atualização de posição"""
        emoji = self.get_emoji_for_side(side)
        pnl_emoji = self.get_pnl_emoji(pnl)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        pnl_color = Colors.BRIGHT_GREEN if pnl >= 0 else Colors.BRIGHT_RED
        
        message = (
            f"{Colors.BOLD}{self.symbol}{Colors.RESET} {emoji} "
            f"{Colors.BRIGHT_BLUE}POSIÇÃO ATUALIZADA{Colors.RESET} | "
            f"📍 Entry: {self.format_price(entry_price)} | "
            f"📦 Size: {size:.4f} | "
            f"💰 PNL: {pnl_color}{pnl:+.4f} USDT{Colors.RESET} {pnl_emoji} | "
            f"⏰ {timestamp}"
        )
        
        # Log para arquivo
        clean_message = self._remove_ansi_codes(message)
        self.logger.info(clean_message)
        
        # Print para terminal
        print(f"{Colors.BRIGHT_MAGENTA}📊 POSITION:{Colors.RESET} {message}")
    
    def log_error(self, error_msg: str):
        """Log de erro"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message = (
            f"{Colors.BOLD}{self.symbol}{Colors.RESET} "
            f"{Colors.BG_RED}{Colors.WHITE} ERROR {Colors.RESET} "
            f"{Colors.BRIGHT_RED}{error_msg}{Colors.RESET} | "
            f"⏰ {timestamp}"
        )
        
        # Log para arquivo
        clean_message = self._remove_ansi_codes(message)
        self.logger.error(clean_message)
        
        # Print para terminal
        print(f"{Colors.BRIGHT_RED}❌ ERROR:{Colors.RESET} {message}")
    
    def log_info(self, info_msg: str):
        """Log de informação"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message = (
            f"{Colors.BOLD}{self.symbol}{Colors.RESET} "
            f"{Colors.BRIGHT_BLUE}ℹ️  {info_msg}{Colors.RESET} | "
            f"⏰ {timestamp}"
        )
        
        # Log para arquivo
        clean_message = self._remove_ansi_codes(message)
        self.logger.info(clean_message)
        
        # Print para terminal
        print(f"{Colors.BRIGHT_CYAN}ℹ️  INFO:{Colors.RESET} {message}")
    
    def _remove_ansi_codes(self, text: str) -> str:
        """Remove códigos ANSI para arquivo de log"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

class MultiPairLogger:
    """Gerenciador de logs para múltiplos pares"""
    
    def __init__(self, log_dir: str = "logs/pairs"):
        self.log_dir = log_dir
        self.pair_loggers: Dict[str, PairLogger] = {}
        self.lock = threading.Lock()
        
        # Logger principal
        self.main_logger = logging.getLogger("multi_pair")
        self.main_logger.setLevel(logging.INFO)
        
        # Handler para arquivo principal
        main_log_file = os.path.join(log_dir, "multi_pair.log")
        os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(main_log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.main_logger.addHandler(file_handler)
        
        self._print_header()
    
    def _print_header(self):
        """Imprime header do sistema"""
        header = f"""
{Colors.BOLD}{Colors.BG_CYAN}{Colors.WHITE} MULTI-PAIR TRADING SYSTEM - LOGS SEPARADOS {Colors.RESET}
{Colors.CYAN}════════════════════════════════════════════════════════════════════════════════{Colors.RESET}
{Colors.BRIGHT_YELLOW}📊 Sistema de logs individuais por par com métricas detalhadas{Colors.RESET}
{Colors.BRIGHT_GREEN}💰 PNL, TP/SL, Indicadores, Grid Status e mais!{Colors.RESET}
{Colors.BRIGHT_BLUE}🎯 Logs salvos em: {self.log_dir}{Colors.RESET}
{Colors.CYAN}════════════════════════════════════════════════════════════════════════════════{Colors.RESET}
        """
        print(header)
    
    def get_pair_logger(self, symbol: str) -> PairLogger:
        """Obtém ou cria logger para um par"""
        with self.lock:
            if symbol not in self.pair_loggers:
                self.pair_loggers[symbol] = PairLogger(symbol, self.log_dir)
                self.main_logger.info(f"Created logger for {symbol}")
            return self.pair_loggers[symbol]
    
    def log_system_event(self, message: str, level: str = "INFO"):
        """Log de evento do sistema"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        color_map = {
            "INFO": Colors.BRIGHT_CYAN,
            "WARNING": Colors.BRIGHT_YELLOW,
            "ERROR": Colors.BRIGHT_RED,
            "SUCCESS": Colors.BRIGHT_GREEN
        }
        
        emoji_map = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅"
        }
        
        color = color_map.get(level, Colors.WHITE)
        emoji = emoji_map.get(level, "📢")
        
        terminal_message = (
            f"{color}{emoji} SYSTEM:{Colors.RESET} "
            f"{Colors.BOLD}{message}{Colors.RESET} | "
            f"⏰ {timestamp}"
        )
        
        # Log para arquivo
        clean_message = f"{emoji} SYSTEM: {message} | {timestamp}"
        if level == "ERROR":
            self.main_logger.error(clean_message)
        elif level == "WARNING":
            self.main_logger.warning(clean_message)
        else:
            self.main_logger.info(clean_message)
        
        # Print para terminal
        print(terminal_message)
    
    def print_status_summary(self):
        """Imprime resumo de status de todos os pares"""
        if not self.pair_loggers:
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        header = f"""
{Colors.BOLD}{Colors.BG_BLUE}{Colors.WHITE} STATUS SUMMARY - {timestamp} {Colors.RESET}
{Colors.BLUE}{'─' * 80}{Colors.RESET}"""
        
        print(header)
        
        for symbol, logger in self.pair_loggers.items():
            m = logger.metrics
            
            # Status resumido por linha
            pnl_color = Colors.BRIGHT_GREEN if m.unrealized_pnl >= 0 else Colors.BRIGHT_RED
            pnl_emoji = logger.get_pnl_emoji(m.unrealized_pnl)
            pos_emoji = logger.get_emoji_for_side(m.position_side)
            
            summary_line = (
                f"{Colors.BOLD}{symbol:12}{Colors.RESET} | "
                f"{pos_emoji} {m.position_side:5} | "
                f"💰 {pnl_color}{m.unrealized_pnl:+8.4f}{Colors.RESET} {pnl_emoji} | "
                f"🔲 {m.active_orders:2} orders | "
                f"📈 ${m.current_price:8.4f} | "
                f"⚡ {m.leverage:2}x"
            )
            
            print(summary_line)
        
        print(f"{Colors.BLUE}{'─' * 80}{Colors.RESET}\n")

# Instância global
_multi_pair_logger = None

def get_multi_pair_logger() -> MultiPairLogger:
    """Obtém instância global do multi pair logger"""
    global _multi_pair_logger
    if _multi_pair_logger is None:
        _multi_pair_logger = MultiPairLogger()
    return _multi_pair_logger

def get_pair_logger(symbol: str) -> PairLogger:
    """Obtém logger para um par específico"""
    return get_multi_pair_logger().get_pair_logger(symbol)

# Exemplo de uso
if __name__ == "__main__":
    # Teste do sistema
    multi_logger = get_multi_pair_logger()
    
    # Criar alguns loggers de teste
    btc_logger = get_pair_logger("BTCUSDT")
    eth_logger = get_pair_logger("ETHUSDT")
    
    # Simular algumas métricas
    btc_logger.update_metrics(
        current_price=45000.50,
        position_side="LONG",
        position_size=0.001,
        unrealized_pnl=25.50,
        tp_price=46000.0,
        sl_price=44000.0,
        rsi=65.5,
        atr=1250.0,
        adx=45.2,
        volume_24h=1250000000,
        price_change_24h=2.5,
        grid_levels=10,
        active_orders=5,
        filled_orders=3,
        grid_profit=12.25,
        leverage=10
    )
    
    eth_logger.update_metrics(
        current_price=3200.75,
        position_side="SHORT",
        position_size=-0.5,
        unrealized_pnl=-15.25,
        tp_price=3100.0,
        sl_price=3300.0,
        rsi=35.8,
        atr=125.0,
        adx=32.1,
        volume_24h=850000000,
        price_change_24h=-1.8,
        grid_levels=8,
        active_orders=4,
        filled_orders=2,
        grid_profit=-5.50,
        leverage=5
    )
    
    # Testar logs
    multi_logger.log_system_event("Sistema iniciado com sucesso", "SUCCESS")
    
    btc_logger.log_trading_cycle()
    eth_logger.log_trading_cycle()
    
    btc_logger.log_order_event("BUY", 44950.0, 0.001, "GRID")
    eth_logger.log_position_update("SHORT", 3220.0, -0.5, -15.25)
    
    multi_logger.print_status_summary()
    
    time.sleep(1)
    
    btc_logger.log_info("Grid rebalanceado com sucesso")
    eth_logger.log_error("Falha ao conectar com a API")
    
    multi_logger.log_system_event("Ciclo de trading completo", "INFO")