#!/usr/bin/env python3
"""
Quick test of current model response times.
"""
import asyncio
import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agents.ai_agent import LocalAIClient

async def quick_model_test():
    """Quick test of current model performance."""
    print("⚡ Quick Model Response Time Test")
    print("=" * 40)
    
    client = LocalAIClient()
    
    try:
        await client.start_session()
        
        # Detect current model
        print("🔍 Detecting current model...")
        model = await client.get_running_model()
        
        if not model:
            print("❌ No model detected or available")
            return
        
        print(f"✅ Current model: {model}")
        
        # Test scenarios with different complexities
        tests = [
            {
                "name": "Simple Greeting",
                "messages": [{"role": "user", "content": "Hello! How are you?"}],
                "max_tokens": 50
            },
            {
                "name": "Sentiment Analysis",
                "messages": [
                    {"role": "system", "content": "Analyze sentiment and respond with JSON: {\"sentiment\": \"positive/negative/neutral\", \"score\": 0.0-1.0}"},
                    {"role": "user", "content": "Bitcoin is showing incredible bullish momentum!"}
                ],
                "max_tokens": 100
            },
            {
                "name": "Trading Analysis", 
                "messages": [
                    {"role": "system", "content": "You are a crypto trading expert. Provide brief analysis."},
                    {"role": "user", "content": "BTC broke $45k resistance with high volume. RSI at 65. What's your view?"}
                ],
                "max_tokens": 200
            },
            {
                "name": "Complex Reasoning",
                "messages": [
                    {"role": "system", "content": "You are an expert trader. Analyze the situation and provide recommendations."},
                    {"role": "user", "content": "Market conditions: Strong uptrend, volume 40% above average, positive sentiment, but RSI approaching 70. Should we enter a long position? Consider risk/reward."}
                ],
                "max_tokens": 300
            }
        ]
        
        print(f"\n🧪 Running {len(tests)} performance tests...")
        results = []
        
        for i, test in enumerate(tests, 1):
            print(f"\n{i}. {test['name']} (max {test['max_tokens']} tokens)")
            print("   ", end="", flush=True)
            
            start_time = time.time()
            
            try:
                response = await client.chat_completion(
                    messages=test["messages"],
                    max_tokens=test["max_tokens"]
                )
                
                response_time = time.time() - start_time
                
                if response and "choices" in response:
                    content = response["choices"][0]["message"]["content"]
                    tokens_used = response.get("usage", {}).get("total_tokens", 0)
                    tokens_per_sec = tokens_used / response_time if response_time > 0 else 0
                    
                    print(f"✅ {response_time:.2f}s ({tokens_per_sec:.1f} tok/s)")
                    print(f"      Response: {content[:80]}{'...' if len(content) > 80 else ''}")
                    
                    results.append({
                        "test": test["name"],
                        "response_time": response_time,
                        "tokens": tokens_used,
                        "tokens_per_sec": tokens_per_sec,
                        "success": True
                    })
                else:
                    print("❌ No response received")
                    results.append({"test": test["name"], "success": False})
                    
            except asyncio.TimeoutError:
                timeout_time = time.time() - start_time
                print(f"⏰ TIMEOUT after {timeout_time:.1f}s")
                results.append({
                    "test": test["name"], 
                    "response_time": timeout_time,
                    "success": False,
                    "timeout": True
                })
            except Exception as e:
                error_time = time.time() - start_time
                print(f"❌ ERROR: {str(e)[:50]}...")
                results.append({
                    "test": test["name"],
                    "response_time": error_time, 
                    "success": False,
                    "error": str(e)
                })
        
        # Summary
        successful_tests = [r for r in results if r["success"]]
        
        print(f"\n📊 SUMMARY FOR {model}")
        print("=" * 40)
        print(f"✅ Successful tests: {len(successful_tests)}/{len(tests)}")
        
        if successful_tests:
            avg_time = sum(r["response_time"] for r in successful_tests) / len(successful_tests)
            max_time = max(r["response_time"] for r in successful_tests)
            min_time = min(r["response_time"] for r in successful_tests)
            
            avg_speed = sum(r.get("tokens_per_sec", 0) for r in successful_tests) / len(successful_tests)
            
            print(f"⏱️  Response times: {min_time:.2f}s - {max_time:.2f}s (avg: {avg_time:.2f}s)")
            print(f"🚀 Average speed: {avg_speed:.1f} tokens/second")
            
            # Timeout recommendation
            recommended_timeout = int(max_time * 2 + 15)
            print(f"💡 Recommended timeout: {recommended_timeout}s")
            
            # Performance assessment
            if avg_time < 10:
                print("🏆 Performance: EXCELLENT (< 10s avg)")
            elif avg_time < 20:
                print("🥈 Performance: GOOD (< 20s avg)")  
            elif avg_time < 40:
                print("🥉 Performance: ACCEPTABLE (< 40s avg)")
            else:
                print("⚠️  Performance: SLOW (> 40s avg)")
        
        # Check client statistics
        stats = client.get_statistics()
        print(f"\n📈 Client Stats:")
        print(f"   Total requests: {stats['requests_made']}")
        print(f"   Failed requests: {stats['requests_failed']}")
        print(f"   Timeouts: {stats['timeouts']}")
        
        if model in stats.get("model_performance", {}):
            perf = stats["model_performance"][model]
            print(f"   Model success rate: {perf['successful_requests']}/{perf['total_requests']}")
            if perf['successful_requests'] > 0:
                print(f"   Model avg time: {perf['avg_response_time']:.2f}s")
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        
    finally:
        await client.close_session()

if __name__ == "__main__":
    asyncio.run(quick_model_test())