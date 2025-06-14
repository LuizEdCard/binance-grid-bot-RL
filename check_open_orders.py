#!/usr/bin/env python3
"""
Check current open orders to see if ADAUSDT order is still active
"""

import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
import yaml

def load_config():
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    print("🔍 Checking Open Orders")
    print("=" * 30)
    
    config = load_config()
    api = APIClient(config)
    
    # Check all open futures orders
    print("📋 All Open Futures Orders:")
    all_orders = api.get_open_futures_orders()
    
    if all_orders:
        print(f"  Found {len(all_orders)} open orders:")
        for i, order in enumerate(all_orders):
            symbol = order.get('symbol')
            side = order.get('side')
            qty = order.get('origQty')
            price = order.get('price')
            order_id = order.get('orderId')
            status = order.get('status')
            order_type = order.get('type')
            
            print(f"  {i+1}. {symbol}: {side} {qty} @ ${price}")
            print(f"      ID: {order_id}, Status: {status}, Type: {order_type}")
            
        # Check specifically for ADAUSDT
        ada_orders = [o for o in all_orders if o.get('symbol') == 'ADAUSDT']
        if ada_orders:
            print(f"\n🎯 ADAUSDT Orders ({len(ada_orders)}):")
            for order in ada_orders:
                print(f"  Order ID: {order.get('orderId')}")
                print(f"  Side: {order.get('side')}")
                print(f"  Quantity: {order.get('origQty')}")
                print(f"  Price: ${order.get('price')}")
                print(f"  Status: {order.get('status')}")
                print(f"  Type: {order.get('type')}")
        else:
            print(f"\n❌ No ADAUSDT orders found")
    else:
        print("  ❌ No open futures orders found")
    
    # Also check if there are any filled orders recently
    print(f"\n📈 Current Positions:")
    positions = api.get_futures_positions()
    active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
    
    if active_positions:
        for pos in active_positions:
            symbol = pos.get('symbol')
            amount = pos.get('positionAmt')
            entry_price = pos.get('entryPrice')
            mark_price = pos.get('markPrice')
            pnl = pos.get('unRealizedProfit')
            print(f"  {symbol}: {amount} @ ${entry_price} (Mark: ${mark_price}, PnL: ${pnl})")
            
            if symbol == 'ADAUSDT':
                print(f"  🎯 Found ADAUSDT position!")
    else:
        print("  No active positions")

if __name__ == "__main__":
    main()