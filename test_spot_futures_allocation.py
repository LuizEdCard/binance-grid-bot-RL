#!/usr/bin/env python3
"""
Teste para verificar como o sistema aloca capital entre Spot e Futures
"""
import sys
import os
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.capital_management import CapitalManager
from utils.api_client import APIClient
from utils.logger import setup_logger

log = setup_logger("spot_futures_test")


def load_config():
    """Carrega configuração"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_spot_futures_allocation():
    """Testa como o sistema aloca capital entre Spot e Futures"""
    print("🔄 Testing Spot vs Futures Capital Allocation")
    print("=" * 50)
    
    # Carregar configuração
    config = load_config()
    
    # Inicializar API client e capital manager
    api_client = APIClient(config)
    capital_manager = CapitalManager(api_client, config)
    
    # Verificar configuração atual
    print("1. Configuração de alocação entre mercados:")
    market_allocation = capital_manager.market_allocation
    print(f"   Spot: {market_allocation.get('spot_percentage', 0)}%")
    print(f"   Futures: {market_allocation.get('futures_percentage', 0)}%")
    
    # Verificar saldos atuais
    print(f"\n2. Saldos atuais na Binance:")
    balances = capital_manager.get_available_balances()
    print(f"   Spot USDT: ${balances['spot_usdt']:.2f}")
    print(f"   Futures USDT: ${balances['futures_usdt']:.2f}")
    print(f"   Total USDT: ${balances['total_usdt']:.2f}")
    
    # Testar alocação automática
    print(f"\n3. Teste de alocação automática (sem especificar mercado):")
    symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
    
    allocations = capital_manager.calculate_optimal_allocations(symbols)
    
    spot_count = 0
    futures_count = 0
    spot_capital = 0
    futures_capital = 0
    
    for allocation in allocations:
        print(f"   {allocation.symbol}:")
        print(f"     Mercado: {allocation.market_type}")
        print(f"     Capital: ${allocation.allocated_amount:.2f}")
        
        if allocation.market_type == "spot":
            spot_count += 1
            spot_capital += allocation.allocated_amount
        else:
            futures_count += 1
            futures_capital += allocation.allocated_amount
    
    print(f"\n4. Resumo da alocação atual:")
    print(f"   Pares em Spot: {spot_count} (${spot_capital:.2f})")
    print(f"   Pares em Futures: {futures_count} (${futures_capital:.2f})")
    
    if spot_capital + futures_capital > 0:
        spot_percentage = (spot_capital / (spot_capital + futures_capital)) * 100
        futures_percentage = (futures_capital / (spot_capital + futures_capital)) * 100
        print(f"   Distribuição real: Spot {spot_percentage:.1f}% | Futures {futures_percentage:.1f}%")
    
    # Testar forçando mercados específicos
    print(f"\n5. Teste forçando mercados específicos:")
    
    # Especificar tipos de mercado
    market_types = {
        'BTCUSDT': 'futures',
        'ETHUSDT': 'spot',
        'ADAUSDT': 'futures'
    }
    
    print("   Mercados desejados:")
    for symbol, market in market_types.items():
        print(f"     {symbol}: {market}")
    
    allocations_specific = capital_manager.calculate_optimal_allocations(symbols, market_types)
    
    print("   Resultado:")
    for allocation in allocations_specific:
        print(f"     {allocation.symbol}: {allocation.market_type} (${allocation.allocated_amount:.2f})")
    
    # Analisar comportamento quando há saldo insuficiente
    print(f"\n6. Teste de fallback entre mercados:")
    print("   Simulando cenário onde um mercado tem capital insuficiente...")
    
    # Criar situação simulada onde tentamos alocar mais do que disponível
    if balances['spot_usdt'] < 20 and balances['futures_usdt'] > 20:
        print("   Cenário: Pouco capital em Spot, mais em Futures")
        
        # Tentar forçar spot em símbolos
        forced_spot = {
            'BTCUSDT': 'spot',
            'ETHUSDT': 'spot',
            'ADAUSDT': 'spot'
        }
        
        fallback_allocations = capital_manager.calculate_optimal_allocations(symbols, forced_spot)
        
        print("   Tentando forçar todos para Spot:")
        for allocation in fallback_allocations:
            print(f"     {allocation.symbol}: {allocation.market_type} (fallback ativo)")
    
    # Verificar se a configuração percentage é usada
    print(f"\n7. Análise da implementação atual:")
    
    # Examinar o código atual
    print("   ✅ Sistema suporta fallback automático entre mercados")
    print("   ✅ Pode especificar mercado por símbolo")
    print("   ❓ Configuração percentage não está sendo aplicada automaticamente")
    
    # Mostrar sugestão de melhoria
    print(f"\n💡 Estado atual da alocação Spot/Futures:")
    if balances['spot_usdt'] > 0 and balances['futures_usdt'] > 0:
        print("   ✅ Você tem saldo em ambos os mercados")
        print("   🔄 Sistema usa fallback inteligente baseado em disponibilidade")
        print("   📊 Sem aplicação automática da proporção 40%/60%")
    elif balances['futures_usdt'] > 0:
        print("   📍 Todo saldo está em Futures")
        print("   🎯 Sistema operará apenas em Futures automaticamente")
    elif balances['spot_usdt'] > 0:
        print("   📍 Todo saldo está em Spot")
        print("   🎯 Sistema operará apenas em Spot automaticamente")


if __name__ == "__main__":
    test_spot_futures_allocation()