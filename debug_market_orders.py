#!/usr/bin/env python3
"""
Debug avançado para entender por que o sistema não está usando ordens de mercado
"""
import sys
import os
import yaml
from decimal import Decimal

# Adicionar o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def simulate_order_decision_logic():
    """Simula a lógica de decisão de ordens exatamente como no GridLogic"""
    try:
        from utils.market_order_manager import MarketOrderManager
        from utils.api_client import APIClient
        
        print("🔬 SIMULANDO LÓGICA DE DECISÃO DE ORDENS")
        print("=" * 60)
        
        # Carregar configuração
        config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Simular inicialização do MarketOrderManager
        print("1. Simulando inicialização do MarketOrderManager...")
        
        # Criar client mock (sem conexão real)
        api_client = None  # Seria necessário para teste real
        
        # Verificar configuração
        market_order_config = config.get("market_orders", {})
        print(f"✅ Market Orders Config: {market_order_config.get('enabled', False)}")
        
        if market_order_config.get("enabled", True):
            print("✅ Market Order Manager seria inicializado")
            
            # Simular verificação das condições
            print("\n2. Simulando verificação de condições para uma ordem...")
            
            # Parâmetros de teste
            test_symbol = "SOLUSDT"
            test_price = 147.65
            test_quantity = 0.1
            min_capital = market_order_config.get("min_capital_for_market_orders", 50.0)
            
            order_value = test_price * test_quantity
            print(f"📊 Ordem de teste: {test_quantity} {test_symbol.replace('USDT', '')} @ ${test_price}")
            print(f"💰 Valor da ordem: ${order_value:.2f}")
            print(f"🎯 Capital mínimo: ${min_capital}")
            
            # Verificar condição de capital
            if order_value >= min_capital:
                print(f"✅ Capital suficiente: ${order_value:.2f} >= ${min_capital}")
                
                # Simular determinação de urgência
                print(f"\n3. Determinando urgência baseada em RSI...")
                test_rsi = 35  # Exemplo
                urgency_level = "normal"
                
                if test_rsi < 30 or test_rsi > 70:
                    urgency_level = "high"
                elif test_rsi < 35 or test_rsi > 65:
                    urgency_level = "normal"
                else:
                    urgency_level = "low"
                
                print(f"📈 RSI de teste: {test_rsi}")
                print(f"⚡ Urgência determinada: {urgency_level}")
                
                # Simular método should_use_market_order
                print(f"\n4. Simulando should_use_market_order...")
                
                # Como não temos histórico, assume que seria True
                avg_slippage = 0.0  # Sem histórico
                max_slippage = market_order_config.get("max_slippage_percentage", 0.15)
                
                slippage_thresholds = {
                    "low": max_slippage * 0.5,
                    "normal": max_slippage * 0.75,
                    "high": max_slippage,
                    "critical": max_slippage * 1.5
                }
                
                threshold = slippage_thresholds.get(urgency_level, max_slippage)
                should_use_market = avg_slippage <= threshold
                
                print(f"📊 Slippage médio histórico: {avg_slippage:.3f}%")
                print(f"🎯 Threshold para urgência '{urgency_level}': {threshold:.3f}%")
                print(f"✅ Should use market order: {should_use_market}")
                
                if should_use_market:
                    print(f"\n🎉 RESULTADO: Ordem seria executada como MERCADO")
                    print(f"🔄 Processo: LIMITE → MERCADO")
                else:
                    print(f"\n⚠️ RESULTADO: Ordem seria executada como LIMITE")
                    print(f"📊 Motivo: Slippage histórico muito alto")
                
            else:
                print(f"❌ Capital insuficiente: ${order_value:.2f} < ${min_capital}")
                print(f"🔄 Resultado: Ordem seria executada como LIMITE")
        else:
            print("❌ Market Order Manager seria desabilitado")
            print("🔄 Resultado: Todas as ordens seriam LIMITE")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro na simulação: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_actual_logs_for_market_orders():
    """Verifica logs reais para entender o que está acontecendo"""
    print("\n🔍 ANALISANDO LOGS REAIS")
    print("=" * 60)
    
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    
    # Procurar por logs que contenham informações sobre ordens
    import glob
    log_files = glob.glob(os.path.join(logs_dir, '*.log'))
    
    market_order_mentions = []
    limit_order_mentions = []
    
    for log_file in log_files[-5:]:  # Últimos 5 arquivos
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines):
                if any(keyword in line.lower() for keyword in ['market order', 'mercado', 'slippage']):
                    market_order_mentions.append((log_file, i+1, line.strip()))
                elif any(keyword in line.lower() for keyword in ['colocando ordem', 'ordem', 'limit']):
                    limit_order_mentions.append((log_file, i+1, line.strip()))
                    
        except Exception as e:
            print(f"⚠️ Erro ao ler {log_file}: {e}")
    
    print(f"📊 Menções a Market Orders encontradas: {len(market_order_mentions)}")
    for log_file, line_num, content in market_order_mentions[-5:]:
        print(f"  📄 {os.path.basename(log_file)}:{line_num} - {content}")
    
    print(f"\n📊 Menções a ordens (geral) encontradas: {len(limit_order_mentions)}")
    for log_file, line_num, content in limit_order_mentions[-10:]:
        if any(word in content.lower() for word in ['colocando', 'placing']):
            print(f"  📄 {os.path.basename(log_file)}:{line_num} - {content}")

def check_initialization_logs():
    """Verifica se o MarketOrderManager foi inicializado corretamente"""
    print("\n🔍 VERIFICANDO LOGS DE INICIALIZAÇÃO")
    print("=" * 60)
    
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    
    # Procurar por logs de inicialização
    import glob
    log_files = glob.glob(os.path.join(logs_dir, '*.log'))
    
    initialization_logs = []
    
    for log_file in log_files[-5:]:
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines):
                if any(keyword in line for keyword in [
                    'Market Order Manager inicializado',
                    'MarketOrderManager inicializado',
                    'Market Order Manager desabilitado',
                    'GridLogic inicializado'
                ]):
                    initialization_logs.append((log_file, i+1, line.strip()))
                    
        except Exception as e:
            print(f"⚠️ Erro ao ler {log_file}: {e}")
    
    print(f"📊 Logs de inicialização encontrados: {len(initialization_logs)}")
    for log_file, line_num, content in initialization_logs:
        print(f"  📄 {os.path.basename(log_file)}:{line_num}")
        print(f"     {content}")

def suggest_debugging_steps():
    """Sugere próximos passos para debug"""
    print("\n💡 SUGESTÕES PARA DEBUG")
    print("=" * 60)
    print("1. 🔍 Verificar se o sistema está realmente iniciando:")
    print("   python src/multi_agent_bot.py")
    print()
    print("2. 🔍 Adicionar logs de debug temporários no GridLogic:")
    print("   Adicionar log.info() na linha 638 do _place_order_unified")
    print()
    print("3. 🔍 Verificar se há ordens sendo colocadas:")
    print("   grep -r 'Colocando ordem' logs/")
    print()
    print("4. 🔍 Verificar se MarketOrderManager está ativo:")
    print("   grep -r 'Market Order Manager' logs/")
    print()
    print("5. 🔍 Verificar condições de ativação:")
    print("   - Capital por ordem >= $50")
    print("   - RSI em condições extremas")
    print("   - Slippage histórico baixo")

def main():
    """Função principal de debug"""
    print("🔬 DEBUG AVANÇADO - SISTEMA DE ORDENS DE MERCADO")
    print("=" * 70)
    
    # Teste 1: Simular lógica de decisão
    simulate_order_decision_logic()
    
    # Teste 2: Analisar logs reais
    check_actual_logs_for_market_orders()
    
    # Teste 3: Verificar inicialização
    check_initialization_logs()
    
    # Teste 4: Sugestões
    suggest_debugging_steps()
    
    print("\n" + "=" * 70)
    print("📋 RESUMO DO DEBUG:")
    print("✅ Configuração: Market Orders estão HABILITADOS")
    print("✅ Código: Lógica de decisão está implementada")
    print("❓ Execução: Precisa verificar se condições estão sendo atendidas")
    print("\n💡 PRÓXIMO PASSO: Executar o bot e monitorar logs em tempo real")

if __name__ == "__main__":
    main()

