# Data Agent - Centralizes market data collection and caching
import asyncio
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import aiohttp
import numpy as np
import pandas as pd

from utils.api_client import APIClient
from utils.logger import setup_logger

log = setup_logger("data_agent")


class DataCache:
    """Thread-safe cache for market data with TTL support."""
    
    def __init__(self, default_ttl_seconds: int = 60):
        self.default_ttl = default_ttl_seconds
        self.cache = {}
        self.timestamps = {}
        self.lock = threading.RLock()
    
    def get(self, key: str, ttl_seconds: Optional[int] = None) -> Optional[any]:
        with self.lock:
            if key not in self.cache:
                return None
            
            ttl = ttl_seconds or self.default_ttl
            if time.time() - self.timestamps[key] > ttl:
                del self.cache[key]
                del self.timestamps[key]
                return None
            
            return self.cache[key]
    
    def set(self, key: str, value: any) -> None:
        with self.lock:
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def clear_expired(self) -> None:
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, timestamp in self.timestamps.items()
                if current_time - timestamp > self.default_ttl
            ]
            for key in expired_keys:
                if key in self.cache:
                    del self.cache[key]
                if key in self.timestamps:
                    del self.timestamps[key]
    
    def clear_all(self) -> None:
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()


class DataAgent:
    """Centralized data collection and distribution agent."""
    
    def __init__(self, config: dict, api_client: APIClient):
        self.config = config
        self.api_client = api_client
        
        # Cache configurations
        self.ticker_cache = DataCache(default_ttl_seconds=30)  # Tickers updated frequently
        self.kline_cache = DataCache(default_ttl_seconds=60)   # Klines less frequent
        self.position_cache = DataCache(default_ttl_seconds=10) # Positions very frequent
        self.balance_cache = DataCache(default_ttl_seconds=30)  # Balance moderate
        
        # Data aggregation
        self.subscribers = defaultdict(list)  # symbol -> [callback_functions]
        self.market_data_history = defaultdict(lambda: deque(maxlen=100))
        
        # Threading
        self.stop_event = threading.Event()
        self.data_thread = None
        self.cleanup_thread = None
        
        # Performance metrics
        self.stats = {
            'api_calls_saved': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'data_updates': 0
        }
        
        log.info("DataAgent initialized with intelligent caching")
    
    def start(self) -> None:
        """Start the data agent background processes."""
        self.stop_event.clear()
        
        # Start data collection thread
        self.data_thread = threading.Thread(
            target=self._data_collection_loop,
            daemon=True,
            name="DataAgent-Collection"
        )
        self.data_thread.start()
        
        # Start cache cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cache_cleanup_loop,
            daemon=True,
            name="DataAgent-Cleanup"
        )
        self.cleanup_thread.start()
        
        log.info("DataAgent started with background processes")
    
    def stop(self) -> None:
        """Stop the data agent."""
        log.info("Stopping DataAgent...")
        self.stop_event.set()
        
        if self.data_thread and self.data_thread.is_alive():
            self.data_thread.join(timeout=5)
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        
        log.info("DataAgent stopped")
    
    def subscribe_to_symbol(self, symbol: str, callback_func) -> None:
        """Subscribe to data updates for a specific symbol."""
        self.subscribers[symbol].append(callback_func)
        log.debug(f"Subscribed to {symbol} data updates")
    
    def unsubscribe_from_symbol(self, symbol: str, callback_func) -> None:
        """Unsubscribe from data updates for a specific symbol."""
        if symbol in self.subscribers and callback_func in self.subscribers[symbol]:
            self.subscribers[symbol].remove(callback_func)
            log.debug(f"Unsubscribed from {symbol} data updates")
    
    def get_ticker_data(self, symbol: str = None, market_type: str = "futures") -> Optional[Dict]:
        """Get ticker data with caching."""
        cache_key = f"ticker_{market_type}_{symbol or 'all'}"
        cached_data = self.ticker_cache.get(cache_key)
        
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            log.debug(f"Cache hit for ticker data: {cache_key}")
            return cached_data
        
        self.stats['cache_misses'] += 1
        log.debug(f"Cache miss for ticker data: {cache_key}")
        
        try:
            if market_type == "futures":
                if symbol:
                    data = self.api_client.get_futures_ticker(symbol=symbol)
                else:
                    data = self.api_client.get_futures_ticker()
            else:  # spot
                if symbol:
                    data = self.api_client.get_spot_ticker(symbol=symbol)
                else:
                    data = self.api_client.get_spot_ticker()
            
            if data:
                self.ticker_cache.set(cache_key, data)
                log.debug(f"Cached ticker data: {cache_key}")
            
            return data
            
        except Exception as e:
            log.error(f"Error fetching ticker data for {symbol}: {e}")
            return None
    
    def get_kline_data(
        self, 
        symbol: str, 
        interval: str = "1h", 
        limit: int = 100,
        market_type: str = "futures"
    ) -> Optional[pd.DataFrame]:
        """Get kline data with caching and DataFrame conversion."""
        cache_key = f"kline_{market_type}_{symbol}_{interval}_{limit}"
        cached_data = self.kline_cache.get(cache_key)
        
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            log.debug(f"Cache hit for kline data: {cache_key}")
            return cached_data
        
        self.stats['cache_misses'] += 1
        log.debug(f"Cache miss for kline data: {cache_key}")
        
        try:
            if market_type == "futures":
                klines = self.api_client.get_futures_klines(symbol, interval, limit)
            else:  # spot
                klines = self.api_client.get_spot_klines(symbol, interval, limit)
            
            if klines and len(klines) > 0:
                df = pd.DataFrame(
                    klines,
                    columns=[
                        "Open time", "Open", "High", "Low", "Close", "Volume",
                        "Close time", "Quote asset volume", "Number of trades",
                        "Taker buy base asset volume", "Taker buy quote asset volume", "Ignore"
                    ],
                )
                
                # Convert numeric columns
                numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col])
                
                # Add timestamp
                df['timestamp'] = pd.to_datetime(df['Open time'], unit='ms')
                
                self.kline_cache.set(cache_key, df)
                log.debug(f"Cached kline data: {cache_key}")
                return df
            
            return None
            
        except Exception as e:
            log.error(f"Error fetching kline data for {symbol}: {e}")
            return None
    
    def get_position_data(self, symbol: str) -> Optional[Dict]:
        """Get position data with caching."""
        cache_key = f"position_{symbol}"
        cached_data = self.position_cache.get(cache_key)
        
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            return cached_data
        
        self.stats['cache_misses'] += 1
        
        try:
            data = self.api_client.get_futures_position(symbol)
            if data:
                self.position_cache.set(cache_key, data)
            return data
            
        except Exception as e:
            log.error(f"Error fetching position data for {symbol}: {e}")
            return None
    
    def get_balance_data(self, market_type: str = "futures") -> Optional[Dict]:
        """Get balance data with caching."""
        cache_key = f"balance_{market_type}"
        cached_data = self.balance_cache.get(cache_key)
        
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            return cached_data
        
        self.stats['cache_misses'] += 1
        
        try:
            if market_type == "futures":
                data = self.api_client.get_futures_balance()
            else:  # spot
                data = self.api_client.get_spot_balance()
            
            if data:
                self.balance_cache.set(cache_key, data)
            return data
            
        except Exception as e:
            log.error(f"Error fetching balance data: {e}")
            return None
    
    def batch_fetch_data(self, symbols: List[str], data_types: List[str]) -> Dict:
        """Batch fetch multiple data types for multiple symbols."""
        results = {}
        
        for symbol in symbols:
            results[symbol] = {}
            
            for data_type in data_types:
                if data_type == "ticker":
                    results[symbol]["ticker"] = self.get_ticker_data(symbol)
                elif data_type == "klines":
                    results[symbol]["klines"] = self.get_kline_data(symbol)
                elif data_type == "position":
                    results[symbol]["position"] = self.get_position_data(symbol)
                elif data_type == "balance":
                    results[symbol]["balance"] = self.get_balance_data()
        
        return results
    
    def _data_collection_loop(self) -> None:
        """Background data collection and distribution loop."""
        collection_interval = 30  # seconds
        
        while not self.stop_event.is_set():
            try:
                start_time = time.time()
                
                # Collect data for subscribed symbols
                for symbol in self.subscribers.keys():
                    self._collect_and_distribute_data(symbol)
                
                # Update statistics
                self.stats['data_updates'] += 1
                
                # Calculate and log performance
                elapsed = time.time() - start_time
                if self.stats['data_updates'] % 10 == 0:
                    self._log_performance_stats()
                
                # Wait for next collection cycle
                wait_time = max(0, collection_interval - elapsed)
                if wait_time > 0:
                    self.stop_event.wait(wait_time)
                
            except Exception as e:
                log.error(f"Error in data collection loop: {e}", exc_info=True)
                self.stop_event.wait(10)  # Wait before retry
    
    def _collect_and_distribute_data(self, symbol: str) -> None:
        """Collect fresh data for a symbol and notify subscribers."""
        try:
            # Collect fresh data
            ticker_data = self.get_ticker_data(symbol)
            kline_data = self.get_kline_data(symbol, limit=50)
            position_data = self.get_position_data(symbol)
            
            # Prepare data package
            data_package = {
                'symbol': symbol,
                'ticker': ticker_data,
                'klines': kline_data,
                'position': position_data,
                'timestamp': time.time()
            }
            
            # Store in history
            self.market_data_history[symbol].append(data_package)
            
            # Notify subscribers
            for callback in self.subscribers[symbol]:
                try:
                    callback(data_package)
                except Exception as e:
                    log.error(f"Error notifying subscriber for {symbol}: {e}")
        
        except Exception as e:
            log.error(f"Error collecting data for {symbol}: {e}")
    
    def _cache_cleanup_loop(self) -> None:
        """Background cache cleanup loop."""
        cleanup_interval = 300  # 5 minutes
        
        while not self.stop_event.is_set():
            try:
                log.debug("Running cache cleanup...")
                
                self.ticker_cache.clear_expired()
                self.kline_cache.clear_expired()
                self.position_cache.clear_expired()
                self.balance_cache.clear_expired()
                
                log.debug("Cache cleanup completed")
                
            except Exception as e:
                log.error(f"Error in cache cleanup: {e}")
            
            self.stop_event.wait(cleanup_interval)
    
    def _log_performance_stats(self) -> None:
        """Log performance statistics."""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        log.info(
            f"DataAgent Stats - Cache Hit Rate: {hit_rate:.1f}%, "
            f"API Calls Saved: {self.stats['api_calls_saved']}, "
            f"Data Updates: {self.stats['data_updates']}"
        )
    
    def get_statistics(self) -> Dict:
        """Get current performance statistics."""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hit_rate': hit_rate,
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'api_calls_saved': self.stats['api_calls_saved'],
            'data_updates': self.stats['data_updates']
        }