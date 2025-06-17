#!/usr/bin/env python3
"""
Script para verificar e cancelar ordens antigas (>24h) automaticamente
"""
import sys
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from utils.logger import setup_logger
import yaml

log = setup_logger("check_old_orders")

def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def check_and_cancel_old_orders():
    """Verifica e cancela ordens antigas (>24h)"""
    try:
        config = load_config()
        api_client = APIClient(config)
        
        # Obter ordens abertas
        orders = api_client.get_open_futures_orders()
        if not orders:
            log.info("✅ Nenhuma ordem aberta encontrada")
            return
        
        log.info(f"🔍 Verificando {len(orders)} ordens abertas...")
        
        current_time = time.time() * 1000  # Convert to milliseconds
        old_order_threshold = 24 * 60 * 60 * 1000  # 24 horas em ms
        
        orders_to_cancel = []
        
        for order in orders:
            order_time = int(order.get('time', 0))
            order_age_ms = current_time - order_time
            order_age_hours = order_age_ms / (60 * 60 * 1000)
            
            symbol = order.get('symbol', '')
            order_id = order.get('orderId', '')
            side = order.get('side', '')
            price = order.get('price', '0')
            qty = order.get('origQty', '0')
            
            if order_age_ms > old_order_threshold:
                orders_to_cancel.append({
                    'symbol': symbol,
                    'orderId': order_id,
                    'age_hours': order_age_hours,
                    'side': side,
                    'price': price,
                    'qty': qty
                })
                
                log.warning(f"🕐 Ordem antiga detectada: {symbol} {side} {qty}@{price} (idade: {order_age_hours:.1f}h)")
            else:
                log.debug(f"✅ {symbol} {side} {qty}@{price} (idade: {order_age_hours:.1f}h) - OK")
        
        if not orders_to_cancel:
            log.info("✅ Nenhuma ordem antiga (>24h) encontrada")
            return
        
        log.info(f"🛑 Cancelando {len(orders_to_cancel)} ordens antigas...")
        
        cancelled_count = 0
        for order_info in orders_to_cancel:
            try:
                result = api_client.cancel_futures_order(
                    symbol=order_info['symbol'],
                    orderId=order_info['orderId']
                )
                
                if result:
                    cancelled_count += 1
                    log.info(f"✅ Ordem cancelada: {order_info['symbol']} {order_info['side']} "
                            f"{order_info['qty']}@{order_info['price']} (idade: {order_info['age_hours']:.1f}h)")
                else:
                    log.error(f"❌ Falha ao cancelar: {order_info['symbol']} OrderID {order_info['orderId']}")
                
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                log.error(f"❌ Erro ao cancelar ordem {order_info['symbol']} {order_info['orderId']}: {e}")
        
        log.info(f"📊 Resultado: {cancelled_count}/{len(orders_to_cancel)} ordens canceladas com sucesso")
        
        if cancelled_count > 0:
            log.info("🔄 Ordens antigas removidas! O sistema pode agora selecionar novos pares.")
        
    except Exception as e:
        log.error(f"Erro geral no cancelamento de ordens antigas: {e}")

if __name__ == "__main__":
    log.info("🔍 Iniciando verificação de ordens antigas (>24h)...")
    check_and_cancel_old_orders()
    log.info("✅ Verificação concluída!")