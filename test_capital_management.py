#!/usr/bin/env python3
"""
Teste do sistema de gestão de capital
"""
import sys
import os
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.capital_management import CapitalManager
from utils.api_client import APIClient
from utils.logger import setup_logger

log = setup_logger("capital_test")


def load_config():
    """Carrega configuração"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_capital_management():
    """Testa o sistema de gestão de capital"""
    print("🏦 Testing Capital Management System")
    print("=" * 40)
    
    # Carregar configuração
    config = load_config()
    
    # Inicializar API client
    api_client = APIClient(config)
    
    # Inicializar capital manager
    capital_manager = CapitalManager(api_client, config)
    
    # 1. Testar obtenção de saldos
    print("1. Testing balance retrieval...")
    try:
        balances = capital_manager.get_available_balances()
        print(f"   ✅ Balances retrieved:")
        print(f"      Spot USDT: ${balances['spot_usdt']:.2f}")
        print(f"      Futures USDT: ${balances['futures_usdt']:.2f}")
        print(f"      Total USDT: ${balances['total_usdt']:.2f}")
        
        if balances['total_usdt'] < 5:
            print(f"   ⚠️  Warning: Low balance (${balances['total_usdt']:.2f})")
        
    except Exception as e:
        print(f"   ❌ Error getting balances: {e}")
        return
    
    # 2. Testar cálculo de alocações
    print(f"\n2. Testing capital allocation calculation...")
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT', 'SOLUSDT']
    
    try:
        allocations = capital_manager.calculate_optimal_allocations(test_symbols)
        
        print(f"   ✅ Calculated allocations for {len(allocations)} symbols:")
        total_allocated = 0
        
        for allocation in allocations:
            print(f"      {allocation.symbol}:")
            print(f"         Capital: ${allocation.allocated_amount:.2f}")
            print(f"         Market: {allocation.market_type}")
            print(f"         Grid levels: {allocation.grid_levels}")
            print(f"         Spacing: {allocation.spacing_percentage:.4f}")
            print(f"         Max position: ${allocation.max_position_size:.2f}")
            total_allocated += allocation.allocated_amount
        
        print(f"   📊 Total allocated: ${total_allocated:.2f}")
        print(f"   📊 Symbols trading: {len(allocations)} of {len(test_symbols)} requested")
        
        if len(allocations) < len(test_symbols):
            print(f"   ⚠️  Capital limited trading - some symbols excluded")
            
    except Exception as e:
        print(f"   ❌ Error calculating allocations: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. Testar verificação individual de símbolos
    print(f"\n3. Testing individual symbol validation...")
    test_symbol = 'BTCUSDT'
    required_capital = 5.0
    
    try:
        can_trade = capital_manager.can_trade_symbol(test_symbol, required_capital)
        print(f"   Can trade {test_symbol} with ${required_capital}: {'✅ Yes' if can_trade else '❌ No'}")
        
    except Exception as e:
        print(f"   ❌ Error checking symbol: {e}")
    
    # 4. Mostrar estatísticas
    print(f"\n4. Capital management statistics...")
    try:
        stats = capital_manager.get_statistics()
        print(f"   ✅ Statistics:")
        print(f"      Balance checks: {stats['balance_checks']}")
        print(f"      Allocation updates: {stats['allocation_updates']}")
        print(f"      Active allocations: {stats['number_of_active_allocations']}")
        print(f"      Capital utilization: {stats['capital_utilization_percentage']:.1f}%")
        print(f"      Effective max pairs: {stats['effective_max_pairs']}")
        
    except Exception as e:
        print(f"   ❌ Error getting statistics: {e}")
    
    # 5. Log status completo
    print(f"\n5. Complete capital status...")
    try:
        capital_manager.log_capital_status()
        print(f"   ✅ Status logged to console")
        
    except Exception as e:
        print(f"   ❌ Error logging status: {e}")
    
    print(f"\n🎉 Capital management test completed!")
    
    # Recomendações baseadas no saldo
    total_balance = balances.get('total_usdt', 0)
    if total_balance < 20:
        print(f"\n💡 Recommendations for low balance (${total_balance:.2f}):")
        print(f"   • Consider reducing capital_per_pair_usd to $5-8")
        print(f"   • Limit max_concurrent_pairs to 1-2")
        print(f"   • Use simpler grid configurations (fewer levels)")
        print(f"   • Focus on high-volume pairs only")
    elif total_balance < 50:
        print(f"\n💡 Recommendations for medium balance (${total_balance:.2f}):")
        print(f"   • Current settings should work well")
        print(f"   • Consider 2-3 concurrent pairs maximum")
        print(f"   • Monitor capital utilization closely")


if __name__ == "__main__":
    test_capital_management()