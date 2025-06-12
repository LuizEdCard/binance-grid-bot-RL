#!/usr/bin/env python3
"""
Comprehensive benchmark test for Ollama models response times.
Tests different types of tasks to understand model performance characteristics.
"""
import asyncio
import time
import json
import statistics
import aiohttp
from typing import Dict, List

class ModelBenchmark:
    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120)  # 2 minutes max
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def get_available_models(self) -> List[str]:
        """Get list of available models."""
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    result = await response.json()
                    return [model.get("name", "") for model in result.get("models", [])]
        except Exception as e:
            print(f"Error getting models: {e}")
        return []
    
    async def test_model_response(self, model_name: str, prompt: str, test_name: str, timeout: int = 60) -> Dict:
        """Test a single model with a specific prompt."""
        start_time = time.time()
        
        try:
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 200
                }
            }
            
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    response_time = time.time() - start_time
                    
                    return {
                        "model": model_name,
                        "test": test_name,
                        "status": "success",
                        "response_time": round(response_time, 2),
                        "response_length": len(result.get("response", "")),
                        "tokens_generated": result.get("eval_count", 0),
                        "tokens_per_second": round(result.get("eval_count", 0) / response_time, 2) if response_time > 0 else 0,
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "total_time": result.get("total_duration", 0) / 1e9,  # Convert to seconds
                        "load_time": result.get("load_duration", 0) / 1e9,
                        "response_preview": result.get("response", "")[:100] + "..." if len(result.get("response", "")) > 100 else result.get("response", "")
                    }
                else:
                    return {
                        "model": model_name,
                        "test": test_name, 
                        "status": "http_error",
                        "error": f"HTTP {response.status}",
                        "response_time": round(time.time() - start_time, 2)
                    }
                    
        except asyncio.TimeoutError:
            return {
                "model": model_name,
                "test": test_name,
                "status": "timeout", 
                "response_time": round(time.time() - start_time, 2),
                "error": f"Timeout after {timeout}s"
            }
        except Exception as e:
            return {
                "model": model_name,
                "test": test_name,
                "status": "error",
                "error": str(e),
                "response_time": round(time.time() - start_time, 2)
            }

async def run_comprehensive_benchmark():
    """Run comprehensive benchmark on all available models."""
    
    # Test scenarios of varying complexity
    test_scenarios = [
        {
            "name": "simple_greeting",
            "prompt": "Hello! Please respond with a brief greeting.",
            "timeout": 15,
            "description": "Simple greeting (baseline)"
        },
        {
            "name": "sentiment_analysis", 
            "prompt": """Analyze the sentiment of this text and respond only with JSON:
{"sentiment": "positive", "confidence": 0.8, "score": 0.7}

Text: "Bitcoin is showing incredible bullish momentum with massive volume!"
""",
            "timeout": 30,
            "description": "Sentiment analysis (trading task)"
        },
        {
            "name": "market_analysis",
            "prompt": """Analyze this market data and provide insights:
Price: $45,000, Volume: 1.2B, RSI: 65, ATR: 2.5%

Provide brief analysis on trend and recommendations.""",
            "timeout": 45,
            "description": "Market analysis (complex reasoning)"
        },
        {
            "name": "reasoning_task",
            "prompt": """You are a trading expert. Given these conditions:
- Price broke above resistance at $44,500
- Volume increased 40% in last hour  
- RSI at 62 (not overbought)
- Bullish sentiment score: 0.7

Should we enter a long position? Explain your reasoning briefly.""",
            "timeout": 60,
            "description": "Complex reasoning task"
        },
        {
            "name": "json_response",
            "prompt": """Respond only with valid JSON containing market recommendations:
{
  "action": "buy" | "sell" | "hold",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "risk_level": "low" | "medium" | "high"
}

Market conditions: Strong uptrend, high volume, positive sentiment.""",
            "timeout": 30,
            "description": "Structured JSON response"
        }
    ]
    
    print("🚀 Starting Comprehensive Model Benchmark")
    print("=" * 60)
    
    async with ModelBenchmark() as benchmark:
        # Get available models
        models = await benchmark.get_available_models()
        
        if not models:
            print("❌ No models found in Ollama")
            return
            
        print(f"📋 Found {len(models)} models: {', '.join(models)}")
        print(f"🧪 Running {len(test_scenarios)} test scenarios per model")
        print()
        
        all_results = []
        model_stats = {}
        
        for model in models:
            print(f"\n🔍 Testing model: {model}")
            print("-" * 40)
            
            model_results = []
            
            for scenario in test_scenarios:
                print(f"  Running {scenario['name']}... ", end="", flush=True)
                
                result = await benchmark.test_model_response(
                    model, 
                    scenario["prompt"],
                    scenario["name"],
                    scenario["timeout"]
                )
                
                if result["status"] == "success":
                    print(f"✅ {result['response_time']}s ({result['tokens_per_second']} tok/s)")
                elif result["status"] == "timeout":
                    print(f"⏰ TIMEOUT ({result['response_time']}s)")
                else:
                    print(f"❌ {result['status']}")
                    
                result.update(scenario)
                model_results.append(result)
                all_results.append(result)
                
                # Small delay between tests
                await asyncio.sleep(1)
            
            # Calculate model statistics
            successful_tests = [r for r in model_results if r["status"] == "success"]
            if successful_tests:
                response_times = [r["response_time"] for r in successful_tests]
                tokens_per_sec = [r["tokens_per_second"] for r in successful_tests if r["tokens_per_second"] > 0]
                
                model_stats[model] = {
                    "success_rate": len(successful_tests) / len(model_results) * 100,
                    "avg_response_time": statistics.mean(response_times),
                    "min_response_time": min(response_times),
                    "max_response_time": max(response_times),
                    "median_response_time": statistics.median(response_times),
                    "avg_tokens_per_sec": statistics.mean(tokens_per_sec) if tokens_per_sec else 0,
                    "total_tests": len(model_results),
                    "successful_tests": len(successful_tests)
                }
            else:
                model_stats[model] = {
                    "success_rate": 0,
                    "total_tests": len(model_results),
                    "successful_tests": 0
                }
    
    # Print comprehensive results
    print("\n" + "=" * 60)
    print("📊 BENCHMARK RESULTS SUMMARY")
    print("=" * 60)
    
    for model, stats in model_stats.items():
        print(f"\n🤖 {model}")
        print(f"   Success Rate: {stats['success_rate']:.1f}% ({stats['successful_tests']}/{stats['total_tests']})")
        
        if stats['success_rate'] > 0:
            print(f"   Avg Response Time: {stats['avg_response_time']:.2f}s")
            print(f"   Response Time Range: {stats['min_response_time']:.2f}s - {stats['max_response_time']:.2f}s")
            print(f"   Median Response Time: {stats['median_response_time']:.2f}s")
            if stats['avg_tokens_per_sec'] > 0:
                print(f"   Avg Tokens/Second: {stats['avg_tokens_per_sec']:.1f}")
    
    # Recommendations
    print("\n💡 TIMEOUT RECOMMENDATIONS")
    print("=" * 30)
    
    for model, stats in model_stats.items():
        if stats['success_rate'] > 0:
            # Recommend timeout based on max response time + buffer
            recommended_timeout = int(stats['max_response_time'] * 1.5 + 10)
            print(f"{model}: {recommended_timeout}s timeout recommended")
    
    # Performance ranking
    successful_models = [(model, stats) for model, stats in model_stats.items() if stats['success_rate'] > 80]
    if successful_models:
        print("\n🏆 PERFORMANCE RANKING (80%+ success rate)")
        print("=" * 45)
        
        # Sort by average response time
        successful_models.sort(key=lambda x: x[1]['avg_response_time'])
        
        for i, (model, stats) in enumerate(successful_models, 1):
            print(f"{i}. {model}: {stats['avg_response_time']:.2f}s avg ({stats['avg_tokens_per_sec']:.1f} tok/s)")
    
    # Save detailed results
    with open("benchmark_results.json", "w") as f:
        json.dump({
            "summary": model_stats,
            "detailed_results": all_results,
            "test_scenarios": test_scenarios,
            "timestamp": time.time()
        }, f, indent=2)
    
    print(f"\n💾 Detailed results saved to benchmark_results.json")

if __name__ == "__main__":
    print("⚡ Model Response Time Benchmark")
    print("Testing all available models with various complexity levels...")
    print()
    
    asyncio.run(run_comprehensive_benchmark())