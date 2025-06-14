#!/usr/bin/env python3
"""
Debug spot balance detection
"""

import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.capital_management import CapitalManager
import yaml

def load_config():
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    print("🔍 Spot Balance Detection Debug")
    print("=" * 35)
    
    config = load_config()
    api = APIClient(config)
    capital_manager = CapitalManager(api, config)
    
    # Test spot account balance
    print("📊 Spot Account Balance (Raw API):")
    spot_account = api.get_spot_account_balance()
    
    if spot_account and 'balances' in spot_account:
        usdt_balance = None
        for balance in spot_account['balances']:
            if balance['asset'] == 'USDT':
                usdt_balance = balance
                break
        
        if usdt_balance:
            free = float(usdt_balance.get('free', 0))
            locked = float(usdt_balance.get('locked', 0))
            total = free + locked
            print(f"  USDT Free: ${free:.4f}")
            print(f"  USDT Locked: ${locked:.4f}")
            print(f"  USDT Total: ${total:.4f}")
        else:
            print("  ❌ USDT not found in spot balances")
    else:
        print("  ❌ Could not get spot account info")
    
    # Test capital manager detection
    print("\n💰 Capital Manager Detection:")
    balances = capital_manager.get_available_balances()
    print(f"  Spot: ${balances.get('spot_usdt', 0):.2f}")
    print(f"  Futures: ${balances.get('futures_usdt', 0):.2f}")
    print(f"  Total: ${balances.get('total_usdt', 0):.2f}")
    
    # Test both markets
    print(f"\n🔄 Testing spot trading capability:")
    can_trade_spot = capital_manager.can_trade_symbol("BTCUSDT", 5.0, "spot")
    print(f"  Can trade BTCUSDT on spot: {'✅ Yes' if can_trade_spot else '❌ No'}")
    
    print(f"\n🔄 Testing futures trading capability:")
    can_trade_futures = capital_manager.can_trade_symbol("BTCUSDT", 5.0, "futures")
    print(f"  Can trade BTCUSDT on futures: {'✅ Yes' if can_trade_futures else '❌ No'}")
    
    # Check current config market type
    print(f"\n⚙️ Current Configuration:")
    default_market = config.get('default_market_type', 'spot')
    print(f"  Default Market Type: {default_market}")
    
    spot_percentage = config.get('trading', {}).get('market_allocation', {}).get('spot_percentage', 40)
    futures_percentage = config.get('trading', {}).get('market_allocation', {}).get('futures_percentage', 60)
    print(f"  Spot Allocation: {spot_percentage}%")
    print(f"  Futures Allocation: {futures_percentage}%")

if __name__ == "__main__":
    main()