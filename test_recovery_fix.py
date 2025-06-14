#!/usr/bin/env python3
"""
Teste da correção de recuperação de posições
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
from core.capital_management import CapitalManager

def test_recovery_logic():
    """Testa a lógica de recuperação de posições"""
    
    # Load environment and config
    ENV_PATH = os.path.join("secrets", ".env")
    CONFIG_PATH = os.path.join("src", "config", "config.yaml")
    
    load_dotenv(dotenv_path=ENV_PATH)
    
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    
    # Setup logger
    log = setup_logger("recovery_fix_test")
    
    # Initialize API client and capital manager
    operation_mode = config.get("operation_mode", "Shadow").lower()
    api_client = APIClient(config, operation_mode=operation_mode)
    capital_manager = CapitalManager(api_client, config)
    
    # Test symbols with known positions
    test_symbols = ["ADAUSDT", "TRXUSDT", "ALGOUSDT", "CELRUSDT", "DOGEUSDT"]
    
    log.info("🔧 Testing position recovery logic...")
    
    for symbol in test_symbols:
        log.info(f"\n📊 Testing {symbol}:")
        
        # Simulate the new logic from multi_agent_bot.py
        min_capital = capital_manager.min_capital_per_pair_usd
        has_existing_position = False
        
        # Check for existing grid state file
        try:
            state_file = f"data/grid_states/{symbol}_state.json"
            if os.path.exists(state_file):
                has_existing_position = True
                log.info(f"   ✅ Found existing grid state - would allow recovery despite low capital")
            
            # Also check for existing positions in the exchange
            if not has_existing_position:
                try:
                    positions = api_client.get_futures_positions()
                    if positions:
                        for pos in positions:
                            if pos.get('symbol') == symbol and float(pos.get('positionAmt', 0)) != 0:
                                has_existing_position = True
                                log.info(f"   ✅ Found existing position in exchange - would allow recovery")
                                break
                except:
                    log.info(f"   ⚠️  Could not check exchange positions (expected in shadow mode)")
                    
        except Exception as e:
            log.warning(f"   ❌ Error checking for existing positions: {e}")
        
        # Test capital validation logic
        can_trade_normally = capital_manager.can_trade_symbol(symbol, min_capital)
        
        if has_existing_position:
            log.info(f"   💡 NEW LOGIC: Would proceed with recovery mode (existing position detected)")
            log.info(f"   📝 Normal capital check: {can_trade_normally} (minimum: ${min_capital:.2f})")
            log.info(f"   🎯 RESULT: WORKER WOULD START (Recovery Mode)")
        elif can_trade_normally:
            log.info(f"   💰 NEW LOGIC: Would proceed normally (sufficient capital)")
            log.info(f"   🎯 RESULT: WORKER WOULD START (Normal Mode)")
        else:
            log.info(f"   ❌ NEW LOGIC: Would reject (no existing position + insufficient capital)")
            log.info(f"   📝 Capital check: {can_trade_normally} (minimum: ${min_capital:.2f})")
            log.info(f"   🎯 RESULT: WORKER WOULD BE REJECTED")
    
    # Show current capital status
    log.info(f"\n💰 CAPITAL SUMMARY:")
    try:
        capital_manager.log_capital_status()
    except Exception as e:
        log.error(f"Error getting capital status: {e}")
    
    log.info("\n✅ Recovery logic test completed!")
    log.info("📋 SUMMARY:")
    log.info("   - Symbols with existing grid states should now be allowed to start")
    log.info("   - Symbols without existing positions still require minimum capital")
    log.info("   - The system should recover existing positions on restart")

if __name__ == "__main__":
    test_recovery_logic()