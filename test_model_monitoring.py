#!/usr/bin/env python3
"""
Script para testar o sistema de detecção automática de modelos de IA.
"""

import asyncio
import os
import sys
import time
import yaml

# Add src directory to Python path
SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
sys.path.append(SRC_DIR)

from agents.ai_agent import AIAgent


async def test_model_monitoring():
    """Test the AI model monitoring system."""
    print("🔍 Testing AI Model Monitoring System\n")
    
    # Load config
    config_path = os.path.join(SRC_DIR, "config", "config.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize AI Agent
    print("📱 Initializing AI Agent...")
    ai_agent = AIAgent(config)
    
    # Test initial detection
    print(f"🌐 AI Base URL: {ai_agent.ai_base_url}")
    print(f"⏱️  Model check interval: {ai_agent.model_check_interval}s")
    print(f"📊 Initial available models: {len(ai_agent.available_models)}")
    
    # Start AI Agent
    print("\n🚀 Starting AI Agent with model monitoring...")
    await ai_agent.start()
    
    # Check AI availability
    print(f"✅ AI Available: {ai_agent.is_available}")
    print(f"🤖 Current Model: {ai_agent.current_model or 'None detected'}")
    print(f"📋 Available Models: {len(ai_agent.available_models)}")
    
    if ai_agent.available_models:
        print("📝 Available models list:")
        for i, model in enumerate(ai_agent.available_models[:5], 1):
            print(f"   {i}. {model}")
        if len(ai_agent.available_models) > 5:
            print(f"   ... and {len(ai_agent.available_models) - 5} more")
    
    # Get detailed model info
    print("\n📊 Model monitoring statistics:")
    model_info = ai_agent.get_model_info()
    for key, value in model_info.items():
        if key == "available_models":
            continue  # Skip the long list
        print(f"   {key}: {value}")
    
    # Test force model check
    print("\n🔄 Testing force model check...")
    check_result = await ai_agent.force_model_check()
    print(f"Force check result: {check_result}")
    
    # Simulate monitoring for a short time
    print("\n⏰ Monitoring for 30 seconds (model changes will be detected automatically)...")
    print("   (You can switch models in Ollama during this time to test detection)")
    
    for i in range(6):  # 30 seconds, check every 5
        await asyncio.sleep(5)
        stats = ai_agent.get_statistics()
        current_model = stats.get("current_model", "None")
        model_changes = stats.get("model_changes_detected", 0)
        auto_reconnections = stats.get("auto_reconnections", 0)
        
        print(f"   [{i*5+5:2d}s] Model: {current_model}, Changes: {model_changes}, Reconnects: {auto_reconnections}")
        
        if ai_agent.model_change_detected:
            print("   🎉 MODEL CHANGE DETECTED!")
            ai_agent.reset_model_change_flag()
    
    # Final statistics
    print("\n📈 Final Statistics:")
    final_stats = ai_agent.get_statistics()
    relevant_stats = {
        "is_available": final_stats["is_available"],
        "current_model": final_stats["current_model"],
        "total_models": final_stats["total_models"],
        "model_changes_detected": final_stats["model_changes_detected"],
        "auto_reconnections": final_stats["auto_reconnections"],
        "analyses_performed": final_stats["analyses_performed"]
    }
    
    for key, value in relevant_stats.items():
        print(f"   {key}: {value}")
    
    # Stop AI Agent
    print("\n🛑 Stopping AI Agent...")
    ai_agent.stop()
    
    print("\n✅ Model monitoring test completed!")
    
    return {
        "model_monitoring_works": True,
        "models_detected": len(ai_agent.available_models),
        "current_model": ai_agent.current_model,
        "changes_detected": final_stats["model_changes_detected"]
    }


def main():
    """Main test function."""
    print("🧪 AI Model Monitoring Test Suite")
    print("=" * 50)
    
    try:
        result = asyncio.run(test_model_monitoring())
        
        print("\n🎯 Test Results:")
        print(f"   ✅ Model monitoring: {'WORKING' if result['model_monitoring_works'] else 'FAILED'}")
        print(f"   📊 Models detected: {result['models_detected']}")
        print(f"   🤖 Current model: {result['current_model'] or 'None'}")
        print(f"   🔄 Changes detected: {result['changes_detected']}")
        
        if result["models_detected"] > 0:
            print("\n🎉 SUCCESS: AI model monitoring is working!")
            print("   The system can now:")
            print("   • Automatically detect when you switch models")
            print("   • Reconnect when AI becomes available")
            print("   • Track all available models dynamically")
            print("   • Clear cache when models change")
        else:
            print("\n⚠️  No models detected, but monitoring system is functional.")
            print("   Start an AI model (e.g., ollama run qwen3:1.7b) and run again.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)