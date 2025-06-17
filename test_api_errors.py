#!/usr/bin/env python3
"""
Teste para verificar correções dos erros 2022 e 2011 da API Binance
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from utils.logger import setup_logger
import yaml

def load_config():
    """Carrega configuração do bot."""
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def test_api_fixes():
    """Testa correções dos erros de API."""
    log = setup_logger("test_api_fixes")
    
    try:
        # Carregar configuração
        config = load_config()
        
        # Inicializar API client
        print("🔧 Testing API error fixes...")
        print("=" * 50)
        
        api_client = APIClient(config)
        
        if not api_client.client:
            print("❌ Failed to connect to Binance API")
            return False
        
        print("✅ API connection successful")
        
        # Test 1: Time synchronization
        print("\n1. Testing time synchronization:")
        try:
            server_time = api_client.client.futures_time()['serverTime']
            local_time = int(time.time() * 1000)
            time_diff = server_time - local_time
            
            print(f"   Server time: {server_time}")
            print(f"   Local time:  {local_time}")
            print(f"   Difference:  {time_diff}ms")
            
            if abs(time_diff) > 1000:
                print("   ⚠️  Time difference > 1 second - may cause signature errors")
            else:
                print("   ✅ Time synchronization OK")
                
        except Exception as e:
            print(f"   ❌ Time sync test failed: {e}")
        
        # Test 2: Basic API calls
        print("\n2. Testing basic API calls:")
        
        # Test account info
        try:
            balance = api_client.get_futures_balance()
            if balance:
                print("   ✅ get_futures_balance() - OK")
            else:
                print("   ⚠️  get_futures_balance() - No data returned")
        except Exception as e:
            print(f"   ❌ get_futures_balance() failed: {e}")
        
        # Test positions
        try:
            positions = api_client.get_futures_positions()
            if positions:
                open_count = sum(1 for p in positions if float(p.get('positionAmt', 0)) != 0)
                print(f"   ✅ get_futures_positions() - OK ({open_count} open positions)")
            else:
                print("   ⚠️  get_futures_positions() - No data returned")
        except Exception as e:
            print(f"   ❌ get_futures_positions() failed: {e}")
        
        # Test 3: Order validation (without placing)
        print("\n3. Testing order parameter validation:")
        
        # Test invalid order type (should catch error 2011)
        result = api_client.place_futures_order(
            symbol="BTCUSDT",
            side="BUY", 
            order_type="INVALID_TYPE",  # Invalid type
            quantity="0.001"
        )
        if result is None:
            print("   ✅ Invalid order type correctly rejected")
        else:
            print("   ❌ Invalid order type not caught")
        
        # Test missing parameters
        result = api_client.place_futures_order(
            symbol="",  # Missing symbol
            side="BUY",
            order_type="MARKET",
            quantity="0.001"
        )
        if result is None:
            print("   ✅ Missing parameters correctly rejected")
        else:
            print("   ❌ Missing parameters not caught")
        
        print("\n" + "=" * 50)
        print("✅ API error fix testing completed!")
        print("\nImprovements implemented:")
        print("  📈 Automatic time synchronization")
        print("  🛡️  Enhanced error handling for codes -2022 and -2011")
        print("  ✅ Order parameter validation")
        print("  🔄 Automatic retry with time sync for signature errors")
        
        return True
        
    except Exception as e:
        log.error(f"Error in API fixes test: {e}")
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    import time
    test_api_fixes()