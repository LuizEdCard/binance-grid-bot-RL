# Sentiment Agent - Distributed sentiment analysis system
import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np

from utils.logger import setup_logger
from utils.hybrid_sentiment_analyzer import HybridSentimentAnalyzer
from utils.social_listener import SocialListener

log = setup_logger("sentiment_agent")


class SentimentSource(ABC):
    """Abstract base class for sentiment data sources."""
    
    @abstractmethod
    def fetch_data(self, config: dict) -> List[str]:
        """Fetch raw text data from the source."""
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Get the name of this sentiment source."""
        pass


class RedditSentimentSource(SentimentSource):
    """Reddit sentiment data source."""
    
    def __init__(self):
        self.listener = SocialListener()
        self.source_name = "reddit"
    
    def fetch_data(self, config: dict) -> List[str]:
        """Fetch text data from Reddit."""
        texts = []
        reddit_config = config.get("reddit", {})
        
        if not reddit_config.get("enabled", False):
            return texts
        
        try:
            subreddits = reddit_config.get("subreddits", [])
            posts_limit = reddit_config.get("posts_limit_per_subreddit", 10)
            comments_limit = reddit_config.get("comments_limit_per_post", 5)
            time_filter = reddit_config.get("time_filter", "day")
            
            for subreddit in subreddits:
                try:
                    posts = self.listener.get_subreddit_posts(
                        subreddit, limit=posts_limit, time_filter=time_filter
                    )
                    
                    for post in posts:
                        # Add post title and text
                        if post.get("title"):
                            texts.append(post["title"])
                        if post.get("selftext"):
                            texts.append(post["selftext"])
                        
                        # Add comments
                        comments = self.listener.get_post_comments(
                            post["id"], limit=comments_limit
                        )
                        texts.extend(comments)
                        
                        # Avoid hitting API limits
                        time.sleep(0.2)
                
                except Exception as e:
                    log.error(f"Error fetching Reddit data from r/{subreddit}: {e}")
                    
        except Exception as e:
            log.error(f"Error in Reddit sentiment source: {e}")
        
        log.info(f"Reddit source collected {len(texts)} texts")
        return texts
    
    def get_source_name(self) -> str:
        return self.source_name


class BinanceNewsSentimentSource(SentimentSource):
    """Binance news sentiment data source."""
    
    def __init__(self):
        self.source_name = "binance_news"
    
    def fetch_data(self, config: dict) -> List[str]:
        """Fetch text data from Binance news sources."""
        texts = []
        binance_config = config.get("binance_news", {})
        
        if not binance_config.get("enabled", False):
            return texts
        
        try:
            # Import here to avoid circular imports
            from utils.binance_news_listener import BinanceNewsListener
            
            # Get configuration
            hours_back = binance_config.get("hours_back", 24)
            min_relevance = binance_config.get("min_relevance_score", 0.2)
            max_news = binance_config.get("max_news_per_fetch", 20)
            
            async def _fetch_news():
                async with BinanceNewsListener() as listener:
                    # Test connection first
                    if not await listener.test_connection():
                        log.warning("Cannot connect to Binance news API")
                        return []
                    
                    # Set listener configuration
                    listener.max_news_per_fetch = max_news
                    
                    # Fetch recent news based on config
                    news_items = await listener.fetch_all_recent_news(hours_back=hours_back)
                    
                    # Filter by relevance
                    relevant_news = [
                        news for news in news_items 
                        if news.relevance_score >= min_relevance
                    ]
                    
                    # Extract text from news items
                    news_texts = []
                    for news in relevant_news:
                        # Add title
                        if news.title:
                            news_texts.append(news.title)
                        
                        # Add body excerpt (first 200 chars to avoid overwhelming)
                        if news.body:
                            body_excerpt = news.body[:200] + "..." if len(news.body) > 200 else news.body
                            news_texts.append(body_excerpt)
                    
                    return news_texts
            
            # Run async function
            try:
                # Tentar usar loop existente
                loop = asyncio.get_running_loop()
                # Se há um loop rodando, usar ThreadPoolExecutor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _fetch_news())
                    texts = future.result()
            except RuntimeError:
                # Não há loop rodando, criar um novo
                texts = asyncio.run(_fetch_news())
                    
        except Exception as e:
            log.error(f"Error in Binance news sentiment source: {e}")
        
        log.info(f"Binance news source collected {len(texts)} texts")
        return texts
    
    def get_source_name(self) -> str:
        return self.source_name


class TwitterSentimentSource(SentimentSource):
    """Twitter sentiment data source (placeholder for future implementation)."""
    
    def __init__(self):
        self.source_name = "twitter"
    
    def fetch_data(self, config: dict) -> List[str]:
        """Fetch text data from Twitter."""
        # Placeholder - could integrate with Twitter API v2
        log.debug("Twitter sentiment source not yet implemented")
        return []
    
    def get_source_name(self) -> str:
        return self.source_name


class SentimentAggregator:
    """Aggregates and weights sentiment from multiple sources."""
    
    def __init__(self, config: dict):
        self.config = config
        self.source_weights = config.get("source_weights", {
            "reddit": 0.6,
            "news": 0.3,
            "twitter": 0.1
        })
        
        # History for smoothing
        smoothing_window = config.get("smoothing_window", 10)
        self.sentiment_history = deque(maxlen=smoothing_window)
        self.source_history = {
            source: deque(maxlen=smoothing_window) 
            for source in self.source_weights.keys()
        }
    
    def aggregate_sentiments(self, source_results: Dict[str, Dict]) -> Dict:
        """Aggregate sentiment results from multiple sources."""
        try:
            total_weight = 0
            weighted_score = 0
            source_scores = {}
            
            for source_name, result in source_results.items():
                if not result or "score" not in result:
                    continue
                
                weight = self.source_weights.get(source_name, 0)
                score = result["score"]
                
                weighted_score += score * weight
                total_weight += weight
                source_scores[source_name] = score
                
                # Store in source history
                if source_name in self.source_history:
                    self.source_history[source_name].append(score)
            
            # Calculate final score
            if total_weight > 0:
                final_score = weighted_score / total_weight
            else:
                final_score = 0.0
            
            # Add to global history
            self.sentiment_history.append(final_score)
            
            # Calculate smoothed score
            smoothed_score = np.mean(list(self.sentiment_history)) if self.sentiment_history else final_score
            
            return {
                "raw_score": final_score,
                "smoothed_score": smoothed_score,
                "source_scores": source_scores,
                "total_weight": total_weight,
                "history_size": len(self.sentiment_history)
            }
            
        except Exception as e:
            log.error(f"Error aggregating sentiments: {e}")
            return {
                "raw_score": 0.0,
                "smoothed_score": 0.0,
                "source_scores": {},
                "total_weight": 0,
                "history_size": 0
            }
    
    def get_source_statistics(self) -> Dict:
        """Get statistics for each sentiment source."""
        stats = {}
        
        for source_name, history in self.source_history.items():
            if history:
                scores = list(history)
                stats[source_name] = {
                    "avg_score": np.mean(scores),
                    "std_score": np.std(scores),
                    "min_score": np.min(scores),
                    "max_score": np.max(scores),
                    "samples": len(scores)
                }
            else:
                stats[source_name] = {
                    "avg_score": 0.0,
                    "std_score": 0.0,
                    "min_score": 0.0,
                    "max_score": 0.0,
                    "samples": 0
                }
        
        return stats


class SentimentAgent:
    """Distributed sentiment analysis agent."""
    
    def __init__(self, config: dict):
        self.config = config
        self.sentiment_config = config.get("sentiment_analysis", {})
        
        # Initialize components
        try:
            from utils.hybrid_sentiment_analyzer import HybridSentimentAnalyzer
            self.analyzer = HybridSentimentAnalyzer(prefer_gemma3=True)
            log.info("Using Hybrid Sentiment Analyzer (Gemma-3 + ONNX fallback)")
        except ImportError:
            log.warning("Hybrid Sentiment Analyzer not available, using fallback")
            self.analyzer = None
        
        self.aggregator = SentimentAggregator(self.sentiment_config)
        
        # Initialize sources
        self.sources = {
            "reddit": RedditSentimentSource(),
            "binance_news": BinanceNewsSentimentSource(),
            "twitter": TwitterSentimentSource()
        }
        
        # Threading
        self.stop_event = threading.Event()
        self.analysis_thread = None
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="SentimentWorker")
        
        # State
        self.latest_sentiment = {
            "raw_score": 0.0,
            "smoothed_score": 0.0,
            "source_scores": {},
            "timestamp": time.time()
        }
        self.sentiment_lock = threading.RLock()
        
        # Callbacks
        self.sentiment_callbacks = []
        
        # Performance stats
        self.stats = {
            "analysis_cycles": 0,
            "texts_analyzed": 0,
            "avg_cycle_time": 0.0,
            "errors": 0
        }
        
        log.info("SentimentAgent initialized with distributed analysis")
    
    def start(self) -> None:
        """Start the sentiment analysis agent."""
        if not self.sentiment_config.get("enabled", False):
            log.info("Sentiment analysis disabled in config")
            return
        
        # Check if analyzer is available (works with both ONNX and Hybrid analyzers)
        analyzer_available = False
        if hasattr(self.analyzer, 'session') and self.analyzer.session:
            analyzer_available = True  # ONNX analyzer
        elif hasattr(self.analyzer, 'gemma3_analyzer') and self.analyzer.gemma3_analyzer:
            analyzer_available = True  # Hybrid analyzer with Gemma-3
        elif hasattr(self.analyzer, 'onnx_analyzer') and self.analyzer.onnx_analyzer:
            analyzer_available = True  # Hybrid analyzer with ONNX fallback
        
        if not analyzer_available:
            log.error("Sentiment analyzer not loaded, cannot start agent")
            return
        
        self.stop_event.clear()
        self.analysis_thread = threading.Thread(
            target=self._analysis_loop,
            daemon=True,
            name="SentimentAgent-Analysis"
        )
        self.analysis_thread.start()
        
        log.info("SentimentAgent started")
    
    def stop(self) -> None:
        """Stop the sentiment analysis agent."""
        log.info("Stopping SentimentAgent...")
        self.stop_event.set()
        
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analysis_thread.join(timeout=10)
        
        self.executor.shutdown(wait=True)
        log.info("SentimentAgent stopped")
    
    def register_sentiment_callback(self, callback_func) -> None:
        """Register a callback for sentiment updates."""
        self.sentiment_callbacks.append(callback_func)
        log.debug("Registered sentiment callback")
    
    def unregister_sentiment_callback(self, callback_func) -> None:
        """Unregister a sentiment callback."""
        if callback_func in self.sentiment_callbacks:
            self.sentiment_callbacks.remove(callback_func)
            log.debug("Unregistered sentiment callback")
    
    def get_latest_sentiment(self, smoothed: bool = True) -> float:
        """Get the latest sentiment score."""
        with self.sentiment_lock:
            if smoothed:
                return self.latest_sentiment["smoothed_score"]
            else:
                return self.latest_sentiment["raw_score"]
    
    def get_detailed_sentiment(self) -> Dict:
        """Get detailed sentiment information."""
        with self.sentiment_lock:
            return self.latest_sentiment.copy()
    
    def _analysis_loop(self) -> None:
        """Main sentiment analysis loop."""
        fetch_interval = self.sentiment_config.get("fetch_interval_minutes", 60) * 60
        
        while not self.stop_event.is_set():
            cycle_start = time.time()
            
            try:
                log.info("Starting sentiment analysis cycle...")
                
                # Fetch data from all sources in parallel
                source_futures = {}
                for source_name, source in self.sources.items():
                    future = self.executor.submit(self._fetch_source_data, source_name, source)
                    source_futures[source_name] = future
                
                # Collect results
                source_texts = {}
                for source_name, future in source_futures.items():
                    try:
                        texts = future.result(timeout=30)  # 30 second timeout per source
                        source_texts[source_name] = texts
                    except Exception as e:
                        log.error(f"Error fetching data from {source_name}: {e}")
                        source_texts[source_name] = []
                
                # Analyze sentiments in parallel
                source_results = {}
                analysis_futures = {}
                
                for source_name, texts in source_texts.items():
                    if texts:
                        future = self.executor.submit(self._analyze_texts, source_name, texts)
                        analysis_futures[source_name] = future
                
                # Collect analysis results
                for source_name, future in analysis_futures.items():
                    try:
                        result = future.result(timeout=60)  # 60 second timeout for analysis
                        source_results[source_name] = result
                    except Exception as e:
                        log.error(f"Error analyzing {source_name} sentiment: {e}")
                        self.stats["errors"] += 1
                
                # Aggregate results
                aggregated = self.aggregator.aggregate_sentiments(source_results)
                
                # Update latest sentiment
                with self.sentiment_lock:
                    self.latest_sentiment.update({
                        "raw_score": aggregated["raw_score"],
                        "smoothed_score": aggregated["smoothed_score"],
                        "source_scores": aggregated["source_scores"],
                        "timestamp": time.time()
                    })
                
                # Notify callbacks
                self._notify_callbacks(aggregated)
                
                # Update stats
                self.stats["analysis_cycles"] += 1
                cycle_time = time.time() - cycle_start
                self.stats["avg_cycle_time"] = (
                    (self.stats["avg_cycle_time"] * (self.stats["analysis_cycles"] - 1) + cycle_time) 
                    / self.stats["analysis_cycles"]
                )
                
                log.info(
                    f"Sentiment analysis cycle completed in {cycle_time:.2f}s. "
                    f"Raw: {aggregated['raw_score']:.4f}, "
                    f"Smoothed: {aggregated['smoothed_score']:.4f}"
                )
                
                # Wait for next cycle
                elapsed = time.time() - cycle_start
                wait_time = max(0, fetch_interval - elapsed)
                if wait_time > 0:
                    self.stop_event.wait(wait_time)
                
            except Exception as e:
                log.error(f"Error in sentiment analysis loop: {e}", exc_info=True)
                self.stats["errors"] += 1
                self.stop_event.wait(60)  # Wait 1 minute before retry
    
    def _fetch_source_data(self, source_name: str, source: SentimentSource) -> List[str]:
        """Fetch data from a single source."""
        try:
            source_config = self.sentiment_config.get(source_name, {})
            if not source_config.get("enabled", False):
                return []
            
            texts = source.fetch_data(source_config)
            log.debug(f"Fetched {len(texts)} texts from {source_name}")
            return texts
            
        except Exception as e:
            log.error(f"Error fetching data from {source_name}: {e}")
            return []
    
    def _analyze_texts(self, source_name: str, texts: List[str]) -> Dict:
        """Analyze sentiment for texts from a source."""
        if not texts:
            return {"score": 0.0, "count": 0, "breakdown": {"positive": 0, "negative": 0, "neutral": 0}}
        
        try:
            sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
            analyzed_count = 0
            
            for text in texts:
                if not text or len(text.strip()) == 0:
                    continue
                
                try:
                    result = self.analyzer.analyze(text)
                    if result and "sentiment" in result:
                        sentiment = result["sentiment"].lower()
                        if sentiment in sentiment_counts:
                            sentiment_counts[sentiment] += 1
                            analyzed_count += 1
                        
                except Exception as e:
                    log.debug(f"Error analyzing individual text: {e}")
                    continue
            
            # Calculate score
            total_valid = sum(sentiment_counts.values())
            if total_valid > 0:
                score = (sentiment_counts["positive"] - sentiment_counts["negative"]) / total_valid
            else:
                score = 0.0
            
            self.stats["texts_analyzed"] += analyzed_count
            
            result = {
                "score": score,
                "count": analyzed_count,
                "breakdown": sentiment_counts
            }
            
            log.debug(f"{source_name} analysis: {result}")
            return result
            
        except Exception as e:
            log.error(f"Error analyzing {source_name} texts: {e}")
            return {"score": 0.0, "count": 0, "breakdown": {"positive": 0, "negative": 0, "neutral": 0}}
    
    def _notify_callbacks(self, sentiment_data: Dict) -> None:
        """Notify registered callbacks of sentiment updates."""
        for callback in self.sentiment_callbacks:
            try:
                callback(sentiment_data)
            except Exception as e:
                log.error(f"Error notifying sentiment callback: {e}")
    
    def get_statistics(self) -> Dict:
        """Get sentiment agent statistics."""
        source_stats = self.aggregator.get_source_statistics()
        
        return {
            "analysis_cycles": self.stats["analysis_cycles"],
            "texts_analyzed": self.stats["texts_analyzed"],
            "avg_cycle_time": self.stats["avg_cycle_time"],
            "errors": self.stats["errors"],
            "source_statistics": source_stats,
            "latest_sentiment": self.get_detailed_sentiment()
        }
    
    def get_sentiment_history(self, limit: int = 20) -> Dict:
        """Get recent sentiment history from the aggregator."""
        history = {}
        for source_name, source_history in self.aggregator.source_history.items():
            history[source_name] = list(source_history)[-limit:]
        return history