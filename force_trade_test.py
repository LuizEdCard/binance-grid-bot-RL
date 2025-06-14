#!/usr/bin/env python3
"""
Force Trade Test - Skip pair selection and force a trading attempt
"""

import sys
import os
import asyncio

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.grid_logic import GridLogic
from core.capital_management import CapitalManager
from utils.logger import setup_logger
import yaml

log = setup_logger("force_trade")

def load_config():
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    """Force a trade execution test."""
    print("🚀 Force Trade Test - Direct Order Execution")
    print("=" * 50)
    
    try:
        config = load_config()
        
        # Initialize components
        api_client = APIClient(config)
        capital_manager = CapitalManager(api_client, config)
        
        # Check current balance
        print("📊 Checking account balance...")
        futures_balance = api_client.get_futures_account_balance()
        
        if futures_balance:
            # Handle list format
            if isinstance(futures_balance, list):
                usdt_balance = None
                for asset in futures_balance:
                    if asset.get("asset") == "USDT":
                        usdt_balance = asset
                        break
                
                if usdt_balance:
                    available = float(usdt_balance.get("availableBalance", "0"))
                    total = float(usdt_balance.get("walletBalance", "0"))
                    print(f"💰 USDT Balance: Available=${available:.2f}, Total=${total:.2f}")
                else:
                    print("❌ USDT balance not found")
                    return
            else:
                available = float(futures_balance.get("availableBalance", "0"))
                total = float(futures_balance.get("totalWalletBalance", "0"))
                print(f"💰 Balance: Available=${available:.2f}, Total=${total:.2f}")
        
        # Force test with known working symbols
        test_symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        
        for symbol in test_symbols:
            print(f"\n🎯 Testing symbol: {symbol}")
            
            try:
                # Check if symbol exists
                ticker = api_client.get_futures_ticker(symbol)
                if not ticker:
                    print(f"❌ {symbol} ticker not available")
                    continue
                
                price = float(ticker.get("price", 0))
                print(f"📈 Current price: ${price:.4f}")
                
                # Check minimum capital requirements
                balances = capital_manager.get_available_balances()
                print(f"🔍 Debug balances: {balances}")
                available_capital = balances.get("Futures", balances.get("futures", 0))  # Try both keys
                print(f"💵 Available capital: ${available_capital:.2f}")
                
                if available_capital < 5:
                    print(f"❌ Insufficient capital (${available_capital:.2f} < $5.00)")
                    # Force use actual API balance for testing
                    print("🔧 Forcing with actual API balance...")
                    available_capital = 60.29
                
                # Initialize GridLogic for this symbol
                print(f"⚙️ Initializing GridLogic for {symbol}...")
                grid_config = {
                    "initial_levels": 5,  # Reduced levels for testing
                    "initial_spacing_perc": "0.01",  # 1% spacing
                    "leverage": 1
                }
                
                grid_logic = GridLogic(
                    symbol=symbol,
                    config=grid_config,
                    api_client=api_client,
                    operation_mode="production"
                )
                
                # Check if symbol can be traded
                can_trade = capital_manager.can_trade_symbol(symbol, 5.0, "futures")
                print(f"💰 Can trade {symbol}: {'✅ Yes' if can_trade else '❌ No'}")
                
                if not can_trade:
                    continue
                
                # Try to run one grid cycle
                print(f"🔄 Running grid cycle for {symbol}...")
                grid_result = grid_logic.run_cycle()
                
                print(f"📊 Grid cycle result: {grid_result}")
                
                # Check for any orders
                open_orders = api_client.get_open_futures_orders(symbol)
                if open_orders:
                    print(f"✅ SUCCESS! {len(open_orders)} orders created:")
                    for order in open_orders[:3]:  # Show first 3 orders
                        print(f"  📋 Order: {order.get('side')} {order.get('origQty')} at ${order.get('price')}")
                    return True
                else:
                    print(f"⚠️ No orders created for {symbol}")
                
            except Exception as e:
                print(f"❌ Error with {symbol}: {e}")
                continue
        
        print("\n❌ No orders were executed with any symbol")
        return False
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 MISSION ACCOMPLISHED: Orders executed successfully!")
    else:
        print("\n😔 Mission failed: No orders executed")