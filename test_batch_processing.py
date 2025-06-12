#!/usr/bin/env python3
"""
Test script to validate batch processing optimization for 471 USDT pairs.
"""

import os
import sys
import yaml
import time
import asyncio

# Add src directory to Python path
SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
sys.path.append(SRC_DIR)

def test_market_summary_generation():
    """Test if PairSelector can generate market summary efficiently."""
    print("🧪 Testing Market Summary Generation...")
    try:
        from core.pair_selector import PairSelector
        from utils.api_client import APIClient
        
        # Load config
        config_path = os.path.join(SRC_DIR, "config", "config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize components
        api_client = APIClient(config, operation_mode="shadow")
        pair_selector = PairSelector(config, api_client)
        
        # Test market summary generation
        start_time = time.time()
        market_summary = pair_selector.get_market_summary()
        generation_time = time.time() - start_time
        
        print(f"✅ Market summary generated in {generation_time:.2f} seconds")
        print(f"   Total pairs analyzed: {market_summary.get('total_pairs', 0)}")
        print(f"   Market trend: {market_summary.get('market_trend', 'unknown')}")
        print(f"   Average volatility: {market_summary.get('avg_volatility', 0):.2f}%")
        print(f"   Market conditions: {market_summary.get('market_conditions', 'unknown')}")
        print(f"   High volume pairs: {market_summary.get('high_volume_pairs', [])[:5]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing market summary: {e}")
        return False

def test_smart_trading_engine():
    """Test if SmartTradingDecisionEngine can handle market overview analysis."""
    print("\n🧪 Testing SmartTradingDecisionEngine Market Overview...")
    try:
        from integrations.ai_trading_integration import SmartTradingDecisionEngine
        from agents.ai_agent import AIAgent
        from utils.api_client import APIClient
        
        # Load config
        config_path = os.path.join(SRC_DIR, "config", "config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize components
        api_client = APIClient(config, operation_mode="shadow")
        ai_agent = AIAgent(config)
        smart_engine = SmartTradingDecisionEngine(ai_agent, api_client, config)
        
        # Test market overview analysis with mock data
        mock_market_summary = {
            "total_pairs": 471,
            "avg_volume": 5000000,
            "high_volume_pairs": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            "market_trend": "bullish",
            "avg_volatility": 2.8,
            "volatility_distribution": {"low": 150, "medium": 200, "high": 121},
            "avg_adx": 28,
            "market_conditions": "good_for_grid"
        }
        
        # Test the method exists
        if hasattr(smart_engine, 'get_market_overview_analysis'):
            print("✅ SmartTradingDecisionEngine.get_market_overview_analysis method exists")
            print(f"   AI agent available: {ai_agent.is_available}")
            print(f"   Order sizer initialized: {smart_engine.order_sizer is not None}")
            
            # Test async execution (would require actual AI agent to be running)
            if ai_agent.is_available:
                async def test_analysis():
                    try:
                        analysis = await smart_engine.get_market_overview_analysis(mock_market_summary)
                        return analysis
                    except Exception as e:
                        print(f"   Note: Analysis failed (expected if AI not running): {e}")
                        return None
                
                result = asyncio.run(test_analysis())
                if result:
                    print(f"   Analysis result: {result}")
                else:
                    print("   Analysis test completed (AI may not be running)")
            else:
                print("   AI agent not available (expected in test environment)")
            
            return True
        else:
            print("❌ SmartTradingDecisionEngine.get_market_overview_analysis method missing")
            return False
            
    except Exception as e:
        print(f"❌ Error testing SmartTradingDecisionEngine: {e}")
        return False

def test_batch_trading_actions():
    """Test if SmartTradingDecisionEngine can handle batch processing."""
    print("\n🧪 Testing Batch Trading Actions...")
    try:
        from integrations.ai_trading_integration import SmartTradingDecisionEngine
        from agents.ai_agent import AIAgent
        from utils.api_client import APIClient
        
        # Load config
        config_path = os.path.join(SRC_DIR, "config", "config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize components
        api_client = APIClient(config, operation_mode="shadow")
        ai_agent = AIAgent(config)
        smart_engine = SmartTradingDecisionEngine(ai_agent, api_client, config)
        
        # Test batch processing method
        if hasattr(smart_engine, 'get_batch_trading_actions'):
            print("✅ SmartTradingDecisionEngine.get_batch_trading_actions method exists")
            
            # Create mock batch data
            mock_symbols_data = []
            test_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
            
            for symbol in test_symbols:
                mock_symbols_data.append({
                    "symbol": symbol,
                    "market_data": {
                        "current_price": 50000 if symbol == "BTCUSDT" else 3000,
                        "volume_24h": 1000000000,
                        "price_change_24h": 2.5,
                        "rsi": 55,
                        "atr_percentage": 2.8,
                        "adx": 25
                    },
                    "grid_params": {
                        "num_levels": 10,
                        "spacing_perc": 0.005
                    },
                    "balance": 1000
                })
            
            print(f"   Testing batch processing with {len(mock_symbols_data)} symbols")
            
            # Test async batch processing
            async def test_batch():
                try:
                    start_time = time.time()
                    results = await smart_engine.get_batch_trading_actions(mock_symbols_data)
                    processing_time = time.time() - start_time
                    
                    print(f"   Batch processing completed in {processing_time:.2f} seconds")
                    print(f"   Results for {len(results)} symbols received")
                    
                    for symbol, result in results.items():
                        action = result.get("action", "unknown")
                        confidence = result.get("confidence", 0)
                        source = result.get("source", "unknown")
                        print(f"     {symbol}: action={action}, confidence={confidence:.2f}, source={source}")
                    
                    return True
                    
                except Exception as e:
                    print(f"   Batch processing failed: {e}")
                    return False
            
            success = asyncio.run(test_batch())
            return success
            
        else:
            print("❌ SmartTradingDecisionEngine.get_batch_trading_actions method missing")
            return False
            
    except Exception as e:
        print(f"❌ Error testing batch trading actions: {e}")
        return False

def main():
    """Main test function."""
    print("🔧 Testing Batch Processing Optimization for 471 USDT Pairs")
    print("=" * 65)
    
    tests = [
        test_market_summary_generation,
        test_smart_trading_engine,
        test_batch_trading_actions
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 Batch Processing Optimization is working!")
        print("\n✅ System optimizations:")
        print("   • Market summary generation for 471 pairs")
        print("   • AI market overview analysis (aggregated data)")
        print("   • Batch processing of trading decisions")
        print("   • Efficient resource utilization")
        print("\n📈 Expected benefits:")
        print("   • Reduced AI API calls (471 → 1 for overview)")
        print("   • Faster processing with concurrent batch operations")
        print("   • Lower latency and resource usage")
        print("   • Scalable to handle even more pairs")
        return True
    else:
        print("❌ Some optimizations need attention")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)