#!/usr/bin/env python3
"""
Simplified WebSocket client for real-time price data
"""

import json
import threading
import time
import websocket
from collections import defaultdict
from decimal import Decimal

from utils.logger import setup_logger

log = setup_logger("simple_websocket")


class SimpleBinanceWebSocket:
    """Simplified WebSocket client for real-time Binance price data."""
    
    def __init__(self, testnet: bool = False, config: dict = None):
        self.testnet = testnet
        
        # Configuration
        self.config = config or {}
        websocket_config = self.config.get('websocket_config', {})
        
        # Load URLs from config
        if testnet:
            self.base_url = websocket_config.get('testnet_url', "wss://testnet.binance.vision/ws/")
        else:
            self.base_url = websocket_config.get('production_url', "wss://stream.binance.com:9443/ws/")
        self.join_timeout = websocket_config.get('join_timeout_seconds', 2)
        
        # Real-time data storage
        self.ticker_data = {}
        self.subscribed_symbols = set()
        self.is_running = False
        self.ws = None
        self.thread = None
        
        # Statistics
        self.stats = {
            "messages_received": 0,
            "last_message_time": None,
            "connection_time": None
        }
    
    def start(self):
        """Start WebSocket connection in background thread."""
        if self.is_running:
            return
            
        self.is_running = True
        self.thread = threading.Thread(target=self._run_websocket, daemon=True)
        self.thread.start()
        log.info("SimpleBinanceWebSocket started")
    
    def stop(self):
        """Stop WebSocket connection."""
        self.is_running = False
        if self.ws:
            self.ws.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=self.join_timeout)
        log.info("SimpleBinanceWebSocket stopped")
    
    def subscribe_ticker(self, symbol: str):
        """Subscribe to ticker price updates for a symbol."""
        symbol_lower = symbol.lower()
        if symbol_lower not in self.subscribed_symbols:
            self.subscribed_symbols.add(symbol_lower)
            log.info(f"Subscribed to ticker updates for {symbol}")
    
    def unsubscribe_ticker(self, symbol: str):
        """Unsubscribe from ticker price updates for a symbol."""
        symbol_lower = symbol.lower()
        if symbol_lower in self.subscribed_symbols:
            self.subscribed_symbols.remove(symbol_lower)
            log.info(f"Unsubscribed from ticker updates for {symbol}")
            # Note: To fully unsubscribe, we would need to reconnect with new streams
            # For now, we just remove from our tracked symbols
    
    def get_price(self, symbol: str) -> float:
        """Get latest price for a symbol."""
        # Try both uppercase and lowercase versions
        price = self.ticker_data.get(symbol.upper(), {}).get('price', None)
        if price is None:
            price = self.ticker_data.get(symbol.lower(), {}).get('price', None)
        if price is None:
            price = self.ticker_data.get(symbol, {}).get('price', None)
        
        # Debug logging if price is still None
        if price is None:
            available_symbols = list(self.ticker_data.keys())
            log.warning(f"No price data for {symbol}. Available symbols: {available_symbols[:5]}...")
        
        return price
    
    def _run_websocket(self):
        """Run WebSocket connection."""
        while self.is_running:
            try:
                # Create stream URL for all subscribed symbols
                if not self.subscribed_symbols:
                    time.sleep(1)
                    continue
                
                streams = [f"{symbol}@ticker" for symbol in self.subscribed_symbols]
                stream_url = self.base_url + "/".join(streams)
                
                log.info(f"Connecting to: {stream_url}")
                
                self.ws = websocket.WebSocketApp(
                    stream_url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open
                )
                
                self.ws.run_forever()
                
            except Exception as e:
                log.error(f"WebSocket error: {e}")
                if self.is_running:
                    reconnect_delay = websocket_config.get('reconnect_delay_seconds', 5)
                    time.sleep(reconnect_delay)  # Wait before reconnecting
                    
    def _on_open(self, ws):
        """Called when WebSocket connection opens."""
        self.stats["connection_time"] = time.time()
        log.info("WebSocket connection opened")
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Handle single ticker message
            if 'c' in data and 's' in data:  # 'c' = current price, 's' = symbol
                symbol = data['s']
                price = float(data['c'])
                
                self.ticker_data[symbol] = {
                    'price': price,
                    'timestamp': time.time()
                }
                
                self.stats["messages_received"] += 1
                self.stats["last_message_time"] = time.time()
                
                log.debug(f"Price update: {symbol} = ${price}")
            
            # Handle multiple streams
            elif 'stream' in data and 'data' in data:
                ticker_data = data['data']
                if 'c' in ticker_data and 's' in ticker_data:
                    symbol = ticker_data['s']
                    price = float(ticker_data['c'])
                    
                    self.ticker_data[symbol] = {
                        'price': price,
                        'timestamp': time.time()
                    }
                    
                    self.stats["messages_received"] += 1
                    self.stats["last_message_time"] = time.time()
                    
                    log.debug(f"Price update: {symbol} = ${price}")
                
        except Exception as e:
            log.error(f"Error processing WebSocket message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        log.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        log.warning(f"WebSocket closed: {close_status_code} - {close_msg}")


# Global instance for easy access
_global_ws_client = None

def get_global_websocket():
    """Get global WebSocket client instance."""
    global _global_ws_client
    if _global_ws_client is None:
        _global_ws_client = SimpleBinanceWebSocket()
    return _global_ws_client