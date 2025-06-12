# Hybrid Sentiment Analyzer - Uses Gemma-3-1b-it and fallback support
# Provides intelligent sentiment analysis with local and online model support

import time
from typing import Dict, List, Optional, Union
from .logger import log

# Import sentiment analyzers
try:
    from .gemma3_sentiment_analyzer import Gemma3SentimentAnalyzer
    gemma3_available = True
except ImportError:
    log.warning("Gemma-3 Sentiment Analyzer not available")
    gemma3_available = False


class HybridSentimentAnalyzer:
    """
    Intelligent sentiment analyzer using Gemma-3-1b-it with fallback support.
    
    Strategy:
    - Use Gemma-3 for all sentiment analysis (high accuracy)
    - Support for future online API integrations
    - Smart caching and batch processing
    """
    
    def __init__(self, prefer_gemma3: bool = True):
        self.prefer_gemma3 = prefer_gemma3
        
        # Initialize analyzers
        self.gemma3_analyzer = None
        
        # Performance tracking
        self.stats = {
            "gemma3_used": 0,
            "fallbacks": 0,
            "total_analyses": 0,
            "avg_latency": 0.0
        }
        
        self.crypto_keywords = {
            "high_priority": [
                "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
                "blockchain", "defi", "nft", "altcoin", "hodl", "moon", "lambo",
                "diamond hands", "paper hands", "whale", "pump", "dump", "bull",
                "bear", "satoshi", "gwei", "gas fee", "mining", "staking"
            ],
            "medium_priority": [
                "investment", "trading", "market", "price", "value", "profit",
                "loss", "portfolio", "exchange", "wallet", "transaction"
            ]
        }
        
        self._initialize_analyzers()
    
    def _initialize_analyzers(self):
        """Initialize available sentiment analyzers."""
        
        # Initialize Gemma-3 if available and preferred
        if gemma3_available and self.prefer_gemma3:
            try:
                log.info("Initializing Gemma-3-1b-it sentiment analyzer...")
                self.gemma3_analyzer = Gemma3SentimentAnalyzer()
                
                if self.gemma3_analyzer.available:
                    log.info("Gemma-3 sentiment analyzer ready")
                else:
                    log.warning("Gemma-3 failed to load properly")
                    self.gemma3_analyzer = None
                    
            except Exception as e:
                log.error(f"Failed to initialize Gemma-3 analyzer: {e}")
                self.gemma3_analyzer = None
        
        # Log final status
        gemma3_status = "✅" if self.gemma3_analyzer else "❌"
        log.info(f"Hybrid Sentiment Analyzer Status: Gemma-3 {gemma3_status}")
    
    def _calculate_crypto_relevance(self, text: str) -> float:
        """Calculate how crypto-relevant a text is (0.0 to 1.0)."""
        text_lower = text.lower()
        
        high_priority_matches = sum(1 for keyword in self.crypto_keywords["high_priority"]
                                   if keyword in text_lower)
        medium_priority_matches = sum(1 for keyword in self.crypto_keywords["medium_priority"]
                                     if keyword in text_lower)
        
        # Calculate relevance score
        relevance = (high_priority_matches * 0.3 + medium_priority_matches * 0.1)
        return min(relevance, 1.0)
    
    def _should_use_gemma3(self, text: str) -> bool:
        """Determine if Gemma-3 should be used for this text."""
        # Always use Gemma-3 if available (no ONNX fallback)
        return self.gemma3_analyzer is not None
    
    def _normalize_response(self, response: Dict, analyzer_type: str) -> Dict:
        """Normalize responses from different analyzers to consistent format."""
        if not response:
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "analyzer_used": analyzer_type,
                "reasoning": "analysis_failed"
            }
        
        # Handle Gemma-3 response
        if analyzer_type == "gemma3":
            return {
                "sentiment": response.get("sentiment", "NEUTRAL").lower(),
                "confidence": response.get("confidence", 0.0),
                "analyzer_used": "gemma3",
                "reasoning": response.get("reasoning", "gemma3_analysis")
            }
        
        # Handle online API response (future extension)
        elif analyzer_type == "online_api":
            sentiment = response.get("sentiment", "neutral").lower()
            
            # Map common sentiment values
            sentiment_mapping = {
                "positive": "bullish",
                "negative": "bearish",
                "neutral": "neutral"
            }
            
            return {
                "sentiment": sentiment_mapping.get(sentiment, sentiment),
                "confidence": response.get("confidence", 0.7),
                "analyzer_used": "online_api",
                "reasoning": "online_api_analysis"
            }
        
        return response
    
    def analyze(self, text: str) -> Optional[Dict]:
        """
        Analyze sentiment using the most appropriate analyzer.
        
        Args:
            text: Text to analyze
            
        Returns:
            Normalized sentiment analysis result
        """
        if not text or not text.strip():
            return None
        
        start_time = time.time()
        result = None
        analyzer_used = None
        
        try:
            # Use Gemma-3 analyzer
            if self.gemma3_analyzer:
                try:
                    result = self.gemma3_analyzer.analyze(text)
                    analyzer_used = "gemma3"
                    self.stats["gemma3_used"] += 1
                    
                except Exception as e:
                    log.warning(f"Gemma-3 analysis failed: {e}")
                    result = None
                    self.stats["fallbacks"] += 1
            
            # Normalize response
            if result:
                result = self._normalize_response(result, analyzer_used)
            
            # Update performance stats
            latency = time.time() - start_time
            self.stats["avg_latency"] = (
                (self.stats["avg_latency"] * self.stats["total_analyses"] + latency) /
                (self.stats["total_analyses"] + 1)
            )
            self.stats["total_analyses"] += 1
            
            log.debug(f"Sentiment analysis ({analyzer_used}): '{text[:50]}...' -> {result}")
            return result
            
        except Exception as e:
            log.error(f"Hybrid sentiment analysis failed: {e}", exc_info=True)
            return None
    
    def analyze_batch(self, texts: List[str]) -> List[Optional[Dict]]:
        """Analyze multiple texts efficiently."""
        if not texts:
            return []
        
        results = []
        
        # Initialize results array
        results = [None] * len(texts)
        
        # Process all texts with Gemma-3
        if self.gemma3_analyzer:
            try:
                batch_results = self.gemma3_analyzer.analyze_batch(texts)
                for idx, result in enumerate(batch_results):
                    results[idx] = self._normalize_response(result, "gemma3")
                    self.stats["gemma3_used"] += 1
            except Exception as e:
                log.warning(f"Gemma-3 batch analysis failed: {e}")
                # Fallback to individual analysis
                for idx, text in enumerate(texts):
                    results[idx] = self.analyze(text)
        
        # Handle any remaining None results
        for i, result in enumerate(results):
            if result is None:
                results[i] = self.analyze(texts[i])
        
        return results
    
    def get_stats(self) -> Dict:
        """Get performance and usage statistics."""
        total_analyses = self.stats["total_analyses"]
        
        return {
            "total_analyses": total_analyses,
            "gemma3_usage": f"{(self.stats['gemma3_used'] / max(total_analyses, 1)) * 100:.1f}%",
            "fallback_rate": f"{(self.stats['fallbacks'] / max(total_analyses, 1)) * 100:.1f}%",
            "avg_latency_ms": f"{self.stats['avg_latency'] * 1000:.1f}ms",
            "gemma3_available": self.gemma3_analyzer is not None
        }
    
    def get_model_status(self) -> Dict:
        """Get detailed status of both models."""
        status = {
            "gemma3": {
                "available": self.gemma3_analyzer is not None,
                "loaded": False,
                "stats": {}
            }
        }
        
        if self.gemma3_analyzer:
            status["gemma3"]["loaded"] = self.gemma3_analyzer.available
            status["gemma3"]["stats"] = self.gemma3_analyzer.get_stats()
        
        return status


# Factory function for easy integration
def create_sentiment_analyzer(prefer_gemma3: bool = True) -> HybridSentimentAnalyzer:
    """Create and return a hybrid sentiment analyzer instance."""
    return HybridSentimentAnalyzer(prefer_gemma3=prefer_gemma3)


# Example usage
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    analyzer = create_sentiment_analyzer()
    
    test_texts = [
        "Bitcoin is going to the moon! 🚀",
        "This market crash is terrible",
        "The weather is nice today",
        "HODL diamond hands until 100k",
        "Generic positive sentiment text"
    ]
    
    print("Hybrid Sentiment Analysis Test:")
    print("=" * 40)
    
    for text in test_texts:
        result = analyzer.analyze(text)
        print(f"Text: {text}")
        print(f"Result: {result}")
        print("-" * 30)
    
    print("\nPerformance Stats:")
    stats = analyzer.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")