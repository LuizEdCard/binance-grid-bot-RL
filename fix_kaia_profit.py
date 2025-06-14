#!/usr/bin/env python3
"""
Sistema automático de take profit para posições sem ordens ativas
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
import yaml

def create_smart_take_profit(api, symbol, position, profit_threshold=0.01):
    """Cria take profit inteligente baseado na posição atual."""
    try:
        position_amt = float(position.get('positionAmt', 0))
        entry_price = float(position.get('entryPrice', 0))
        mark_price = float(position.get('markPrice', 0))
        unrealized_pnl = float(position.get('unRealizedProfit', 0))
        
        print(f"📊 Análise da posição {symbol}:")
        print(f"   Quantidade: {position_amt}")
        print(f"   Entrada: ${entry_price:.6f}")
        print(f"   Atual: ${mark_price:.6f}")
        print(f"   PnL: ${unrealized_pnl:.4f}")
        
        # Só processar se há lucro acima do threshold
        if unrealized_pnl <= profit_threshold:
            print(f"   ⚠️ Lucro ${unrealized_pnl:.4f} < ${profit_threshold:.2f} threshold")
            return None
        
        # Calcular preço de take profit baseado no lucro atual
        if position_amt > 0:  # Long position
            side = 'SELL'
            # Take profit com small margin para garantir execução
            profit_margin = (mark_price - entry_price) * 0.8  # 80% do lucro atual
            take_profit_price = entry_price + profit_margin
        else:  # Short position  
            side = 'BUY'
            profit_margin = (entry_price - mark_price) * 0.8
            take_profit_price = entry_price - profit_margin
        
        quantity = abs(position_amt)
        
        # Ajustar precisão do preço (KAIA tem 7 decimais)
        take_profit_price = round(take_profit_price, 7)
        
        print(f"🎯 Criando take profit:")
        print(f"   Side: {side}")
        print(f"   Quantidade: {quantity}")
        print(f"   Preço TP: ${take_profit_price:.7f}")
        print(f"   Lucro esperado: ${unrealized_pnl * 0.8:.4f}")
        
        # Criar ordem
        order_result = api.place_futures_order(
            symbol=symbol,
            side=side,
            order_type='LIMIT',
            quantity=int(quantity),  # KAIA quantidade é inteira
            price=take_profit_price,
            time_in_force='GTC'
        )
        
        if order_result:
            print(f"   ✅ Take profit criado: ID {order_result.get('orderId')}")
            return order_result
        else:
            print(f"   ❌ Falha ao criar take profit")
            return None
            
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return None

def monitor_and_create_take_profits():
    """Monitora todas as posições e cria take profits quando necessário."""
    print("💰 SISTEMA INTELIGENTE DE TAKE PROFIT")
    print("=" * 50)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    print("\n1. 🔍 ANALISANDO TODAS AS POSIÇÕES COM LUCRO:")
    
    # Buscar todas as posições
    positions = api.get_futures_positions()
    profitable_positions = []
    
    if positions:
        for position in positions:
            symbol = position.get('symbol')
            position_amt = float(position.get('positionAmt', 0))
            unrealized_pnl = float(position.get('unRealizedProfit', 0))
            
            # Filtrar posições ativas com lucro
            if position_amt != 0 and unrealized_pnl > 0.01:
                profitable_positions.append(position)
                
                entry_price = float(position.get('entryPrice', 0))
                mark_price = float(position.get('markPrice', 0))
                
                print(f"📈 {symbol}:")
                print(f"   Posição: {position_amt}")
                print(f"   PnL: ${unrealized_pnl:.4f}")
                print(f"   Lucro %: {((mark_price-entry_price)/entry_price)*100:.2f}%")
    
    if not profitable_positions:
        print("   ❌ Nenhuma posição com lucro > $0.01")
        return
    
    print(f"\n2. 🎯 CRIANDO TAKE PROFITS INTELIGENTES:")
    
    created_orders = 0
    for position in profitable_positions:
        symbol = position.get('symbol')
        
        # Verificar se já tem ordens ativas
        existing_orders = api.get_open_futures_orders(symbol)
        
        if existing_orders:
            print(f"⚠️ {symbol}: Já tem {len(existing_orders)} ordens - analisando...")
            
            # Verificar se tem take profit
            has_take_profit = False
            position_amt = float(position.get('positionAmt', 0))
            
            for order in existing_orders:
                order_side = order.get('side')
                # Se long e tem SELL, ou short e tem BUY = take profit
                if (position_amt > 0 and order_side == 'SELL') or (position_amt < 0 and order_side == 'BUY'):
                    has_take_profit = True
                    print(f"   ✅ {symbol}: Take profit já existe")
                    break
            
            if has_take_profit:
                continue
        
        # Criar take profit inteligente
        order = create_smart_take_profit(api, symbol, position, 0.01)
        if order:
            created_orders += 1
    
    print(f"\n3. 📊 RESUMO:")
    print(f"   Posições com lucro: {len(profitable_positions)}")
    print(f"   Take profits criados: {created_orders}")
    
    if created_orders > 0:
        print(f"\n✅ Sistema de take profit inteligente ativado!")
        print(f"💡 Lucros serão realizados automaticamente")
    else:
        print(f"\n⚠️ Nenhum take profit criado (já existem ou outras condições)")

if __name__ == "__main__":
    monitor_and_create_take_profits()