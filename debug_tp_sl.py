#!/usr/bin/env python3
"""
Script de debug para verificar TP/SL ativo na Binance
"""

import sys
import os
sys.path.append('src')

from utils.api_client import APIClient
import yaml

def debug_tp_sl():
    # Carregar configuração
    with open('src/config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Inicializar API client
    api_client = APIClient(config)
    
    print("🔍 Verificando ordens TP/SL ativas...")
    
    # 1. Verificar posições ativas
    positions = api_client.get_futures_positions()
    active_positions = [pos for pos in positions if float(pos.get('positionAmt', 0)) != 0]
    
    print(f"\n📊 Posições ativas: {len(active_positions)}")
    for pos in active_positions:
        symbol = pos['symbol']
        size = float(pos['positionAmt'])
        entry = float(pos['entryPrice'])
        mark = float(pos['markPrice'])
        pnl = float(pos['unRealizedProfit'])
        
        print(f"  {symbol}: {size:+.2f} @ ${entry:.4f} | Mark: ${mark:.4f} | PnL: ${pnl:+.4f}")
    
    # 2. Verificar ordens abertas (TP/SL)
    print(f"\n🎯 Verificando ordens TP/SL abertas...")
    
    for pos in active_positions:
        symbol = pos['symbol']
        try:
            orders = api_client.get_open_futures_orders(symbol=symbol)
            
            if orders:
                print(f"\n  {symbol} - Ordens abertas: {len(orders)}")
                for order in orders:
                    order_type = order.get('type', 'UNKNOWN')
                    side = order.get('side', 'UNKNOWN')
                    price = order.get('price', '0')
                    qty = order.get('origQty', '0')
                    status = order.get('status', 'UNKNOWN')
                    
                    # Identificar se é TP ou SL
                    if order_type in ['TAKE_PROFIT_MARKET', 'TAKE_PROFIT']:
                        order_label = "🎯 TP"
                    elif order_type in ['STOP_MARKET', 'STOP']:
                        order_label = "🛡️ SL"
                    else:
                        order_label = f"📋 {order_type}"
                    
                    print(f"    {order_label}: {side} {qty} @ ${price} ({status})")
            else:
                print(f"  {symbol} - Nenhuma ordem aberta")
                
        except Exception as e:
            print(f"  Erro ao verificar ordens de {symbol}: {e}")

if __name__ == "__main__":
    debug_tp_sl()