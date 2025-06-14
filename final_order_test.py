#!/usr/bin/env python3
"""
Final test with minimum possible order using available balance
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
    print("🎯 Final Order Test - Minimum Possible Order")
    print("=" * 45)
    
    config = load_config()
    api = APIClient(config)
    
    # Use available balance: $7.60
    available_balance = 7.60
    
    # Test ADAUSDT - cheapest option
    symbol = "ADAUSDT"
    ticker = api.get_futures_ticker(symbol)
    price = float(ticker.get('price', 0))
    
    # Calculate max affordable quantity
    max_affordable = int(available_balance / price)
    # Use minimum required (8 ADA = $5.04)
    test_qty = max(8, min(max_affordable, 10))  # Between 8-10 ADA
    
    print(f"💰 Available Balance: ${available_balance:.2f}")
    print(f"📈 {symbol} Price: ${price:.6f}")
    print(f"🔢 Test Quantity: {test_qty} ADA")
    print(f"💵 Order Value: ${test_qty * price:.2f}")
    
    try:
        print(f"\n🚀 Placing BUY order for {test_qty} ADA...")
        
        # Place a simple market buy order first to test
        order_result = api.place_futures_order(
            symbol=symbol,
            side='BUY', 
            order_type='MARKET',
            quantity=str(test_qty)
        )
        
        if order_result:
            print(f"✅ SUCCESS! Order placed:")
            print(f"   Order ID: {order_result.get('orderId')}")
            print(f"   Status: {order_result.get('status')}")
            print(f"   Filled: {order_result.get('executedQty')} ADA")
            print(f"   Price: ${order_result.get('avgPrice', 'N/A')}")
            
            print(f"\n🎉 MISSION ACCOMPLISHED!")
            print(f"   First real order executed successfully!")
            return True
        else:
            print(f"❌ Order failed - no response")
            return False
            
    except Exception as e:
        print(f"❌ Order failed: {e}")
        
        # Try with even smaller quantity
        if "insufficient" in str(e).lower():
            min_qty = 6
            print(f"\n🔄 Retrying with minimum quantity: {min_qty} ADA")
            try:
                order_result = api.place_futures_order(
                    symbol=symbol,
                    side='BUY', 
                    order_type='MARKET',
                    quantity=str(min_qty)
                )
                if order_result:
                    print(f"✅ SUCCESS with minimum order!")
                    return True
            except Exception as e2:
                print(f"❌ Even minimum order failed: {e2}")
        
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🏆 GOAL ACHIEVED: Real order execution successful!")
    else:
        print("\n😔 Failed to execute any orders")