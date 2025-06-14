#!/usr/bin/env python3
"""
Teste do sistema com dependências limpas
"""

import sys
import subprocess
import importlib
from pathlib import Path

def test_essential_imports():
    """Testa se todas as dependências essenciais podem ser importadas."""
    
    print("🧪 TESTANDO IMPORTS ESSENCIAIS")
    print("=" * 50)
    
    essential_modules = [
        ('numpy', 'np'),
        ('pandas', 'pd'), 
        ('yaml', None),
        ('dotenv', None),
        ('aiohttp', None),
        ('requests', None),
        ('binance', None),
        # ('tensorflow', 'tf'),  # REMOVIDO - RL desabilitado
        # ('gymnasium', 'gym'),  # REMOVIDO - RL desabilitado
        ('xgboost', 'xgb'),
        ('talib', None),
        # ('pandas_ta', None),  # Removed due to compatibility issues
        ('praw', None),
        ('telegram', None),
        ('flask', None),
        ('flask_cors', None),
        ('psutil', None)
    ]
    
    results = {}
    
    for module_name, alias in essential_modules:
        try:
            if alias:
                exec(f"import {module_name} as {alias}")
            else:
                exec(f"import {module_name}")
            
            print(f"   ✅ {module_name}")
            results[module_name] = True
            
        except ImportError as e:
            print(f"   ❌ {module_name} - {e}")
            results[module_name] = False
        except Exception as e:
            print(f"   ⚠️ {module_name} - {e}")
            results[module_name] = False
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n📊 RESULTADO: {success_count}/{total_count} imports bem-sucedidos")
    
    if success_count == total_count:
        print("🎉 TODOS OS IMPORTS ESSENCIAIS FUNCIONANDO!")
        return True
    else:
        print("⚠️ ALGUNS IMPORTS FALHARAM")
        return False

def test_core_functionality():
    """Testa funcionalidades core do sistema."""
    
    print("\n🔧 TESTANDO FUNCIONALIDADES CORE")
    print("=" * 50)
    
    try:
        print("1. 📊 Testando carregamento de config...")
        import yaml
        config = yaml.safe_load(open('src/config/config.yaml'))
        print(f"   ✅ Config carregada: {len(config)} seções")
        
        print("2. 🌐 Testando APIClient...")
        sys.path.append('src')
        from utils.api_client import APIClient
        api = APIClient(config)
        print(f"   ✅ APIClient inicializado em modo {api.operation_mode}")
        
        print("3. 🎯 Testando PairSelector...")
        from core.pair_selector import PairSelector
        pair_selector = PairSelector(config, api)
        pairs = pair_selector.get_selected_pairs()
        print(f"   ✅ PairSelector funcionando: {len(pairs)} pares selecionados")
        
        print("4. 💰 Testando CapitalManager...")
        from core.capital_management import CapitalManager
        capital_manager = CapitalManager(api, config)
        balances = capital_manager.get_available_balances()
        print(f"   ✅ CapitalManager funcionando: ${balances['total_usdt']:.2f} total")
        
        print("5. 🛡️ Testando RiskAgent...")
        from agents.risk_agent import RiskAgent
        from utils.alerter import Alerter
        alerter = Alerter(api)
        risk_agent = RiskAgent(config, api, alerter)
        print(f"   ✅ RiskAgent inicializado")
        
        print("6. 🤖 Testando AIAgent...")
        from agents.ai_agent import AIAgent
        ai_agent = AIAgent(config)
        print(f"   ✅ AIAgent inicializado, disponível: {ai_agent.is_available}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_bot_instantiation():
    """Testa se o MultiAgentBot pode ser instanciado."""
    
    print("\n🤖 TESTANDO INSTANCIAÇÃO DO BOT")
    print("=" * 50)
    
    try:
        sys.path.append('src')
        from multi_agent_bot import MultiAgentTradingBot
        
        print("   🔄 Criando MultiAgentTradingBot...")
        bot = MultiAgentTradingBot()
        
        print(f"   ✅ Bot criado com sucesso!")
        print(f"   📊 Modo de operação: {bot.operation_mode}")
        print(f"   🔌 API conectada: {type(bot.api_client).__name__}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_unused_packages():
    """Verifica se ainda há pacotes não utilizados instalados."""
    
    print("\n🔍 VERIFICANDO PACOTES DESNECESSÁRIOS")
    print("=" * 50)
    
    # Pacotes que foram identificados como não utilizados
    potentially_unused = [
        'asyncio-throttle',
        'stable-baselines3', 
        'transformers',
        'torch',
        'tensorflow',
        'gymnasium',
        'lz4',
        'msgpack',
        'sqlalchemy',
        'cryptography',
        'rich',
        'tqdm',
        'redis',
        'prometheus-client',
        'plotly',
        'ccxt'
    ]
    
    installed_unused = []
    
    for package in potentially_unused:
        try:
            importlib.import_module(package.replace('-', '_'))
            installed_unused.append(package)
        except ImportError:
            pass
    
    if installed_unused:
        print(f"⚠️ Pacotes desnecessários ainda instalados:")
        for package in installed_unused:
            print(f"   📦 {package}")
        
        print(f"\n💡 Para remover:")
        print(f"   pip uninstall {' '.join(installed_unused)}")
        
        return False
    else:
        print("✅ Nenhum pacote desnecessário detectado")
        return True

def main():
    print("🧹 TESTE COMPLETO: DEPENDÊNCIAS LIMPAS")
    print("=" * 60)
    
    # Executar todos os testes
    test1 = test_essential_imports()
    test2 = test_core_functionality() 
    test3 = test_bot_instantiation()
    test4 = check_unused_packages()
    
    print(f"\n📊 RESUMO DOS TESTES:")
    print(f"   1. Imports essenciais: {'✅' if test1 else '❌'}")
    print(f"   2. Funcionalidades core: {'✅' if test2 else '❌'}")
    print(f"   3. Instanciação do bot: {'✅' if test3 else '❌'}")
    print(f"   4. Verificação de pacotes desnecessários: {'✅' if test4 else '⚠️'}")
    
    if test1 and test2 and test3:
        print(f"\n🎉 SISTEMA FUNCIONANDO COM DEPENDÊNCIAS LIMPAS!")
        print(f"💾 Economia estimada: ~70% menos dependências")
        print(f"🚀 Sistema mais leve e rápido para deploy")
        
        if not test4:
            print(f"\n💡 Considere remover pacotes desnecessários para otimização máxima")
        
        print(f"\n✅ PRÓXIMO PASSO:")
        print(f"   cp requirements_multi_agent_clean.txt requirements_multi_agent.txt")
        
    else:
        print(f"\n❌ ALGUNS TESTES FALHARAM - VERIFICAR DEPENDÊNCIAS")

if __name__ == "__main__":
    main()