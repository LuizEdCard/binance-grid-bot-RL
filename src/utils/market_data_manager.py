# Market Data Manager - Unified WebSocket + Local Storage System
import asyncio
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sqlite3
import os
import json

from utils.logger import setup_logger
from utils.websocket_client import BinanceWebSocketClient, HighFrequencyTradeEngine
from utils.api_client import APIClient
import yaml
import os

log = setup_logger("market_data_manager")


class MarketDataManager:
    """Unified market data manager using WebSocket + local storage to minimize API calls."""
    
    def __init__(self, api_client: APIClient, testnet: bool = False):
        self.api_client = api_client
        self.testnet = testnet
        
        # Load config
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            log.warning(f"Could not load config: {e}, using defaults")
            config = {}
        
        # WebSocket client for real-time data
        self.ws_client = BinanceWebSocketClient(testnet=testnet)
        self.hft_engine = None  # Initialize later if needed
        
        # Local data storage
        self.db_path = "data/market_data.db"
        self.ensure_database()
        
        # Data caches - configurable sizes
        websocket_config = config.get('websocket_config', {})
        kline_cache_max = websocket_config.get('kline_cache_max_size', 1000)
        
        self.ticker_cache = {}
        self.kline_cache = defaultdict(lambda: deque(maxlen=kline_cache_max))
        self.volume_cache = {}
        
        # High volatility pairs for better trading opportunities (validated symbols only)
        self.high_volatility_pairs = [
            # Major volatility pairs
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT",
            "DOGEUSDT", "XRPUSDT", "DOTUSDT", "AVAXUSDT",
            
            # Mid-cap high volatility
            "LINKUSDT", "ATOMUSDT", "NEARUSDT", "FTMUSDT", "SANDUSDT",
            "MANAUSDT", "CHZUSDT", "ENJUSDT", "GALAUSDT", "FLOWUSDT",
            
            # Small-cap high volatility (validated symbols)
            "PNUTUSDT", "ACTUSDT", "SCRUSDT", "NEIROUSDT", "MOODENGUSDT",
            "RIFUSDT", "WIFUSDT", "BONKUSDT", "PEPEUSDT", "SHIBUSDT",
            
            # DeFi high volatility
            "UNIUSDT", "AAVEUSDT", "COMPUSDT", "SUSHIUSDT", "CAKEUSDT",
            "1INCHUSDT", "BALUSDT", "CRVUSDT", "MKRUSDT", "YFIUSDT",
            
            # Additional volatile pairs
            "LTCUSDT", "BCHUSDT", "FILUSDT", "TRXUSDT", "XLMUSDT"
        ]
        
        # Subscription management
        self.subscribed_symbols = set()
        self.last_api_call = {}
        self.api_call_cooldown = websocket_config.get('api_call_cooldown_seconds', 300)
        
        # Performance tracking
        self.stats = {
            "websocket_messages": 0,
            "api_calls_saved": 0,
            "cache_hits": 0,
            "last_update": None
        }
        
        # Background tasks
        self.background_tasks = []
        self.is_running = False
        
        log.info("Market Data Manager initialized with WebSocket + local storage")
    
    def ensure_database(self):
        """Ensure SQLite database exists with required tables."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Ticker data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickers (
                    symbol TEXT,
                    price REAL,
                    change_percent REAL,
                    volume REAL,
                    high_24h REAL,
                    low_24h REAL,
                    timestamp INTEGER,
                    PRIMARY KEY (symbol, timestamp)
                )
            """)
            
            # Kline data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS klines (
                    symbol TEXT,
                    interval TEXT,
                    open_time INTEGER,
                    open_price REAL,
                    high_price REAL,
                    low_price REAL,
                    close_price REAL,
                    volume REAL,
                    close_time INTEGER,
                    PRIMARY KEY (symbol, interval, open_time)
                )
            """)
            
            # Volume analysis table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS volume_analysis (
                    symbol TEXT,
                    avg_volume_24h REAL,
                    volume_spike_ratio REAL,
                    volatility_score REAL,
                    last_calculated INTEGER,
                    PRIMARY KEY (symbol)
                )
            """)
            
            conn.commit()
            log.info("Database tables ensured")
    
    async def start(self):
        """Start the market data manager."""
        self.is_running = True
        
        # Start WebSocket client
        await self.ws_client.start()
        
        # Subscribe to high volatility pairs
        await self._subscribe_to_high_volatility_pairs()
        
        # Start background tasks
        self.background_tasks = [
            asyncio.create_task(self._volatility_analyzer()),
            asyncio.create_task(self._data_persistence_worker()),
            asyncio.create_task(self._api_supplement_worker())
        ]
        
        log.info("Market Data Manager started successfully")
    
    async def stop(self):
        """Stop the market data manager."""
        self.is_running = False
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Stop WebSocket client
        await self.ws_client.stop()
        
        log.info("Market Data Manager stopped")
    
    async def _subscribe_to_high_volatility_pairs(self):
        """Subscribe to WebSocket streams for high volatility pairs."""
        try:
            # Subscribe to ticker data for real-time prices
            await self.ws_client.subscribe_ticker(self.high_volatility_pairs, "spot")
            await self.ws_client.subscribe_ticker(self.high_volatility_pairs, "futures")
            
            # Subscribe to klines for technical analysis
            await self.ws_client.subscribe_klines(self.high_volatility_pairs, "1m", "spot")
            await self.ws_client.subscribe_klines(self.high_volatility_pairs, "3m", "spot")
            
            # Subscribe to trade data for volume analysis
            await self.ws_client.subscribe_trades(self.high_volatility_pairs, "spot")
            
            self.subscribed_symbols.update(self.high_volatility_pairs)
            
            log.info(f"Subscribed to WebSocket data for {len(self.high_volatility_pairs)} high volatility pairs")
            
        except Exception as e:
            log.error(f"Error subscribing to WebSocket streams: {e}")
    
    async def _volatility_analyzer(self):
        """Background task to analyze volatility and update pair rankings."""
        while self.is_running:
            try:
                await self._calculate_volatility_scores()
                await asyncio.sleep(300)  # Run every 5 minutes
            except Exception as e:
                log.error(f"Error in volatility analyzer: {e}")
                await asyncio.sleep(60)
    
    async def _data_persistence_worker(self):
        """Background task to persist WebSocket data to database."""
        while self.is_running:
            try:
                await self._persist_realtime_data()
                await asyncio.sleep(60)  # Persist every minute
            except Exception as e:
                log.error(f"Error in data persistence: {e}")
                await asyncio.sleep(30)
    
    async def _api_supplement_worker(self):
        """Background task to supplement WebSocket data with API calls when needed."""
        while self.is_running:
            try:
                await self._supplement_missing_data()
                await asyncio.sleep(600)  # Run every 10 minutes
            except Exception as e:
                log.error(f"Error in API supplement worker: {e}")
                await asyncio.sleep(120)
    
    async def _calculate_volatility_scores(self):
        """Calculate volatility scores for all symbols."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for symbol in self.subscribed_symbols:
                    # Get recent price data
                    cursor.execute("""
                        SELECT high_24h, low_24h, volume, price 
                        FROM tickers 
                        WHERE symbol = ? 
                        ORDER BY timestamp DESC 
                        LIMIT 100
                    """, (symbol,))
                    
                    rows = cursor.fetchall()
                    if len(rows) >= 10:
                        # Calculate volatility metrics
                        prices = [row[3] for row in rows]
                        volumes = [row[2] for row in rows]
                        
                        # Price volatility (standard deviation)
                        avg_price = sum(prices) / len(prices)
                        price_variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
                        price_volatility = (price_variance ** 0.5) / avg_price
                        
                        # Volume metrics
                        avg_volume = sum(volumes) / len(volumes)
                        latest_volume = volumes[0] if volumes else 0
                        volume_spike = latest_volume / avg_volume if avg_volume > 0 else 1
                        
                        # Combined volatility score
                        volatility_score = price_volatility * 100 + (volume_spike - 1) * 10
                        
                        # Store analysis
                        cursor.execute("""
                            INSERT OR REPLACE INTO volume_analysis 
                            (symbol, avg_volume_24h, volume_spike_ratio, volatility_score, last_calculated)
                            VALUES (?, ?, ?, ?, ?)
                        """, (symbol, avg_volume, volume_spike, volatility_score, int(time.time())))
                
                conn.commit()
                
        except Exception as e:
            log.error(f"Error calculating volatility scores: {e}")
    
    async def _persist_realtime_data(self):
        """Persist real-time WebSocket data to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Persist ticker data
                for symbol, ticker_data in self.ws_client.ticker_data.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO tickers 
                        (symbol, price, change_percent, volume, high_24h, low_24h, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol,
                        ticker_data['price'],
                        ticker_data['change'],
                        ticker_data['volume'],
                        ticker_data['high'],
                        ticker_data['low'],
                        ticker_data['timestamp']
                    ))
                
                # Persist recent kline data
                for key, klines in self.ws_client.kline_data.items():
                    symbol, interval = key.split('_', 1)
                    
                    # Only persist closed klines
                    for kline in list(klines)[-10:]:  # Last 10 klines
                        if kline.get('is_closed', False):
                            cursor.execute("""
                                INSERT OR REPLACE INTO klines 
                                (symbol, interval, open_time, open_price, high_price, low_price, close_price, volume, close_time)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                symbol, interval,
                                kline['open_time'], kline['open'],
                                kline['high'], kline['low'],
                                kline['close'], kline['volume'],
                                kline['close_time']
                            ))
                
                conn.commit()
                
        except Exception as e:
            log.error(f"Error persisting real-time data: {e}")
    
    async def _supplement_missing_data(self):
        """Supplement WebSocket data with API calls for missing information."""
        try:
            current_time = time.time()
            
            for symbol in self.subscribed_symbols:
                # Check if we need fresh data and cooldown has passed
                last_call = self.last_api_call.get(symbol, 0)
                
                if current_time - last_call > self.api_call_cooldown:
                    # Check if we have recent WebSocket data
                    ticker_data = self.ws_client.get_latest_ticker(symbol)
                    
                    if not ticker_data or current_time - ticker_data.get('timestamp', 0) > 300:
                        # No recent data - supplement with API call
                        await self._api_supplement_symbol(symbol)
                        self.last_api_call[symbol] = current_time
                        self.stats["api_calls_saved"] += 1
                        
                        # Don't overwhelm API - wait between calls
                        await asyncio.sleep(1)
        
        except Exception as e:
            log.error(f"Error supplementing missing data: {e}")
    
    async def _api_supplement_symbol(self, symbol: str):
        """Supplement data for a specific symbol using API."""
        try:
            # Get ticker data from API
            ticker = await asyncio.to_thread(
                self.api_client._make_request,
                lambda: self.api_client.client.get_symbol_ticker(symbol=symbol)
            )
            
            if ticker:
                # Store in cache
                self.ticker_cache[symbol] = {
                    'symbol': symbol,
                    'price': float(ticker['price']),
                    'timestamp': int(time.time() * 1000)
                }
                
                log.debug(f"API supplemented data for {symbol}")
        
        except Exception as e:
            log.debug(f"Could not supplement data for {symbol}: {e}")
    
    def get_market_data(self, limit: int = 50) -> List[Dict]:
        """Get market data using primarily WebSocket data, fallback to cache/API."""
        try:
            market_data = []
            
            # Get data from WebSocket first (real-time)
            for symbol in list(self.subscribed_symbols)[:limit]:
                ticker_data = self.ws_client.get_latest_ticker(symbol)
                
                if ticker_data:
                    # Use real-time WebSocket data
                    market_data.append({
                        'symbol': ticker_data['symbol'],
                        'price': f"{ticker_data['price']:.8f}",
                        'change_24h': f"{ticker_data['change']:.2f}%",
                        'volume': f"{ticker_data['volume']:.2f}",
                        'high_24h': f"{ticker_data['high']:.8f}",
                        'low_24h': f"{ticker_data['low']:.8f}",
                        'source': 'websocket'
                    })
                    self.stats["cache_hits"] += 1
                
                elif symbol in self.ticker_cache:
                    # Fallback to local cache
                    cached_data = self.ticker_cache[symbol]
                    market_data.append({
                        'symbol': cached_data['symbol'],
                        'price': f"{cached_data['price']:.8f}",
                        'change_24h': "0.00%",
                        'volume': "0.00",
                        'high_24h': f"{cached_data['price']:.8f}",
                        'low_24h': f"{cached_data['price']:.8f}",
                        'source': 'cache'
                    })
            
            # Sort by volume (descending)
            market_data.sort(key=lambda x: float(x['volume']), reverse=True)
            
            self.stats["last_update"] = datetime.now().isoformat()
            
            return market_data[:limit]
        
        except Exception as e:
            log.error(f"Error getting market data: {e}")
            return []
    
    def get_high_volatility_pairs(self, limit: int = 20) -> List[Dict]:
        """Get highest volatility pairs from analysis."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT symbol, volatility_score, volume_spike_ratio, avg_volume_24h
                    FROM volume_analysis 
                    ORDER BY volatility_score DESC 
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                
                volatility_pairs = []
                for row in rows:
                    symbol, vol_score, spike_ratio, avg_volume = row
                    
                    # Get current price from WebSocket
                    ticker_data = self.ws_client.get_latest_ticker(symbol)
                    current_price = ticker_data['price'] if ticker_data else 0
                    
                    volatility_pairs.append({
                        'symbol': symbol,
                        'volatility_score': round(vol_score, 2),
                        'volume_spike_ratio': round(spike_ratio, 2),
                        'avg_volume_24h': round(avg_volume, 2),
                        'current_price': current_price,
                        'recommended': vol_score > 5.0  # High volatility threshold
                    })
                
                return volatility_pairs
        
        except Exception as e:
            log.error(f"Error getting high volatility pairs: {e}")
            return []
    
    def get_realtime_klines(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[Dict]:
        """Get real-time klines from WebSocket data."""
        try:
            # Get from WebSocket first
            klines = self.ws_client.get_latest_klines(symbol, interval, limit)
            
            if klines:
                return [
                    {
                        'timestamp': kline['open_time'],
                        'open': kline['open'],
                        'high': kline['high'],
                        'low': kline['low'],
                        'close': kline['close'],
                        'volume': kline['volume'],
                        'close_time': kline['close_time']
                    }
                    for kline in klines
                ]
            
            # Fallback to database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT open_time, open_price, high_price, low_price, close_price, volume, close_time
                    FROM klines 
                    WHERE symbol = ? AND interval = ?
                    ORDER BY open_time DESC 
                    LIMIT ?
                """, (symbol, interval, limit))
                
                rows = cursor.fetchall()
                
                return [
                    {
                        'timestamp': row[0],
                        'open': row[1],
                        'high': row[2],
                        'low': row[3],
                        'close': row[4],
                        'volume': row[5],
                        'close_time': row[6]
                    }
                    for row in reversed(rows)  # Reverse to get chronological order
                ]
        
        except Exception as e:
            log.error(f"Error getting real-time klines for {symbol}: {e}")
            return []
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics of the market data manager."""
        ws_stats = self.ws_client.get_statistics()
        
        return {
            **self.stats,
            'websocket_stats': ws_stats,
            'subscribed_symbols': len(self.subscribed_symbols),
            'high_volatility_pairs': len(self.high_volatility_pairs),
            'api_call_savings': f"{self.stats['api_calls_saved']} calls avoided",
            'cache_performance': f"{self.stats['cache_hits']} hits",
            'is_running': self.is_running
        }
    
    def enable_high_frequency_trading(self, symbols: List[str] = None):
        """Enable high-frequency trading for specified symbols."""
        if not self.hft_engine:
            self.hft_engine = HighFrequencyTradeEngine(
                self.ws_client, 
                self.api_client,
                min_profit_threshold=0.0005  # 0.05% minimum profit
            )
        
        # Add high volatility symbols to HFT
        target_symbols = symbols or self.high_volatility_pairs[:10]  # Top 10 by default
        
        for symbol in target_symbols:
            self.hft_engine.add_symbol(symbol)
        
        log.info(f"High-frequency trading enabled for {len(target_symbols)} symbols")
        
        return self.hft_engine
    
    def disable_high_frequency_trading(self):
        """Disable high-frequency trading."""
        if self.hft_engine:
            for symbol in list(self.hft_engine.active_symbols):
                self.hft_engine.remove_symbol(symbol)
            
            self.hft_engine = None
            log.info("High-frequency trading disabled")


# Global instance for Flask API
market_data_manager = None


def get_market_data_manager(api_client: APIClient, testnet: bool = False) -> MarketDataManager:
    """Get or create global market data manager instance."""
    global market_data_manager
    
    if market_data_manager is None:
        market_data_manager = MarketDataManager(api_client, testnet)
    
    return market_data_manager


async def initialize_market_data_manager(api_client: APIClient, testnet: bool = False):
    """Initialize and start the market data manager."""
    manager = get_market_data_manager(api_client, testnet)
    
    if not manager.is_running:
        await manager.start()
        log.info("Market Data Manager initialized and started")
    
    return manager