#!/usr/bin/env python3
"""
Test script to validate automatic model detection from Ollama.
"""
import asyncio
import sys
import os

# Add src to path  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agents.ai_agent import LocalAIClient

async def test_auto_detection():
    """Test automatic model detection."""
    print("🔍 Testing Automatic Model Detection")
    print("=" * 40)
    
    # Create AI client
    client = LocalAIClient("http://127.0.0.1:11434")
    
    try:
        await client.start_session()
        
        # Test health check
        print("1. Testing Ollama health...")
        is_healthy = await client.health_check()
        if is_healthy:
            print("✅ Ollama is running and healthy")
        else:
            print("❌ Ollama is not responding")
            return
            
        # Test model detection
        print("\n2. Testing model detection...")
        detected_model = await client.get_running_model()
        
        if detected_model:
            print(f"✅ Auto-detected model: {detected_model}")
            
            # Test chat with detected model
            print(f"\n3. Testing chat with {detected_model}...")
            messages = [
                {
                    "role": "system", 
                    "content": "You are a helpful assistant. Respond briefly."
                },
                {
                    "role": "user", 
                    "content": "Hello! What's your name?"
                }
            ]
            
            response = await client.chat_completion(messages=messages)
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                print(f"✅ Model response: {content[:100]}...")
                print(f"   Tokens used: {response.get('usage', {}).get('total_tokens', 'unknown')}")
            else:
                print("❌ No response from model")
                
        else:
            print("❌ No model detected")
            
        # Test sentiment analysis
        print(f"\n4. Testing sentiment analysis with auto-detection...")
        
        # Import sentiment analyzer
        from utils.sentiment_analyzer import SentimentAnalyzer
        
        analyzer = SentimentAnalyzer()
        test_text = "Bitcoin is showing amazing bullish momentum!"
        
        sentiment_result = analyzer.analyze(test_text)
        if sentiment_result:
            print(f"✅ Sentiment analysis result: {sentiment_result}")
        else:
            print("❌ Sentiment analysis failed")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        
    finally:
        await client.close_session()

async def test_model_switching():
    """Test detection when models are switched."""
    print("\n🔄 Testing Model Switching Detection")
    print("=" * 40)
    
    client = LocalAIClient("http://127.0.0.1:11434")
    
    try:
        await client.start_session()
        
        print("NOTE: This test requires you to manually switch models in Ollama")
        print("You can do this by running a different model in your Ollama terminal")
        print("For example: ollama run qwen3:4b")
        print()
        
        for i in range(3):
            print(f"Detection attempt {i+1}:")
            detected_model = await client.get_running_model()
            
            if detected_model:
                print(f"  Current model: {detected_model}")
            else:
                print("  No model detected")
                
            if i < 2:
                print("  Waiting 5 seconds for potential model switch...")
                await asyncio.sleep(5)
                
    except Exception as e:
        print(f"❌ Error during switching test: {e}")
        
    finally:
        await client.close_session()

if __name__ == "__main__":
    print("🧪 AI Model Auto-Detection Test Suite")
    print("====================================\n")
    
    async def run_all_tests():
        await test_auto_detection()
        
        # Ask user if they want to test switching
        print("\n" + "="*50)
        user_input = input("Do you want to test model switching? (y/n): ")
        if user_input.lower() in ['y', 'yes']:
            await test_model_switching()
        
        print("\n✅ All tests completed!")
    
    asyncio.run(run_all_tests())