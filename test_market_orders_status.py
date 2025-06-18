#!/usr/bin/env python3
"""
Teste simples para verificar se o sistema está usando ordens de mercado
"""
import sys
import os
import yaml

# Adicionar o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_market_orders_config():
    """Testa a configuração de ordens de mercado"""
    
    # Carregar configuração
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    
    print(f"🔍 Carregando configuração de: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        print("✅ Configuração carregada com sucesso")
        
        # Verificar configuração de market_orders
        market_orders_config = config.get('market_orders', {})
        
        print("\n📊 CONFIGURAÇÃO DE ORDENS DE MERCADO:")
        print("=" * 50)
        print(f"Enabled: {market_orders_config.get('enabled', False)}")
        print(f"Max Slippage: {market_orders_config.get('max_slippage_percentage', 'N/A')}%")
        print(f"Max Order Size: {market_orders_config.get('max_order_size_percentage', 'N/A')}%")
        print(f"Pre-execution Check: {market_orders_config.get('enable_pre_execution_check', 'N/A')}")
        print(f"Position Size Multiplier: {market_orders_config.get('reduced_position_size_multiplier', 'N/A')}")
        print(f"Grid Spacing Multiplier: {market_orders_config.get('reduced_grid_spacing_multiplier', 'N/A')}")
        print(f"Min Capital: ${market_orders_config.get('min_capital_for_market_orders', 'N/A')}")
        
        urgency_levels = market_orders_config.get('urgency_levels', {})
        print(f"\n🎯 NÍVEIS DE URGÊNCIA:")
        for level, value in urgency_levels.items():
            print(f"  {level.upper()}: {value}%")
        
        # Verificar se está habilitado
        if market_orders_config.get('enabled', False):
            print("\n✅ ORDENS DE MERCADO ESTÃO HABILITADAS")
        else:
            print("\n❌ ORDENS DE MERCADO ESTÃO DESABILITADAS")
            
        return market_orders_config.get('enabled', False)
        
    except Exception as e:
        print(f"❌ Erro ao carregar configuração: {e}")
        return False

def test_market_order_manager():
    """Testa a inicialização do Market Order Manager"""
    try:
        from utils.market_order_manager import MarketOrderManager, SlippageMonitor, MarketDepthAnalyzer
        print("\n✅ Market Order Manager importado com sucesso")
        
        # Teste básico do SlippageMonitor
        monitor = SlippageMonitor("TESTUSDT", 0.15)
        print(f"✅ SlippageMonitor criado para TESTUSDT com max slippage 0.15%")
        
        # Teste de statistics
        stats = monitor.get_statistics()
        print(f"✅ Estatísticas: {stats}")
        
        return True
    except Exception as e:
        print(f"❌ Erro ao importar Market Order Manager: {e}")
        return False

def simulate_grid_logic_initialization():
    """Simula a inicialização do GridLogic com Market Orders"""
    try:
        # Carregar configuração
        config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        print("\n🧪 SIMULANDO INICIALIZAÇÃO DO GRIDLOGIC:")
        print("=" * 50)
        
        # Simular verificação no GridLogic
        market_order_config = config.get("market_orders", {})
        
        if market_order_config.get("enabled", True):
            print("✅ Market Order Manager seria inicializado")
            
            # Simular ajustes de risco
            position_multiplier = market_order_config.get("reduced_position_size_multiplier", 0.7)
            spacing_multiplier = market_order_config.get("reduced_grid_spacing_multiplier", 0.8)
            min_capital = market_order_config.get("min_capital_for_market_orders", 50.0)
            
            print(f"✅ Multiplicador de posição: {position_multiplier}")
            print(f"✅ Multiplicador de espaçamento: {spacing_multiplier}")
            print(f"✅ Capital mínimo: ${min_capital}")
            
            # Simular decisão de uso de ordens de mercado
            test_order_value = 75.0  # $75
            
            if test_order_value >= min_capital:
                print(f"✅ Ordem de ${test_order_value} seria executada como MERCADO")
            else:
                print(f"⚠️ Ordem de ${test_order_value} seria executada como LIMITE (capital insuficiente)")
        else:
            print("❌ Market Order Manager seria desabilitado")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro na simulação: {e}")
        return False

def check_system_status():
    """Verifica o status geral do sistema"""
    print("\n🔍 VERIFICANDO STATUS DO SISTEMA:")
    print("=" * 50)
    
    # Verificar se há logs recentes
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if os.path.exists(logs_dir):
        latest_log = os.path.join(logs_dir, 'latest.log')
        if os.path.exists(latest_log):
            print(f"✅ Log mais recente encontrado: {latest_log}")
            
            # Ler últimas linhas
            try:
                with open(latest_log, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_lines = lines[-5:]
                        print("📄 Últimas 5 linhas do log:")
                        for line in last_lines:
                            print(f"  {line.strip()}")
                    else:
                        print("⚠️ Log está vazio")
            except Exception as e:
                print(f"❌ Erro ao ler log: {e}")
        else:
            print("⚠️ Arquivo latest.log não encontrado")
    else:
        print("⚠️ Diretório de logs não encontrado")

def main():
    """Função principal de teste"""
    print("🚀 TESTE DO SISTEMA DE ORDENS DE MERCADO")
    print("=" * 60)
    
    # Teste 1: Configuração
    config_ok = test_market_orders_config()
    
    # Teste 2: Importação de módulos
    modules_ok = test_market_order_manager()
    
    # Teste 3: Simulação de inicialização
    simulation_ok = simulate_grid_logic_initialization()
    
    # Teste 4: Status do sistema
    check_system_status()
    
    # Resultado final
    print("\n" + "=" * 60)
    print("📊 RESULTADO DOS TESTES:")
    print(f"✅ Configuração: {'OK' if config_ok else 'FALHA'}")
    print(f"✅ Módulos: {'OK' if modules_ok else 'FALHA'}")
    print(f"✅ Simulação: {'OK' if simulation_ok else 'FALHA'}")
    
    if config_ok and modules_ok and simulation_ok:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("💡 O sistema ESTÁ CONFIGURADO para usar ordens de mercado")
        
        if not config_ok:
            print("\n⚠️ PROBLEMA DETECTADO:")
            print("  - Ordens de mercado podem estar desabilitadas na configuração")
            print("  - Verifique o arquivo src/config/config.yaml")
        
    else:
        print("\n❌ ALGUNS TESTES FALHARAM")
        print("💡 Verifique os erros acima para diagnosticar o problema")

if __name__ == "__main__":
    main()

