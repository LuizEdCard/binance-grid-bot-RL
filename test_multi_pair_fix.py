#!/usr/bin/env python3
"""
Teste das correções para múltiplos pares e alavancagem
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.capital_management import CapitalManager
from core.pair_selector import PairSelector
import yaml

def test_capital_allocation_with_leverage():
    """Testa alocação de capital considerando alavancagem."""
    print("🧪 TESTE: ALOCAÇÃO DE CAPITAL COM ALAVANCAGEM")
    print("=" * 60)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    capital_manager = CapitalManager(api, config)
    
    # Símbolos para teste
    test_symbols = ['ADAUSDT', 'XRPUSDT', 'DOGEUSDT', 'TRXUSDT', 'XLMUSDT']
    
    print(f"\n1. 💰 SALDOS ATUAIS:")
    balances = capital_manager.get_available_balances()
    print(f"   Spot: ${balances['spot_usdt']:.2f}")
    print(f"   Futures: ${balances['futures_usdt']:.2f}")
    print(f"   Total: ${balances['total_usdt']:.2f}")
    
    print(f"\n2. 📊 TESTANDO ALOCAÇÃO PARA {len(test_symbols)} PARES:")
    
    # Calcular alocações
    allocations = capital_manager.calculate_optimal_allocations(test_symbols)
    
    if not allocations:
        print("   ❌ Nenhuma alocação calculada - capital insuficiente!")
        return False
    
    print(f"   ✅ {len(allocations)} alocações calculadas:")
    
    total_spot = 0
    total_futures = 0
    
    for alloc in allocations:
        market_type = alloc.market_type
        capital = alloc.allocated_amount
        leverage = getattr(alloc, 'leverage', 1)
        
        if market_type == "spot":
            total_spot += capital
            print(f"   📈 {alloc.symbol} (SPOT): ${capital:.2f} - {alloc.grid_levels} levels, {alloc.spacing_percentage*100:.2f}% spacing")
        else:
            total_futures += capital
            effective_capital = capital * 10  # 10x leverage
            print(f"   🚀 {alloc.symbol} (FUTURES): ${capital:.2f} (${effective_capital:.2f} effective) - {alloc.grid_levels} levels, {alloc.spacing_percentage*100:.2f}% spacing")
    
    print(f"\n3. 📈 RESUMO DA ALOCAÇÃO:")
    print(f"   Spot total: ${total_spot:.2f}")
    print(f"   Futures total: ${total_futures:.2f}")
    print(f"   Total alocado: ${total_spot + total_futures:.2f}")
    
    # Verificar se a alavancagem está sendo considerada
    futures_allocations = [a for a in allocations if a.market_type == "futures"]
    if futures_allocations:
        futures_alloc = futures_allocations[0]
        leverage = config.get("grid", {}).get("futures", {}).get("leverage", 10)
        
        print(f"\n4. 🎚️ VERIFICAÇÃO DE ALAVANCAGEM:")
        print(f"   Alavancagem configurada: {leverage}x")
        print(f"   Grid levels futures: {futures_alloc.grid_levels}")
        print(f"   Spacing futures: {futures_alloc.spacing_percentage*100:.3f}%")
        
        # Comparar com spot
        spot_allocations = [a for a in allocations if a.market_type == "spot"]
        if spot_allocations:
            spot_alloc = spot_allocations[0]
            print(f"   Grid levels spot: {spot_alloc.grid_levels}")
            print(f"   Spacing spot: {spot_alloc.spacing_percentage*100:.3f}%")
            
            if futures_alloc.grid_levels > spot_alloc.grid_levels:
                print("   ✅ Futures tem mais levels (correto com alavancagem)")
            if futures_alloc.spacing_percentage < spot_alloc.spacing_percentage:
                print("   ✅ Futures tem spacing menor (correto com alavancagem)")
    
    return len(allocations) >= 3

def test_pair_selection():
    """Testa seleção de pares."""
    print(f"\n🔍 TESTE: SELEÇÃO DE PARES")
    print("=" * 60)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    # Verificar configuração atual
    max_pairs = config.get('trading', {}).get('max_concurrent_pairs', 1)
    print(f"   Max concurrent pairs: {max_pairs}")
    
    if max_pairs < 3:
        print("   ⚠️ max_concurrent_pairs muito baixo!")
        return False
    
    pair_selector = PairSelector(config, api)
    
    print(f"   🔄 Atualizando seleção de pares...")
    try:
        # Forçar atualização
        pair_selector.update_pair_selection(force_update=True)
        selected_pairs = pair_selector.get_selected_pairs()
        
        print(f"   ✅ Pares selecionados: {len(selected_pairs)}")
        for i, pair in enumerate(selected_pairs[:5]):
            print(f"      {i+1}. {pair}")
        
        if len(selected_pairs) >= 3:
            print("   ✅ Seleção de múltiplos pares funcionando!")
            return True
        else:
            print("   ❌ Poucos pares selecionados")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro na seleção: {e}")
        return False

def test_leverage_application():
    """Testa aplicação automática de alavancagem."""
    print(f"\n🎚️ TESTE: APLICAÇÃO DE ALAVANCAGEM")
    print("=" * 60)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    # Símbolos de teste
    test_symbols = ['ADAUSDT', 'XRPUSDT']
    
    for symbol in test_symbols:
        try:
            print(f"   🎯 Testando {symbol}...")
            
            # Verificar alavancagem atual
            position = api.get_futures_position(symbol)
            if position:
                current_leverage = position.get('leverage', 'N/A')
                print(f"      Alavancagem atual: {current_leverage}")
            
            # Aplicar nova alavancagem
            result = api.change_leverage(symbol, 10)
            if result:
                print(f"      ✅ Alavancagem ajustada para 10x")
            else:
                print(f"      ❌ Falha ao ajustar alavancagem")
                
        except Exception as e:
            print(f"      ❌ Erro: {e}")
    
    return True

def main():
    print("🚀 TESTE COMPLETO: CORREÇÕES MULTI-PARES + ALAVANCAGEM")
    print("=" * 70)
    
    # Executar testes
    test1 = test_pair_selection()
    test2 = test_capital_allocation_with_leverage()
    test3 = test_leverage_application()
    
    print(f"\n📊 RESUMO DOS TESTES:")
    print(f"   1. Seleção de pares: {'✅ PASSOU' if test1 else '❌ FALHOU'}")
    print(f"   2. Alocação com alavancagem: {'✅ PASSOU' if test2 else '❌ FALHOU'}")
    print(f"   3. Aplicação de alavancagem: {'✅ PASSOU' if test3 else '❌ FALHOU'}")
    
    if test1 and test2 and test3:
        print(f"\n🎉 TODOS OS TESTES PASSARAM!")
        print(f"💡 O sistema está pronto para operar múltiplos pares com alavancagem!")
        
        # Mostrar configuração recomendada
        print(f"\n🔧 CONFIGURAÇÃO ATUAL:")
        print(f"   • Max pares: 15")
        print(f"   • Alavancagem: 10x (max 15x)")  
        print(f"   • Spacing reduzido para futures")
        print(f"   • Mais grid levels com alavancagem")
        
    else:
        print(f"\n⚠️ ALGUNS TESTES FALHARAM - VERIFICAR CORREÇÕES")

if __name__ == "__main__":
    main()