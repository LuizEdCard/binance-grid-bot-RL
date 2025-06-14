# WebSocket Client for Real-time Market Data
import asyncio
import json
import time
import threading
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
import websockets
import gzip

from utils.logger import setup_logger
from utils.data_storage import LocalDataStorage

log = setup_logger("websocket_client")


class BinanceWebSocketClient:
    """High-performance WebSocket client for real-time Binance data."""
    
    def __init__(self, testnet: bool = False):
        self.testnet = testnet
        self.base_url = "wss://testnet.binance.vision" if testnet else "wss://stream.binance.com:9443"
        self.futures_url = "wss://dstream.binance.com" if not testnet else "wss://dstream.binancefuture.com"
        
        # Connection management
        self.connections = {}
        self.subscribers = defaultdict(list)
        self.is_running = False
        self.reconnect_delay = 5
        
        # Data storage
        self.local_storage = LocalDataStorage()
        
        # Real-time data buffers
        self.ticker_data = {}
        self.depth_data = defaultdict(lambda: {"bids": [], "asks": []})
        self.kline_data = defaultdict(lambda: deque(maxlen=1000))
        self.trade_data = defaultdict(lambda: deque(maxlen=500))
        
        # Performance tracking
        self.stats = {
            "messages_received": 0,
            "reconnections": 0,
            "avg_latency": 0.0,
            "last_message_time": None
        }
        
        # Callback handlers
        self.callbacks = {
            "ticker": [],
            "depth": [],
            "kline": [],
            "trade": [],
            "aggTrade": []
        }
        
        log.info(f"WebSocket client initialized ({'TESTNET' if testnet else 'MAINNET'})")
    
    async def start(self):
        """Start WebSocket connections."""
        self.is_running = True
        log.info("Starting WebSocket connections...")
        
        # Load cached data on startup
        await self.local_storage.load_cached_data()
        
    async def stop(self):
        """Stop all WebSocket connections."""
        self.is_running = False
        log.info("Stopping WebSocket connections...")
        
        # Close all connections
        for stream_name, ws in self.connections.items():
            try:
                await ws.close()
                log.info(f"Closed WebSocket connection: {stream_name}")
            except Exception as e:
                log.error(f"Error closing connection {stream_name}: {e}")
        
        self.connections.clear()
        
        # Save data before shutdown
        await self.local_storage.save_data_to_cache({
            "tickers": self.ticker_data,
            "depth": dict(self.depth_data),
            "klines": {k: list(v) for k, v in self.kline_data.items()},
            "trades": {k: list(v) for k, v in self.trade_data.items()}
        })
    
    async def subscribe_ticker(self, symbols: List[str], market_type: str = "spot"):
        """Subscribe to real-time ticker data."""
        if market_type == "spot":
            stream_names = [f"{symbol.lower()}@ticker" for symbol in symbols]
            url = f"{self.base_url}/ws/{'!'.join(stream_names)}"
        else:  # futures
            stream_names = [f"{symbol.lower()}@ticker" for symbol in symbols]
            url = f"{self.futures_url}/ws/{'!'.join(stream_names)}"
        
        await self._create_connection(f"ticker_{market_type}", url, self._handle_ticker_message)
        log.info(f"Subscribed to ticker data for {len(symbols)} symbols ({market_type})")
    
    async def subscribe_depth(self, symbols: List[str], levels: int = 20, update_speed: str = "100ms"):
        """Subscribe to real-time order book depth."""
        stream_names = [f"{symbol.lower()}@depth{levels}@{update_speed}" for symbol in symbols]
        url = f"{self.base_url}/ws/{'!'.join(stream_names)}"
        
        await self._create_connection("depth", url, self._handle_depth_message)
        log.info(f"Subscribed to depth data for {len(symbols)} symbols (levels: {levels})")
    
    async def subscribe_klines(self, symbols: List[str], interval: str = "1m", market_type: str = "spot"):
        """Subscribe to real-time kline data."""
        if market_type == "spot":
            stream_names = [f"{symbol.lower()}@kline_{interval}" for symbol in symbols]
            url = f"{self.base_url}/ws/{'!'.join(stream_names)}"
        else:  # futures
            stream_names = [f"{symbol.lower()}@kline_{interval}" for symbol in symbols]
            url = f"{self.futures_url}/ws/{'!'.join(stream_names)}"
        
        await self._create_connection(f"klines_{interval}_{market_type}", url, self._handle_kline_message)
        log.info(f"Subscribed to {interval} klines for {len(symbols)} symbols ({market_type})")
    
    async def subscribe_trades(self, symbols: List[str], market_type: str = "spot"):
        """Subscribe to real-time trade data."""
        if market_type == "spot":
            stream_names = [f"{symbol.lower()}@trade" for symbol in symbols]
            url = f"{self.base_url}/ws/{'!'.join(stream_names)}"
        else:  # futures
            stream_names = [f"{symbol.lower()}@aggTrade" for symbol in symbols]
            url = f"{self.futures_url}/ws/{'!'.join(stream_names)}"
        
        await self._create_connection(f"trades_{market_type}", url, self._handle_trade_message)
        log.info(f"Subscribed to trade data for {len(symbols)} symbols ({market_type})")
    
    async def _create_connection(self, stream_name: str, url: str, handler: Callable):
        """Create and manage a WebSocket connection."""
        if stream_name in self.connections:
            log.warning(f"Connection {stream_name} already exists")
            return
        
        asyncio.create_task(self._connection_manager(stream_name, url, handler))
    
    async def _connection_manager(self, stream_name: str, url: str, handler: Callable):
        """Manage WebSocket connection with auto-reconnection."""
        while self.is_running:
            try:
                log.info(f"Connecting to {stream_name}: {url}")
                
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    self.connections[stream_name] = ws
                    log.info(f"Connected to {stream_name}")
                    
                    async for message in ws:
                        if not self.is_running:
                            break
                        
                        try:
                            # Handle compressed messages
                            if isinstance(message, bytes):
                                message = gzip.decompress(message).decode('utf-8')
                            
                            data = json.loads(message)
                            await handler(data)
                            
                            # Update statistics
                            self.stats["messages_received"] += 1
                            self.stats["last_message_time"] = time.time()
                            
                        except Exception as e:
                            log.error(f"Error processing message from {stream_name}: {e}")
                            continue
            
            except Exception as e:
                log.error(f"Connection error for {stream_name}: {e}")
                self.stats["reconnections"] += 1
                
                if stream_name in self.connections:
                    del self.connections[stream_name]
                
                if self.is_running:
                    log.info(f"Reconnecting to {stream_name} in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(self.reconnect_delay * 1.5, 60)  # Exponential backoff
                else:
                    break
    
    async def _handle_ticker_message(self, data: Dict):
        """Handle ticker WebSocket messages."""
        if 'stream' in data and 'data' in data:
            ticker_data = data['data']
            symbol = ticker_data['s']
            
            # Store real-time ticker data
            self.ticker_data[symbol] = {
                'symbol': symbol,
                'price': float(ticker_data['c']),
                'change': float(ticker_data['P']),
                'volume': float(ticker_data['v']),
                'high': float(ticker_data['h']),
                'low': float(ticker_data['l']),
                'timestamp': int(ticker_data['E'])
            }
            
            # Notify callbacks
            for callback in self.callbacks["ticker"]:
                try:
                    await callback(symbol, self.ticker_data[symbol])
                except Exception as e:
                    log.error(f"Error in ticker callback: {e}")
            
            # Store to local cache periodically
            if self.stats["messages_received"] % 100 == 0:
                await self.local_storage.store_ticker_data(symbol, self.ticker_data[symbol])
    
    async def _handle_depth_message(self, data: Dict):
        """Handle depth/order book WebSocket messages."""
        if 'stream' in data and 'data' in data:
            depth_data = data['data']
            symbol = depth_data['s']
            
            # Update order book
            self.depth_data[symbol] = {
                'bids': [[float(price), float(qty)] for price, qty in depth_data['b']],
                'asks': [[float(price), float(qty)] for price, qty in depth_data['a']],
                'lastUpdateId': depth_data['lastUpdateId'],
                'timestamp': time.time()
            }
            
            # Notify callbacks
            for callback in self.callbacks["depth"]:
                try:
                    await callback(symbol, self.depth_data[symbol])
                except Exception as e:
                    log.error(f"Error in depth callback: {e}")
    
    async def _handle_kline_message(self, data: Dict):
        """Handle kline WebSocket messages."""
        if 'stream' in data and 'data' in data:
            kline_data = data['data']['k']
            symbol = kline_data['s']
            
            kline_info = {
                'symbol': symbol,
                'open_time': int(kline_data['t']),
                'close_time': int(kline_data['T']),
                'open': float(kline_data['o']),
                'high': float(kline_data['h']),
                'low': float(kline_data['l']),
                'close': float(kline_data['c']),
                'volume': float(kline_data['v']),
                'is_closed': kline_data['x']  # True when kline is closed
            }
            
            # Store kline data
            key = f"{symbol}_{kline_data['i']}"  # symbol_interval
            self.kline_data[key].append(kline_info)
            
            # Notify callbacks only for closed klines
            if kline_info['is_closed']:
                for callback in self.callbacks["kline"]:
                    try:
                        await callback(symbol, kline_info)
                    except Exception as e:
                        log.error(f"Error in kline callback: {e}")
    
    async def _handle_trade_message(self, data: Dict):
        """Handle trade WebSocket messages."""
        if 'stream' in data and 'data' in data:
            trade_data = data['data']
            symbol = trade_data['s']
            
            trade_info = {
                'symbol': symbol,
                'price': float(trade_data['p']),
                'quantity': float(trade_data['q']),
                'timestamp': int(trade_data['T']),
                'is_buyer_maker': trade_data.get('m', False)
            }
            
            # Store trade data
            self.trade_data[symbol].append(trade_info)
            
            # Notify callbacks
            for callback in self.callbacks["trade"]:
                try:
                    await callback(symbol, trade_info)
                except Exception as e:
                    log.error(f"Error in trade callback: {e}")
    
    def add_callback(self, data_type: str, callback: Callable):
        """Add callback for specific data type."""
        if data_type in self.callbacks:
            self.callbacks[data_type].append(callback)
            log.info(f"Added callback for {data_type} data")
        else:
            log.error(f"Invalid data type: {data_type}")
    
    def get_latest_ticker(self, symbol: str) -> Optional[Dict]:
        """Get latest ticker data for symbol."""
        return self.ticker_data.get(symbol)
    
    def get_order_book(self, symbol: str) -> Optional[Dict]:
        """Get latest order book for symbol."""
        return self.depth_data.get(symbol)
    
    def get_latest_klines(self, symbol: str, interval: str, limit: int = 100) -> List[Dict]:
        """Get latest klines for symbol."""
        key = f"{symbol}_{interval}"
        if key in self.kline_data:
            return list(self.kline_data[key])[-limit:]
        return []
    
    def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for symbol."""
        if symbol in self.trade_data:
            return list(self.trade_data[symbol])[-limit:]
        return []
    
    def get_statistics(self) -> Dict:
        """Get WebSocket client statistics."""
        return {
            **self.stats,
            "active_connections": len(self.connections),
            "connected_streams": list(self.connections.keys()),
            "symbols_tracking": {
                "tickers": len(self.ticker_data),
                "depth": len(self.depth_data),
                "klines": len(self.kline_data),
                "trades": len(self.trade_data)
            }
        }


class HighFrequencyTradeEngine:
    """High-frequency trading engine for micro-profit strategies."""
    
    def __init__(self, ws_client: BinanceWebSocketClient, api_client, min_profit_threshold: float = 0.0001):
        self.ws_client = ws_client
        self.api_client = api_client
        self.min_profit_threshold = min_profit_threshold  # 0.01% minimum profit
        
        # Trading state
        self.active_symbols = set()
        self.position_tracker = {}
        self.profit_tracker = defaultdict(float)
        
        # Performance metrics
        self.trade_stats = {
            "total_trades": 0,
            "profitable_trades": 0,
            "total_profit": 0.0,
            "avg_profit_per_trade": 0.0,
            "trades_per_minute": 0.0
        }
        
        # Setup callbacks
        self.ws_client.add_callback("ticker", self._on_ticker_update)
        self.ws_client.add_callback("depth", self._on_depth_update)
        
        log.info(f"High-frequency trading engine initialized (min profit: {min_profit_threshold*100:.3f}%)")
    
    async def _on_ticker_update(self, symbol: str, ticker_data: Dict):
        """Handle real-time ticker updates for scalping opportunities."""
        if symbol not in self.active_symbols:
            return
        
        current_price = ticker_data['price']
        price_change = ticker_data['change']
        
        # Look for micro-movements
        if abs(price_change) >= self.min_profit_threshold:
            await self._evaluate_scalping_opportunity(symbol, current_price, price_change)
    
    async def _on_depth_update(self, symbol: str, depth_data: Dict):
        """Handle order book updates for spread trading."""
        if symbol not in self.active_symbols:
            return
        
        bids = depth_data['bids']
        asks = depth_data['asks']
        
        if bids and asks:
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread = (best_ask - best_bid) / best_bid
            
            # Look for profitable spread opportunities
            if spread > self.min_profit_threshold * 2:  # 2x minimum for safety
                await self._evaluate_spread_opportunity(symbol, best_bid, best_ask, spread)
    
    async def _evaluate_scalping_opportunity(self, symbol: str, price: float, change: float):
        """Evaluate scalping opportunity based on price momentum."""
        try:
            # Simple momentum strategy
            if change > self.min_profit_threshold:
                # Price moving up - look for continuation
                target_price = price * (1 + self.min_profit_threshold)
                await self._place_scalp_order(symbol, "BUY", price, target_price)
            
            elif change < -self.min_profit_threshold:
                # Price moving down - look for bounce
                target_price = price * (1 - self.min_profit_threshold)
                await self._place_scalp_order(symbol, "SELL", price, target_price)
        
        except Exception as e:
            log.error(f"Error evaluating scalping opportunity for {symbol}: {e}")
    
    async def _evaluate_spread_opportunity(self, symbol: str, bid: float, ask: float, spread: float):
        """Evaluate spread trading opportunity."""
        try:
            # Calculate potential profit after fees (assume 0.1% total fees)
            fee_rate = 0.001
            net_profit = spread - (2 * fee_rate)
            
            if net_profit > self.min_profit_threshold:
                # Profitable spread - place both orders
                await self._place_spread_orders(symbol, bid, ask)
        
        except Exception as e:
            log.error(f"Error evaluating spread opportunity for {symbol}: {e}")
    
    async def _place_scalp_order(self, symbol: str, side: str, entry_price: float, target_price: float):
        """Place scalping order with tight stop-loss."""
        try:
            # Calculate position size based on risk management
            position_size = self._calculate_scalp_position_size(symbol, entry_price)
            
            if position_size > 0:
                # Place market order for entry
                order_result = self.api_client.place_futures_order(
                    symbol=symbol,
                    side=side,
                    order_type="MARKET",
                    quantity=position_size
                )
                
                if order_result:
                    log.info(f"Scalp order placed: {symbol} {side} {position_size} @ {entry_price}")
                    
                    # Track position
                    self.position_tracker[symbol] = {
                        "side": side,
                        "entry_price": entry_price,
                        "target_price": target_price,
                        "quantity": position_size,
                        "timestamp": time.time()
                    }
                    
                    # Schedule exit order
                    asyncio.create_task(self._manage_scalp_position(symbol))
        
        except Exception as e:
            log.error(f"Error placing scalp order for {symbol}: {e}")
    
    async def _place_spread_orders(self, symbol: str, bid: float, ask: float):
        """Place spread trading orders."""
        try:
            position_size = self._calculate_spread_position_size(symbol, bid)
            
            if position_size > 0:
                # Place buy at bid and sell at ask simultaneously
                buy_task = self.api_client.place_futures_order(
                    symbol=symbol,
                    side="BUY",
                    order_type="LIMIT",
                    quantity=position_size,
                    price=bid,
                    timeInForce="IOC"  # Immediate or Cancel
                )
                
                sell_task = self.api_client.place_futures_order(
                    symbol=symbol,
                    side="SELL",
                    order_type="LIMIT",
                    quantity=position_size,
                    price=ask,
                    timeInForce="IOC"
                )
                
                # Execute simultaneously
                results = await asyncio.gather(buy_task, sell_task, return_exceptions=True)
                
                successful_orders = [r for r in results if not isinstance(r, Exception)]
                
                if len(successful_orders) >= 1:
                    log.info(f"Spread orders placed: {symbol} bid:{bid} ask:{ask}")
        
        except Exception as e:
            log.error(f"Error placing spread orders for {symbol}: {e}")
    
    def _calculate_scalp_position_size(self, symbol: str, price: float) -> float:
        """Calculate optimal position size for scalping."""
        # Simple position sizing - use 1% of available balance
        try:
            balance = self.api_client.get_futures_account_balance()
            if balance:
                available_balance = float(balance[0].get('availableBalance', 0))
                max_position_value = available_balance * 0.01  # 1% risk
                position_size = max_position_value / price
                
                # Round to appropriate precision
                return round(position_size, 6)
        except:
            pass
        
        return 0.0
    
    def _calculate_spread_position_size(self, symbol: str, price: float) -> float:
        """Calculate position size for spread trading."""
        # Conservative sizing for spread trades
        return self._calculate_scalp_position_size(symbol, price) * 0.5
    
    async def _manage_scalp_position(self, symbol: str):
        """Manage scalp position with tight exit conditions."""
        if symbol not in self.position_tracker:
            return
        
        position = self.position_tracker[symbol]
        max_hold_time = 60  # Maximum 60 seconds hold time
        start_time = position["timestamp"]
        
        while symbol in self.position_tracker:
            try:
                # Check if max hold time exceeded
                if time.time() - start_time > max_hold_time:
                    await self._exit_scalp_position(symbol, "TIME_LIMIT")
                    break
                
                # Check current price for profit/loss
                current_ticker = self.ws_client.get_latest_ticker(symbol)
                if current_ticker:
                    current_price = current_ticker['price']
                    
                    # Calculate current P&L
                    if position["side"] == "BUY":
                        pnl_percent = (current_price - position["entry_price"]) / position["entry_price"]
                    else:
                        pnl_percent = (position["entry_price"] - current_price) / position["entry_price"]
                    
                    # Exit conditions
                    if pnl_percent >= self.min_profit_threshold:
                        await self._exit_scalp_position(symbol, "PROFIT_TARGET")
                        break
                    elif pnl_percent <= -self.min_profit_threshold * 2:  # 2x stop loss
                        await self._exit_scalp_position(symbol, "STOP_LOSS")
                        break
                
                await asyncio.sleep(0.1)  # Check every 100ms
            
            except Exception as e:
                log.error(f"Error managing scalp position for {symbol}: {e}")
                break
    
    async def _exit_scalp_position(self, symbol: str, reason: str):
        """Exit scalp position."""
        if symbol not in self.position_tracker:
            return
        
        try:
            position = self.position_tracker[symbol]
            
            # Place opposite order to close position
            exit_side = "SELL" if position["side"] == "BUY" else "BUY"
            
            exit_order = self.api_client.place_futures_order(
                symbol=symbol,
                side=exit_side,
                order_type="MARKET",
                quantity=position["quantity"]
            )
            
            if exit_order:
                # Calculate actual profit
                current_ticker = self.ws_client.get_latest_ticker(symbol)
                if current_ticker:
                    exit_price = current_ticker['price']
                    
                    if position["side"] == "BUY":
                        profit = (exit_price - position["entry_price"]) * position["quantity"]
                    else:
                        profit = (position["entry_price"] - exit_price) * position["quantity"]
                    
                    # Update statistics
                    self.trade_stats["total_trades"] += 1
                    self.trade_stats["total_profit"] += profit
                    
                    if profit > 0:
                        self.trade_stats["profitable_trades"] += 1
                    
                    self.profit_tracker[symbol] += profit
                    
                    log.info(f"Scalp position closed: {symbol} {reason} P&L: {profit:.6f}")
                
                # Remove from tracking
                del self.position_tracker[symbol]
        
        except Exception as e:
            log.error(f"Error exiting scalp position for {symbol}: {e}")
    
    def add_symbol(self, symbol: str):
        """Add symbol to high-frequency trading."""
        self.active_symbols.add(symbol)
        log.info(f"Added {symbol} to high-frequency trading")
    
    def remove_symbol(self, symbol: str):
        """Remove symbol from high-frequency trading."""
        self.active_symbols.discard(symbol)
        if symbol in self.position_tracker:
            asyncio.create_task(self._exit_scalp_position(symbol, "MANUAL_STOP"))
        log.info(f"Removed {symbol} from high-frequency trading")
    
    def get_performance_stats(self) -> Dict:
        """Get trading performance statistics."""
        total_trades = self.trade_stats["total_trades"]
        
        return {
            **self.trade_stats,
            "win_rate": (self.trade_stats["profitable_trades"] / total_trades * 100) if total_trades > 0 else 0,
            "avg_profit_per_trade": (self.trade_stats["total_profit"] / total_trades) if total_trades > 0 else 0,
            "active_positions": len(self.position_tracker),
            "active_symbols": list(self.active_symbols),
            "profit_by_symbol": dict(self.profit_tracker)
        }