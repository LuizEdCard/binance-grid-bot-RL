#!/usr/bin/env python3
"""
Teste do sistema de logging por pares
"""

import sys
import os
import time
import random
from decimal import Decimal

# Adicionar src ao path
sys.path.append('src')

from utils.pair_logger import get_multi_pair_logger, get_pair_logger

def test_pair_logging():
    """Testa o sistema de logging separado por pares"""
    
    print("🧪 TESTANDO SISTEMA DE LOGGING POR PARES")
    print("=" * 60)
    
    # Obter logger principal
    multi_logger = get_multi_pair_logger()
    
    # Criar loggers para diferentes pares
    symbols = ["XRPUSDT", "ADAUSDT", "DOGEUSDT"]
    loggers = {}
    
    for symbol in symbols:
        loggers[symbol] = get_pair_logger(symbol)
        loggers[symbol].log_info(f"Sistema de logging inicializado para {symbol}")
    
    # Simular dados de trading
    base_prices = {
        "XRPUSDT": 0.5234,
        "ADAUSDT": 0.3456, 
        "DOGEUSDT": 0.0789
    }
    
    multi_logger.log_system_event("Iniciando simulação de trading", "INFO")
    
    # Simular 5 ciclos de trading
    for cycle in range(5):
        print(f"\n{'='*20} CICLO {cycle + 1} {'='*20}")
        
        multi_logger.log_system_event(f"Iniciando ciclo {cycle + 1} de trading", "INFO")
        
        for symbol in symbols:
            logger = loggers[symbol]
            base_price = base_prices[symbol]
            
            # Simular variação de preço
            price_change = random.uniform(-3.0, 3.0)
            current_price = base_price * (1 + price_change / 100)
            
            # Simular posição (randomizada)
            position_types = ["LONG", "SHORT", "NONE"]
            position_side = random.choice(position_types)
            
            if position_side == "LONG":
                position_size = random.uniform(10, 100)
                entry_price = current_price * 0.98
            elif position_side == "SHORT":
                position_size = -random.uniform(10, 100)
                entry_price = current_price * 1.02
            else:
                position_size = 0
                entry_price = 0
            
            # Calcular PNL
            if position_size != 0:
                pnl = position_size * (current_price - entry_price) if position_size > 0 else -position_size * (entry_price - current_price)
            else:
                pnl = 0
            
            # Atualizar métricas
            logger.update_metrics(
                current_price=current_price,
                entry_price=entry_price,
                tp_price=entry_price * 1.05 if position_side == "LONG" else entry_price * 0.95 if position_side == "SHORT" else 0,
                sl_price=entry_price * 0.95 if position_side == "LONG" else entry_price * 1.05 if position_side == "SHORT" else 0,
                unrealized_pnl=pnl,
                realized_pnl=random.uniform(-10, 25),
                position_size=position_size,
                leverage=random.choice([5, 10, 15]),
                rsi=random.uniform(20, 80),
                atr=current_price * random.uniform(0.01, 0.05),
                adx=random.uniform(20, 60),
                volume_24h=random.uniform(1000000, 50000000),
                price_change_24h=price_change,
                grid_levels=random.randint(8, 15),
                active_orders=random.randint(3, 8),
                filled_orders=random.randint(0, 5),
                grid_profit=random.uniform(-5, 15),
                position_side=position_side,
                market_type="FUTURES"
            )
            
            # Log do ciclo de trading
            logger.log_trading_cycle()
            
            # Simular alguns eventos aleatórios
            if random.random() < 0.3:  # 30% chance de ordem
                side = random.choice(["BUY", "SELL"])
                price = current_price * random.uniform(0.995, 1.005)
                quantity = random.uniform(5, 20)
                logger.log_order_event(side, price, quantity, "GRID")
            
            if random.random() < 0.2:  # 20% chance de update de posição
                if position_size != 0:
                    logger.log_position_update(position_side, entry_price, position_size, pnl)
            
            if random.random() < 0.1:  # 10% chance de erro
                logger.log_error("Simulação de erro de conexão com API")
            
            # Pausa pequena entre pares
            time.sleep(0.5)
        
        # Summary no final de cada ciclo
        multi_logger.print_status_summary()
        
        # Pausa entre ciclos
        time.sleep(2)
    
    multi_logger.log_system_event("Simulação de trading concluída com sucesso", "SUCCESS")
    
    print("\n" + "="*60)
    print("✅ TESTE CONCLUÍDO!")
    print("📁 Logs salvos em: logs/pairs/")
    print("📊 Cada par tem seu arquivo individual de log")
    print("🎯 Logs combinados em: logs/pairs/multi_pair.log")

if __name__ == "__main__":
    test_pair_logging()