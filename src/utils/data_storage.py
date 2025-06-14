# Local Data Storage for Persistent Caching and Shadow Mode
import os
import json
import sqlite3
import pickle
import gzip
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import pandas as pd
from pathlib import Path
import logging

log = logging.getLogger(__name__)

class ShadowDataStorage:
    """Gerencia armazenamento de dados simulados para treinamento RL."""
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.trades_file = os.path.join(data_dir, "shadow_trades.jsonl")
        self.states_file = os.path.join(data_dir, "market_states.jsonl") 
        self.actions_file = os.path.join(data_dir, "rl_actions.jsonl")
        self.performance_file = os.path.join(data_dir, "performance.jsonl")
        
        # Criar diretório se não existir
        os.makedirs(data_dir, exist_ok=True)
        
        log.info(f"ShadowDataStorage inicializado: {data_dir}")
    
    def log_trade(self, trade_data: Dict[str, Any]):
        """Salva dados de trade simulado."""
        trade_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "shadow_trade",
            **trade_data
        }
        
        self._append_to_file(self.trades_file, trade_entry)
        log.debug(f"Trade simulado salvo: {trade_data['symbol']} {trade_data['side']}")
    
    def log_market_state(self, symbol: str, state: List[float], price: float):
        """Salva estado de mercado capturado."""
        state_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "current_price": price,
            "state_vector": state,
            "state_size": len(state)
        }
        
        self._append_to_file(self.states_file, state_entry)
        log.debug(f"Estado de mercado salvo: {symbol} @ {price}")
    
    def log_rl_action(self, symbol: str, state: List[float], action: int, 
                     reward: float = None, next_state: List[float] = None):
        """Salva ação do RL e contexto."""
        action_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "state": state,
            "action": action,
            "reward": reward,
            "next_state": next_state
        }
        
        self._append_to_file(self.actions_file, action_entry)
        log.debug(f"Ação RL salva: {symbol} action={action}")
    
    def log_performance(self, symbol: str, metrics: Dict[str, float]):
        """Salva métricas de performance."""
        perf_entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            **metrics
        }
        
        self._append_to_file(self.performance_file, perf_entry)
        log.debug(f"Performance salva: {symbol}")
    
    def _append_to_file(self, filepath: str, data: Dict[str, Any]):
        """Adiciona linha ao arquivo JSONL."""
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        except Exception as e:
            log.error(f"Erro ao salvar dados em {filepath}: {e}")
    
    def load_trades_df(self, symbol: str = None, last_days: int = None) -> pd.DataFrame:
        """Carrega trades como DataFrame para análise."""
        try:
            if not os.path.exists(self.trades_file):
                return pd.DataFrame()
            
            trades = []
            with open(self.trades_file, 'r', encoding='utf-8') as f:
                for line in f:
                    trade = json.loads(line.strip())
                    if symbol is None or trade.get('symbol') == symbol:
                        trades.append(trade)
            
            df = pd.DataFrame(trades)
            if df.empty:
                return df
                
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            if last_days:
                cutoff = datetime.now() - pd.Timedelta(days=last_days)
                df = df[df['timestamp'] >= cutoff]
            
            return df.sort_values('timestamp')
            
        except Exception as e:
            log.error(f"Erro ao carregar trades: {e}")
            return pd.DataFrame()
    
    def load_training_data(self, symbol: str = None, limit: int = 10000) -> Dict[str, List]:
        """Carrega dados para treinamento RL (estados, ações, rewards)."""
        try:
            if not os.path.exists(self.actions_file):
                return {"states": [], "actions": [], "rewards": [], "next_states": []}
            
            states, actions, rewards, next_states = [], [], [], []
            
            with open(self.actions_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                        
                    action_data = json.loads(line.strip())
                    if symbol is None or action_data.get('symbol') == symbol:
                        if (action_data.get('state') and 
                            action_data.get('action') is not None and
                            action_data.get('reward') is not None):
                            
                            states.append(action_data['state'])
                            actions.append(action_data['action'])
                            rewards.append(action_data['reward'])
                            next_states.append(action_data.get('next_state', action_data['state']))
            
            log.info(f"Dados de treinamento carregados: {len(states)} samples")
            return {
                "states": states,
                "actions": actions, 
                "rewards": rewards,
                "next_states": next_states
            }
            
        except Exception as e:
            log.error(f"Erro ao carregar dados de treinamento: {e}")
            return {"states": [], "actions": [], "rewards": [], "next_states": []}
    
    def get_data_stats(self) -> Dict[str, int]:
        """Retorna estatísticas dos dados salvos."""
        stats = {}
        
        for name, filepath in [
            ("trades", self.trades_file),
            ("states", self.states_file), 
            ("actions", self.actions_file),
            ("performance", self.performance_file)
        ]:
            try:
                if os.path.exists(filepath):
                    with open(filepath, 'r') as f:
                        count = sum(1 for _ in f)
                    stats[name] = count
                else:
                    stats[name] = 0
            except:
                stats[name] = 0
        
        return stats

class LocalDataStorage:
    """Local storage system for persistent data caching."""
    
    def __init__(self, storage_dir: str = "data/cache"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Database setup
        self.db_path = self.storage_dir / "market_data.db"
        self.json_cache_dir = self.storage_dir / "json_cache"
        self.json_cache_dir.mkdir(exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Memory cache for hot data
        self.memory_cache = {}
        self.cache_ttl = {}
        
        log.info(f"Local data storage initialized at: {self.storage_dir}")
    
    def _init_database(self):
        """Initialize SQLite database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Ticker data table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS ticker_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    change_percent REAL,
                    volume REAL,
                    high REAL,
                    low REAL,
                    timestamp INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticker_symbol_timestamp ON ticker_data(symbol, timestamp)")
                
                # Kline data table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS kline_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    open_time INTEGER NOT NULL,
                    close_time INTEGER NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume REAL NOT NULL,
                    is_closed BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, interval, open_time)
                )
                """)
                
                # Order book snapshots
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS orderbook_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    bids TEXT NOT NULL,
                    asks TEXT NOT NULL,
                    last_update_id INTEGER,
                    timestamp INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_orderbook_symbol_timestamp ON orderbook_snapshots(symbol, timestamp)")
                
                # Trade data
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    timestamp INTEGER NOT NULL,
                    is_buyer_maker BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_symbol_timestamp ON trade_data(symbol, timestamp)")
                
                # Social sentiment data
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS social_sentiment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    content TEXT,
                    sentiment_score REAL,
                    author TEXT,
                    followers_count INTEGER,
                    timestamp INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_symbol_timestamp_source ON social_sentiment(symbol, timestamp, source)")
                
                # News and announcements
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT,
                    source TEXT NOT NULL,
                    url TEXT,
                    symbols TEXT,
                    sentiment_score REAL,
                    relevance_score REAL,
                    published_time INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_symbols_published ON news_data(symbols, published_time)")
                
                # Trading performance cache
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS trading_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    trade_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    pnl REAL,
                    fees REAL,
                    timestamp INTEGER NOT NULL,
                    status TEXT DEFAULT 'open',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_symbol_timestamp_strategy ON trading_performance(symbol, timestamp, strategy)")
                
                conn.commit()
                log.info("Database tables initialized successfully")
        
        except Exception as e:
            log.error(f"Error initializing database: {e}")
            raise
    
    async def store_ticker_data(self, symbol: str, ticker_data: Dict):
        """Store ticker data to database and cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO ticker_data (symbol, price, change_percent, volume, high, low, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    ticker_data['price'],
                    ticker_data.get('change', 0),
                    ticker_data.get('volume', 0),
                    ticker_data.get('high', 0),
                    ticker_data.get('low', 0),
                    ticker_data.get('timestamp', int(time.time() * 1000))
                ))
                conn.commit()
            
            # Update memory cache
            self.memory_cache[f"ticker_{symbol}"] = ticker_data
            self.cache_ttl[f"ticker_{symbol}"] = time.time() + 30  # 30 second TTL
            
        except Exception as e:
            log.error(f"Error storing ticker data for {symbol}: {e}")
    
    async def get_cached_ticker(self, symbol: str) -> Optional[Dict]:
        """Get cached ticker data."""
        # Check memory cache first
        cache_key = f"ticker_{symbol}"
        if cache_key in self.memory_cache:
            if time.time() < self.cache_ttl.get(cache_key, 0):
                return self.memory_cache[cache_key]
            else:
                # Cache expired
                del self.memory_cache[cache_key]
                del self.cache_ttl[cache_key]
        
        # Check database
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT price, change_percent, volume, high, low, timestamp
                FROM ticker_data 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
                """, (symbol,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'symbol': symbol,
                        'price': row[0],
                        'change': row[1],
                        'volume': row[2],
                        'high': row[3],
                        'low': row[4],
                        'timestamp': row[5]
                    }
        
        except Exception as e:
            log.error(f"Error getting cached ticker for {symbol}: {e}")
        
        return None
    
    async def save_data_to_cache(self, data: Dict):
        """Save bulk data to JSON cache files."""
        try:
            for data_type, content in data.items():
                cache_file = self.json_cache_dir / f"{data_type}_{int(time.time())}.json.gz"
                
                with gzip.open(cache_file, 'wt', encoding='utf-8') as f:
                    json.dump(content, f, separators=(',', ':'))
                
                log.info(f"Saved {data_type} data to cache: {cache_file}")
        
        except Exception as e:
            log.error(f"Error saving data to cache: {e}")
    
    async def load_cached_data(self) -> Dict:
        """Load most recent cached data on startup."""
        try:
            cached_data = {}
            
            for cache_file in self.json_cache_dir.glob("*.json.gz"):
                try:
                    data_type = cache_file.stem.split('_')[0]
                    
                    with gzip.open(cache_file, 'rt', encoding='utf-8') as f:
                        content = json.load(f)
                        cached_data[data_type] = content
                
                except Exception as e:
                    log.error(f"Error loading cache file {cache_file}: {e}")
            
            log.info(f"Loaded {len(cached_data)} cached data types on startup")
            return cached_data
        
        except Exception as e:
            log.error(f"Error loading cached data: {e}")
            return {}
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics."""
        try:
            stats = {
                "database_size_mb": self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0,
                "cache_files": len(list(self.json_cache_dir.glob("*.json.gz"))),
                "memory_cache_entries": len(self.memory_cache)
            }
            
            # Get record counts from database
            if self.db_path.exists():
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    tables = [
                        'ticker_data', 'kline_data', 'orderbook_snapshots',
                        'trade_data', 'social_sentiment', 'news_data', 'trading_performance'
                    ]
                    
                    for table in tables:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            count = cursor.fetchone()[0]
                            stats[f"{table}_records"] = count
                        except:
                            stats[f"{table}_records"] = 0
            
            return stats
        
        except Exception as e:
            log.error(f"Error getting storage stats: {e}")
            return {}


# Instância global para uso em todo o projeto
shadow_storage = ShadowDataStorage()
local_storage = LocalDataStorage()