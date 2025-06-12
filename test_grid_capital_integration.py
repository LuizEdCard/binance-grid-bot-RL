#!/usr/bin/env python3
"""
Teste da integração do sistema de gestão de capital com GridLogic
"""
import sys
import os
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.capital_management import CapitalManager
from core.grid_logic import GridLogic
from utils.api_client import APIClient
from utils.logger import setup_logger

log = setup_logger("grid_capital_test")


def load_config():
    """Carrega configuração"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_grid_capital_integration():
    """Testa a integração completa de capital management com grid logic"""
    print("🔧 Testing Grid-Capital Integration")
    print("=" * 50)
    
    # Carregar configuração
    config = load_config()
    
    # Inicializar API client
    api_client = APIClient(config)
    
    # Inicializar capital manager
    capital_manager = CapitalManager(api_client, config)
    
    # Símbolos para teste
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT', 'SOLUSDT']
    
    print("1. Testing capital allocation...")
    balances = capital_manager.get_available_balances()
    print(f"   Total balance: ${balances['total_usdt']:.2f}")
    
    allocations = capital_manager.calculate_optimal_allocations(test_symbols)
    print(f"   ✅ {len(allocations)} symbols can be traded with current capital")
    
    # Teste de inicialização do GridLogic para cada alocação
    print(f"\n2. Testing GridLogic initialization with capital constraints...")
    
    successful_grids = 0
    failed_grids = 0
    
    for allocation in allocations:
        try:
            print(f"\n   Testing {allocation.symbol}:")
            print(f"      Allocated capital: ${allocation.allocated_amount:.2f}")
            print(f"      Market type: {allocation.market_type}")
            print(f"      Grid levels: {allocation.grid_levels}")
            
            # Verificar se temos capital suficiente
            if not capital_manager.can_trade_symbol(allocation.symbol, allocation.allocated_amount):
                print(f"      ❌ Insufficient capital for {allocation.symbol}")
                failed_grids += 1
                continue
            
            # Criar configuração adaptada
            adapted_config = config.copy()
            adapted_config['initial_levels'] = allocation.grid_levels
            adapted_config['initial_spacing_perc'] = str(allocation.spacing_percentage)
            adapted_config['max_position_size_usd'] = allocation.max_position_size
            
            # Tentar inicializar GridLogic
            grid_logic = GridLogic(
                allocation.symbol, 
                adapted_config, 
                api_client, 
                operation_mode="shadow",  # Use shadow para evitar ordens reais
                market_type=allocation.market_type
            )
            
            print(f"      ✅ GridLogic initialized successfully")
            successful_grids += 1
            
            # Tentar obter preço atual (era onde falhava antes)
            try:
                ticker = grid_logic._get_ticker()
                price = grid_logic._get_current_price_from_ticker(ticker)
                if price is not None:
                    print(f"      ✅ Current price retrieved: ${price:.2f}")
                    
                    # Teste que costumava falhar: definir grid levels
                    try:
                        grid_logic.define_grid_levels(price)
                        if grid_logic.grid_levels:
                            print(f"      ✅ Grid levels defined successfully ({len(grid_logic.grid_levels)} levels)")
                        else:
                            print(f"      ⚠️  Grid levels empty after definition")
                    except Exception as grid_error:
                        print(f"      ❌ Grid level definition failed: {grid_error}")
                        failed_grids += 1
                        successful_grids -= 1
                        continue
                else:
                    print(f"      ❌ Invalid ticker response or price not found: {ticker}")
                    failed_grids += 1
                    successful_grids -= 1
                    continue
            except Exception as e:
                print(f"      ❌ Price retrieval failed: {e}")
                failed_grids += 1
                successful_grids -= 1
                continue
            
        except Exception as e:
            print(f"      ❌ GridLogic initialization failed: {e}")
            failed_grids += 1
            continue
    
    print(f"\n3. Summary:")
    print(f"   ✅ Successful grid initializations: {successful_grids}")
    print(f"   ❌ Failed grid initializations: {failed_grids}")
    print(f"   📊 Success rate: {(successful_grids / (successful_grids + failed_grids)) * 100:.1f}%" if (successful_grids + failed_grids) > 0 else "   📊 No grids tested")
    
    # Teste do cenário de capital insuficiente
    print(f"\n4. Testing insufficient capital scenario...")
    
    # Simular cenário onde tentamos alocar mais símbolos do que o capital permite
    # Já temos 2 símbolos alocados, agora vamos ver se conseguimos alocar o 3º
    remaining_symbols = [s for s in test_symbols if s not in [a.symbol for a in allocations]]
    
    if remaining_symbols:
        test_symbol = remaining_symbols[0]
        print(f"   Testing {test_symbol} with current capital state...")
        
        # Capital já foi parcialmente alocado, verificar se consegue mais um
        all_symbols_including_new = [a.symbol for a in allocations] + [test_symbol]
        expanded_allocations = capital_manager.calculate_optimal_allocations(all_symbols_including_new)
        
        if len(expanded_allocations) <= len(allocations):
            print(f"   ✅ Correctly limited trading - cannot add {test_symbol} due to capital constraints")
        else:
            print(f"   ⚠️  System allowed adding {test_symbol} (may be valid if there's enough capital)")
            
        # Teste específico: tentar com um valor alto de capital requerido
        high_capital_required = balances['total_usdt'] * 0.9  # 90% do capital total
        if not capital_manager.can_trade_symbol(test_symbol, high_capital_required):
            print(f"   ✅ Correctly rejected {test_symbol} when requiring ${high_capital_required:.2f}")
        else:
            print(f"   ❌ Unexpectedly approved {test_symbol} for ${high_capital_required:.2f}")
    else:
        print(f"   ✅ All symbols had sufficient capital allocated")
    
    print(f"\n🎉 Grid-Capital integration test completed!")
    
    if successful_grids > 0 and failed_grids == 0:
        print(f"✅ Integration working perfectly - all grids initialized successfully")
    elif successful_grids > failed_grids:
        print(f"⚠️  Integration mostly working - {successful_grids}/{successful_grids + failed_grids} grids successful")
    else:
        print(f"❌ Integration needs attention - {failed_grids} failures detected")


if __name__ == "__main__":
    test_grid_capital_integration()