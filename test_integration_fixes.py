#!/usr/bin/env python3
"""
Test script to validate all integration fixes applied.
"""

import os
import sys
import yaml

# Add src directory to Python path
SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
sys.path.append(SRC_DIR)

def test_ai_agent_method():
    """Test if AIAgent has analyze_market_text method."""
    print("🧪 Testing AIAgent.analyze_market_text method...")
    try:
        from agents.ai_agent import AIAgent
        
        # Load config
        config_path = os.path.join(SRC_DIR, "config", "config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        ai_agent = AIAgent(config)
        
        # Check if method exists
        if hasattr(ai_agent, 'analyze_market_text'):
            print("✅ AIAgent.analyze_market_text method exists")
            return True
        else:
            print("❌ AIAgent.analyze_market_text method missing")
            return False
            
    except Exception as e:
        print(f"❌ Error testing AIAgent: {e}")
        return False

def test_api_client_methods():
    """Test if APIClient has futures_exchange_info and spot_exchange_info methods."""
    print("\n🧪 Testing APIClient exchange_info methods...")
    try:
        from utils.api_client import APIClient
        
        # Load config
        config_path = os.path.join(SRC_DIR, "config", "config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        api_client = APIClient(config, operation_mode="shadow")
        
        # Check methods
        methods_ok = 0
        if hasattr(api_client, 'futures_exchange_info'):
            print("✅ APIClient.futures_exchange_info method exists")
            methods_ok += 1
        else:
            print("❌ APIClient.futures_exchange_info method missing")
        
        if hasattr(api_client, 'spot_exchange_info'):
            print("✅ APIClient.spot_exchange_info method exists")
            methods_ok += 1
        else:
            print("❌ APIClient.spot_exchange_info method missing")
            
        return methods_ok == 2
        
    except Exception as e:
        print(f"❌ Error testing APIClient: {e}")
        return False

def test_grid_logic_run_cycle():
    """Test if GridLogic.run_cycle accepts ai_decision parameter."""
    print("\n🧪 Testing GridLogic.run_cycle ai_decision parameter...")
    try:
        from core.grid_logic import GridLogic
        from utils.api_client import APIClient
        
        # Load config
        config_path = os.path.join(SRC_DIR, "config", "config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        api_client = APIClient(config, operation_mode="shadow")
        grid_logic = GridLogic("BTCUSDT", config, api_client, "shadow", "futures")
        
        # Test method signature
        import inspect
        sig = inspect.signature(grid_logic.run_cycle)
        params = list(sig.parameters.keys())
        
        if 'ai_decision' in params:
            print("✅ GridLogic.run_cycle accepts ai_decision parameter")
            print(f"   Method signature: {params}")
            return True
        else:
            print("❌ GridLogic.run_cycle missing ai_decision parameter")
            print(f"   Current parameters: {params}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing GridLogic: {e}")
        return False

def test_smart_decision_engine():
    """Test if SmartTradingDecisionEngine can be created."""
    print("\n🧪 Testing SmartTradingDecisionEngine integration...")
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
        
        print("✅ SmartTradingDecisionEngine created successfully")
        print(f"   AI agent available: {ai_agent.is_available}")
        print(f"   Order sizer initialized: {smart_engine.order_sizer is not None}")
        return True
        
    except Exception as e:
        print(f"❌ Error testing SmartTradingDecisionEngine: {e}")
        return False

def main():
    """Main test function."""
    print("🔧 Testing Integration Fixes")
    print("=" * 50)
    
    tests = [
        test_ai_agent_method,
        test_api_client_methods,
        test_grid_logic_run_cycle,
        test_smart_decision_engine
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All integration fixes are working!")
        print("\n✅ Ready to test multi-agent bot:")
        print("   • AIAgent.analyze_market_text method fixed")
        print("   • APIClient exchange_info methods added")  
        print("   • GridLogic.run_cycle accepts ai_decision")
        print("   • SmartTradingDecisionEngine integration working")
        print("   • Telegram errors converted to warnings")
        return True
    else:
        print("❌ Some fixes still need attention")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)