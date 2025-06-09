# Async API Client - High-performance asynchronous API operations
import asyncio
import time
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import pandas as pd
from decimal import Decimal

from utils.logger import setup_logger

log = setup_logger("async_client")


class AsyncAPIClient:
    """Asynchronous API client for high-performance operations."""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Base URLs
        if testnet:
            self.futures_base_url = "https://testnet.binancefuture.com"
            self.spot_base_url = "https://testnet.binance.vision"
        else:
            self.futures_base_url = "https://fapi.binance.com"
            self.spot_base_url = "https://api.binance.com"
        
        # Session management
        self.session = None
        self.rate_limiter = AsyncRateLimiter(
            requests_per_minute=1200,  # Binance limit
            burst_requests=20
        )
        
        # Performance tracking
        self.stats = {
            "requests_made": 0,
            "requests_failed": 0,
            "avg_response_time": 0.0,
            "cache_hits": 0,
            "rate_limit_hits": 0
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()
    
    async def start_session(self) -> None:
        """Start the aiohttp session."""
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=20,  # Per host connection limit
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "Binance-Grid-Bot-RL/1.0",
                "X-MBX-APIKEY": self.api_key
            }
        )
        log.info("Async API client session started")
    
    async def close_session(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            log.info("Async API client session closed")
    
    async def batch_fetch_tickers(
        self, 
        symbols: List[str] = None, 
        market_type: str = "futures"
    ) -> Dict[str, Dict]:
        """Batch fetch ticker data for multiple symbols."""
        try:
            if market_type == "futures":
                url = f"{self.futures_base_url}/fapi/v1/ticker/24hr"
            else:
                url = f"{self.spot_base_url}/api/v3/ticker/24hr"
            
            params = {}
            if symbols:
                if len(symbols) == 1:
                    params["symbol"] = symbols[0]
                else:
                    params["symbols"] = str(symbols)
            
            async with self.rate_limiter:
                response_data = await self._make_request("GET", url, params=params)
            
            if response_data:
                # Convert list to dict keyed by symbol
                if isinstance(response_data, list):
                    return {item["symbol"]: item for item in response_data}
                else:
                    return {response_data["symbol"]: response_data}
            
            return {}
        
        except Exception as e:
            log.error(f"Error batch fetching tickers: {e}")
            return {}
    
    async def batch_fetch_klines(
        self,
        symbol_intervals: List[Tuple[str, str]],
        limit: int = 100,
        market_type: str = "futures"
    ) -> Dict[str, pd.DataFrame]:
        """Batch fetch kline data for multiple symbol-interval pairs."""
        tasks = []
        
        for symbol, interval in symbol_intervals:
            task = self._fetch_single_klines(symbol, interval, limit, market_type)
            tasks.append(task)
        
        # Execute all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        kline_data = {}
        for i, result in enumerate(results):
            symbol, interval = symbol_intervals[i]
            key = f"{symbol}_{interval}"
            
            if isinstance(result, Exception):
                log.error(f"Error fetching klines for {symbol} {interval}: {result}")
                continue
            
            if result:
                kline_data[key] = result
        
        return kline_data
    
    async def _fetch_single_klines(
        self,
        symbol: str,
        interval: str,
        limit: int,
        market_type: str
    ) -> Optional[pd.DataFrame]:
        """Fetch klines for a single symbol."""
        try:
            if market_type == "futures":
                url = f"{self.futures_base_url}/fapi/v1/klines"
            else:
                url = f"{self.spot_base_url}/api/v3/klines"
            
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            async with self.rate_limiter:
                klines = await self._make_request("GET", url, params=params)
            
            if klines:
                df = pd.DataFrame(
                    klines,
                    columns=[
                        "Open time", "Open", "High", "Low", "Close", "Volume",
                        "Close time", "Quote asset volume", "Number of trades",
                        "Taker buy base asset volume", "Taker buy quote asset volume", "Ignore"
                    ]
                )
                
                # Convert numeric columns
                numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col])
                
                df['timestamp'] = pd.to_datetime(df['Open time'], unit='ms')
                return df
            
            return None
        
        except Exception as e:
            log.error(f"Error fetching klines for {symbol}: {e}")
            return None
    
    async def batch_fetch_positions(self, symbols: List[str] = None) -> Dict[str, Dict]:
        """Batch fetch position data."""
        try:
            url = f"{self.futures_base_url}/fapi/v2/positionRisk"
            params = {}
            
            if symbols and len(symbols) == 1:
                params["symbol"] = symbols[0]
            
            async with self.rate_limiter:
                positions = await self._make_request("GET", url, params=params, signed=True)
            
            if positions:
                # Filter for requested symbols if specified
                if symbols and len(symbols) > 1:
                    positions = [pos for pos in positions if pos["symbol"] in symbols]
                
                # Convert to dict and filter non-zero positions
                result = {}
                for pos in positions:
                    if Decimal(pos.get("positionAmt", "0")) != 0:
                        result[pos["symbol"]] = pos
                
                return result
            
            return {}
        
        except Exception as e:
            log.error(f"Error batch fetching positions: {e}")
            return {}
    
    async def batch_place_orders(self, orders: List[Dict]) -> List[Dict]:
        """Batch place multiple orders."""
        tasks = []
        
        for order in orders:
            task = self._place_single_order(order)
            tasks.append(task)
        
        # Execute with controlled concurrency to avoid rate limits
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent order placements
        
        async def place_with_semaphore(order_task):
            async with semaphore:
                return await order_task
        
        limited_tasks = [place_with_semaphore(task) for task in tasks]
        results = await asyncio.gather(*limited_tasks, return_exceptions=True)
        
        # Process results
        successful_orders = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log.error(f"Error placing order {i}: {result}")
                continue
            
            if result:
                successful_orders.append(result)
        
        return successful_orders
    
    async def _place_single_order(self, order_params: Dict) -> Optional[Dict]:
        """Place a single order."""
        try:
            url = f"{self.futures_base_url}/fapi/v1/order"
            
            async with self.rate_limiter:
                order_result = await self._make_request("POST", url, params=order_params, signed=True)
            
            return order_result
        
        except Exception as e:
            log.error(f"Error placing single order: {e}")
            return None
    
    async def _make_request(
        self,
        method: str,
        url: str,
        params: Dict = None,
        signed: bool = False
    ) -> Optional[Union[Dict, List]]:
        """Make an HTTP request with rate limiting and error handling."""
        if not self.session:
            await self.start_session()
        
        start_time = time.time()
        
        try:
            # Prepare request
            if signed:
                params = self._sign_request(params or {})
            
            # Make request
            if method == "GET":
                async with self.session.get(url, params=params) as response:
                    data = await self._handle_response(response)
            elif method == "POST":
                async with self.session.post(url, data=params) as response:
                    data = await self._handle_response(response)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Update stats
            self.stats["requests_made"] += 1
            response_time = time.time() - start_time
            self.stats["avg_response_time"] = (
                (self.stats["avg_response_time"] * (self.stats["requests_made"] - 1) + response_time)
                / self.stats["requests_made"]
            )
            
            return data
        
        except Exception as e:
            self.stats["requests_failed"] += 1
            log.error(f"Request failed for {method} {url}: {e}")
            return None
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Optional[Union[Dict, List]]:
        """Handle API response."""
        if response.status == 200:
            return await response.json()
        elif response.status == 429:
            # Rate limit hit
            self.stats["rate_limit_hits"] += 1
            log.warning("Rate limit hit, backing off...")
            await asyncio.sleep(1)
            return None
        else:
            error_text = await response.text()
            log.error(f"API error {response.status}: {error_text}")
            return None
    
    def _sign_request(self, params: Dict) -> Dict:
        """Sign request for authenticated endpoints."""
        import hmac
        import hashlib
        from urllib.parse import urlencode
        
        # Add timestamp
        params["timestamp"] = int(time.time() * 1000)
        
        # Create signature
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        params["signature"] = signature
        return params
    
    def get_statistics(self) -> Dict:
        """Get async client statistics."""
        return self.stats.copy()


class AsyncRateLimiter:
    """Async rate limiter with burst support."""
    
    def __init__(self, requests_per_minute: int, burst_requests: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_requests = burst_requests
        
        # Rate limiting state
        self.tokens = burst_requests
        self.last_update = time.time()
        self.lock = asyncio.Lock()
        
        # Calculate refill rate
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
    
    async def __aenter__(self):
        """Async context manager entry - acquire rate limit token."""
        async with self.lock:
            await self._wait_for_token()
            self.tokens -= 1
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    async def _wait_for_token(self) -> None:
        """Wait for a rate limit token to become available."""
        current_time = time.time()
        
        # Refill tokens based on elapsed time
        elapsed = current_time - self.last_update
        self.tokens = min(
            self.burst_requests,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_update = current_time
        
        # Wait if no tokens available
        if self.tokens < 1:
            wait_time = (1 - self.tokens) / self.refill_rate
            log.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
            self.tokens = 1
            self.last_update = time.time()


class AsyncDataProcessor:
    """Async data processing utilities."""
    
    @staticmethod
    async def process_market_data_batch(
        data_batch: Dict[str, pd.DataFrame],
        indicators: List[str] = None
    ) -> Dict[str, Dict]:
        """Process a batch of market data with technical indicators."""
        if not indicators:
            indicators = ["rsi", "atr", "adx"]
        
        tasks = []
        for symbol, df in data_batch.items():
            task = AsyncDataProcessor._process_single_dataframe(symbol, df, indicators)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        processed_data = {}
        for i, result in enumerate(results):
            symbol = list(data_batch.keys())[i]
            if isinstance(result, Exception):
                log.error(f"Error processing data for {symbol}: {result}")
                continue
            
            processed_data[symbol] = result
        
        return processed_data
    
    @staticmethod
    async def _process_single_dataframe(
        symbol: str,
        df: pd.DataFrame,
        indicators: List[str]
    ) -> Dict:
        """Process a single DataFrame with indicators."""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            AsyncDataProcessor._calculate_indicators,
            symbol,
            df,
            indicators
        )
    
    @staticmethod
    def _calculate_indicators(symbol: str, df: pd.DataFrame, indicators: List[str]) -> Dict:
        """Calculate technical indicators (runs in thread pool)."""
        try:
            result = {
                "symbol": symbol,
                "timestamp": time.time(),
                "indicators": {}
            }
            
            if len(df) < 20:
                return result
            
            # Import TA-Lib if available
            try:
                import talib
                
                high = df["High"].values
                low = df["Low"].values
                close = df["Close"].values
                volume = df["Volume"].values
                
                if "rsi" in indicators:
                    rsi = talib.RSI(close, timeperiod=14)
                    result["indicators"]["rsi"] = float(rsi[-1]) if not np.isnan(rsi[-1]) else None
                
                if "atr" in indicators:
                    atr = talib.ATR(high, low, close, timeperiod=14)
                    result["indicators"]["atr"] = float(atr[-1]) if not np.isnan(atr[-1]) else None
                
                if "adx" in indicators:
                    adx = talib.ADX(high, low, close, timeperiod=14)
                    result["indicators"]["adx"] = float(adx[-1]) if not np.isnan(adx[-1]) else None
                
                if "volume_sma" in indicators:
                    vol_sma = talib.SMA(volume, timeperiod=20)
                    result["indicators"]["volume_sma"] = float(vol_sma[-1]) if not np.isnan(vol_sma[-1]) else None
                
            except ImportError:
                log.warning("TA-Lib not available for async processing")
            
            return result
        
        except Exception as e:
            log.error(f"Error calculating indicators for {symbol}: {e}")
            return {"symbol": symbol, "timestamp": time.time(), "indicators": {}}


# Usage example and utility functions
async def example_usage():
    """Example of how to use the async client."""
    api_key = "your_api_key"
    api_secret = "your_api_secret"
    
    async with AsyncAPIClient(api_key, api_secret) as client:
        # Batch fetch tickers
        tickers = await client.batch_fetch_tickers(["BTCUSDT", "ETHUSDT"])
        print(f"Fetched {len(tickers)} tickers")
        
        # Batch fetch klines
        symbol_intervals = [
            ("BTCUSDT", "1h"),
            ("ETHUSDT", "1h"),
            ("ADAUSDT", "1h")
        ]
        klines = await client.batch_fetch_klines(symbol_intervals)
        print(f"Fetched klines for {len(klines)} symbol-interval pairs")
        
        # Process market data
        processed = await AsyncDataProcessor.process_market_data_batch(klines)
        print(f"Processed data for {len(processed)} symbols")
        
        # Get statistics
        stats = client.get_statistics()
        print(f"Client stats: {stats}")


if __name__ == "__main__":
    # Example usage
    asyncio.run(example_usage())