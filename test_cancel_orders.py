#!/usr/bin/env python3
"""
Teste da funcionalidade de cancelar ordens usando as ordens ETH ativas
"""

import sys
import os
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
import yaml

def load_config():
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def test_cancel_orders():
    print("🧪 TESTE: CANCELAMENTO DE ORDENS")
    print("=" * 50)
    
    config = load_config()
    api = APIClient(config)
    
    # 1. Verificar ordens abertas antes
    print("\n📋 1. Verificando ordens abertas ANTES do cancelamento:")
    orders_before = api.get_open_futures_orders()
    
    if not orders_before:
        print("   ❌ Nenhuma ordem aberta encontrada para testar")
        return False
        
    print(f"   ✅ Encontradas {len(orders_before)} ordens abertas:")
    eth_orders = []
    
    for i, order in enumerate(orders_before):
        symbol = order.get('symbol')
        side = order.get('side')
        qty = order.get('origQty')
        price = order.get('price')
        order_id = order.get('orderId')
        
        print(f"   {i+1}. {symbol}: {side} {qty} @ ${price} (ID: {order_id})")
        
        if symbol == 'ETHUSDT':
            eth_orders.append(order)
    
    if not eth_orders:
        print("   ⚠️  Nenhuma ordem ETH encontrada para testar")
        # Pegar primeira ordem disponível
        test_order = orders_before[0]
    else:
        # Usar primeira ordem ETH
        test_order = eth_orders[0]
    
    print(f"\n🎯 2. Testando cancelamento da ordem:")
    print(f"   Símbolo: {test_order['symbol']}")
    print(f"   ID: {test_order['orderId']}")
    print(f"   Tipo: {test_order['side']} @ ${test_order['price']}")
    
    # 2. Tentar cancelar uma ordem
    try:
        print("\n⏳ Cancelando ordem...")
        result = api.cancel_futures_order(
            symbol=test_order['symbol'], 
            orderId=test_order['orderId']
        )
        
        if result:
            print("   ✅ Ordem cancelada com sucesso!")
            print(f"   📄 Detalhes: {result}")
        else:
            print("   ❌ Falha no cancelamento - resultado None")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro ao cancelar ordem: {e}")
        return False
    
    # 3. Aguardar e verificar se foi cancelada
    print("\n⏳ Aguardando 3 segundos...")
    time.sleep(3)
    
    print("\n📋 3. Verificando ordens abertas APÓS cancelamento:")
    orders_after = api.get_open_futures_orders()
    
    print(f"   Ordens antes: {len(orders_before)}")
    print(f"   Ordens depois: {len(orders_after) if orders_after else 0}")
    
    if orders_after is None:
        orders_after = []
    
    # Verificar se a ordem foi removida
    canceled_order_found = False
    if orders_after:
        for order in orders_after:
            if order.get('orderId') == test_order['orderId']:
                canceled_order_found = True
                break
    
    if not canceled_order_found:
        print("   ✅ Ordem cancelada com sucesso - não encontrada na lista!")
        print(f"   📉 Redução de ordens: {len(orders_before)} → {len(orders_after)}")
        return True
    else:
        print("   ❌ Ordem ainda aparece na lista - cancelamento pode ter falhado")
        return False

def test_cancel_all_symbol_orders():
    """Teste para cancelar todas as ordens de um símbolo específico"""
    print("\n" + "=" * 50)
    print("🧪 TESTE: CANCELAR TODAS AS ORDENS DE UM SÍMBOLO")
    print("=" * 50)
    
    config = load_config()
    api = APIClient(config)
    
    # Verificar se há ordens ETH para cancelar
    orders = api.get_open_futures_orders()
    if not orders:
        print("   ❌ Nenhuma ordem para testar cancelamento em lote")
        return True
    
    eth_orders = [o for o in orders if o.get('symbol') == 'ETHUSDT']
    
    if not eth_orders:
        print("   ⚠️  Nenhuma ordem ETHUSDT para testar")
        # Usar qualquer símbolo disponível
        available_symbols = list(set(o.get('symbol') for o in orders))
        if available_symbols:
            test_symbol = available_symbols[0]
            test_orders = [o for o in orders if o.get('symbol') == test_symbol]
        else:
            return True
    else:
        test_symbol = 'ETHUSDT'
        test_orders = eth_orders
    
    print(f"\n🎯 Cancelando todas as ordens de {test_symbol}:")
    print(f"   📊 Total de ordens: {len(test_orders)}")
    
    success_count = 0
    for order in test_orders:
        try:
            result = api.cancel_futures_order(
                symbol=order['symbol'],
                orderId=order['orderId']
            )
            if result:
                print(f"   ✅ Cancelada: {order['orderId']}")
                success_count += 1
            else:
                print(f"   ❌ Falhou: {order['orderId']}")
        except Exception as e:
            print(f"   ❌ Erro: {order['orderId']} - {e}")
    
    print(f"\n📈 Resultado: {success_count}/{len(test_orders)} ordens canceladas")
    return success_count == len(test_orders)

if __name__ == "__main__":
    print("🚀 INICIANDO TESTES DE CANCELAMENTO DE ORDENS")
    
    # Teste 1: Cancelar uma ordem individual
    test1_result = test_cancel_orders()
    
    # Teste 2: Cancelar todas as ordens de um símbolo  
    test2_result = test_cancel_all_symbol_orders()
    
    print("\n" + "=" * 50)
    print("📊 RESUMO DOS TESTES")
    print("=" * 50)
    print(f"✅ Teste 1 (Cancelar ordem individual): {'PASSOU' if test1_result else 'FALHOU'}")
    print(f"✅ Teste 2 (Cancelar todas do símbolo): {'PASSOU' if test2_result else 'FALHOU'}")
    
    if test1_result and test2_result:
        print("\n🎉 TODOS OS TESTES PASSARAM - Função de cancelamento OK!")
    else:
        print("\n⚠️  ALGUNS TESTES FALHARAM - Verificar implementação")