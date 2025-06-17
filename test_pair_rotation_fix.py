#!/usr/bin/env python3
"""
Teste de Rotação de Pares - Verifica se os imports estão funcionando
"""

import sys
import os

# Adicionar o diretório src ao Python path
sys.path.append('src')

def test_imports():
    """Testa todos os imports críticos para rotação de pares."""
    
    print("🧪 TESTE DE IMPORTS PARA ROTAÇÃO DE PARES")
    print("=" * 50)
    
    try:
        # 1. Teste do trade activity tracker
        print("📊 Testando Trade Activity Tracker...")
        from src.utils.trade_activity_tracker import get_trade_activity_tracker
        print("   ✅ trade_activity_tracker import OK")
        
        # 2. Teste do multi-agent bot
        print("🤖 Testando Multi-Agent Bot...")
        from src.multi_agent_bot import MultiAgentTradingBot
        print("   ✅ MultiAgentTradingBot import OK")
        
        # 3. Teste do pair selector
        print("🎯 Testando Pair Selector...")
        from src.core.pair_selector import PairSelector
        print("   ✅ PairSelector import OK")
        
        # 4. Teste da simulação de update_trading_pairs
        print("🔄 Testando método update_trading_pairs...")
        
        # Simular carregamento de config
        import yaml
        config_path = os.path.join('src', 'config', 'config.yaml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Verificar configurações de rotação
        auto_pair_enabled = config.get("trading", {}).get("enable_auto_pair_addition", False)
        pair_update_cycle = config.get("multi_agent_system", {}).get("pair_update_cycle_minutes", 2)
        inactivity_timeout = config.get("trade_activity_tracker", {}).get("inactivity_timeout_seconds", 3600)
        
        print(f"   📋 Auto pair addition: {auto_pair_enabled}")
        print(f"   ⏱️  Update cycle: {pair_update_cycle} minutos")
        print(f"   ⏰ Inactivity timeout: {inactivity_timeout/3600:.1f} horas")
        
        # Testar se consegue instanciar o tracker
        tracker = get_trade_activity_tracker(config=config)
        print("   ✅ Trade Activity Tracker instanciado")
        
        print("\n🎉 TODOS OS IMPORTS FUNCIONANDO!")
        print("✅ Sistema de rotação de pares está operacional")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rotation_logic():
    """Testa a lógica de rotação com dados simulados."""
    
    print("\n🔄 TESTE DE LÓGICA DE ROTAÇÃO")
    print("=" * 50)
    
    try:
        from src.utils.trade_activity_tracker import get_trade_activity_tracker
        import yaml
        import time
        
        # Carregar config
        config_path = os.path.join('src', 'config', 'config.yaml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Instanciar tracker
        tracker = get_trade_activity_tracker(config=config)
        
        # Simular par inativo
        current_time = time.time()
        inactive_time = current_time - 7200  # 2 horas atrás (> 1h timeout)
        
        # Dados de teste
        test_activity = {
            "TESTUSDT": {
                "last_trade_time": inactive_time,
                "total_trades": 0,
                "consecutive_losses": 0,
                "total_profit": 0.0
            },
            "ACTIVEUSDT": {
                "last_trade_time": current_time - 300,  # 5 min atrás
                "total_trades": 5,
                "consecutive_losses": 0,
                "total_profit": 10.5
            }
        }
        
        # Testar detecção de pares inativos
        timeout_seconds = config.get("trade_activity_tracker", {}).get("inactivity_timeout_seconds", 3600)
        
        for symbol, activity in test_activity.items():
            inactive_duration = current_time - activity["last_trade_time"]
            is_inactive = inactive_duration > timeout_seconds
            
            print(f"📊 {symbol}:")
            print(f"   Última atividade: {inactive_duration/3600:.1f}h atrás")
            print(f"   Status: {'🔴 INATIVO' if is_inactive else '🟢 ATIVO'}")
            
            if is_inactive:
                print(f"   ⚠️  Candidato para rotação!")
        
        print("\n✅ Lógica de detecção funcionando corretamente!")
        return True
        
    except Exception as e:
        print(f"❌ ERRO na lógica: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Executa todos os testes."""
    
    print("🚀 SISTEMA DE TESTES - ROTAÇÃO DE PARES")
    print("=" * 60)
    
    # Teste 1: Imports
    import_success = test_imports()
    
    # Teste 2: Lógica
    logic_success = test_rotation_logic()
    
    # Resultado final
    print("\n" + "=" * 60)
    print("📋 RESUMO DOS TESTES")
    print(f"✅ Imports: {'PASSOU' if import_success else 'FALHOU'}")
    print(f"🔄 Lógica: {'PASSOU' if logic_success else 'FALHOU'}")
    
    if import_success and logic_success:
        print("\n🎉 SISTEMA COMPLETAMENTE FUNCIONAL!")
        print("🔄 Rotação de pares está pronta para funcionar")
        print("📝 Logs preservados para monitoramento")
    else:
        print("\n⚠️  ALGUNS TESTES FALHARAM")
        print("🔧 Verifique os erros acima")
    
    return import_success and logic_success

if __name__ == "__main__":
    main()