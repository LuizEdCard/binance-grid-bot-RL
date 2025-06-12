#!/usr/bin/env python3
"""
Test script to validate AI integration fixes for multi-agent bot.
"""

import os
import sys
import yaml

# Add src directory to Python path
SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
sys.path.append(SRC_DIR)

from core.grid_logic import GridLogic
from utils.api_client import APIClient
from integrations.ai_trading_integration import SmartTradingDecisionEngine
from agents.ai_agent import AIAgent

def test_grid_logic_attributes():
    """Test if GridLogic has the necessary attributes."""
    print("=== Testing GridLogic Attributes ===")
    
    # Load config
    config_path = os.path.join(SRC_DIR, "config", "config.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize API client
    api_client = APIClient(config, operation_mode="shadow")
    
    # Initialize GridLogic
    grid_logic = GridLogic("BTCUSDT", config, api_client, "shadow", "futures")
    
    # Test ticker and price methods
    print("Testing ticker methods...")
    ticker = grid_logic._get_ticker()
    if ticker:
        current_price = grid_logic._get_current_price_from_ticker(ticker)
        print(f"✅ Current price: {current_price}")
    else:
        print("⚠️ Could not get ticker (expected in shadow mode)")
        current_price = 50000  # Default for testing
    
    # Test attributes
    print(f"✅ num_levels: {grid_logic.num_levels}")
    print(f"✅ current_spacing_percentage: {grid_logic.current_spacing_percentage}")
    print(f"✅ total_realized_pnl: {grid_logic.total_realized_pnl}")
    
    # Test market data structure
    market_data = {
        "current_price": float(current_price) if current_price else 50000,
        "volume_24h": getattr(grid_logic, 'volume_24h', 0),
        "price_change_24h": getattr(grid_logic, 'price_change_24h', 0),
        "rsi": getattr(grid_logic, 'current_rsi', 50),
        "atr_percentage": getattr(grid_logic, 'current_atr_percentage', 1.0),
        "adx": getattr(grid_logic, 'current_adx', 25)
    }
    
    current_grid_params = {
        "num_levels": grid_logic.num_levels,
        "spacing_perc": float(grid_logic.current_spacing_percentage),
        "recent_pnl": float(grid_logic.total_realized_pnl)
    }
    
    print(f"✅ Market data structure: {market_data}")
    print(f"✅ Grid params structure: {current_grid_params}")
    
    return True

def test_ai_integration():
    """Test AI integration components."""
    print("\n=== Testing AI Integration ===")
    
    # Load config
    config_path = os.path.join(SRC_DIR, "config", "config.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize components
    api_client = APIClient(config, operation_mode="shadow")
    
    # Test AI Agent
    print("Testing AI Agent...")
    ai_agent = AIAgent(config)
    print(f"✅ AI Agent available: {ai_agent.is_available}")
    
    # Test Smart Decision Engine
    if ai_agent.is_available:
        print("Testing Smart Decision Engine...")
        smart_engine = SmartTradingDecisionEngine(ai_agent, api_client, config)
        print("✅ Smart Decision Engine initialized")
    else:
        print("⚠️ AI Agent not available, skipping Smart Decision Engine test")
    
    return True

def main():
    """Main test function."""
    print("Testing AI Integration Fixes...")
    
    try:
        # Test 1: GridLogic attributes
        test_grid_logic_attributes()
        
        # Test 2: AI integration
        test_ai_integration()
        
        print("\n🎉 All tests passed! The integration fixes should work.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)