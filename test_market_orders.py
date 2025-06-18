#!/usr/bin/env python3
"""
Script de teste para sistema de ordens de mercado com controle de slippage
"""

import os
import sys
import yaml
import logging
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.api_client import APIClient
from src.utils.market_order_manager import MarketOrderManager, SlippageMonitor, MarketDepthAnalyzer
from src.utils.logger import setup_logger

# Setup logging
log = setup_logger("test_market_orders")

def load_config():
    """Carrega configuração do arquivo YAML."""
    config_path = os.path.join(os.path.dirname(__file__), "src", "config", "config.yaml")
    
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    
    # Load environment variables
    config['api']['key'] = os.getenv('BINANCE_API_KEY')
    config['api']['secret'] = os.getenv('BINANCE_API_SECRET')
    
    return config

def test_slippage_monitor():
    """Testa o monitor de slippage."""
    log.info("=== Testando SlippageMonitor ===")
    
    monitor = SlippageMonitor("BTCUSDT", max_slippage_percentage=0.15)
    
    # Simular algumas ordens com slippage
    test_orders = [
        {"expected": Decimal("50000"), "executed": Decimal("50007.5"), "quantity": Decimal("0.001")},  # 0.015% slippage
        {"expected": Decimal("50000"), "executed": Decimal("50025"), "quantity": Decimal("0.002")},     # 0.05% slippage
        {"expected": Decimal("50000"), "executed": Decimal("50100"), "quantity": Decimal("0.001")},     # 0.2% slippage (alto)
        {"expected": Decimal("50000"), "executed": Decimal("50005"), "quantity": Decimal("0.003")},     # 0.01% slippage
    ]
    
    for order in test_orders:
        slippage_data = monitor.calculate_slippage(
            order["expected"], order["executed"], order["quantity"]
        )
        log.info(f"Slippage: {slippage_data['slippage_percentage']:.3f}% "
                f"(Custo: ${slippage_data['slippage_cost_usdt']:.4f})")
    
    # Verificar estatísticas
    stats = monitor.get_statistics()
    log.info(f"Estatísticas finais: {stats}")
    
    # Testar verificação de slippage aceitável
    current_price = Decimal("50000")
    acceptable = monitor.is_slippage_acceptable(current_price, Decimal("50100"))
    log.info(f"Slippage de 0.2% é aceitável: {acceptable}")

def test_market_depth_analyzer(api_client):
    """Testa o analisador de profundidade de mercado."""
    log.info("=== Testando MarketDepthAnalyzer ===")
    
    analyzer = MarketDepthAnalyzer(api_client)
    
    # Testar com um símbolo real
    symbol = "ADAUSDT"
    quantity = Decimal("100")
    
    # Analisar para ordem de compra
    log.info(f"Analisando profundidade para ordem BUY de {quantity} {symbol}")
    buy_analysis = analyzer.analyze_market_depth(symbol, quantity, "BUY")
    
    if "error" not in buy_analysis:
        log.info(f"Análise BUY: Impacto no preço: {buy_analysis.get('price_impact', 0):.3f}%")
        log.info(f"Liquidez suficiente: {buy_analysis.get('liquidity_sufficient', False)}")
        log.info(f"Melhor preço: ${buy_analysis.get('best_price', 0)}")
    else:
        log.warning(f"Erro na análise BUY: {buy_analysis['error']}")
    
    # Analisar para ordem de venda
    log.info(f"Analisando profundidade para ordem SELL de {quantity} {symbol}")
    sell_analysis = analyzer.analyze_market_depth(symbol, quantity, "SELL")
    
    if "error" not in sell_analysis:
        log.info(f"Análise SELL: Impacto no preço: {sell_analysis.get('price_impact', 0):.3f}%")
        log.info(f"Liquidez suficiente: {sell_analysis.get('liquidity_sufficient', False)}")
        log.info(f"Melhor preço: ${sell_analysis.get('best_price', 0)}")
    else:
        log.warning(f"Erro na análise SELL: {sell_analysis['error']}")

def test_market_order_manager(api_client, config):
    """Testa o gerenciador de ordens de mercado."""
    log.info("=== Testando MarketOrderManager ===")
    
    # Configurar para testnet se estiver usando
    manager = MarketOrderManager(api_client, config)
    
    symbol = "ADAUSDT"
    
    # Testar se deve usar ordem de mercado
    should_use = manager.should_use_market_order(symbol, "normal")
    log.info(f"Deve usar ordem de mercado para {symbol}: {should_use}")
    
    # Testar diferentes níveis de urgência
    urgency_levels = ["low", "normal", "high", "critical"]
    for urgency in urgency_levels:
        should_use = manager.should_use_market_order(symbol, urgency)
        log.info(f"Urgência {urgency}: usar mercado = {should_use}")
    
    # Obter estatísticas
    stats = manager.get_statistics()
    log.info(f"Estatísticas do manager: {stats}")
    
    # Testar otimização de parâmetros
    optimization = manager.optimize_parameters(symbol)
    log.info(f"Otimização para {symbol}: {optimization}")
    
    # AVISO: Não executar ordens reais em modo de teste
    log.warning("AVISO: Não executando ordens reais no modo de teste")
    
    # Simular colocação de ordem (sem executar)
    log.info("Simulando colocação de ordem de mercado...")
    # order_result = manager.place_market_order_with_slippage_control(
    #     symbol=symbol,
    #     side="BUY",
    #     quantity="10",
    #     market_type="futures"
    # )

def test_grid_integration(config):
    """Testa integração com GridLogic."""
    log.info("=== Testando integração com GridLogic ===")
    
    try:
        from src.core.grid_logic import GridLogic
        from src.utils.api_client import APIClient
        
        # Criar API client
        api_client = APIClient(config)
        
        # Criar GridLogic com ordens de mercado habilitadas
        grid = GridLogic(
            symbol="ADAUSDT",
            config=config,
            api_client=api_client,
            operation_mode="shadow",  # Modo de teste
            market_type="futures"
        )
        
        # Verificar se market order manager foi inicializado
        if grid.market_order_manager:
            log.info("✅ MarketOrderManager inicializado no GridLogic")
            
            # Verificar configuração
            market_config = grid.get_market_order_config()
            log.info(f"Configuração de ordens de mercado: {market_config}")
            
            # Verificar estatísticas
            stats = grid.get_slippage_statistics()
            log.info(f"Estatísticas de slippage: {stats}")
            
            # Testar otimização
            optimization = grid.optimize_market_order_parameters()
            log.info(f"Otimização de parâmetros: {optimization}")
            
        else:
            log.error("❌ MarketOrderManager não foi inicializado")
        
    except Exception as e:
        log.error(f"Erro na integração com GridLogic: {e}")

def main():
    """Função principal de teste."""
    log.info("🚀 Iniciando testes do sistema de ordens de mercado")
    
    try:
        # Carregar configuração
        config = load_config()
        
        # Verificar se as chaves da API estão configuradas
        if not config['api']['key'] or not config['api']['secret']:
            log.error("❌ Chaves da API não configuradas. Configure BINANCE_API_KEY e BINANCE_API_SECRET")
            sys.exit(1)
        
        # Criar API client
        api_client = APIClient(config)
        
        # Executar testes
        test_slippage_monitor()
        test_market_depth_analyzer(api_client)
        test_market_order_manager(api_client, config)
        test_grid_integration(config)
        
        log.info("✅ Todos os testes concluídos com sucesso!")
        
    except Exception as e:
        log.error(f"❌ Erro durante os testes: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

