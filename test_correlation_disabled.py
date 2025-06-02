#!/usr/bin/env python3
"""
Teste para verificar se a correlação BTC está desabilitada e se isso resolve
o problema de execução de ordens.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.grid_logic import GridLogic
from utils.api_client import APIClient
import yaml
import time

def test_correlation_status():
    """Testa se a correlação BTC está desabilitada"""
    
    # Carregar configuração
    config_path = os.path.join(os.path.dirname(__file__), "src", "config", "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    print("=== TESTE: Status da Correlação BTC ===")
    
    # Configuração de teste simples
    test_config = {
        "initial_levels": 5,
        "initial_spacing_perc": "0.005",
        "market_type": "spot"
    }
    
    # Cliente mock (modo shadow)
    api_config = {"key": "test", "secret": "test"}
    client = APIClient(api_config, operation_mode="shadow")
    
    try:
        # Criar instância do GridLogic
        grid = GridLogic(
            symbol="ETHUSDT",
            config=test_config,
            api_client=client,
            operation_mode="shadow",
            market_type="spot"
        )
        
        # Verificar status da correlação
        print(f"Correlação habilitada: {grid.correlation_enabled}")
        print(f"Analisador de correlação: {grid.correlation_analyzer}")
        
        if not grid.correlation_enabled:
            print("✅ SUCESSO: Correlação BTC está desabilitada como esperado")
            return True
        else:
            print("❌ ERRO: Correlação BTC ainda está habilitada!")
            return False
            
    except Exception as e:
        print(f"❌ ERRO durante teste: {e}")
        return False

def test_grid_initialization():
    """Testa se o grid inicializa corretamente sem correlação"""
    
    config_path = os.path.join(os.path.dirname(__file__), "src", "config", "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    print("\n=== TESTE: Inicialização do Grid ===")
    
    test_config = {
        "initial_levels": 5,
        "initial_spacing_perc": "0.005",
        "market_type": "spot",
        "grid": {
            "initial_levels": 5,
            "initial_spacing_perc": "0.005"
        },
        "trading": {
            "capital_per_pair_usd": "100"
        }
    }
    
    api_config = {"key": "test", "secret": "test"}
    client = APIClient(api_config, operation_mode="shadow")
    
    try:
        grid = GridLogic(
            symbol="ETHUSDT",
            config=test_config,
            api_client=client,
            operation_mode="shadow",
            market_type="spot"
        )
        
        print(f"Grid inicializado: ✅")
        print(f"Modo: {grid.operation_mode}")
        print(f"Símbolo: {grid.symbol}")
        print(f"Níveis configurados: {grid.num_levels}")
        print(f"Espaçamento base: {grid.base_spacing_percentage}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO na inicialização: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testando estado da correlação BTC após desabilitação...")
    
    correlation_test = test_correlation_status()
    grid_test = test_grid_initialization()
    
    print(f"\n=== RESULTADOS ===")
    print(f"Teste correlação: {'✅ PASSOU' if correlation_test else '❌ FALHOU'}")
    print(f"Teste grid: {'✅ PASSOU' if grid_test else '❌ FALHOU'}")
    
    if correlation_test and grid_test:
        print("\n🎉 SUCESSO: Sistema está funcionando com correlação desabilitada!")
        print("O problema de execução de ordens pode ter sido resolvido.")
    else:
        print("\n❌ ERRO: Ainda há problemas no sistema.")