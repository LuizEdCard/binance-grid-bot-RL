#!/usr/bin/env python3
"""
Script de teste para verificar a recuperação de posições existentes
"""

import os
import sys
import yaml
from dotenv import load_dotenv

# Add src directory to Python path
SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
sys.path.append(SRC_DIR)

from utils.api_client import APIClient
from utils.logger import setup_logger

def test_position_recovery():
    """Testa a recuperação de posições existentes"""
    
    # Load environment and config
    ENV_PATH = os.path.join("secrets", ".env")
    CONFIG_PATH = os.path.join("src", "config", "config.yaml")
    
    load_dotenv(dotenv_path=ENV_PATH)
    
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    
    # Setup logger
    log = setup_logger("position_recovery_test")
    
    # Initialize API client
    api_client = APIClient(config, operation_mode="shadow")
    
    # Test symbols with known positions
    test_symbols = ["ADAUSDT", "ALGOUSDT", "CELRUSDT", "DOGEUSDT", "TRXUSDT"]
    
    log.info("🔍 Testing position recovery for symbols with existing states...")
    
    for symbol in test_symbols:
        log.info(f"\n📊 Testing {symbol}:")
        
        # Check for existing grid state file
        state_file = f"data/grid_states/{symbol}_state.json"
        has_state_file = os.path.exists(state_file)
        log.info(f"   Grid state file exists: {has_state_file}")
        
        if has_state_file:
            try:
                import json
                with open(state_file, 'r') as f:
                    state_data = json.load(f)
                
                active_orders = state_data.get('active_grid_orders', {})
                log.info(f"   Active orders in state: {len(active_orders)}")
                
                for price, order_id in active_orders.items():
                    log.info(f"   - Order {order_id} at ${price}")
                    
            except Exception as e:
                log.error(f"   Error reading state file: {e}")
        
        # Check for existing positions in exchange
        try:
            positions = api_client.get_futures_positions()
            if positions:
                for pos in positions:
                    if pos.get('symbol') == symbol:
                        position_amt = float(pos.get('positionAmt', 0))
                        if position_amt != 0:
                            entry_price = float(pos.get('entryPrice', 0))
                            unrealized_pnl = float(pos.get('unRealizedProfit', 0))
                            log.info(f"   📈 Active position: {position_amt:.4f} @ ${entry_price:.4f}")
                            log.info(f"   💰 Unrealized PnL: {unrealized_pnl:+.4f} USDT")
                        else:
                            log.info(f"   ⚪ No active position")
                        break
            else:
                log.info(f"   ❌ Could not fetch positions")
                
        except Exception as e:
            log.error(f"   Error checking positions: {e}")
        
        # Check for open orders
        try:
            open_orders = api_client.get_open_futures_orders(symbol)
            if open_orders:
                log.info(f"   📋 Open orders: {len(open_orders)}")
                for order in open_orders:
                    order_id = order.get('orderId')
                    side = order.get('side')
                    price = order.get('price')
                    quantity = order.get('origQty')
                    log.info(f"   - {side} {quantity} @ ${price} (ID: {order_id})")
            else:
                log.info(f"   ⚪ No open orders")
                
        except Exception as e:
            log.error(f"   Error checking open orders: {e}")
    
    log.info("\n✅ Position recovery test completed!")

if __name__ == "__main__":
    test_position_recovery()