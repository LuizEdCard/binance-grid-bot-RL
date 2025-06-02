# Ollama-powered Sentiment Analyzer for Cryptocurrency Trading  
# Uses Ollama as inference engine instead of Transformers for Gemma-3 model
# Ollama = Simple deployment + automatic optimization + resource management

import json
import re
import time
import requests
from typing import Dict, List, Optional, Union
import logging
from .logger import log


class Gemma3SentimentAnalyzer:
    """
    Cryptocurrency sentiment analyzer using Ollama for Gemma-3 inference.
    
    Uses latest Gemma-3 model via Ollama instead of Transformers:
    - Ollama: Simple setup, automatic optimization, REST API
    - Transformers: Complex setup, manual config, Python library
    
    Same Gemma-3 model performance, much easier deployment.
    """
    
    def __init__(self, 
                 model_name: str = "gemma3:1b",  # Latest Gemma-3 model
                 ollama_host: str = "http://localhost:11434",
                 timeout: int = 30):
        self.model_name = model_name
        self.ollama_host = ollama_host
        self.timeout = timeout
        self.session = requests.Session()
        
        # Performance tracking
        self.total_analyses = 0
        self.successful_analyses = 0
        self.avg_latency = 0.0
        self.cache = {}
        
        # Crypto-specific knowledge
        self.crypto_keywords = self._load_crypto_keywords()
        
        # Check Ollama availability
        self.available = self._check_ollama_status()
        if self.available:
            self._ensure_model_available()
    
    def _load_crypto_keywords(self) -> Dict[str, List[str]]:
        """Enhanced crypto keyword detection for 2024."""
        return {
            "bullish_signals": [
                "moon", "lambo", "diamond hands", "hodl", "buy the dip",
                "to the moon", "bullish", "pump", "breakout", "rally",
                "bullrun", "accumulate", "strong hands", "wagmi", "lfg",
                "number go up", "probably nothing", "few understand"
            ],
            "bearish_signals": [
                "dump", "crash", "bear market", "paper hands", "sell off",
                "correction", "bearish", "fud", "panic sell", "liquidation",
                "rug pull", "scam", "dead cat bounce", "ngmi", "rekt",
                "exit liquidity", "bags", "bag holder"
            ],
            "sarcasm_indicators": [
                "great", "wonderful", "amazing", "perfect", "fantastic",
                "totally", "definitely", "sure", "of course"
            ],
            "crypto_entities": [
                "bitcoin", "btc", "ethereum", "eth", "solana", "sol",
                "cardano", "ada", "polygon", "matic", "chainlink", "link",
                "defi", "nft", "dao", "yield farming", "staking"
            ]
        }
    
    def _check_ollama_status(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            response = self.session.get(f"{self.ollama_host}/api/tags", timeout=5)
            if response.status_code == 200:
                log.info("Ollama service is available")
                return True
            else:
                log.warning(f"Ollama service returned status {response.status_code}")
                return False
        except Exception as e:
            log.warning(f"Ollama service not available: {e}")
            return False
    
    def _ensure_model_available(self) -> bool:
        """Ensure the specified model is available in Ollama."""
        try:
            # Check if model is already pulled
            response = self.session.get(f"{self.ollama_host}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                
                if self.model_name in model_names:
                    log.info(f"Model {self.model_name} is available")
                    return True
                else:
                    log.warning(f"Model {self.model_name} not found. Available models: {model_names}")
                    log.info(f"To install: ollama pull {self.model_name}")
                    return False
            else:
                log.error(f"Failed to check available models: {response.status_code}")
                return False
                
        except Exception as e:
            log.error(f"Error checking model availability: {e}")
            return False
    
    def _create_sentiment_prompt(self, text: str) -> str:
        """Create optimized prompt for crypto sentiment analysis."""
        prompt = f"""You are an expert cryptocurrency market sentiment analyst. Analyze the following text for trading sentiment.

CONTEXT: Cryptocurrency markets are highly emotional and driven by social media sentiment. Consider:
- Crypto slang and terminology (HODL, moon, diamond hands, paper hands, etc.)
- Sarcasm and irony common in crypto communities
- Market psychology and trader emotions
- Social media tone and emojis

TEXT TO ANALYZE: "{text}"

INSTRUCTIONS:
1. Determine if sentiment is BULLISH (positive for price), BEARISH (negative for price), or NEUTRAL
2. Assign confidence level 0.0-1.0
3. Provide brief reasoning

RESPOND WITH ONLY THIS JSON FORMAT:
{{"sentiment": "BULLISH|BEARISH|NEUTRAL", "confidence": 0.85, "reasoning": "brief explanation"}}

JSON RESPONSE:"""
        
        return prompt
    
    def _call_ollama_api(self, prompt: str) -> Optional[str]:
        """Make API call to Ollama service."""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,      # Low temperature for consistent results
                    "top_p": 0.9,           # Focus on most likely tokens
                    "repeat_penalty": 1.1,  # Avoid repetition
                    "num_predict": 150      # Limit response length
                }
            }
            
            response = self.session.post(
                f"{self.ollama_host}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                log.error(f"Ollama API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            log.warning(f"Ollama API timeout after {self.timeout}s")
            return None
        except Exception as e:
            log.error(f"Ollama API call failed: {e}")
            return None
    
    def _extract_json_response(self, response: str) -> Optional[Dict]:
        """Extract and parse JSON from Ollama response."""
        try:
            # Find JSON in response
            json_match = re.search(r'\{[^{}]*\}', response)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                
                # Validate required fields
                if 'sentiment' in parsed and 'confidence' in parsed:
                    return parsed
                else:
                    log.warning(f"Invalid JSON structure: {parsed}")
                    return None
            else:
                log.warning(f"No JSON found in response: {response}")
                return None
                
        except json.JSONDecodeError as e:
            log.warning(f"JSON decode error: {e}")
            return None
        except Exception as e:
            log.error(f"Error extracting JSON: {e}")
            return None
    
    def _fallback_analysis(self, text: str) -> Dict:
        """Fallback sentiment analysis using keyword matching."""
        text_lower = text.lower()
        
        # Count keyword matches
        bullish_score = sum(1 for word in self.crypto_keywords["bullish_signals"] 
                           if word in text_lower)
        bearish_score = sum(1 for word in self.crypto_keywords["bearish_signals"] 
                           if word in text_lower)
        
        # Check for sarcasm
        sarcasm_count = sum(1 for indicator in self.crypto_keywords["sarcasm_indicators"]
                           if indicator in text_lower)
        
        # Determine sentiment
        if sarcasm_count > 0 and bullish_score > bearish_score:
            # Sarcasm likely inverts sentiment
            sentiment = "BEARISH"
            confidence = 0.6
            reasoning = "sarcasm detected, inverted sentiment"
        elif bullish_score > bearish_score:
            sentiment = "BULLISH"
            confidence = min(0.8, 0.5 + bullish_score * 0.1)
            reasoning = f"{bullish_score} bullish signals detected"
        elif bearish_score > bullish_score:
            sentiment = "BEARISH"
            confidence = min(0.8, 0.5 + bearish_score * 0.1)
            reasoning = f"{bearish_score} bearish signals detected"
        else:
            sentiment = "NEUTRAL"
            confidence = 0.5
            reasoning = "no clear sentiment signals"
        
        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "reasoning": reasoning
        }
    
    def analyze(self, text: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Analyze sentiment using Ollama API.
        
        Args:
            text: Text to analyze
            use_cache: Whether to use cached results
            
        Returns:
            Dict with sentiment, confidence, and reasoning
        """
        if not self.available:
            log.warning("Ollama not available, using fallback analysis")
            return self._fallback_analysis(text)
        
        if not text or not text.strip():
            return None
        
        # Check cache
        text_hash = hash(text.strip())
        if use_cache and text_hash in self.cache:
            return self.cache[text_hash]
        
        start_time = time.time()
        
        try:
            # Create prompt and call Ollama
            prompt = self._create_sentiment_prompt(text)
            response = self._call_ollama_api(prompt)
            
            if response:
                # Parse JSON response
                result = self._extract_json_response(response)
                
                if result:
                    # Normalize sentiment values
                    sentiment = result['sentiment'].upper()
                    if sentiment not in ['BULLISH', 'BEARISH', 'NEUTRAL']:
                        sentiment = 'NEUTRAL'
                    
                    result['sentiment'] = sentiment
                    result['confidence'] = min(max(result['confidence'], 0.0), 1.0)
                    
                    self.successful_analyses += 1
                else:
                    # Fallback if parsing failed
                    log.warning("Failed to parse Ollama response, using fallback")
                    result = self._fallback_analysis(text)
            else:
                # Fallback if API call failed
                log.warning("Ollama API call failed, using fallback")
                result = self._fallback_analysis(text)
            
            # Update performance metrics
            latency = time.time() - start_time
            self.avg_latency = (
                (self.avg_latency * self.total_analyses + latency) / 
                (self.total_analyses + 1)
            )
            self.total_analyses += 1
            
            # Cache result
            if use_cache and result:
                self.cache[text_hash] = result
            
            log.debug(f"Ollama sentiment analysis: '{text[:50]}...' -> {result}")
            return result
            
        except Exception as e:
            log.error(f"Error in Ollama sentiment analysis: {e}", exc_info=True)
            return self._fallback_analysis(text)
    
    def analyze_batch(self, texts: List[str], batch_size: int = 5) -> List[Optional[Dict]]:
        """
        Analyze multiple texts with controlled concurrency.
        
        Args:
            texts: List of texts to analyze
            batch_size: Number of concurrent requests
            
        Returns:
            List of sentiment analysis results
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = []
            
            for text in batch:
                result = self.analyze(text)
                batch_results.append(result)
            
            results.extend(batch_results)
            
            # Small delay between batches to avoid overwhelming Ollama
            if i + batch_size < len(texts):
                time.sleep(0.2)
        
        return results
    
    def get_stats(self) -> Dict:
        """Get performance statistics."""
        success_rate = (
            (self.successful_analyses / max(self.total_analyses, 1)) * 100
        )
        
        return {
            "total_analyses": self.total_analyses,
            "successful_analyses": self.successful_analyses,
            "success_rate": f"{success_rate:.1f}%",
            "avg_latency_ms": f"{self.avg_latency * 1000:.1f}ms",
            "cache_size": len(self.cache),
            "ollama_available": self.available,
            "model_name": self.model_name,
            "ollama_host": self.ollama_host
        }
    
    def get_model_info(self) -> Dict:
        """Get information about the current model."""
        if not self.available:
            return {"error": "Ollama not available"}
        
        try:
            # Get model info from Ollama
            response = self.session.post(
                f"{self.ollama_host}/api/show",
                json={"name": self.model_name},
                timeout=10
            )
            
            if response.status_code == 200:
                model_info = response.json()
                return {
                    "name": self.model_name,
                    "size": model_info.get('size', 'unknown'),
                    "family": model_info.get('details', {}).get('family', 'unknown'),
                    "parameters": model_info.get('details', {}).get('parameter_size', 'unknown'),
                    "quantization": model_info.get('details', {}).get('quantization_level', 'unknown')
                }
            else:
                return {"error": f"Failed to get model info: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Error getting model info: {e}"}
    
    def switch_model(self, new_model: str) -> bool:
        """Switch to a different model."""
        old_model = self.model_name
        self.model_name = new_model
        
        if self._ensure_model_available():
            log.info(f"Switched from {old_model} to {new_model}")
            self.cache.clear()  # Clear cache when switching models
            return True
        else:
            self.model_name = old_model  # Revert on failure
            log.error(f"Failed to switch to {new_model}, reverting to {old_model}")
            return False
    
    def clear_cache(self):
        """Clear the response cache."""
        self.cache.clear()
        log.info("Ollama sentiment analysis cache cleared")


# Factory functions for different Gemma-3 model sizes
def create_gemma3_analyzer_1b() -> Gemma3SentimentAnalyzer:
    """Create analyzer with Gemma-3 1B model (fast, good for crypto sentiment)."""
    return Gemma3SentimentAnalyzer(model_name="gemma3:1b")

def create_gemma3_analyzer_2b() -> Gemma3SentimentAnalyzer:
    """Create analyzer with Gemma-3 2B model (more accurate, slower)."""
    return Gemma3SentimentAnalyzer(model_name="gemma3:2b")

def create_gemma3_analyzer_custom(model_name: str) -> Gemma3SentimentAnalyzer:
    """Create analyzer with custom model."""
    return Gemma3SentimentAnalyzer(model_name=model_name)


# Example usage and testing
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Test different model sizes
    print("Testing Gemma-3 Sentiment Analyzers (via Ollama):")
    print("=" * 50)
    
    analyzers = {
        "Gemma-3 1B": create_gemma3_analyzer_1b(),
        "Gemma-3 2B": create_gemma3_analyzer_2b()
    }
    
    test_texts = [
        "Bitcoin to the moon! 🚀 Diamond hands HODL!",
        "This crash is devastating... paper hands selling everything 📉",
        "Great, another -50% day 😭 Just perfect",
        "BTC consolidating between 45k-50k, waiting for breakout",
        "Whale just moved 10k BTC to exchange, could be bearish",
        "DeFi yields looking sus, might be a rug pull"
    ]
    
    for analyzer_name, analyzer in analyzers.items():
        if analyzer.available:
            print(f"\n{analyzer_name} Results:")
            print("-" * 30)
            
            for text in test_texts[:3]:  # Test first 3 texts
                result = analyzer.analyze(text)
                if result:
                    print(f"Text: {text}")
                    print(f"Sentiment: {result['sentiment']} (confidence: {result['confidence']:.2f})")
                    print(f"Reasoning: {result['reasoning']}")
                    print()
            
            # Show stats
            stats = analyzer.get_stats()
            print(f"Stats: {stats['total_analyses']} analyses, {stats['avg_latency_ms']} avg latency")
        else:
            print(f"\n{analyzer_name}: Not available (Ollama not running or model not installed)")
    
    print("\nTo install models:")
    print("ollama pull gemma3:1b")
    print("ollama pull gemma3:2b")