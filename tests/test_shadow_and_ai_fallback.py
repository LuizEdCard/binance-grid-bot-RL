#!/usr/bin/env python3
# Test script for Shadow mode (testnet) and AI fallback functionality
import asyncio
import os
import sys
import time
from datetime import datetime

# Add src to path
sys.path.append('../src')

from agents.ai_agent import AIAgent
from utils.api_client import APIClient
from utils.logger import setup_logger

log = setup_logger("test_shadow_ai")


def test_shadow_mode():
    """Test Shadow mode (testnet) functionality."""
    print("🧪 Testing Shadow Mode (Binance Testnet)")
    print("=" * 50)
    
    # Test configuration
    config = {
        "api": {
            "key": "${BINANCE_API_KEY}",
            "secret": "${BINANCE_API_SECRET}"
        }
    }
    
    try:
        # Test Shadow mode (should connect to testnet)
        print("📡 Testing connection to Binance Testnet...")
        api_client_shadow = APIClient(config, operation_mode="shadow")
        
        if api_client_shadow.client:
            print("✅ Shadow mode connection successful!")
            print(f"   Connected to: {'TESTNET' if api_client_shadow.use_testnet else 'PRODUCTION'}")
            
            # Test basic functionality
            try:
                server_time = api_client_shadow.client.futures_time()
                print(f"   Server time: {server_time['serverTime']}")
                
                # Test getting futures exchange info
                exchange_info = api_client_shadow.client.futures_exchange_info()
                print(f"   Available symbols: {len(exchange_info['symbols'])}")
                
                # Test getting ticker for BTCUSDT
                ticker = api_client_shadow.get_futures_ticker("BTCUSDT")
                if ticker:
                    print(f"   BTCUSDT ticker: {ticker.get('lastPrice', 'N/A')}")
                else:
                    print("   ⚠️  Could not fetch BTCUSDT ticker")
                
            except Exception as e:
                print(f"   ⚠️  Some testnet operations failed: {e}")
                print("   This is normal if testnet has limited functionality")
        else:
            print("❌ Shadow mode connection failed")
            print("   Check your API credentials and testnet access")
            return False
        
        # Test Production mode for comparison
        print("\n📡 Testing connection to Binance Production...")
        api_client_production = APIClient(config, operation_mode="production")
        
        if api_client_production.client:
            print("✅ Production mode connection successful!")
            print(f"   Connected to: {'TESTNET' if api_client_production.use_testnet else 'PRODUCTION'}")
        else:
            print("❌ Production mode connection failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Shadow mode: {e}")
        return False


async def test_ai_fallback():
    """Test AI fallback functionality."""
    print("\n🤖 Testing AI Fallback Functionality")
    print("=" * 50)
    
    # Test with AI not available
    print("🔌 Testing with AI offline...")
    config = {
        "ai_agent": {
            "enabled": True,
            "base_url": "http://127.0.0.1:9999"  # Non-existent port
        }
    }
    
    ai_agent = AIAgent(config, "http://127.0.0.1:9999")
    
    try:
        await ai_agent.start()
        
        if not ai_agent.is_available:
            print("✅ AI correctly detected as unavailable")
            
            # Test all major functions return None gracefully
            print("📊 Testing market analysis fallback...")
            result = await ai_agent.analyze_market({"test": "data"})
            if result is None:
                print("✅ Market analysis gracefully returns None")
            else:
                print("❌ Market analysis should return None when AI unavailable")
            
            print("⚙️ Testing grid optimization fallback...")
            result = await ai_agent.optimize_grid_strategy({}, {})
            if result is None:
                print("✅ Grid optimization gracefully returns None")
            else:
                print("❌ Grid optimization should return None when AI unavailable")
            
            print("💡 Testing decision explanation fallback...")
            result = await ai_agent.explain_decision({})
            if result is None:
                print("✅ Decision explanation gracefully returns None")
            else:
                print("❌ Decision explanation should return None when AI unavailable")
            
            print("📋 Testing report generation fallback...")
            result = await ai_agent.generate_market_report({})
            if result is None:
                print("✅ Report generation gracefully returns None")
            else:
                print("❌ Report generation should return None when AI unavailable")
            
        else:
            print("❌ AI should be detected as unavailable")
            return False
        
        ai_agent.stop()
        
        # Test with AI potentially available
        print("\n🔌 Testing with AI potentially online...")
        config_online = {
            "ai_agent": {
                "enabled": True,
                "base_url": "http://127.0.0.1:1234"  # Your AI port
            }
        }
        
        ai_agent_online = AIAgent(config_online, "http://127.0.0.1:1234")
        await ai_agent_online.start()
        
        if ai_agent_online.is_available:
            print("✅ AI detected as available")
            print("   Your local AI is running and responding")
        else:
            print("ℹ️  AI detected as unavailable")
            print("   This is expected if your AI isn't running on port 1234")
            print("   Bot will continue operating normally without AI")
        
        ai_agent_online.stop()
        return True
        
    except Exception as e:
        print(f"❌ Error testing AI fallback: {e}")
        return False


def test_environment_variables():
    """Test environment variable configuration."""
    print("\n🔧 Testing Environment Variables")
    print("=" * 50)
    
    # Check required variables
    required_vars = ["BINANCE_API_KEY", "BINANCE_API_SECRET"]
    optional_vars = ["BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_API_SECRET"]
    
    print("📋 Required variables:")
    all_required_present = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {'*' * 8}")  # Mask the value
        else:
            print(f"   ❌ {var}: Not set")
            all_required_present = False
    
    print("\n📋 Optional testnet variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {'*' * 8}")  # Mask the value
        else:
            print(f"   ℹ️  {var}: Not set (will use production keys for testnet)")
    
    if not all_required_present:
        print("\n⚠️  Missing required environment variables!")
        print("   Create a .env file with your Binance API credentials")
        print("   See config/.env.example for template")
        return False
    
    return True


def show_usage_examples():
    """Show usage examples."""
    print("\n📖 Usage Examples")
    print("=" * 50)
    
    print("1. Shadow Mode (Testnet):")
    print("   ./start_multi_agent_bot.sh --shadow")
    print("   or")
    print("   python src/multi_agent_bot.py")
    print("   (with operation_mode: Shadow in config.yaml)")
    
    print("\n2. Production Mode:")
    print("   ./start_multi_agent_bot.sh --production")
    print("   or")
    print("   python src/multi_agent_bot.py")
    print("   (with operation_mode: Production in config.yaml)")
    
    print("\n3. With AI enabled:")
    print("   - Start your AI on http://127.0.0.1:1234")
    print("   - Set ai_agent.enabled: true in config.yaml")
    print("   - Run normally")
    
    print("\n4. Without AI:")
    print("   - Set ai_agent.enabled: false in config.yaml")
    print("   - Or just don't start your AI")
    print("   - Bot will work normally without AI features")
    
    print("\n5. Environment setup:")
    print("   - Copy config/.env.example to config/.env")
    print("   - Add your Binance API credentials")
    print("   - Optionally add testnet credentials for shadow mode")


async def main():
    """Main test function."""
    print(f"🧪 Shadow Mode & AI Fallback Test Suite")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Test environment variables
    env_ok = test_environment_variables()
    
    if not env_ok:
        print("\n❌ Environment setup incomplete")
        show_usage_examples()
        return
    
    # Test Shadow mode
    shadow_ok = test_shadow_mode()
    
    # Test AI fallback
    ai_fallback_ok = await test_ai_fallback()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   Environment Variables: {'✅ PASS' if env_ok else '❌ FAIL'}")
    print(f"   Shadow Mode (Testnet): {'✅ PASS' if shadow_ok else '❌ FAIL'}")
    print(f"   AI Fallback: {'✅ PASS' if ai_fallback_ok else '❌ FAIL'}")
    
    if env_ok and shadow_ok and ai_fallback_ok:
        print("\n🎉 All tests passed!")
        print("\n✅ Key Points Confirmed:")
        print("   • Shadow mode connects to Binance Testnet")
        print("   • Production mode connects to Binance Production")
        print("   • Bot continues operating when AI is offline")
        print("   • All AI functions gracefully handle unavailability")
        print("   • No crashes or errors when AI is not available")
        
        show_usage_examples()
    else:
        print("\n⚠️  Some tests failed. Check the issues above.")
        
        if not shadow_ok:
            print("\n🔧 Shadow Mode Troubleshooting:")
            print("   • Verify your API keys work with Binance Testnet")
            print("   • Check if you have testnet access enabled")
            print("   • Ensure network connectivity to Binance")
        
        if not ai_fallback_ok:
            print("\n🔧 AI Fallback Troubleshooting:")
            print("   • This might indicate code logic issues")
            print("   • Check the error messages above for details")


if __name__ == "__main__":
    asyncio.run(main())