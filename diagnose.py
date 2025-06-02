#!/usr/bin/env python3
# diagnose.py
import os
import sys

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.api_client import APIClient
from src.core.grid_logic import GridLogic
import yaml
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)

def run_diagnosis():
    print("🔍 Starting grid diagnostics for ADAUSDT...")
    
    # Load configuration
    try:
        with open("src/config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        print("✅ Configuration loaded successfully")
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return
    
    # Initialize API client
    try:
        api_client = APIClient(config["api"], operation_mode="production")
        print("✅ API client initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing API client: {e}")
        return
    
    # Check futures orders
    try:
        print("\n📊 Checking FUTURES orders...")
        futures_orders = api_client._make_request(
            api_client.client.futures_get_open_orders,
            symbol="ADAUSDT"
        )
        if futures_orders:
            print(f"✅ Found {len(futures_orders)} FUTURES orders:")
            for order in futures_orders:
                print(f"  - {order['side']} order @ {order['price']}, Amount: {order['origQty']}")
        else:
            print("ℹ️ No FUTURES orders found")
    except Exception as e:
        print(f"❌ Error checking futures orders: {e}")

    # Check spot orders
    try:
        print("\n📊 Checking SPOT orders...")
        spot_orders = api_client._make_request(
            api_client.client.get_open_orders,
            symbol="ADAUSDT"
        )
        if spot_orders:
            print(f"✅ Found {len(spot_orders)} SPOT orders:")
            for order in spot_orders:
                print(f"  - {order['side']} order @ {order['price']}, Amount: {order['origQty']}")
        else:
            print("ℹ️ No SPOT orders found")
    except Exception as e:
        print(f"❌ Error checking spot orders: {e}")

    # Check futures position
    try:
        print("\n📊 Checking FUTURES position...")
        position = api_client._make_request(
            api_client.client.futures_position_information,
            symbol="ADAUSDT"
        )
        if position:
            pos = position[0]  # Get first position
            amt = float(pos['positionAmt'])
            if amt != 0:
                print(f"✅ Active FUTURES position:")
                print(f"  - Amount: {amt}")
                print(f"  - Entry price: {pos['entryPrice']}")
                print(f"  - Unrealized PnL: {pos['unRealizedProfit']}")
            else:
                print("ℹ️ No active FUTURES position")
    except Exception as e:
        print(f"❌ Error checking futures position: {e}")

    # Check spot balance
    try:
        print("\n📊 Checking SPOT balance...")
        account = api_client._make_request(api_client.client.get_account)
        if account and 'balances' in account:
            ada_balance = next((b for b in account['balances'] if b['asset'] == 'ADA'), None)
            usdt_balance = next((b for b in account['balances'] if b['asset'] == 'USDT'), None)
            
            if ada_balance:
                print(f"  - ADA: {float(ada_balance['free'])} (free) + {float(ada_balance['locked'])} (locked)")
            if usdt_balance:
                print(f"  - USDT: {float(usdt_balance['free'])} (free) + {float(usdt_balance['locked'])} (locked)")
    except Exception as e:
        print(f"❌ Error checking spot balance: {e}")

    # Try to check actual grid recovery
    try:
        print("\n🔄 Testing manual grid recovery from orders...")
        # Initialize a GridLogic with the correct market type based on where we found orders
        market_type = "futures"  # Default to futures since we saw futures orders
        grid = GridLogic(
            symbol="ADAUSDT",
            config=config,
            api_client=api_client,
            operation_mode="production",
            market_type=market_type
        )
        
        # Get all futures orders for manual analysis
        futures_orders = api_client._make_request(
            api_client.client.futures_get_open_orders,
            symbol="ADAUSDT"
        ) or []
        
        # Analyze spacing of futures orders if they exist
        if futures_orders and len(futures_orders) >= 2:
            print(f"\n📊 Analyzing spacing of {len(futures_orders)} futures orders...")
            # Sort by price
            futures_orders.sort(key=lambda x: float(x['price']))
            
            # Calculate spacing between consecutive orders
            spacings = []
            for i in range(1, len(futures_orders)):
                price1 = float(futures_orders[i-1]['price'])
                price2 = float(futures_orders[i]['price'])
                spacing = abs((price2 - price1) / price1) * 100
                spacings.append(spacing)
                print(f"  - Spacing between {price1} and {price2}: {spacing:.2f}%")
            
            # Calculate average spacing
            if spacings:
                avg_spacing = sum(spacings) / len(spacings)
                print(f"  - Average spacing: {avg_spacing:.2f}%")
                
                # Check if spacings are consistent (variation < 25%)
                spacing_variation = [abs(s - avg_spacing) / avg_spacing for s in spacings]
                is_consistent = all(v < 0.25 for v in spacing_variation)
                print(f"  - Spacings are {'consistent' if is_consistent else 'not consistent'}")
                
                if not is_consistent:
                    for i, var in enumerate(spacing_variation):
                        if var >= 0.25:
                            print(f"  - High variation at spacing {i}: {var*100:.1f}%")
        else:
            print("ℹ️ Not enough futures orders to analyze spacing")

    except Exception as e:
        print(f"❌ Error during manual grid analysis: {e}")

    print("\n✅ Diagnosis complete")

if __name__ == "__main__":
    run_diagnosis()

