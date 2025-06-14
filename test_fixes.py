#!/usr/bin/env python3
"""
Teste rápido das correções aplicadas
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.pair_selector import PairSelector
import yaml

def test_all_fixes():
    print("🔧 TESTE DAS CORREÇÕES APLICADAS")
    print("=" * 50)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    print("\n1. 🎯 TESTANDO SELEÇÃO RÁPIDA DE PARES:")
    
    try:
        pair_selector = PairSelector(config, api)
        
        # Forçar seleção com preferred symbols
        selected_pairs = pair_selector.get_selected_pairs(force_update=True)
        
        print(f"   ✅ Pares selecionados: {len(selected_pairs)}")
        for i, pair in enumerate(selected_pairs):
            print(f"      {i+1}. {pair}")
            
        if len(selected_pairs) == 5 and 'XRPUSDT' in selected_pairs:
            print("   ✅ Seleção de preferred symbols funcionando!")
            test1 = True
        else:
            print("   ❌ Ainda não está usando preferred symbols")
            test1 = False
            
    except Exception as e:
        print(f"   ❌ Erro na seleção: {e}")
        test1 = False
    
    print("\n2. 🛡️ TESTANDO CORREÇÃO DO RISK AGENT:")
    
    try:
        # Testar get_futures_position
        position = api.get_futures_position("ADAUSDT")
        if position is None:
            print("   ✅ get_futures_position retorna None para posição inexistente")
            test2 = True
        elif isinstance(position, dict):
            print("   ✅ get_futures_position retorna dict corretamente")
            test2 = True
        else:
            print(f"   ❌ get_futures_position retorna tipo incorreto: {type(position)}")
            test2 = False
            
    except Exception as e:
        print(f"   ❌ Erro no get_futures_position: {e}")
        test2 = False
    
    print("\n3. 🤖 TESTANDO INTEGRAÇÃO IA:")
    
    try:
        from agents.ai_agent import AIAgent
        ai_base_url = config.get("ai_agent", {}).get("base_url", "http://127.0.0.1:11434")
        ai_agent = AIAgent(config, ai_base_url)
        
        print(f"   ✅ AIAgent carregado com sucesso")
        print(f"   🔄 AI disponível: {ai_agent.is_available}")
        test3 = True
            
    except Exception as e:
        print(f"   ❌ Erro no AIAgent: {e}")
        test3 = False
    
    print(f"\n📊 RESUMO DOS TESTES:")
    print(f"   1. Seleção rápida de pares: {'✅ OK' if test1 else '❌ FALHOU'}")
    print(f"   2. Correção Risk Agent: {'✅ OK' if test2 else '❌ FALHOU'}")
    print(f"   3. Integração IA: {'✅ OK' if test3 else '❌ FALHOU'}")
    
    if test1 and test2 and test3:
        print(f"\n🎉 TODAS AS CORREÇÕES FUNCIONANDO!")
        print(f"🚀 Sistema pronto para reiniciar com múltiplos pares")
    else:
        print(f"\n⚠️ AINDA HÁ PROBLEMAS A CORRIGIR")
    
    return test1 and test2 and test3

if __name__ == "__main__":
    test_all_fixes()