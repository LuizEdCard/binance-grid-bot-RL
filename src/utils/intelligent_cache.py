# Intelligent Cache System - Advanced caching with predictive prefetching
import hashlib
import json
import pickle
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from utils.logger import setup_logger

log = setup_logger("intelligent_cache")


class CacheEntry:
    """Represents a single cache entry with metadata."""
    
    def __init__(self, key: str, value: Any, ttl: float, priority: int = 1):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.priority = priority
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 1
        self.size = self._calculate_size(value)
    
    def _calculate_size(self, value: Any) -> int:
        """Estimate the size of the cached value."""
        try:
            return len(pickle.dumps(value))
        except:
            return len(str(value))
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.created_at > self.ttl
    
    def access(self) -> Any:
        """Access the cached value and update metadata."""
        self.last_accessed = time.time()
        self.access_count += 1
        return self.value
    
    def get_age(self) -> float:
        """Get the age of the cache entry in seconds."""
        return time.time() - self.created_at
    
    def get_access_frequency(self) -> float:
        """Get the access frequency (accesses per second)."""
        age = self.get_age()
        return self.access_count / age if age > 0 else 0


class AccessPattern:
    """Tracks access patterns for predictive caching."""
    
    def __init__(self, max_history: int = 1000):
        self.access_history = deque(maxlen=max_history)
        self.key_frequencies = defaultdict(int)
        self.key_timings = defaultdict(list)
        self.sequential_patterns = defaultdict(list)
        self.last_accessed_key = None
    
    def record_access(self, key: str) -> None:
        """Record a cache access."""
        current_time = time.time()
        
        # Record access
        self.access_history.append((key, current_time))
        self.key_frequencies[key] += 1
        self.key_timings[key].append(current_time)
        
        # Track sequential patterns
        if self.last_accessed_key and self.last_accessed_key != key:
            self.sequential_patterns[self.last_accessed_key].append(key)
        
        self.last_accessed_key = key
        
        # Cleanup old timing data
        self._cleanup_old_timings()
    
    def _cleanup_old_timings(self) -> None:
        """Remove timing data older than 24 hours."""
        cutoff_time = time.time() - 86400  # 24 hours
        
        for key in list(self.key_timings.keys()):
            self.key_timings[key] = [
                t for t in self.key_timings[key] if t > cutoff_time
            ]
            if not self.key_timings[key]:
                del self.key_timings[key]
    
    def predict_next_keys(self, current_key: str, count: int = 5) -> List[str]:
        """Predict the next keys likely to be accessed."""
        predictions = []
        
        # Sequential pattern prediction
        if current_key in self.sequential_patterns:
            next_keys = self.sequential_patterns[current_key]
            # Count occurrences and sort by frequency
            key_counts = defaultdict(int)
            for key in next_keys:
                key_counts[key] += 1
            
            sorted_keys = sorted(key_counts.items(), key=lambda x: x[1], reverse=True)
            predictions.extend([key for key, _ in sorted_keys[:count]])
        
        # Frequency-based prediction
        frequent_keys = sorted(
            self.key_frequencies.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for key, _ in frequent_keys:
            if key not in predictions and key != current_key:
                predictions.append(key)
                if len(predictions) >= count:
                    break
        
        return predictions[:count]
    
    def get_access_probability(self, key: str) -> float:
        """Get the probability of a key being accessed soon."""
        if key not in self.key_frequencies:
            return 0.0
        
        # Base probability from frequency
        total_accesses = sum(self.key_frequencies.values())
        base_prob = self.key_frequencies[key] / total_accesses if total_accesses > 0 else 0
        
        # Time-based adjustment (recent access increases probability)
        if key in self.key_timings and self.key_timings[key]:
            last_access = max(self.key_timings[key])
            time_since_access = time.time() - last_access
            
            # Exponential decay with 1-hour half-life
            time_factor = np.exp(-time_since_access / 3600)
            return min(1.0, base_prob * (1 + time_factor))
        
        return base_prob


class IntelligentCache:
    """Advanced caching system with predictive prefetching and intelligent eviction."""
    
    def __init__(
        self,
        max_size_mb: int = 100,
        default_ttl: float = 300,
        enable_prefetching: bool = True,
        enable_compression: bool = True
    ):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.enable_prefetching = enable_prefetching
        self.enable_compression = enable_compression
        
        # Storage
        self.cache = {}  # key -> CacheEntry
        self.lock = threading.RLock()
        
        # Access pattern tracking
        self.access_pattern = AccessPattern()
        
        # Prefetching
        self.prefetch_queue = deque()
        self.prefetch_callbacks = {}  # key_pattern -> callback_function
        self.prefetch_thread = None
        self.prefetch_stop_event = threading.Event()
        
        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "prefetch_hits": 0,
            "prefetch_misses": 0,
            "total_size_bytes": 0,
            "avg_access_time": 0.0
        }
        
        # Cleanup thread
        self.cleanup_thread = None
        self.cleanup_stop_event = threading.Event()
        
        log.info(
            f"IntelligentCache initialized - Max Size: {max_size_mb}MB, "
            f"Default TTL: {default_ttl}s, Prefetching: {enable_prefetching}"
        )
        
        self._start_background_threads()
    
    def _start_background_threads(self) -> None:
        """Start background threads for prefetching and cleanup."""
        # Cleanup thread
        self.cleanup_stop_event.clear()
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="Cache-Cleanup"
        )
        self.cleanup_thread.start()
        
        # Prefetch thread
        if self.enable_prefetching:
            self.prefetch_stop_event.clear()
            self.prefetch_thread = threading.Thread(
                target=self._prefetch_loop,
                daemon=True,
                name="Cache-Prefetch"
            )
            self.prefetch_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        start_time = time.time()
        
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                
                if entry.is_expired():
                    del self.cache[key]
                    self.stats["misses"] += 1
                    self.stats["total_size_bytes"] -= entry.size
                    result = None
                else:
                    value = entry.access()
                    self.stats["hits"] += 1
                    result = value
            else:
                self.stats["misses"] += 1
                result = None
            
            # Record access pattern
            self.access_pattern.record_access(key)
            
            # Trigger predictive prefetching
            if self.enable_prefetching and result is not None:
                self._trigger_prefetch(key)
            
            # Update average access time
            access_time = time.time() - start_time
            total_accesses = self.stats["hits"] + self.stats["misses"]
            self.stats["avg_access_time"] = (
                (self.stats["avg_access_time"] * (total_accesses - 1) + access_time)
                / total_accesses
            )
            
            return result
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        priority: int = 1
    ) -> None:
        """Set a value in the cache."""
        if ttl is None:
            ttl = self.default_ttl
        
        with self.lock:
            # Create cache entry
            entry = CacheEntry(key, value, ttl, priority)
            
            # Check if we need to evict entries
            self._ensure_space(entry.size)
            
            # Remove existing entry if present
            if key in self.cache:
                old_entry = self.cache[key]
                self.stats["total_size_bytes"] -= old_entry.size
            
            # Add new entry
            self.cache[key] = entry
            self.stats["total_size_bytes"] += entry.size
            
            log.debug(f"Cached {key} (size: {entry.size} bytes, TTL: {ttl}s)")
    
    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                del self.cache[key]
                self.stats["total_size_bytes"] -= entry.size
                log.debug(f"Deleted {key} from cache")
                return True
            return False
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self.lock:
            self.cache.clear()
            self.stats["total_size_bytes"] = 0
            log.info("Cache cleared")
    
    def _ensure_space(self, required_size: int) -> None:
        """Ensure there's enough space in the cache."""
        while (self.stats["total_size_bytes"] + required_size > self.max_size_bytes 
               and self.cache):
            # Find entry to evict using intelligent scoring
            evict_key = self._select_eviction_candidate()
            if evict_key:
                entry = self.cache[evict_key]
                del self.cache[evict_key]
                self.stats["total_size_bytes"] -= entry.size
                self.stats["evictions"] += 1
                log.debug(f"Evicted {evict_key} (size: {entry.size} bytes)")
            else:
                break
    
    def _select_eviction_candidate(self) -> Optional[str]:
        """Select the best candidate for eviction using intelligent scoring."""
        if not self.cache:
            return None
        
        best_key = None
        best_score = float('inf')
        
        current_time = time.time()
        
        for key, entry in self.cache.items():
            # Calculate eviction score (lower is better for eviction)
            score = self._calculate_eviction_score(entry, current_time)
            
            if score < best_score:
                best_score = score
                best_key = key
        
        return best_key
    
    def _calculate_eviction_score(self, entry: CacheEntry, current_time: float) -> float:
        """Calculate an eviction score for a cache entry."""
        # Factors that make an entry a good eviction candidate:
        # 1. Low access frequency
        # 2. Large size (to free up more space)
        # 3. Old age
        # 4. Low priority
        # 5. Close to expiration
        
        age = current_time - entry.created_at
        time_to_expiry = entry.ttl - age
        access_freq = entry.get_access_frequency()
        
        # Normalize factors
        age_factor = min(1.0, age / 3600)  # Normalize to 1 hour
        size_factor = min(1.0, entry.size / (1024 * 1024))  # Normalize to 1MB
        freq_factor = 1.0 / (1.0 + access_freq)  # Inverse frequency
        priority_factor = 1.0 / entry.priority
        expiry_factor = max(0.0, 1.0 - time_to_expiry / entry.ttl)
        
        # Weighted combination (lower score = better eviction candidate)
        score = (
            0.3 * freq_factor +
            0.2 * size_factor +
            0.2 * age_factor +
            0.1 * priority_factor +
            0.2 * expiry_factor
        )
        
        return score
    
    def _trigger_prefetch(self, accessed_key: str) -> None:
        """Trigger predictive prefetching based on access patterns."""
        predicted_keys = self.access_pattern.predict_next_keys(accessed_key)
        
        for key in predicted_keys:
            if key not in self.cache:
                # Check if we have a callback for this key pattern
                callback = self._find_prefetch_callback(key)
                if callback:
                    self.prefetch_queue.append((key, callback))
    
    def _find_prefetch_callback(self, key: str) -> Optional[callable]:
        """Find a prefetch callback for a given key."""
        for pattern, callback in self.prefetch_callbacks.items():
            if pattern in key:  # Simple pattern matching
                return callback
        return None
    
    def register_prefetch_callback(self, key_pattern: str, callback: callable) -> None:
        """Register a callback for prefetching data matching a key pattern."""
        self.prefetch_callbacks[key_pattern] = callback
        log.debug(f"Registered prefetch callback for pattern: {key_pattern}")
    
    def _prefetch_loop(self) -> None:
        """Background prefetching loop."""
        while not self.prefetch_stop_event.is_set():
            try:
                if self.prefetch_queue:
                    key, callback = self.prefetch_queue.popleft()
                    
                    # Check if key is still not in cache
                    if key not in self.cache:
                        try:
                            # Execute prefetch callback
                            value = callback(key)
                            if value is not None:
                                # Use lower priority for prefetched data
                                self.set(key, value, priority=0.5)
                                self.stats["prefetch_hits"] += 1
                                log.debug(f"Prefetched {key}")
                            else:
                                self.stats["prefetch_misses"] += 1
                        except Exception as e:
                            log.error(f"Error prefetching {key}: {e}")
                            self.stats["prefetch_misses"] += 1
                else:
                    # Wait a bit if queue is empty
                    self.prefetch_stop_event.wait(1.0)
            
            except Exception as e:
                log.error(f"Error in prefetch loop: {e}")
                self.prefetch_stop_event.wait(5.0)
    
    def _cleanup_loop(self) -> None:
        """Background cleanup loop for expired entries."""
        while not self.cleanup_stop_event.is_set():
            try:
                current_time = time.time()
                expired_keys = []
                
                with self.lock:
                    for key, entry in self.cache.items():
                        if entry.is_expired():
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        entry = self.cache[key]
                        del self.cache[key]
                        self.stats["total_size_bytes"] -= entry.size
                        log.debug(f"Expired {key}")
                
                if expired_keys:
                    log.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                
                # Wait 60 seconds before next cleanup
                self.cleanup_stop_event.wait(60)
            
            except Exception as e:
                log.error(f"Error in cleanup loop: {e}")
                self.cleanup_stop_event.wait(60)
    
    def get_statistics(self) -> Dict:
        """Get cache statistics."""
        with self.lock:
            total_accesses = self.stats["hits"] + self.stats["misses"]
            hit_rate = (self.stats["hits"] / total_accesses * 100) if total_accesses > 0 else 0
            
            return {
                "hit_rate_percent": hit_rate,
                "total_entries": len(self.cache),
                "total_size_mb": self.stats["total_size_bytes"] / (1024 * 1024),
                "size_utilization_percent": (self.stats["total_size_bytes"] / self.max_size_bytes * 100),
                "avg_access_time_ms": self.stats["avg_access_time"] * 1000,
                "prefetch_hit_rate": (
                    self.stats["prefetch_hits"] / 
                    (self.stats["prefetch_hits"] + self.stats["prefetch_misses"]) * 100
                    if (self.stats["prefetch_hits"] + self.stats["prefetch_misses"]) > 0 else 0
                ),
                **self.stats
            }
    
    def get_cache_info(self) -> Dict:
        """Get detailed cache information."""
        with self.lock:
            entries_info = []
            
            for key, entry in self.cache.items():
                entries_info.append({
                    "key": key,
                    "size_bytes": entry.size,
                    "age_seconds": entry.get_age(),
                    "access_count": entry.access_count,
                    "access_frequency": entry.get_access_frequency(),
                    "priority": entry.priority,
                    "expires_in": entry.ttl - entry.get_age()
                })
            
            # Sort by access frequency
            entries_info.sort(key=lambda x: x["access_frequency"], reverse=True)
            
            return {
                "entries": entries_info,
                "statistics": self.get_statistics(),
                "access_patterns": {
                    "frequent_keys": dict(list(self.access_pattern.key_frequencies.items())[:10]),
                    "total_patterns": len(self.access_pattern.sequential_patterns)
                }
            }
    
    def shutdown(self) -> None:
        """Shutdown the cache and cleanup threads."""
        log.info("Shutting down IntelligentCache...")
        
        self.cleanup_stop_event.set()
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        
        if self.enable_prefetching:
            self.prefetch_stop_event.set()
            if self.prefetch_thread and self.prefetch_thread.is_alive():
                self.prefetch_thread.join(timeout=5)
        
        self.clear()
        log.info("IntelligentCache shutdown complete")


# Global cache instance for easy access
_global_cache = None


def get_global_cache() -> IntelligentCache:
    """Get the global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = IntelligentCache()
    return _global_cache


def cache_decorator(ttl: float = 300, key_prefix: str = ""):
    """Decorator for caching function results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = {
                "func": func.__name__,
                "args": args,
                "kwargs": kwargs
            }
            key_str = json.dumps(key_data, sort_keys=True, default=str)
            cache_key = f"{key_prefix}{hashlib.md5(key_str.encode()).hexdigest()}"
            
            # Try to get from cache
            cache = get_global_cache()
            result = cache.get(cache_key)
            
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        wrapper._cache_key_prefix = key_prefix
        return wrapper
    
    return decorator


# Example usage
if __name__ == "__main__":
    # Example of using the intelligent cache
    cache = IntelligentCache(max_size_mb=50, enable_prefetching=True)
    
    # Example prefetch callback
    def fetch_market_data(key: str):
        # Simulate fetching market data
        if "BTCUSDT" in key:
            return {"symbol": "BTCUSDT", "price": 45000, "volume": 1000000}
        return None
    
    # Register prefetch callback
    cache.register_prefetch_callback("market_data", fetch_market_data)
    
    # Test basic operations
    cache.set("test_key", {"data": "test_value"}, ttl=60)
    value = cache.get("test_key")
    print(f"Retrieved: {value}")
    
    # Test with decorator
    @cache_decorator(ttl=120, key_prefix="api_")
    def expensive_calculation(x, y):
        time.sleep(1)  # Simulate expensive operation
        return x * y + 42
    
    result1 = expensive_calculation(10, 20)  # Slow (cache miss)
    result2 = expensive_calculation(10, 20)  # Fast (cache hit)
    
    print(f"Results: {result1}, {result2}")
    print(f"Cache stats: {cache.get_statistics()}")
    
    # Cleanup
    cache.shutdown()