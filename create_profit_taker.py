#!/usr/bin/env python3
"""
Implementar sistema de realização de lucro para posições com PnL positivo
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
import yaml
import time

def create_profit_taking_order(api, symbol, position):
    """Cria ordem de take profit para posição lucrativa."""
    try:
        position_amt = float(position.get('positionAmt', 0))
        entry_price = float(position.get('entryPrice', 0))
        mark_price = float(position.get('markPrice', 0))
        unrealized_pnl = float(position.get('unRealizedProfit', 0))
        
        # Só processar se há lucro real
        if unrealized_pnl <= 0.01:  # Menor que $0.01
            return None
            
        # Determinar side da ordem (oposto à posição)
        if position_amt > 0:  # Posição long
            side = 'SELL'
            # Preço de take profit: preço atual + small buffer
            take_profit_price = round(mark_price * 1.001, 4)  # 0.1% acima, 4 decimais
        else:  # Posição short
            side = 'BUY'
            take_profit_price = round(mark_price * 0.999, 4)  # 0.1% abaixo, 4 decimais
        
        # Quantidade = quantidade da posição (inteiro para ADA)
        quantity = int(abs(position_amt))
        
        print(f"🎯 Criando ordem de take profit:")
        print(f"   Símbolo: {symbol}")
        print(f"   Side: {side}")
        print(f"   Quantidade: {quantity}")
        print(f"   Preço: ${take_profit_price:.6f}")
        print(f"   PnL a realizar: ${unrealized_pnl:.4f}")
        
        # Criar ordem limit
        order_result = api.place_futures_order(
            symbol=symbol,
            side=side,
            order_type='LIMIT',
            quantity=quantity,
            price=take_profit_price,
            time_in_force='GTC'
        )
        
        if order_result:
            print(f"   ✅ Ordem criada: ID {order_result.get('orderId')}")
            return order_result
        else:
            print(f"   ❌ Falha ao criar ordem")
            return None
            
    except Exception as e:
        print(f"   ❌ Erro ao criar take profit: {e}")
        return None

def main():
    print("💰 SISTEMA DE REALIZAÇÃO DE LUCRO")
    print("=" * 50)
    
    # Carregar config
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    print("\n1. 🔍 VERIFICANDO POSIÇÕES COM LUCRO:")
    
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
                print(f"   Quantidade: {position_amt}")
                print(f"   Entrada: ${entry_price:.6f}")
                print(f"   Atual: ${mark_price:.6f}")
                print(f"   PnL: ${unrealized_pnl:.4f}")
                print()
    
    if not profitable_positions:
        print("   ❌ Nenhuma posição com lucro encontrada")
        return
    
    print(f"\n2. 🎯 CRIANDO ORDENS DE TAKE PROFIT ({len(profitable_positions)} posições):")
    
    created_orders = 0
    for position in profitable_positions:
        symbol = position.get('symbol')
        
        # Verificar se já existe ordem de take profit
        existing_orders = api.get_open_futures_orders(symbol)
        
        if existing_orders:
            print(f"⚠️  {symbol}: Já tem {len(existing_orders)} ordens ativas - pulando")
            continue
        
        # Criar ordem de take profit
        order = create_profit_taking_order(api, symbol, position)
        if order:
            created_orders += 1
        
        time.sleep(0.5)  # Pequeno delay entre ordens
    
    print(f"\n3. 📊 RESUMO:")
    print(f"   Posições com lucro: {len(profitable_positions)}")
    print(f"   Ordens criadas: {created_orders}")
    
    if created_orders > 0:
        print(f"\n✅ Sistema de take profit ativado!")
        print(f"💡 As ordens serão executadas automaticamente quando o preço atingir o target")
    else:
        print(f"\n⚠️  Nenhuma ordem criada (podem já existir ordens ou outras condições)")

if __name__ == "__main__":
    main()