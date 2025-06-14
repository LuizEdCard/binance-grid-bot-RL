#!/usr/bin/env python3
"""
Corrigir problemas da posição ADA e análise dos erros
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
import yaml

def main():
    print("🔧 CORREÇÃO DOS PROBLEMAS IDENTIFICADOS")
    print("=" * 50)
    
    # Carregar config
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    print("\n1. 📊 VERIFICANDO POSIÇÃO ADA ATUAL:")
    ada_position = api.get_futures_position('ADAUSDT')
    if ada_position:
        pnl = float(ada_position.get("unRealizedProfit", 0))
        entry_price = float(ada_position.get("entryPrice", 0))
        mark_price = float(ada_position.get("markPrice", 0))
        quantity = float(ada_position.get("positionAmt", 0))
        
        print(f"   💰 PnL não realizado: ${pnl:.4f} USDT")
        print(f"   📈 Preço entrada: ${entry_price:.4f}")
        print(f"   🎯 Preço atual: ${mark_price:.4f}")
        print(f"   📊 Quantidade: {quantity} ADA")
        print(f"   📈 Lucro por ADA: ${(mark_price - entry_price):.4f} = {((mark_price - entry_price) / entry_price) * 100:.2f}%")
        
        if pnl > 0.01:  # Se há lucro maior que $0.01
            print(f"   ✅ LUCRO DETECTADO: ${pnl:.4f} - DEVERIA SER REALIZADO!")
        else:
            print(f"   ⚠️  Lucro muito pequeno: ${pnl:.4f}")
    else:
        print("   ❌ Nenhuma posição ADA encontrada")
    
    print("\n2. 🎚️  AJUSTANDO ALAVANCAGEM PARA 10X:")
    leverage_result = api.change_leverage('ADAUSDT', 10)
    if leverage_result:
        print(f"   ✅ Alavancagem ajustada: {leverage_result}")
    else:
        print("   ❌ Falha ao ajustar alavancagem")
    
    print("\n3. 📋 VERIFICANDO ORDENS ATIVAS ADA:")
    ada_orders = api.get_open_futures_orders('ADAUSDT')
    if ada_orders:
        print(f"   📊 {len(ada_orders)} ordens ativas ADA:")
        for order in ada_orders:
            side = order.get('side')
            qty = order.get('origQty')
            price = order.get('price')
            print(f"     {side} {qty} ADA @ ${price}")
    else:
        print("   ⚠️  Nenhuma ordem ADA ativa - isso pode explicar por que o lucro não foi realizado")
    
    print("\n4. 🔍 ANALISANDO SELEÇÃO DE PARES:")
    # Verificar por que apenas KAIAUSDT foi selecionado
    preferred_symbols = config.get('pair_selection', {}).get('futures_pairs', {}).get('preferred_symbols', [])
    print(f"   📝 Símbolos preferenciais configurados: {preferred_symbols}")
    
    # Verificar se ADA está nos símbolos preferenciais
    if 'ADAUSDT' in preferred_symbols:
        print("   ✅ ADAUSDT está nos símbolos preferenciais")
    else:
        print("   ❌ ADAUSDT NÃO está nos símbolos preferenciais")
    
    print("\n5. ⚙️  CONFIGURAÇÕES ATUAIS:")
    max_pairs = config.get('trading', {}).get('max_concurrent_pairs', 1)
    print(f"   📊 Máximo de pares simultâneos: {max_pairs}")
    
    if max_pairs == 1:
        print("   ⚠️  Configurado para apenas 1 par - isso explica por que só KAIAUSDT foi selecionado")
        print("   💡 Sugestão: Aumentar max_concurrent_pairs para 2-3 pares")
    
    print("\n6. 🎯 DIAGNÓSTICO DOS PROBLEMAS:")
    print("   🔴 PROBLEMA 1: Lucro ADA não realizado")
    print("      - Causa: Sem ordens de take profit ativas")
    print("      - Solução: Grid deve criar ordens de venda quando há lucro")
    
    print("   🔴 PROBLEMA 2: Alavancagem ainda em 2x")
    print("      - Causa: Configuração não aplicada automaticamente")
    print("      - Solução: Implementar ajuste automático de alavancagem")
    
    print("   🔴 PROBLEMA 3: Apenas 1 par selecionado")
    print("      - Causa: max_concurrent_pairs = 1")
    print("      - Solução: Aumentar para 2-3 pares")

if __name__ == "__main__":
    main()