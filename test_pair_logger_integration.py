#!/usr/bin/env python3
"""
Test script to demonstrate the pair_logger integration with grid_logic.py
Tests the automatic updating of metrics like volume_24h, price_change_24h, RSI, ATR, ADX during trading cycles.
"""

import sys
import os
import time
from decimal import Decimal

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.pair_logger import get_pair_logger, get_multi_pair_logger
from utils.api_client import APIClient
from core.grid_logic import GridLogic

def test_pair_logger_integration():
    """Test the pair_logger integration with GridLogic"""
    
    print("🚀 Testing pair_logger integration with GridLogic...")
    
    # Get multi-pair logger for system events
    multi_logger = get_multi_pair_logger()
    multi_logger.log_system_event("Starting pair_logger integration test", "INFO")
    
    # Test configuration (shadow mode for safety)
    test_config = {
        "grid": {
            "initial_levels": 5,
            "initial_spacing_perc": "0.01",  # 1%
            "use_dynamic_spacing": True,
            "dynamic_spacing_atr_period": 14,
            "dynamic_spacing_multiplier": "0.5"
        },
        "risk_management": {
            "max_position_value": 100,
            "stop_loss_percentage": 0.05
        },
        "futures": {
            "leverage": 3
        }
    }
    
    # Test symbols
    test_symbols = ["BTCUSDT", "ETHUSDT"]
    
    try:
        # Initialize API client in shadow mode
        api_client = APIClient(operation_mode="shadow")
        
        for symbol in test_symbols:
            print(f"\n📊 Testing {symbol}...")
            
            # Create GridLogic instance (this will initialize pair_logger)
            grid = GridLogic(
                symbol=symbol,
                config=test_config,
                api_client=api_client,
                operation_mode="shadow",
                market_type="futures"
            )
            
            # Test 1: Verify pair_logger is initialized
            assert hasattr(grid, 'pair_logger'), f"pair_logger not initialized for {symbol}"
            print(f"✅ {symbol}: pair_logger initialized successfully")
            
            # Test 2: Test market data update and metrics extraction
            print(f"🔄 {symbol}: Testing market data update...")
            
            # Mock some current price data
            grid.current_price = 45000.0 if symbol == "BTCUSDT" else 3200.0
            grid.current_rsi = 65.5
            grid.current_atr = 1250.0 if symbol == "BTCUSDT" else 125.0
            grid.current_adx = 45.2
            
            # Mock position data
            if symbol == "BTCUSDT":
                grid.position = {
                    "positionAmt": Decimal("0.001"),
                    "entryPrice": Decimal("44500.0"),
                    "unRealizedProfit": Decimal("25.50")
                }
            else:
                grid.position = {
                    "positionAmt": Decimal("-0.5"),
                    "entryPrice": Decimal("3220.0"),
                    "unRealizedProfit": Decimal("-15.25")
                }
            
            # Mock some trading data
            grid.total_realized_pnl = Decimal("12.25")
            grid.total_trades = 5
            grid.active_grid_orders = {45100.0: 12345, 44900.0: 12346}  # Mock active orders
            
            # Test 3: Update pair_logger metrics manually
            print(f"📈 {symbol}: Testing metrics update...")
            
            grid.pair_logger.update_metrics(
                current_price=grid.current_price,
                entry_price=float(grid.position["entryPrice"]),
                unrealized_pnl=float(grid.position["unRealizedProfit"]),
                realized_pnl=float(grid.total_realized_pnl),
                position_size=abs(float(grid.position["positionAmt"])),
                position_side="LONG" if float(grid.position["positionAmt"]) > 0 else "SHORT",
                leverage=test_config["futures"]["leverage"],
                rsi=grid.current_rsi,
                atr=grid.current_atr,
                adx=grid.current_adx,
                volume_24h=1250000000.0 if symbol == "BTCUSDT" else 850000000.0,
                price_change_24h=2.5 if symbol == "BTCUSDT" else -1.8,
                grid_levels=test_config["grid"]["initial_levels"],
                active_orders=len(grid.active_grid_orders),
                filled_orders=grid.total_trades,
                grid_profit=float(grid.total_realized_pnl),
                market_type="FUTURES"
            )
            
            print(f"✅ {symbol}: Metrics updated successfully")
            
            # Test 4: Test trading cycle logging
            print(f"🔄 {symbol}: Testing trading cycle log...")
            grid.pair_logger.log_trading_cycle()
            print(f"✅ {symbol}: Trading cycle logged successfully")
            
            # Test 5: Test order event logging
            print(f"📝 {symbol}: Testing order event logging...")
            grid.pair_logger.log_order_event("BUY", 44950.0, 0.001, "GRID")
            print(f"✅ {symbol}: Order event logged successfully")
            
            # Test 6: Test position update logging
            print(f"📊 {symbol}: Testing position update logging...")
            grid.pair_logger.log_position_update(
                side="LONG" if float(grid.position["positionAmt"]) > 0 else "SHORT",
                entry_price=float(grid.position["entryPrice"]),
                size=abs(float(grid.position["positionAmt"])),
                pnl=float(grid.position["unRealizedProfit"])
            )
            print(f"✅ {symbol}: Position update logged successfully")
            
            # Short delay between symbols
            time.sleep(1)
        
        # Test 7: Test system status summary
        print(f"\n📋 Testing status summary...")
        multi_logger.print_status_summary()
        print(f"✅ Status summary displayed successfully")
        
        # Test 8: Test system event logging
        multi_logger.log_system_event("pair_logger integration test completed successfully", "SUCCESS")
        
        print(f"\n🎉 All tests passed! pair_logger integration is working correctly.")
        print(f"📁 Check logs in: logs/pairs/")
        print(f"   - Individual pair logs: logs/pairs/btcusdt.log, logs/pairs/ethusdt.log")
        print(f"   - Multi-pair log: logs/pairs/multi_pair.log")
        
        return True
        
    except Exception as e:
        multi_logger.log_system_event(f"Integration test failed: {e}", "ERROR")
        print(f"❌ Test failed: {e}")
        return False

def test_market_data_integration():
    """Test the enhanced _update_market_data method"""
    
    print(f"\n🔍 Testing enhanced _update_market_data method...")
    
    # Test with shadow mode to avoid real API calls
    test_config = {
        "grid": {"initial_levels": 5, "initial_spacing_perc": "0.01"},
        "futures": {"leverage": 3}
    }
    
    try:
        api_client = APIClient(operation_mode="shadow")
        grid = GridLogic(
            symbol="BTCUSDT",
            config=test_config,
            api_client=api_client,
            operation_mode="shadow",
            market_type="futures"
        )
        
        print("✅ GridLogic initialized with pair_logger integration")
        
        # Test the _update_pair_logger_metrics method directly
        print("🔄 Testing _update_pair_logger_metrics...")
        
        # Mock some data
        grid.current_price = 45000.0
        grid.current_rsi = 65.5
        grid.current_atr = 1250.0
        grid.current_adx = 45.2
        grid.position = {
            "positionAmt": Decimal("0.001"),
            "entryPrice": Decimal("44500.0"),
            "unRealizedProfit": Decimal("25.50")
        }
        grid.total_realized_pnl = Decimal("12.25")
        grid.total_trades = 5
        grid.active_grid_orders = {45100.0: 12345, 44900.0: 12346}
        
        # Test the method
        grid._update_pair_logger_metrics(price_change_24h=2.5, volume_24h=1250000000.0)
        
        print("✅ _update_pair_logger_metrics executed successfully")
        
        # Verify metrics were updated
        metrics = grid.pair_logger.metrics
        assert metrics.current_price == 45000.0, "Current price not updated"
        assert metrics.rsi == 65.5, "RSI not updated"
        assert metrics.atr == 1250.0, "ATR not updated"
        assert metrics.volume_24h == 1250000000.0, "Volume 24h not updated"
        assert metrics.price_change_24h == 2.5, "Price change 24h not updated"
        
        print("✅ All metrics verified successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Market data integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 pair_logger Integration Tests")
    print("=" * 50)
    
    # Run tests
    test1_result = test_pair_logger_integration()
    test2_result = test_market_data_integration()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"✅ Basic Integration Test: {'PASSED' if test1_result else 'FAILED'}")
    print(f"✅ Market Data Integration Test: {'PASSED' if test2_result else 'FAILED'}")
    
    if test1_result and test2_result:
        print("🎉 All tests PASSED! pair_logger integration is ready for production.")
    else:
        print("❌ Some tests FAILED. Please check the implementation.")
        sys.exit(1)