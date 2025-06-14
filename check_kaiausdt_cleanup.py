#!/usr/bin/env python3
"""
Check and optionally clean up KAIAUSDT orders and positions to allow proper pair switching.
"""

import sys
import os
import yaml
import json

# Add src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient

def main():
    print("🧹 KAIAUSDT CLEANUP CHECK")
    print("=" * 50)
    
    # Load config
    config_path = os.path.join('src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize API client
    try:
        api_client = APIClient(config)
        print("✅ API client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize API client: {e}")
        return
    
    print(f"\n1. 📊 CHECKING KAIAUSDT FUTURES POSITION:")
    
    # Check current position
    try:
        position = api_client.get_futures_position('KAIAUSDT')
        if position:
            position_amt = float(position.get('positionAmt', 0))
            unrealized_pnl = float(position.get('unRealizedProfit', 0))
            entry_price = float(position.get('entryPrice', 0))
            mark_price = float(position.get('markPrice', 0))
            
            print(f"   📈 Position Size: {position_amt} KAIA")
            print(f"   💰 Unrealized PnL: ${unrealized_pnl:.4f}")
            print(f"   🎯 Entry Price: ${entry_price:.4f}")
            print(f"   📊 Current Price: ${mark_price:.4f}")
            
            if abs(position_amt) > 0:
                print(f"   ⚠️  ACTIVE POSITION DETECTED!")
                if unrealized_pnl > 0.01:
                    print(f"   💡 Position is profitable, consider closing")
                elif unrealized_pnl < -0.01:
                    print(f"   ⚠️  Position is at loss")
                else:
                    print(f"   📍 Position is near breakeven")
            else:
                print(f"   ✅ No open position")
        else:
            print(f"   ❌ Could not fetch position info")
    except Exception as e:
        print(f"   ❌ Error checking position: {e}")
    
    print(f"\n2. 📋 CHECKING KAIAUSDT OPEN ORDERS:")
    
    # Check open orders
    try:
        orders = api_client.get_open_futures_orders('KAIAUSDT')
        if orders:
            print(f"   📊 Found {len(orders)} open orders:")
            for i, order in enumerate(orders):
                side = order.get('side')
                qty = order.get('origQty')
                price = order.get('price')
                order_id = order.get('orderId')
                order_type = order.get('type')
                print(f"     {i+1}. {side} {qty} KAIA @ ${price} (ID: {order_id}, Type: {order_type})")
        else:
            print(f"   ✅ No open orders")
    except Exception as e:
        print(f"   ❌ Error checking orders: {e}")
    
    print(f"\n3. 📁 CHECKING KAIAUSDT GRID STATE:")
    
    # Check grid state file
    grid_state_path = os.path.join('src', 'data', 'grid_states', 'KAIAUSDT_state.json')
    if os.path.exists(grid_state_path):
        try:
            with open(grid_state_path, 'r') as f:
                grid_state = json.load(f)
            
            print(f"   📄 Grid state file found: {grid_state_path}")
            print(f"   📊 Grid levels: {len(grid_state.get('grid_levels', []))}")
            print(f"   🔄 Active orders: {len(grid_state.get('active_grid_orders', {}))}")
            print(f"   📅 Last updated: {grid_state.get('last_updated', 'unknown')}")
            
            active_orders = grid_state.get('active_grid_orders', {})
            if active_orders:
                print(f"   📋 Active grid orders:")
                for price, order_id in active_orders.items():
                    print(f"     - Price ${price}: Order ID {order_id}")
        except Exception as e:
            print(f"   ❌ Error reading grid state: {e}")
    else:
        print(f"   ✅ No grid state file found")
    
    print(f"\n4. 🎯 RECOMMENDATIONS:")
    
    print(f"   📝 Current pair selection should now use preferred symbols")
    print(f"   🔄 Next bot restart should pick up the correct pairs")
    
    # Check if there are active positions/orders
    try:
        position = api_client.get_futures_position('KAIAUSDT')
        orders = api_client.get_open_futures_orders('KAIAUSDT')
        
        has_position = position and abs(float(position.get('positionAmt', 0))) > 0
        has_orders = orders and len(orders) > 0
        
        if has_position or has_orders:
            print(f"   ⚠️  ACTIVE KAIAUSDT TRADING DETECTED:")
            print(f"   💡 Consider manually closing position/orders before restart")
            print(f"   🔧 Or let the system naturally close them as part of normal operation")
            print(f"   ⏰ New pair selection will take effect on next cycle")
        else:
            print(f"   ✅ No active KAIAUSDT trading detected")
            print(f"   🚀 Safe to restart bot with new pair selection")
            
    except Exception as e:
        print(f"   ❌ Error during final check: {e}")
    
    print(f"\n🏁 Check completed!")

if __name__ == "__main__":
    main()