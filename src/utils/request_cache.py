# Request Cache Middleware for Flask API Rate Limiting

import time
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
import logging

log = logging.getLogger(__name__)

class RequestCache:
    """Middleware para cache de requests do Flask API para reduzir rate limiting."""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = {
            'status': 10,           # 10 seconds for status endpoints
            'balance': 30,          # 30 seconds for balance data
            'market_data': 15,      # 15 seconds for market data
            'trading_pairs': 20,    # 20 seconds for trading pairs
            'indicators': 60,       # 60 seconds for indicators
            'default': 30           # Default 30 seconds
        }
        self.last_cleanup = datetime.now()
    
    def _get_cache_key(self, endpoint, args=None):
        """Generate cache key for endpoint with arguments."""
        key_data = f"{endpoint}_{args or ''}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cache_type(self, endpoint):
        """Determine cache type based on endpoint."""
        if 'status' in endpoint:
            return 'status'
        elif 'balance' in endpoint:
            return 'balance'
        elif 'market_data' in endpoint:
            return 'market_data'
        elif 'trading/pairs' in endpoint:
            return 'trading_pairs'
        elif 'indicators' in endpoint:
            return 'indicators'
        else:
            return 'default'
    
    def _is_cache_valid(self, cache_key, cache_type):
        """Check if cached data is still valid."""
        if cache_key not in self.cache:
            return False
        
        cached_time, _ = self.cache[cache_key]
        ttl = self.cache_ttl.get(cache_type, self.cache_ttl['default'])
        
        return datetime.now() - cached_time < timedelta(seconds=ttl)
    
    def _cleanup_cache(self):
        """Clean expired cache entries."""
        now = datetime.now()
        
        # Only cleanup every 5 minutes
        if now - self.last_cleanup < timedelta(minutes=5):
            return
        
        expired_keys = []
        for key, (cached_time, _) in self.cache.items():
            # Remove entries older than max TTL (5 minutes)
            if now - cached_time > timedelta(minutes=5):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        self.last_cleanup = now
        
        if expired_keys:
            log.debug(f"Cleaned {len(expired_keys)} expired cache entries")
    
    def cache_response(self, endpoint, response_data, args=None):
        """Cache response data for an endpoint."""
        cache_key = self._get_cache_key(endpoint, args)
        self.cache[cache_key] = (datetime.now(), response_data)
        
        # Periodic cleanup
        self._cleanup_cache()
    
    def get_cached_response(self, endpoint, args=None):
        """Get cached response if available and valid."""
        cache_key = self._get_cache_key(endpoint, args)
        cache_type = self._get_cache_type(endpoint)
        
        if self._is_cache_valid(cache_key, cache_type):
            cached_time, response_data = self.cache[cache_key]
            age_seconds = int((datetime.now() - cached_time).total_seconds())
            log.debug(f"Returning cached response for {endpoint} (age: {age_seconds}s)")
            return response_data, age_seconds
        
        return None, 0

# Global cache instance
request_cache = RequestCache()

def cached_endpoint(cache_key_func=None):
    """Decorator for caching Flask endpoint responses."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            endpoint = func.__name__
            cache_args = None
            if cache_key_func:
                cache_args = cache_key_func(*args, **kwargs)
            
            # Try to get cached response
            cached_response, age = request_cache.get_cached_response(endpoint, cache_args)
            if cached_response:
                # Add cache age to response if it's a dict
                if isinstance(cached_response, dict) and 'timestamp' not in cached_response:
                    cached_response = cached_response.copy()
                    cached_response['cached'] = True
                    cached_response['cache_age_seconds'] = age
                return cached_response
            
            # Execute function and cache response
            response = func(*args, **kwargs)
            
            # Cache the response (only for successful responses)
            if response and (not hasattr(response, 'status_code') or response.status_code == 200):
                response_data = response
                if hasattr(response, 'get_json'):
                    response_data = response.get_json()
                
                request_cache.cache_response(endpoint, response_data, cache_args)
            
            return response
        
        return wrapper
    return decorator