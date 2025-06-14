#!/usr/bin/env python3
"""
Test script for Ollama auto-start functionality
"""

import asyncio
import sys
import os
import subprocess
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from agents.ai_agent import LocalAIClient
from utils.gemma3_sentiment_analyzer import Gemma3SentimentAnalyzer


async def test_ai_agent_autostart():
    """Test AI Agent auto-start functionality."""
    print("=== Testing AI Agent Auto-Start ===")
    
    # Stop Ollama first to test auto-start
    print("Stopping Ollama service...")
    try:
        subprocess.run(["systemctl", "stop", "ollama"], check=True, capture_output=True)
        print("✅ Ollama stopped")
        time.sleep(2)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to stop Ollama: {e}")
        return False
    
    # Test AI Agent
    client = LocalAIClient("http://127.0.0.1:11434")
    
    print("Testing health check with auto-start...")
    is_healthy = await client.health_check()
    
    if is_healthy:
        print("✅ AI Agent successfully auto-started Ollama!")
        
        # Test actual functionality
        print("Testing chat completion...")
        response = await client.chat_completion(
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=50
        )
        
        if response and "choices" in response:
            print("✅ Chat completion working!")
            print(f"Response: {response['choices'][0]['message']['content'][:100]}...")
        else:
            print("❌ Chat completion failed")
            
    else:
        print("❌ AI Agent failed to auto-start Ollama")
    
    await client.close_session()
    return is_healthy


def test_sentiment_analyzer_autostart():
    """Test Sentiment Analyzer auto-start functionality."""
    print("\n=== Testing Sentiment Analyzer Auto-Start ===")
    
    # Stop Ollama first to test auto-start
    print("Stopping Ollama service...")
    try:
        subprocess.run(["systemctl", "stop", "ollama"], check=True, capture_output=True)
        print("✅ Ollama stopped")
        time.sleep(2)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to stop Ollama: {e}")
        return False
    
    # Test Sentiment Analyzer
    analyzer = Gemma3SentimentAnalyzer()
    
    print("Testing sentiment analysis with auto-start...")
    result = analyzer.analyze("Bitcoin is going to the moon! 🚀")
    
    if result and "sentiment" in result:
        print("✅ Sentiment Analyzer successfully auto-started Ollama!")
        print(f"Analysis result: {result}")
    else:
        print("❌ Sentiment Analyzer failed to auto-start Ollama")
        return False
    
    return True


def restore_ollama():
    """Restore Ollama service to running state."""
    print("\n=== Restoring Ollama Service ===")
    try:
        subprocess.run(["systemctl", "start", "ollama"], check=True, capture_output=True)
        print("✅ Ollama service restored")
        time.sleep(2)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to restore Ollama: {e}")


async def main():
    """Main test function."""
    print("🔧 Ollama Auto-Start Test Suite")
    print("================================")
    
    # Check if running as proper user
    user = os.getenv("USER")
    if user == "root":
        print("⚠️  Warning: Running as root. Consider running as regular user.")
    
    try:
        # Test AI Agent
        ai_success = await test_ai_agent_autostart()
        
        # Test Sentiment Analyzer  
        sentiment_success = test_sentiment_analyzer_autostart()
        
        # Results
        print("\n=== Test Results ===")
        print(f"AI Agent Auto-Start: {'✅ PASS' if ai_success else '❌ FAIL'}")
        print(f"Sentiment Analyzer Auto-Start: {'✅ PASS' if sentiment_success else '❌ FAIL'}")
        
        if ai_success and sentiment_success:
            print("\n🎉 All tests passed! Ollama auto-start is working correctly.")
        else:
            print("\n⚠️  Some tests failed. Check the logs above.")
            
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
    finally:
        # Always restore Ollama
        restore_ollama()


if __name__ == "__main__":
    asyncio.run(main())