#!/usr/bin/env python3
"""
Test ADAUSDT trading - lower minimum capital requirement
"""

import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.grid_logic import GridLogic
from utils.logger import setup_logger
import yaml

log = setup_logger("ada_test")

def load_config():
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    """Test ADAUSDT trading with smaller capital."""
    print("🚀 ADAUSDT Trading Test")
    print("=" * 30)
    
    try:
        config = load_config()
        api_client = APIClient(config)
        
        symbol = "ADAUSDT"
        
        # Check symbol info
        ticker = api_client.get_futures_ticker(symbol)
        price = float(ticker.get("price", 0))
        print(f"📈 ADA Price: ${price:.4f}")
        
        # Initialize GridLogic with minimal settings
        grid_config = {
            "initial_levels": 3,  # Only 3 levels
            "initial_spacing_perc": "0.02",  # 2% spacing for more room
            "leverage": 1
        }
        
        grid_logic = GridLogic(
            symbol=symbol,
            config=grid_config,
            api_client=api_client,
            operation_mode="production"
        )
        
        print(f"⚙️ GridLogic initialized for {symbol}")
        print(f"🔄 Running grid cycle...")
        
        # Run grid cycle
        result = grid_logic.run_cycle()
        
        # Check orders
        orders = api_client.get_open_futures_orders(symbol)
        print(f"📊 Orders created: {len(orders)}")
        
        for i, order in enumerate(orders[:5]):
            side = order.get('side')
            qty = order.get('origQty')
            price = order.get('price')
            print(f"  {i+1}. {side} {qty} ADA @ ${price}")
        
        if orders:
            print("✅ SUCCESS! ADA orders executed!")
            return True
        else:
            print("❌ No ADA orders created")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print(f"\nResult: {'🎉 SUCCESS' if success else '😔 FAILED'}")