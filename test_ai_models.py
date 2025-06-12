#!/usr/bin/env python3
"""
Test script to validate AI model integration with different Ollama models.
"""
import asyncio
import json
import time
import aiohttp
import yaml

async def test_ollama_model(model_name: str) -> dict:
    """Test a specific Ollama model with sentiment analysis."""
    print(f"\n🧪 Testing model: {model_name}")
    
    test_text = "Bitcoin is showing strong bullish momentum with great volume!"
    
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                "model": model_name,
                "prompt": f"""Analyze the sentiment of this text and respond only with a JSON object in this exact format:
{{"sentiment": "positive", "confidence": 0.8, "score": 0.7}}

Where sentiment is "positive", "negative", or "neutral", confidence is 0.0-1.0, and score is -1.0 to 1.0.

Text to analyze: {test_text}""",
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 100
                }
            }
            
            start_time = time.time()
            async with session.post(
                "http://127.0.0.1:11434/api/generate",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    result = await response.json()
                    response_text = result.get("response", "")
                    
                    # Try to parse JSON from response
                    sentiment_data = None
                    try:
                        start = response_text.find('{')
                        end = response_text.rfind('}') + 1
                        if start >= 0 and end > start:
                            json_str = response_text[start:end]
                            sentiment_data = json.loads(json_str)
                    except:
                        pass
                    
                    return {
                        "model": model_name,
                        "status": "success",
                        "response_time": round(response_time, 2),
                        "raw_response": response_text[:200] + "..." if len(response_text) > 200 else response_text,
                        "parsed_sentiment": sentiment_data,
                        "tokens_used": result.get("eval_count", 0)
                    }
                else:
                    return {
                        "model": model_name,
                        "status": "http_error",
                        "error": f"HTTP {response.status}",
                        "response_time": round(response_time, 2)
                    }
                    
    except Exception as e:
        return {
            "model": model_name,
            "status": "error",
            "error": str(e),
            "response_time": None
        }

async def test_all_models():
    """Test all available models."""
    models = [
        "qwen3:0.6b",
        "qwen3:1.7b", 
        "qwen3:4b",
        "deepseek-r1:1.5b",
        "gemma3:1b",
        "gemma3:4b"
    ]
    
    print("🚀 Testing AI models integration with Ollama")
    print("=" * 50)
    
    # Test if Ollama is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:11434/api/tags") as response:
                if response.status == 200:
                    tags_data = await response.json()
                    available_models = [model["name"] for model in tags_data.get("models", [])]
                    print(f"✅ Ollama is running. Available models: {available_models}")
                else:
                    print("❌ Ollama not responding")
                    return
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        return
    
    # Test each model
    results = []
    for model in models:
        result = await test_ollama_model(model)
        results.append(result)
        
        # Print result
        if result["status"] == "success":
            print(f"✅ {model}: {result['response_time']}s, Tokens: {result['tokens_used']}")
            if result["parsed_sentiment"]:
                sent = result["parsed_sentiment"]
                print(f"   Sentiment: {sent.get('sentiment', 'unknown')} (score: {sent.get('score', 'N/A')})")
        else:
            print(f"❌ {model}: {result['status']} - {result.get('error', 'Unknown error')}")
    
    # Summary
    print("\n📊 SUMMARY")
    print("=" * 50)
    successful = [r for r in results if r["status"] == "success"]
    
    if successful:
        fastest = min(successful, key=lambda x: x["response_time"])
        print(f"🏆 Fastest model: {fastest['model']} ({fastest['response_time']}s)")
        
        avg_time = sum(r["response_time"] for r in successful) / len(successful)
        print(f"📊 Average response time: {avg_time:.2f}s")
        
        print(f"✅ Working models: {len(successful)}/{len(models)}")
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        if any(r["model"].startswith("qwen3:0.6b") for r in successful):
            print("   - qwen3:0.6b: Fastest, good for real-time sentiment")
        if any(r["model"].startswith("qwen3:1.7b") for r in successful):
            print("   - qwen3:1.7b: Balanced speed/quality") 
        if any(r["model"].startswith("deepseek-r1") for r in successful):
            print("   - deepseek-r1:1.5b: Best for reasoning tasks")
    else:
        print("❌ No models working. Check Ollama installation and model availability.")

if __name__ == "__main__":
    asyncio.run(test_all_models())