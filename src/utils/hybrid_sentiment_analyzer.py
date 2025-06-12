# Hybrid Sentiment Analyzer - Combines ONNX and Gemma-3-1b-it
# Provides intelligent routing between fast ONNX and accurate Gemma-3 analysis

import time
from typing import Dict, List, Optional, Union
from .logger import log

# Import both analyzers
try:
    from .sentiment_analyzer import SentimentAnalyzer as ONNXSentimentAnalyzer
    onnx_available = True
except ImportError:
    log.warning("ONNX Sentiment Analyzer not available")
    onnx_available = False

try:
    from .gemma3_sentiment_analyzer import Gemma3SentimentAnalyzer
    gemma3_available = True
except ImportError:
    log.warning("Gemma-3 Sentiment Analyzer not available")
    gemma3_available = False


class HybridSentimentAnalyzer:
    """
    Intelligent hybrid sentiment analyzer that combines ONNX and Gemma-3-1b-it.
    
    Strategy:
    - Use Gemma-3 for crypto-specific content (high accuracy)
    - Use ONNX for generic content (high speed)
    - Automatic fallback between models
    - Smart caching and batch processing
    """
    
    def __init__(self, prefer_gemma3: bool = True, onnx_fallback: bool = True):
        self.prefer_gemma3 = prefer_gemma3
        self.onnx_fallback = onnx_fallback
        
        # Initialize analyzers
        self.gemma3_analyzer = None
        self.onnx_analyzer = None
        
        # Performance tracking
        self.stats = {
            "gemma3_used": 0,
            "onnx_used": 0,
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
        
        # Initialize ONNX as fallback
        if onnx_available and self.onnx_fallback:
            try:
                log.info("Initializing ONNX sentiment analyzer as fallback...")
                self.onnx_analyzer = ONNXSentimentAnalyzer()
                
                if self.onnx_analyzer.session:
                    log.info("ONNX sentiment analyzer ready")
                else:
                    log.warning("ONNX failed to load properly")
                    self.onnx_analyzer = None
                    
            except Exception as e:
                log.error(f"Failed to initialize ONNX analyzer: {e}")
                self.onnx_analyzer = None
        
        # Log final status
        gemma3_status = "✅" if self.gemma3_analyzer else "❌"
        onnx_status = "✅" if self.onnx_analyzer else "❌"
        log.info(f"Hybrid Sentiment Analyzer Status: Gemma-3 {gemma3_status} | ONNX {onnx_status}")
    
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
        if not self.gemma3_analyzer:
            return False
        
        relevance = self._calculate_crypto_relevance(text)
        
        # Use Gemma-3 for crypto-relevant content
        return relevance >= 0.3
    
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
        
        # Handle ONNX response
        elif analyzer_type == "onnx":
            sentiment = response.get("sentiment", "neutral").lower()
            
            # Map common sentiment values
            sentiment_mapping = {
                "positive": "bullish",
                "negative": "bearish",
                "neutral": "neutral"
            }
            
            return {
                "sentiment": sentiment_mapping.get(sentiment, sentiment),
                "confidence": 0.7,  # Default confidence for ONNX
                "analyzer_used": "onnx",
                "reasoning": "onnx_analysis"
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
            # Decide which analyzer to use
            use_gemma3 = self._should_use_gemma3(text)
            
            if use_gemma3 and self.gemma3_analyzer:
                # Use Gemma-3 for crypto content
                try:
                    result = self.gemma3_analyzer.analyze(text)
                    analyzer_used = "gemma3"
                    self.stats["gemma3_used"] += 1
                    
                except Exception as e:
                    log.warning(f"Gemma-3 analysis failed: {e}")
                    result = None
            
            # Fallback to ONNX if needed
            if not result and self.onnx_analyzer:
                try:
                    result = self.onnx_analyzer.analyze(text)
                    analyzer_used = "onnx"
                    self.stats["onnx_used"] += 1
                    
                    if use_gemma3:  # This was a fallback
                        self.stats["fallbacks"] += 1
                        
                except Exception as e:
                    log.warning(f"ONNX analysis failed: {e}")
                    result = None
            
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
        crypto_texts = []
        generic_texts = []
        crypto_indices = []
        generic_indices = []
        
        # Separate crypto-relevant from generic texts
        for i, text in enumerate(texts):
            if self._should_use_gemma3(text):
                crypto_texts.append(text)
                crypto_indices.append(i)
            else:
                generic_texts.append(text)
                generic_indices.append(i)
        
        # Initialize results array
        results = [None] * len(texts)
        
        # Process crypto texts with Gemma-3
        if crypto_texts and self.gemma3_analyzer:
            try:
                crypto_results = self.gemma3_analyzer.analyze_batch(crypto_texts)
                for idx, result in zip(crypto_indices, crypto_results):
                    results[idx] = self._normalize_response(result, "gemma3")
                    self.stats["gemma3_used"] += 1
            except Exception as e:
                log.warning(f"Gemma-3 batch analysis failed: {e}")
                # Fallback individual analysis
                for idx, text in zip(crypto_indices, crypto_texts):
                    results[idx] = self.analyze(text)
        
        # Process generic texts with ONNX
        if generic_texts and self.onnx_analyzer:
            try:
                for idx, text in zip(generic_indices, generic_texts):
                    result = self.onnx_analyzer.analyze(text)
                    results[idx] = self._normalize_response(result, "onnx")
                    self.stats["onnx_used"] += 1
            except Exception as e:
                log.warning(f"ONNX batch analysis failed: {e}")
                # Fallback individual analysis
                for idx, text in zip(generic_indices, generic_texts):
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
            "onnx_usage": f"{(self.stats['onnx_used'] / max(total_analyses, 1)) * 100:.1f}%",
            "fallback_rate": f"{(self.stats['fallbacks'] / max(total_analyses, 1)) * 100:.1f}%",
            "avg_latency_ms": f"{self.stats['avg_latency'] * 1000:.1f}ms",
            "gemma3_available": self.gemma3_analyzer is not None,
            "onnx_available": self.onnx_analyzer is not None
        }
    
    def get_model_status(self) -> Dict:
        """Get detailed status of both models."""
        status = {
            "gemma3": {
                "available": self.gemma3_analyzer is not None,
                "loaded": False,
                "stats": {}
            },
            "onnx": {
                "available": self.onnx_analyzer is not None,
                "loaded": False,
                "stats": {}
            }
        }
        
        if self.gemma3_analyzer:
            status["gemma3"]["loaded"] = self.gemma3_analyzer.available
            status["gemma3"]["stats"] = self.gemma3_analyzer.get_stats()
        
        if self.onnx_analyzer:
            status["onnx"]["loaded"] = self.onnx_analyzer.session is not None
        
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