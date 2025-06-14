#!/usr/bin/env python3
"""
Debug por que apenas 1 par está sendo executado
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.capital_management import CapitalManager
from core.pair_selector import PairSelector
import yaml

def debug_pair_selection():
    print("🔍 DEBUG: SELEÇÃO DE MÚLTIPLOS PARES")
    print("=" * 50)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    print("\n1. 📊 VERIFICANDO CONFIGURAÇÃO:")
    max_pairs = config.get('trading', {}).get('max_concurrent_pairs', 1)
    preferred_symbols = config.get('pair_selection', {}).get('futures_pairs', {}).get('preferred_symbols', [])
    
    print(f"   Max concurrent pairs: {max_pairs}")
    print(f"   Preferred symbols: {preferred_symbols}")
    
    print("\n2. 🔄 TESTANDO PAIR SELECTOR:")
    pair_selector = PairSelector(config, api)
    
    # Forçar atualização
    try:
        print("   🔄 Forçando atualização de seleção...")
        selected_pairs = pair_selector.get_selected_pairs(force_update=True)
        
        print(f"   ✅ Pares selecionados: {len(selected_pairs)}")
        for i, pair in enumerate(selected_pairs):
            print(f"      {i+1}. {pair}")
            
    except Exception as e:
        print(f"   ❌ Erro na seleção: {e}")
        return False
    
    print("\n3. 💰 TESTANDO CAPITAL ALLOCATION:")
    capital_manager = CapitalManager(api, config)
    
    try:
        # Usar apenas os primeiros 5 pares para teste
        test_symbols = selected_pairs[:5] if len(selected_pairs) >= 5 else selected_pairs
        print(f"   🎯 Testando com {len(test_symbols)} pares: {test_symbols}")
        
        allocations = capital_manager.calculate_optimal_allocations(test_symbols)
        
        print(f"   ✅ Alocações calculadas: {len(allocations)}")
        
        for alloc in allocations:
            print(f"   📈 {alloc.symbol}: ${alloc.allocated_amount:.2f} ({alloc.market_type}) - {alloc.grid_levels} levels")
            
        return len(allocations) >= 3
        
    except Exception as e:
        print(f"   ❌ Erro na alocação: {e}")
        import traceback
        traceback.print_exc()
        return False

def debug_grid_initialization():
    print("\n4. 🔧 TESTANDO INICIALIZAÇÃO DE GRIDS:")
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    # Testar inicialização de um grid simples
    from core.grid_logic import GridLogic
    
    test_symbol = "ADAUSDT"
    try:
        print(f"   🎯 Testando grid para {test_symbol}...")
        
        grid = GridLogic(test_symbol, config, api, market_type="futures")
        print(f"   ✅ Grid {test_symbol} inicializado com sucesso")
        
        # Verificar se consegue obter dados básicos
        price = api.get_futures_ticker(test_symbol)
        if price:
            current_price = float(price.get('price', 0))
            print(f"   📊 Preço atual: ${current_price:.6f}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro na inicialização do grid: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 DEBUG COMPLETO: MÚLTIPLOS PARES")
    print("=" * 60)
    
    # Executar testes
    test1 = debug_pair_selection()
    test2 = debug_grid_initialization()
    
    print(f"\n📊 RESUMO DOS TESTES:")
    print(f"   1. Seleção de pares: {'✅ PASSOU' if test1 else '❌ FALHOU'}")
    print(f"   2. Inicialização de grid: {'✅ PASSOU' if test2 else '❌ FALHOU'}")
    
    if test1 and test2:
        print(f"\n🎉 TUDO FUNCIONANDO - PROBLEMA DEVE ESTAR NO MULTI-AGENT!")
        print(f"💡 O sistema está configurado corretamente para múltiplos pares")
    else:
        print(f"\n⚠️ PROBLEMAS ENCONTRADOS - VERIFICAR CORREÇÕES")

if __name__ == "__main__":
    main()