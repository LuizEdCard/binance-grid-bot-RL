# Multi-Agent Trading Bot - Main entry point using specialized agents
import asyncio
import multiprocessing
import os
import signal
import sys
import threading
import time
from decimal import Decimal
from typing import Dict, List, Optional
from queue import Queue
from threading import Lock

import yaml
from dotenv import load_dotenv

# Add src directory to Python path
SRC_DIR = os.path.dirname(__file__)
sys.path.append(SRC_DIR)

from agents.coordinator_agent import CoordinatorAgent
from agents.data_agent import DataAgent
from agents.risk_agent import RiskAgent
from agents.sentiment_agent import SentimentAgent
from agents.ai_agent import AIAgent
from integrations.ai_trading_integration import AITradingIntegration, SmartTradingDecisionEngine
from core.capital_management import CapitalManager
from core.grid_logic import GridLogic
from core.pair_selector import PairSelector
from utils.alerter import Alerter
from utils.api_client import APIClient
from utils.async_client import AsyncAPIClient

# Import live data API for real-time data sharing
try:
    from routes.live_data_api import update_trading_data, update_agent_decision, update_system_status
    LIVE_DATA_API_AVAILABLE = True
except ImportError:
    LIVE_DATA_API_AVAILABLE = False
    def update_trading_data(*args, **kwargs): pass
    def update_agent_decision(*args, **kwargs): pass
    def update_system_status(*args, **kwargs): pass
from utils.intelligent_cache import IntelligentCache, get_global_cache
from utils.logger import log, setup_logger
from utils.pair_logger import get_multi_pair_logger, get_pair_logger
from utils.global_tp_sl_manager import get_global_tpsl_manager, start_global_tpsl

# Conditional import of RLAgent (after logger is imported)
try:
    from core.rl_agent import RLAgent
    RL_AVAILABLE = True
except ImportError as e:
    RL_AVAILABLE = False
    RLAgent = None
    log.warning(f"RL Agent not available: {e}")
from utils.simple_websocket import SimpleBinanceWebSocket, get_global_websocket
# Conditional import of model_api (may contain RL dependencies)
try:
    from routes import model_api
    MODEL_API_AVAILABLE = True
except ImportError as e:
    MODEL_API_AVAILABLE = False
    log.warning(f"Model API not available: {e}")

# Configuration
ROOT_DIR = os.path.dirname(SRC_DIR)
ENV_PATH = os.path.join(ROOT_DIR, "secrets", ".env")
CONFIG_PATH = os.path.join(SRC_DIR, "config", "config.yaml")

load_dotenv(dotenv_path=ENV_PATH)


class AIProcessingQueue:
    """Global AI processing queue to limit concurrent AI analysis to 2 pairs"""
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.processing_pairs = set()  # Currently processing pairs
        # Load from config - will be set later when config is available
        self.max_concurrent = 2  # Default fallback - overridden by config.yaml multi_agent_system.max_concurrent_ai_processing
        self.queue_lock = Lock()
        self._initialized = True
    
    def can_process(self, symbol: str) -> bool:
        """Check if a pair can start AI processing"""
        with self.queue_lock:
            return len(self.processing_pairs) < self.max_concurrent or symbol in self.processing_pairs
    
    def start_processing(self, symbol: str) -> bool:
        """Try to start AI processing for a pair"""
        with self.queue_lock:
            if symbol in self.processing_pairs:
                return True  # Already processing
            if len(self.processing_pairs) < self.max_concurrent:
                self.processing_pairs.add(symbol)
                return True
            return False  # Queue full
    
    def finish_processing(self, symbol: str):
        """Mark AI processing as finished for a pair"""
        with self.queue_lock:
            self.processing_pairs.discard(symbol)
    
    def get_status(self) -> dict:
        """Get current processing status"""
        with self.queue_lock:
            return {
                "processing_pairs": list(self.processing_pairs),
                "count": len(self.processing_pairs),
                "max_concurrent": self.max_concurrent
            }


class MultiAgentTradingBot:
    """
    Advanced multi-agent trading bot with specialized agents for different tasks.
    
    Architecture:
    - Coordinator Agent: Orchestrates all other agents
    - Data Agent: Centralized data collection and caching
    - Sentiment Agent: Distributed sentiment analysis
    - Risk Agent: Proactive risk monitoring
    - Trading Workers: Execute actual trading logic
    """
    
    def __init__(self):
        self.config = self._load_config()
        setup_logger("multi_agent_bot")
        
        # Core components
        self.operation_mode = self.config["operation_mode"].lower()
        self.api_client = APIClient(self.config, operation_mode=self.operation_mode)
        self.alerter = Alerter(self.api_client)
        
        # Real-time WebSocket client for low-latency data
        testnet = self.operation_mode == "shadow"
        self.ws_client = SimpleBinanceWebSocket(testnet=testnet)
        
        # Initialize intelligent cache
        self.cache = get_global_cache()
        self._setup_cache_callbacks()
        
        # Sistema de logging por pares
        self.multi_pair_logger = get_multi_pair_logger()
        
        # Agents
        self.coordinator = None
        self.data_agent = None
        self.sentiment_agent = None
        self.risk_agent = None
        self.ai_agent = None
        self.ai_integration = None
        self.smart_decision_engine = None
        
        # Trading components
        self.capital_manager = CapitalManager(self.api_client, self.config)
        self.pair_selector = None
        self.trading_workers = {}
        self.rl_agents = {}
        
        # AI Processing Queue - Global singleton
        self.ai_queue = AIProcessingQueue()
        # Apply configuration from config.yaml
        multi_agent_config = self.config.get('multi_agent_system', {})
        configured_max = multi_agent_config['max_concurrent_ai_processing']
        self.ai_queue.max_concurrent = configured_max
        log.info(f"AI Processing Queue configured with max_concurrent = {configured_max}")
        
        # Process management
        self.worker_processes = {}
        self.worker_stop_events = {}  # Individual stop events per worker
        self.stop_event = multiprocessing.Event()  # Global stop event for system shutdown
        self.global_trade_counter = multiprocessing.Value("i", 0)
        
        # Performance monitoring
        self.system_stats = {
            "start_time": time.time(),
            "total_trades": 0,
            "active_pairs": 0,
            "system_health": 100.0,
            "cache_efficiency": 0.0
        }
        
        log.info(f"MultiAgentTradingBot initialized in {self.operation_mode.upper()} mode")
    
    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(CONFIG_PATH, "r") as f:
                config_data = yaml.safe_load(f)
                if config_data is None:
                    log.error(f"Config file {CONFIG_PATH} is empty or invalid")
                    sys.exit(1)
                log.info(f"Configuration loaded from {CONFIG_PATH}")
                return config_data
        except FileNotFoundError:
            log.error(f"Configuration file not found at {CONFIG_PATH}")
            sys.exit(1)
        except Exception as e:
            log.error(f"Error loading configuration: {e}")
            sys.exit(1)
    
    def _setup_cache_callbacks(self) -> None:
        """Setup intelligent cache prefetch callbacks."""
        def fetch_ticker_data(key: str):
            """Callback to fetch ticker data."""
            try:
                if "ticker_" in key:
                    parts = key.split("_")
                    if len(parts) >= 3:
                        market_type = parts[1]
                        symbol = parts[2] if parts[2] != "all" else None
                        return self.api_client.get_futures_ticker(symbol=symbol) if market_type == "futures" else self.api_client.get_spot_ticker(symbol=symbol)
                return None
            except Exception as e:
                log.error(f"Error in ticker prefetch callback: {e}")
                return None
        
        def fetch_kline_data(key: str):
            """Callback to fetch kline data."""
            try:
                if "kline_" in key:
                    parts = key.split("_")
                    if len(parts) >= 5:
                        market_type = parts[1]
                        symbol = parts[2]
                        interval = parts[3]
                        limit = int(parts[4])
                        if market_type == "futures":
                            klines = self.api_client.get_futures_klines(symbol, interval, limit)
                        else:
                            klines = self.api_client.get_spot_klines(symbol, interval, limit)
                        
                        if klines:
                            import pandas as pd
                            df = pd.DataFrame(klines, columns=[
                                "Open time", "Open", "High", "Low", "Close", "Volume",
                                "Close time", "Quote asset volume", "Number of trades",
                                "Taker buy base asset volume", "Taker buy quote asset volume", "Ignore"
                            ])
                            for col in ["Open", "High", "Low", "Close", "Volume"]:
                                df[col] = pd.to_numeric(df[col])
                            return df
                return None
            except Exception as e:
                log.error(f"Error in kline prefetch callback: {e}")
                return None
        
        # Register callbacks
        self.cache.register_prefetch_callback("ticker_", fetch_ticker_data)
        self.cache.register_prefetch_callback("kline_", fetch_kline_data)
        
        log.info("Cache prefetch callbacks registered")
    
    def initialize_agents(self) -> None:
        """Initialize all specialized agents."""
        log.info("Initializing specialized agents...")
        
        try:
            # Initialize Coordinator Agent
            self.coordinator = CoordinatorAgent(self.config, self.api_client)
            self.coordinator.initialize_agents()
            
            # Get agent references from coordinator
            self.data_agent = self.coordinator.get_agent("data")
            self.sentiment_agent = self.coordinator.get_agent("sentiment")
            self.ai_agent = self.coordinator.get_agent("ai")  # May be None if disabled
            
            # Initialize Risk Agent separately
            self.risk_agent = RiskAgent(self.config, self.api_client, self.alerter)
            
            # Initialize AI Integration if AI agent is available
            if self.ai_agent is not None:
                try:
                    self.ai_integration = AITradingIntegration(self.ai_agent)
                    # Initialize Smart Decision Engine
                    self.smart_decision_engine = SmartTradingDecisionEngine(
                        self.ai_agent, self.api_client, self.config
                    )
                    log.info("AI Trading Integration and Smart Decision Engine initialized")
                except Exception as e:
                    log.warning(f"Failed to initialize AI Integration: {e}")
                    self.ai_integration = None
                    self.smart_decision_engine = None
                    log.info("System will continue without AI integration")
            else:
                log.info("AI agent disabled in configuration - no AI integration will be used")
                self.ai_integration = None
                self.smart_decision_engine = None
            
            # Initialize Pair Selector with sentiment integration
            self.pair_selector = PairSelector(
                self.config,
                self.api_client,
                get_sentiment_score_func=self._get_sentiment_score
            )
            
            # Register all agents with the API
            all_agents = {
                "coordinator": self.coordinator,
                "data": self.data_agent,
                "sentiment": self.sentiment_agent,
                "risk": self.risk_agent,
            }
            if self.ai_agent is not None:
                all_agents["ai"] = self.ai_agent
            
            # Register agents with model API (if available)
            if MODEL_API_AVAILABLE:
                model_api.set_agents(all_agents)
                log.info("All agents registered with the API")
            else:
                log.info("Model API not available, skipping agent registration")
            
            log.info("All agents initialized successfully")
            
        except Exception as e:
            log.error(f"Error initializing agents: {e}", exc_info=True)
            raise
    
    def _get_sentiment_score(self, smoothed: bool = True) -> float:
        """Get sentiment score from sentiment agent."""
        if self.sentiment_agent:
            return self.sentiment_agent.get_latest_sentiment(smoothed=smoothed)
        return 0.0
    
    def start(self) -> None:
        """Start the multi-agent trading system."""
        log.info("Starting Multi-Agent Trading System...")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            # Initialize agents
            self.initialize_agents()
            
            # Initialize and start Global TP/SL Manager (singleton)
            log.info("Initializing Global TP/SL Manager...")
            global_tpsl = get_global_tpsl_manager(self.api_client, self.config)
            if global_tpsl:
                start_global_tpsl()
                log.info("🎯 Global TP/SL Manager iniciado para todos os pares")
            else:
                log.error("❌ Falha ao inicializar Global TP/SL Manager")
            
            # Start real-time WebSocket for low-latency data
            log.info("Starting real-time WebSocket connection...")
            self.ws_client.start()
            
            # Start coordinator (this starts data and sentiment agents)
            self.coordinator.start_coordination()
            
            # Initialize smart engine for efficient market analysis
            self.coordinator._pair_selector = self.pair_selector
            self.coordinator.initialize_smart_engine()
            
            # Start risk agent
            self.risk_agent.start()
            
            # Send startup notification
            self.multi_pair_logger.log_system_event(
                f"🚀 Multi-Agent Trading System iniciado em modo {self.operation_mode.upper()}", "SUCCESS"
            )
            self.alerter.send_message(
                f"🚀 Multi-Agent Trading System Started - {self.operation_mode.upper()} Mode 🚀"
            )
            
            # Start main coordination loop
            self._main_loop()
            
        except Exception as e:
            log.error(f"Error starting multi-agent system: {e}", exc_info=True)
            self.alerter.send_critical_alert(f"Failed to start trading system: {e}")
            self.stop()
    
    def _main_loop(self) -> None:
        """Main coordination loop."""
        # Load intervals from config
        multi_agent_config = self.config.get('multi_agent_system', {})
        pair_update_cycle_minutes = multi_agent_config['pair_update_cycle_minutes']
        pair_update_interval = pair_update_cycle_minutes * 60  # Convert to seconds
        last_pair_update = 0
        stats_update_interval = multi_agent_config['stats_update_interval_seconds']
        last_stats_update = 0
        status_summary_interval = multi_agent_config['status_summary_interval_seconds']
        last_status_summary = 0
        
        while not self.stop_event.is_set():
            loop_start = time.time()
            
            try:
                current_time = time.time()
                
                # Update pair selection periodically
                if current_time - last_pair_update > pair_update_interval:
                    self._update_trading_pairs()
                    last_pair_update = current_time
                
                # Update system statistics
                if current_time - last_stats_update > stats_update_interval:
                    self._update_system_stats()
                    last_stats_update = current_time
                
                # Print status summary
                if current_time - last_status_summary > status_summary_interval:
                    self.multi_pair_logger.print_status_summary()
                    last_status_summary = current_time
                
                # Monitor worker processes
                self._monitor_workers()
                
                # Check system health
                self._check_system_health()
                
                # Wait for next iteration
                elapsed = time.time() - loop_start
                main_loop_cycle_seconds = multi_agent_config['main_loop_cycle_seconds']
                wait_time = max(0, main_loop_cycle_seconds - elapsed)
                if wait_time > 0:
                    self.stop_event.wait(wait_time)
                
            except Exception as e:
                log.error(f"Error in main loop: {e}", exc_info=True)
                # Reportar erro crítico mas continuar executando
                try:
                    self.alerter.send_critical_alert(f"Main loop error: {str(e)[:200]}")
                except:
                    pass
                self.stop_event.wait(30)  # Wait before retry
        
        log.info("Main loop exited")
    
    def _update_trading_pairs(self) -> None:
        """Update selected trading pairs and start/stop workers accordingly."""
        log.info("Updating trading pairs...")
        
        try:
            # Initialize trade activity tracker if not exists
            if not hasattr(self, 'trade_activity_tracker'):
                try:
                    from .utils.trade_activity_tracker import get_trade_activity_tracker
                except ImportError:
                    # Fallback for direct script execution
                    import sys
                    import os
                    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                    from src.utils.trade_activity_tracker import get_trade_activity_tracker
                self.trade_activity_tracker = get_trade_activity_tracker(config=self.config)
            
            # Check if auto pair addition is enabled
            auto_pair_enabled = self.config["trading"]["enable_auto_pair_addition"]
            balance_threshold = self.config["trading"]["balance_threshold_usd"]
            
            # Get current balance to determine if we can add more pairs
            balances = self.capital_manager.get_available_balances()
            total_available = balances.get("total_usdt", 0)
            current_pairs = set(self.worker_processes.keys())
            
            log.info(f"💰 Saldo disponível: ${total_available:.2f} USDT, Pares ativos: {len(current_pairs)}")
            
            # ===== NOVO: VERIFICAÇÃO DE MARGEM INSUFICIENTE =====
            # Verificar especificamente o saldo futures
            futures_usdt = balances.get("futures_usdt", 0)
            if futures_usdt < 5.0 and len(current_pairs) > 0:
                log.error(f"🚨 MARGEM INSUFICIENTE: Apenas ${futures_usdt:.2f} USDT na conta futures")
                log.error(f"⚠️ Sistema em MODO DE SOBREVIVÊNCIA - apenas mantendo posições existentes")
                log.error(f"💡 AÇÃO NECESSÁRIA: Transferir USDT para conta Futures")
                
                # Enviar alerta crítico
                self.alerter.send_critical_alert(
                    f"🚨 MARGEM INSUFICIENTE: ${futures_usdt:.2f} USDT - Sistema pausado"
                )
                
                # Não adicionar novos pares quando margem insuficiente
                auto_pair_enabled = False
                log.warning(f"🛑 Adição automática de pares DESABILITADA por margem insuficiente")
            
            # ===== NOVO: SISTEMA DE ROTAÇÃO INTELIGENTE =====
            # 1. Verificar pares inativos e com performance ruim
            inactive_pairs = set()
            poor_performing_pairs = set()
            
            if current_pairs:
                # Obter dados de atividade para análise
                activity_data = self.trade_activity_tracker.get_activity_data(list(current_pairs))
                
                # Usar o monitor de qualidade ATR com dados de atividade
                atr_analysis = self.pair_selector.monitor_atr_quality(
                    list(current_pairs), 
                    trade_activity_data=activity_data
                )
                
                # Identificar pares problemáticos
                problematic_pairs = atr_analysis.get("problematic_pairs", {})
                replacement_suggestions = atr_analysis.get("replacement_suggestions", {})
                
                if problematic_pairs:
                    log.info(f"🔄 Análise de rotação: {len(problematic_pairs)} pares precisam ser substituídos")
                    
                    for symbol, issues in problematic_pairs.items():
                        issues_list = issues.get("issues", [])
                        
                        # Categorizar por tipo de problema
                        if any("Inativo" in issue for issue in issues_list):
                            inactive_pairs.add(symbol)
                        if any("ATR" in issue or "Volume" in issue for issue in issues_list):
                            poor_performing_pairs.add(symbol)
                        
                        log.info(f"❌ {symbol}: {', '.join(issues_list)}")
                
                # Aplicar substituições para pares inativos (sempre) e para poor performers (se há capital)
                pairs_to_replace = set(replacement_suggestions.keys())
                inactive_replacements = {k: v for k, v in replacement_suggestions.items() if k in inactive_pairs}
                performance_replacements = {k: v for k, v in replacement_suggestions.items() if k in poor_performing_pairs}
                
                # SEMPRE substituir pares inativos (>1h sem atividade) - independente do saldo
                if inactive_replacements:
                    log.info(f"🔄 Executando {len(inactive_replacements)} substituições de pares INATIVOS...")
                    
                    for old_pair, new_pair_info in inactive_replacements.items():
                        new_pair = new_pair_info["symbol"]
                        
                        # Parar o par antigo PRIMEIRO (libera capital)
                        if old_pair in current_pairs:
                            log.info(f"🛑 Parando {old_pair} (motivo: inativo há >1h)")
                            self._cancel_orders_for_symbol(old_pair)  # Cancela ordens primeiro
                            self._stop_trading_worker(old_pair)
                            current_pairs.remove(old_pair)
                        
                        # Aguardar um momento para liberação do capital
                        time.sleep(1)
                        
                        # Iniciar o novo par
                        log.info(f"🚀 Iniciando {new_pair} (ATR: {new_pair_info['atr_percentage']:.2f}%)")
                        self._start_trading_worker(new_pair)
                        current_pairs.add(new_pair)
                        
                        # Registrar a troca
                        self.multi_pair_logger.log_system_event(
                            f"🔄 Rotação de par: {old_pair} → {new_pair} (motivo: {', '.join(problematic_pairs.get(old_pair, {}).get('issues', ['inatividade']))})",
                            "PAIR_ROTATION"
                        )
                
                # Substituir pares com performance ruim APENAS se há capital disponível
                if performance_replacements and total_available > balance_threshold:
                    log.info(f"🔄 Executando {len(performance_replacements)} substituições de pares com BAIXA PERFORMANCE...")
                    
                    for old_pair, new_pair_info in performance_replacements.items():
                        new_pair = new_pair_info["symbol"]
                        
                        # Parar o par antigo
                        if old_pair in current_pairs:
                            log.info(f"🛑 Parando {old_pair} (motivo: baixa performance)")
                            self._cancel_orders_for_symbol(old_pair)
                            self._stop_trading_worker(old_pair)
                            current_pairs.remove(old_pair)
                        
                        time.sleep(1)
                        
                        # Iniciar o novo par
                        log.info(f"🚀 Iniciando {new_pair} (ATR: {new_pair_info['atr_percentage']:.2f}%)")
                        self._start_trading_worker(new_pair)
                        current_pairs.add(new_pair)
                        
                        # Registrar a troca
                        self.multi_pair_logger.log_system_event(
                            f"🔄 Rotação de par: {old_pair} → {new_pair} (motivo: {', '.join(problematic_pairs.get(old_pair, {}).get('issues', ['performance']))})",
                            "PAIR_ROTATION"
                        )
            
            # ===== LÓGICA ORIGINAL: ADIÇÃO DE NOVOS PARES =====
            # Get selected pairs from pair selector
            if auto_pair_enabled and total_available > balance_threshold:
                max_pairs = self.config["trading"]["max_concurrent_pairs"]
                available_slots = max_pairs - len(current_pairs)
                
                if available_slots > 0:
                    # Force update to get fresh pair selection when we have available capital
                    log.info(f"🔍 Saldo suficiente detectado (${total_available:.2f}) - buscando novos pares para trading...")
                    log.info(f"📊 Slots disponíveis: {available_slots} de {max_pairs} máximos")
                    selected_pairs = self.pair_selector.get_selected_pairs(force_update=True)
                else:
                    log.info(f"🏪 Máximo de pares atingido ({len(current_pairs)}/{max_pairs})")
                    selected_pairs = list(current_pairs)
            else:
                # Use cache if available or return preferred symbols if no balance/auto disabled
                selected_pairs = self.pair_selector.get_selected_pairs(force_update=False)
                if not selected_pairs and len(current_pairs) == 0:
                    # Force start with preferred symbols if nothing is running
                    log.warning("🆘 Nenhum par ativo - forçando início com símbolos preferred...")
                    preferred = self.config["pair_selection"]["futures_pairs"]["preferred_symbols"]
                    selected_pairs = preferred[:3] if preferred else []
            
            if not selected_pairs:
                log.warning("No pairs selected for trading")
                return
            
            log.info(f"Selected pairs for trading: {selected_pairs}")
            
            # Update worker processes
            target_pairs = set(selected_pairs)
            
            # Stop workers for deselected pairs (que não foram substituídos)
            pairs_to_stop = current_pairs - target_pairs
            for pair in pairs_to_stop:
                log.info(f"🛑 Parando trading para {pair}")
                self._stop_trading_worker(pair)
            
            # Start workers for new pairs (que não foram da substituição)
            pairs_to_start = target_pairs - current_pairs
            for pair in pairs_to_start:
                log.info(f"🚀 Iniciando trading para novo par: {pair}")
                self._start_trading_worker(pair)
            
            # Add pairs to risk monitoring
            for pair in selected_pairs:
                self.risk_agent.add_symbol_monitoring(pair)
            
            # Subscribe to real-time data for active pairs
            for pair in selected_pairs:
                log.info(f"Subscribing to real-time data for {pair}")
                self.ws_client.subscribe_ticker(pair)
            
            # Remove pairs from risk monitoring
            for pair in pairs_to_stop:
                self.risk_agent.remove_symbol_monitoring(pair)
            
            self.system_stats["active_pairs"] = len(selected_pairs)
            
        except Exception as e:
            log.error(f"Error updating trading pairs: {e}", exc_info=True)
            self.alerter.send_critical_alert(f"Error updating trading pairs: {e}")
    
    def _cancel_orders_for_symbol(self, symbol: str) -> None:
        """Cancel all orders for a specific symbol directly via API (independent of worker state)."""
        log.info(f"[{symbol}] Cancelling all orders directly via API...")
        
        try:
            orders_cancelled = 0
            
            # Cancel futures orders
            try:
                futures_orders = self.api_client.get_futures_open_orders(symbol=symbol)
                for order in futures_orders:
                    try:
                        self.api_client.cancel_futures_order(symbol=symbol, orderId=order['orderId'])
                        orders_cancelled += 1
                        log.info(f"[{symbol}] ✅ Cancelled FUTURES order {order['orderId']}")
                    except Exception as e:
                        log.warning(f"[{symbol}] ⚠️ Failed to cancel FUTURES order {order['orderId']}: {e}")
            except Exception as e:
                log.warning(f"[{symbol}] Error fetching/cancelling FUTURES orders: {e}")
            
            # Cancel spot orders (if any)
            try:
                spot_orders = self.api_client.get_spot_open_orders(symbol=symbol)
                for order in spot_orders:
                    try:
                        self.api_client.cancel_spot_order(symbol=symbol, orderId=order['orderId'])
                        orders_cancelled += 1
                        log.info(f"[{symbol}] ✅ Cancelled SPOT order {order['orderId']}")
                    except Exception as e:
                        log.warning(f"[{symbol}] ⚠️ Failed to cancel SPOT order {order['orderId']}: {e}")
            except Exception as e:
                log.warning(f"[{symbol}] Error fetching/cancelling SPOT orders: {e}")
            
            if orders_cancelled > 0:
                log.info(f"[{symbol}] 🎯 Successfully cancelled {orders_cancelled} orders directly")
                self.multi_pair_logger.log_system_event(
                    f"Cancelled {orders_cancelled} orders for {symbol} during pair rotation", "ORDER_CLEANUP"
                )
            else:
                log.info(f"[{symbol}] No open orders found to cancel")
                
        except Exception as e:
            log.error(f"[{symbol}] Error during direct order cancellation: {e}")
            self.alerter.send_critical_alert(f"Failed to cancel orders for {symbol}: {e}")
    
    def _start_trading_worker(self, symbol: str) -> None:
        """Start a trading worker process for a symbol."""
        log.info(f"Starting trading worker for {symbol}")
        
        try:
            max_concurrent = self.config["trading"]["max_concurrent_pairs"]
            if len(self.worker_processes) >= max_concurrent:
                log.warning(f"Max concurrent pairs ({max_concurrent}) reached. Cannot start worker for {symbol}")
                return
            
            # Create individual stop event for this worker
            worker_stop_event = multiprocessing.Event()
            self.worker_stop_events[symbol] = worker_stop_event
            
            # Prepare shared resources for worker
            shared_resources = {
                "ai_agent": self.ai_agent if self.ai_agent is not None else None,
                "smart_decision_engine": self.smart_decision_engine
            }
            
            # Create worker process with both individual and global stop events
            process = multiprocessing.Process(
                target=self._trading_worker_main,
                args=(symbol, self.config, worker_stop_event, self.stop_event, self.global_trade_counter, shared_resources),
                daemon=True,
                name=f"TradingWorker-{symbol}"
            )
            
            self.worker_processes[symbol] = process
            process.start()
            
            log.info(f"Trading worker for {symbol} started (PID: {process.pid})")
            
        except Exception as e:
            log.error(f"Error starting trading worker for {symbol}: {e}")
    
    def _stop_trading_worker(self, symbol: str) -> None:
        """Stop a trading worker process with proper cleanup."""
        log.info(f"🛑 Stopping trading worker for {symbol}")
        
        try:
            # STEP 1: Cancel all orders IMMEDIATELY (independent of worker state)
            log.info(f"[{symbol}] Step 1: Cancelling orders before stopping worker...")
            self._cancel_orders_for_symbol(symbol)
            
            # STEP 2: Stop the worker process
            if symbol in self.worker_processes:
                process = self.worker_processes[symbol]
                
                if process.is_alive():
                    # Use individual stop event (not global)
                    if symbol in self.worker_stop_events:
                        self.worker_stop_events[symbol].set()
                        log.info(f"[{symbol}] Step 2: Signaled individual stop event for worker")
                    
                    # Wait for graceful shutdown
                    multi_agent_config = self.config.get('multi_agent_system', {})
                    worker_shutdown_timeout = multi_agent_config['worker_shutdown_timeout_seconds']
                    process.join(timeout=worker_shutdown_timeout)
                    
                    if process.is_alive():
                        log.warning(f"[{symbol}] Worker did not terminate gracefully. Sending SIGTERM.")
                        try:
                            os.kill(process.pid, signal.SIGTERM)
                            process.join(timeout=worker_shutdown_timeout // 2)
                            
                            if process.is_alive():
                                log.warning(f"[{symbol}] Worker still alive after SIGTERM. Sending SIGKILL.")
                                process.kill()
                                process.join(timeout=worker_shutdown_timeout // 6)
                        except ProcessLookupError:
                            log.info(f"[{symbol}] Process already terminated")
                        except Exception as kill_error:
                            log.error(f"[{symbol}] Error killing process: {kill_error}")
                
                # STEP 3: Cleanup resources
                del self.worker_processes[symbol]
                if symbol in self.worker_stop_events:
                    del self.worker_stop_events[symbol]
                    
                log.info(f"[{symbol}] ✅ Trading worker stopped and cleaned up")
            else:
                log.warning(f"[{symbol}] Worker process not found in worker_processes")
        
        except Exception as e:
            log.error(f"[{symbol}] Error stopping trading worker: {e}")
            # Still try to cleanup resources even if stopping failed
            try:
                if symbol in self.worker_processes:
                    del self.worker_processes[symbol]
                if symbol in self.worker_stop_events:
                    del self.worker_stop_events[symbol]
            except:
                pass
    
    def _trading_worker_main(
        self,
        symbol: str,
        config: dict,
        individual_stop_event: multiprocessing.Event,
        global_stop_event: multiprocessing.Event,
        global_trade_counter: multiprocessing.Value,
        shared_resources: dict = None
    ) -> None:
        """Main function for trading worker process."""
        # Setup logging for worker
        worker_logger = setup_logger(f"{symbol}_worker")
        
        try:
            log.info(f"[{symbol}] Trading worker started (PID: {os.getpid()})")
            
            # Initialize components for this worker
            operation_mode = config["operation_mode"].lower()
            api_client = APIClient(config, operation_mode=operation_mode)
            alerter = Alerter(api_client)
            
            # Initialize capital manager and validate symbol before grid initialization
            capital_manager = CapitalManager(api_client, config)
            
            # Check if we have sufficient capital for this symbol, but allow recovery of existing positions
            min_capital = capital_manager.min_capital_per_pair_usd
            has_existing_position = False
            
            # Quick check for existing positions/orders before capital validation
            try:
                # Check for existing grid state file
                state_file = f"data/grid_states/{symbol}_state.json"
                if os.path.exists(state_file):
                    has_existing_position = True
                    log.info(f"[{symbol}] Found existing grid state - allowing recovery despite low capital")
                
                # Also check for existing positions in the exchange
                if not has_existing_position:
                    positions = api_client.get_futures_positions()
                    if positions:
                        for pos in positions:
                            if pos.get('symbol') == symbol and float(pos.get('positionAmt', 0)) != 0:
                                has_existing_position = True
                                log.info(f"[{symbol}] Found existing position in exchange - allowing recovery")
                                break
            except Exception as e:
                log.warning(f"[{symbol}] Error checking for existing positions: {e}")
            
            # Only enforce capital requirements for new positions
            if not has_existing_position and not capital_manager.can_trade_symbol(symbol, min_capital):
                log.error(f"[{symbol}] Insufficient capital to trade. Minimum required: ${min_capital:.2f}")
                capital_manager.log_capital_status()
                return
            elif has_existing_position:
                log.info(f"[{symbol}] Existing position detected - proceeding with recovery mode")
            
            # Get capital allocation for this symbol
            allocation = capital_manager.get_allocation_for_symbol(symbol)
            if not allocation:
                if has_existing_position:
                    # For existing positions, create minimal allocation for recovery
                    class SimpleAllocation:
                        def __init__(self, symbol, allocated_amount, grid_levels, spacing_percentage, max_position_size, market_type, leverage=10):
                            self.symbol = symbol
                            self.allocated_amount = allocated_amount
                            self.grid_levels = grid_levels
                            self.spacing_percentage = spacing_percentage
                            self.max_position_size = max_position_size
                            self.market_type = market_type
                            self.leverage = leverage
                    
                    allocation = SimpleAllocation(
                        symbol=symbol,
                        allocated_amount=1.0,  # Minimal amount for recovery
                        grid_levels=5,
                        spacing_percentage=0.005,
                        max_position_size=0.5,
                        market_type="futures",
                        leverage=10
                    )
                    log.info(f"[{symbol}] Created minimal allocation for position recovery")
                else:
                    # Calculate allocation for single symbol
                    allocations = capital_manager.calculate_optimal_allocations([symbol])
                    if not allocations:
                        log.error(f"[{symbol}] No capital can be allocated for trading")
                        return
                    allocation = allocations[0]
            
            log.info(f"[{symbol}] Capital allocated: ${allocation.allocated_amount:.2f} ({allocation.market_type}, {allocation.grid_levels} levels)")
            
            # Initialize grid logic with capital-adapted configuration
            # Update config with capital-specific parameters
            adapted_config = config.copy()
            adapted_config['initial_levels'] = allocation.grid_levels
            adapted_config['initial_spacing_perc'] = str(allocation.spacing_percentage)
            adapted_config['max_position_size_usd'] = allocation.max_position_size
            
            # Validate symbol exists in target market before proceeding
            if not capital_manager.is_symbol_valid(symbol, allocation.market_type):
                log.error(f"[{symbol}] Symbol not valid for {allocation.market_type} market. Skipping.")
                return
            
            # Initialize WebSocket client for worker process
            testnet = operation_mode == "shadow"
            worker_ws_client = SimpleBinanceWebSocket(testnet=testnet, config=config)
            worker_ws_client.start()
            worker_ws_client.subscribe_ticker(symbol)
            log.info(f"[{symbol}] Started and subscribed to real-time WebSocket data")
            
            try:
                grid_logic = GridLogic(symbol, adapted_config, api_client, 
                                     operation_mode=operation_mode, 
                                     market_type=allocation.market_type,
                                     ws_client=worker_ws_client)
            except ValueError as e:
                log.error(f"[{symbol}] Failed to initialize GridLogic: {e}")
                log.info(f"[{symbol}] Skipping this symbol and shutting down worker")
                return
            
            # Initialize RL agent (if enabled and available)
            rl_agent = None
            rl_enabled = config["rl_agent"]["enabled"]
            if rl_enabled and RL_AVAILABLE and RLAgent is not None:
                try:
                    rl_agent = RLAgent(config, symbol)
                    if not rl_agent.setup_agent(training=False):
                        log.warning(f"[{symbol}] Failed to setup RL agent, continuing without RL")
                        rl_agent = None
                except Exception as e:
                    log.warning(f"[{symbol}] RL agent initialization failed: {e}, continuing without RL")
                    rl_agent = None
            else:
                if not RL_AVAILABLE:
                    log.info(f"[{symbol}] RL agent not available (missing dependencies)")
                elif not rl_enabled:
                    log.info(f"[{symbol}] RL agent disabled in configuration")
                else:
                    log.info(f"[{symbol}] RL agent module not found")
            
            # Trading loop - AI-driven cycle (wait for previous analysis to complete)
            min_cycle_interval = config["trading"]["cycle_interval_seconds"]  # Minimum wait time
            local_trade_count = 0
            
            # Initialize pair logger
            pair_logger = get_pair_logger(symbol)
            pair_logger.log_info(f"Iniciando sistema de trading AI-driven para {symbol}")
            
            cycle_count = 0
            last_heartbeat = time.time()
            
            while not individual_stop_event.is_set() and not global_stop_event.is_set():
                cycle_start = time.time()
                cycle_count += 1
                
                # Heartbeat a cada 50 ciclos (≈5 minutos se ciclo = 6s)
                if cycle_count % 50 == 0:
                    current_time = time.time()
                    elapsed_minutes = (current_time - last_heartbeat) / 60
                    ai_queue_status = AIProcessingQueue().get_status()
                    log.info(f"[{symbol}] ❤️ Heartbeat: Cycle #{cycle_count}, {elapsed_minutes:.1f}min since last heartbeat, "
                            f"AI Queue: {ai_queue_status['count']}/{ai_queue_status['max_concurrent']} processing {ai_queue_status['processing_pairs']}")
                    last_heartbeat = current_time
                
                try:
                    # Get smart trading decision (AI + Dynamic Sizing)
                    rl_action = None
                    ai_decision = None
                    
                    # Get current market data
                    ticker = grid_logic._get_ticker()
                    current_price = grid_logic._get_current_price_from_ticker(ticker) if ticker else 0
                    market_data = {
                        "current_price": float(current_price),
                        "volume_24h": getattr(grid_logic, 'volume_24h', 0),
                        "price_change_24h": getattr(grid_logic, 'price_change_24h', 0),
                        "rsi": getattr(grid_logic, 'current_rsi', 50),
                        "atr_percentage": getattr(grid_logic, 'current_atr_percentage', 1.0),
                        "adx": getattr(grid_logic, 'current_adx', 25)
                    }
                    
                    # Get position info
                    try:
                        position = api_client.get_futures_position(symbol)
                        position_size = float(position.get('positionAmt', 0)) if position else 0
                        entry_price = float(position.get('entryPrice', 0)) if position else 0
                        unrealized_pnl = float(position.get('unrealizedPnl', 0)) if position else 0
                        position_side = "LONG" if position_size > 0 else "SHORT" if position_size < 0 else "NONE"
                        
                        # NOVO: Verificar se posição deve ser fechada por perda excessiva
                        if position_size != 0 and entry_price > 0:
                            loss_percentage = abs(unrealized_pnl / (abs(position_size) * entry_price))
                            risk_config = config.get('risk_management', {})
                            auto_close_loss_percentage = risk_config['auto_close_loss_percentage']
                            if loss_percentage > auto_close_loss_percentage:
                                log.warning(f"[{symbol}] Excessive loss detected: {loss_percentage*100:.2f}% (${unrealized_pnl:.2f})")
                                try:
                                    # Fechar posição por ordem de mercado
                                    close_side = "SELL" if position_size > 0 else "BUY"
                                    close_result = api_client.place_futures_order(
                                        symbol=symbol,
                                        side=close_side,
                                        order_type="MARKET",
                                        quantity=str(abs(position_size)),
                                        reduceOnly="true"
                                    )
                                    if close_result:
                                        log.info(f"[{symbol}] ✅ Closed losing position: ${unrealized_pnl:.2f}")
                                        pair_logger.log_error(f"🛑 Posição fechada por perda excessiva: {loss_percentage*100:.2f}%")
                                except Exception as e:
                                    log.error(f"[{symbol}] Failed to close losing position: {e}")
                        
                    except:
                        position_size = 0
                        entry_price = 0
                        unrealized_pnl = 0
                        position_side = "NONE"
                    
                    # Get grid info
                    active_orders = len(getattr(grid_logic, 'active_orders', []))
                    filled_orders = getattr(grid_logic, 'total_trades', 0)
                    grid_profit = float(getattr(grid_logic, 'total_realized_pnl', 0))
                    
                    # Update metrics no pair logger
                    pair_logger.update_metrics(
                        current_price=float(current_price),
                        entry_price=entry_price,
                        tp_price=0,  # Será atualizado se houver TP/SL
                        sl_price=0,
                        unrealized_pnl=unrealized_pnl,
                        realized_pnl=grid_profit,
                        position_size=position_size,
                        leverage=allocation.leverage if allocation else 10,
                        rsi=market_data["rsi"],
                        atr=market_data["atr_percentage"] * current_price / 100,
                        adx=market_data["adx"],
                        volume_24h=market_data["volume_24h"],
                        price_change_24h=market_data["price_change_24h"],
                        grid_levels=grid_logic.num_levels,
                        active_orders=active_orders,
                        filled_orders=filled_orders,
                        grid_profit=grid_profit,
                        position_side=position_side,
                        market_type=allocation.market_type if allocation else "FUTURES"
                    )
                    
                    current_grid_params = {
                        "num_levels": grid_logic.num_levels,
                        "spacing_perc": float(grid_logic.current_spacing_percentage),
                        "recent_pnl": float(grid_logic.total_realized_pnl)
                    }
                    
                    # Get available balance
                    balances = capital_manager.get_available_balances()
                    available_balance = balances["futures_usdt"] + balances["spot_usdt"]
                    
                    # Try Smart Decision Engine first (AI + Dynamic Sizer) - Global Queue approach
                    if shared_resources and shared_resources.get("smart_decision_engine"):
                        # Get global AI processing queue
                        ai_queue = AIProcessingQueue()
                        
                        # Check if this pair can process AI analysis
                        if ai_queue.start_processing(symbol):
                            try:
                                # Get async smart decision
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                ai_decision = loop.run_until_complete(
                                    shared_resources["smart_decision_engine"].get_smart_trading_action(
                                        symbol, market_data, current_grid_params, available_balance
                                    )
                                )
                                loop.close()
                                
                                if ai_decision and ai_decision.get("action") is not None:
                                    rl_action = ai_decision["action"]
                                    log.info(f"[{symbol}] AI Decision: action={rl_action}, confidence={ai_decision.get('confidence', 0):.2f}, "
                                            f"reasoning={ai_decision.get('reasoning', 'N/A')}")
                                
                            except Exception as e:
                                log.error(f"[{symbol}] Error getting AI decision: {e}")
                                rl_action = None
                            finally:
                                # Always release the AI processing slot
                                ai_queue.finish_processing(symbol)
                        else:
                            # AI queue is full, skip AI analysis this cycle
                            queue_status = ai_queue.get_status()
                            log.debug(f"[{symbol}] AI queue full ({queue_status['count']}/{queue_status['max_concurrent']}), "
                                     f"processing: {queue_status['processing_pairs']}")
                            rl_action = None
                    
                    # Fallback to traditional RL if AI decision failed and RL is available
                    if rl_action is None and rl_agent is not None:
                        market_state = grid_logic.get_market_state()
                        if market_state is not None:
                            try:
                                # Get sentiment if available
                                sentiment_config = config.get("sentiment_analysis", {})
                                if sentiment_config["rl_feature"]["enabled"]:
                                    sentiment_score = 0.0
                                    rl_action = rl_agent.predict_action(market_state, sentiment_score=sentiment_score)
                                else:
                                    rl_action = rl_agent.predict_action(market_state)
                                
                                log.debug(f"[{symbol}] Fallback RL action: {rl_action}")
                            
                            except Exception as e:
                                log.error(f"[{symbol}] Error getting RL action: {e}")
                                rl_action = 0  # Safe fallback
                    
                    # Execute trading logic with AI/RL decision
                    previous_orders = len(getattr(grid_logic, 'active_orders', []))
                    grid_logic.run_cycle(rl_action=rl_action, ai_decision=ai_decision)
                    current_orders = len(getattr(grid_logic, 'active_orders', []))
                    
                    # Track activity to decide if we should log trading cycle
                    has_activity = False
                    
                    # Check for new orders
                    if current_orders > previous_orders:
                        pair_logger.log_info(f"Novas ordens criadas: {current_orders - previous_orders}")
                        has_activity = True
                    
                    # Update trade counter
                    new_trade_count = grid_logic.total_trades
                    if new_trade_count > local_trade_count:
                        trades_made = new_trade_count - local_trade_count
                        with global_trade_counter.get_lock():
                            global_trade_counter.value += trades_made
                        local_trade_count = new_trade_count
                        
                        # Log trade completion
                        pair_logger.log_info(f"✅ {trades_made} trade(s) executado(s)! Total: {new_trade_count}")
                        has_activity = True
                    
                    # Check for position changes
                    try:
                        new_position = api_client.get_futures_position(symbol)
                        new_position_size = float(new_position.get('positionAmt', 0)) if new_position else 0
                        new_unrealized_pnl = float(new_position.get('unrealizedPnl', 0)) if new_position else 0
                        
                        if abs(new_position_size - position_size) > 0.0001:  # Position changed
                            new_side = "LONG" if new_position_size > 0 else "SHORT" if new_position_size < 0 else "NONE"
                            new_entry = float(new_position.get('entryPrice', 0)) if new_position else 0
                            pair_logger.log_position_update(new_side, new_entry, new_position_size, new_unrealized_pnl)
                            has_activity = True
                    except Exception as pos_error:
                        pass  # Ignore position check errors
                    
                    # Only log full trading cycle when there's relevant activity
                    if has_activity:
                        pair_logger.log_trading_cycle(force_terminal=True)
                
                except Exception as e:
                    pair_logger.log_error(f"Erro no ciclo de trading: {e}")
                    log.error(f"[{symbol}] Error in trading cycle: {e}", exc_info=True)
                    alerter.send_critical_alert(f"Error in {symbol} trading cycle: {e}")
                
                # Standard cycle timing with minimum interval
                elapsed = time.time() - cycle_start
                wait_time = max(0, min_cycle_interval - elapsed)
                
                if wait_time > 0:
                    # Wait on individual stop event, but check global stop event periodically
                    individual_stop_event.wait(wait_time)
        
        except Exception as e:
            log.error(f"[{symbol}] Critical error in trading worker: {e}", exc_info=True)
            try:
                Alerter().send_critical_alert(f"Critical error in {symbol} worker: {e}")
            except:
                pass
        
        finally:
            log.info(f"[{symbol}] Trading worker shutting down - starting cleanup")
            try:
                # Enhanced cleanup process
                if "grid_logic" in locals():
                    # Stop TP/SL manager first
                    if hasattr(grid_logic, 'tpsl_manager'):
                        log.info(f"[{symbol}] Stopping TP/SL manager...")
                        grid_logic.tpsl_manager.stop_monitoring()
                    
                    # Cancel orders in all modes (production, shadow, etc.)
                    log.info(f"[{symbol}] Cancelling all orders during worker cleanup...")
                    grid_logic.cancel_all_orders()
                
                # Clean up loggers to prevent memory leaks
                try:
                    from utils.pair_logger import cleanup_process_loggers
                    cleanup_process_loggers()
                    log.info(f"[{symbol}] Cleaned up process loggers")
                except Exception as cleanup_error:
                    log.warning(f"[{symbol}] Error cleaning up loggers: {cleanup_error}")
                
                # Clean up WebSocket connections
                if "worker_ws_client" in locals():
                    try:
                        worker_ws_client.unsubscribe_ticker(symbol)
                        log.info(f"[{symbol}] Unsubscribed from WebSocket")
                    except Exception as ws_error:
                        log.warning(f"[{symbol}] Error unsubscribing from WebSocket: {ws_error}")
                
                log.info(f"[{symbol}] Worker cleanup completed")
                
            except Exception as e:
                log.error(f"[{symbol}] Error during cleanup: {e}")
    
    def _monitor_workers(self) -> None:
        """Monitor worker processes and restart if needed."""
        restarted_count = 0
        
        for symbol in list(self.worker_processes.keys()):
            process = self.worker_processes[symbol]
            
            if not process.is_alive():
                log.warning(f"Worker for {symbol} (PID: {process.pid}) died. Restarting...")
                
                # Remove dead process
                del self.worker_processes[symbol]
                
                # Restart worker
                self._start_trading_worker(symbol)
                restarted_count += 1
                
                # Send alert
                self.alerter.send_critical_alert(f"Restarted worker for {symbol}")
        
        if restarted_count > 0:
            log.info(f"Restarted {restarted_count} worker processes")
    
    def _update_system_stats(self) -> None:
        """Update system statistics."""
        try:
            # Update trade counter
            with self.global_trade_counter.get_lock():
                self.system_stats["total_trades"] = self.global_trade_counter.value
            
            # Update cache efficiency
            cache_stats = self.cache.get_statistics()
            self.system_stats["cache_efficiency"] = cache_stats.get("hit_rate_percent", 0)
            
            # Update system health from coordinator
            if self.coordinator:
                coordinator_status = self.coordinator.get_system_status()
                agent_health = coordinator_status.get("agent_health", {})
                self.system_stats["system_health"] = agent_health.get("system_health_percentage", 0)
            
            # Log statistics periodically
            uptime = time.time() - self.system_stats["start_time"]
            log.info(
                f"System Stats - Uptime: {uptime/3600:.1f}h, "
                f"Trades: {self.system_stats['total_trades']}, "
                f"Active Pairs: {self.system_stats['active_pairs']}, "
                f"Health: {self.system_stats['system_health']:.1f}%, "
                f"Cache Efficiency: {self.system_stats['cache_efficiency']:.1f}%"
            )
        
        except Exception as e:
            log.error(f"Error updating system stats: {e}")
    
    def _check_system_health(self) -> None:
        """Check overall system health and take action if needed."""
        try:
            health_percentage = self.system_stats.get("system_health", 100)
            
            if health_percentage < 30:
                log.critical(f"Critical system health: {health_percentage:.1f}%")
                self.alerter.send_critical_alert(
                    f"🚨 CRITICAL: System health at {health_percentage:.1f}%! Considering shutdown..."
                )
                
                # Could implement automatic emergency shutdown here
                # self.emergency_shutdown()
            
            elif health_percentage < 60:
                log.warning(f"Poor system health: {health_percentage:.1f}%")
                self.alerter.send_message(
                    f"⚠️ WARNING: System health at {health_percentage:.1f}%"
                )
        
        except Exception as e:
            log.error(f"Error checking system health: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        # Prevent multiple signal handling
        if hasattr(self, '_shutdown_started') and self._shutdown_started:
            return
        
        signal_name = signal.Signals(signum).name
        log.warning(f"Received signal {signal_name}. Initiating graceful shutdown...")
        
        # Mark shutdown as started
        self._shutdown_started = True
        
        # Set stop event immediately
        self.stop_event.set()
        
        # Start shutdown in separate thread to avoid blocking
        shutdown_thread = threading.Thread(target=self._emergency_shutdown, daemon=True)
        shutdown_thread.start()
        
        # Wait a bit for graceful shutdown
        shutdown_thread.join(timeout=5)
        
        # Force exit if still running
        if shutdown_thread.is_alive():
            log.error("Graceful shutdown timeout. Forcing exit...")
            os._exit(1)
    
    def _emergency_shutdown(self):
        """Emergency shutdown procedure."""
        try:
            self.stop()
        except Exception as e:
            log.error(f"Error in emergency shutdown: {e}")
        finally:
            # Force exit after cleanup attempt
            os._exit(0)
    
    def stop(self) -> None:
        """Stop the multi-agent trading system."""
        if hasattr(self, '_shutdown_started') and self._shutdown_started:
            log.info("Shutdown already in progress")
            return
        
        self._shutdown_started = True
        log.info("Stopping Multi-Agent Trading System...")
        self.stop_event.set()  # Global stop event for system components
        
        # Signal all individual worker stop events
        for symbol, stop_event in list(self.worker_stop_events.items()):
            try:
                stop_event.set()
                log.info(f"Signaled stop event for worker {symbol}")
            except Exception as e:
                log.error(f"Error signaling stop event for {symbol}: {e}")
        
        try:
            # Stop all trading workers with timeout
            log.info("Stopping trading workers...")
            worker_stop_timeout = 5
            
            for symbol in list(self.worker_processes.keys()):
                try:
                    self._stop_trading_worker(symbol)
                except Exception as e:
                    log.error(f"Error stopping worker {symbol}: {e}")
            
            # Force kill any remaining workers
            remaining_workers = [p for p in self.worker_processes.values() if p.is_alive()]
            if remaining_workers:
                log.warning(f"Force killing {len(remaining_workers)} remaining workers")
                for process in remaining_workers:
                    try:
                        process.kill()
                        process.join(timeout=2)
                    except Exception as e:
                        log.error(f"Error force killing worker: {e}")
            
            # Cleanup AI agent asyncio components first
            if self.ai_agent is not None:
                try:
                    log.info("Cleaning up AI agent resources...")
                    import asyncio
                    loop = None
                    try:
                        loop = asyncio.get_event_loop()
                        if not loop.is_closed():
                            loop.run_until_complete(self.ai_agent.close_session())
                    except RuntimeError:
                        # Event loop is closed, create new one for cleanup
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.ai_agent.close_session())
                        loop.close()
                    log.info("AI agent cleanup complete")
                except Exception as e:
                    log.error(f"Error cleaning up AI agent: {e}")
            else:
                log.info("AI agent was disabled - no cleanup needed")
            
            # Stop other components with timeout
            components_to_stop = [
                ("risk_agent", self.risk_agent),
                ("coordinator", self.coordinator),
                ("cache", self.cache)
            ]
            
            for name, component in components_to_stop:
                if component:
                    try:
                        if hasattr(component, 'stop'):
                            component.stop()
                        elif hasattr(component, 'stop_coordination'):
                            component.stop_coordination()
                        elif hasattr(component, 'shutdown'):
                            component.shutdown()
                        log.info(f"Stopped {name}")
                    except Exception as e:
                        log.error(f"Error stopping {name}: {e}")
            
            # Send shutdown notification (with timeout)
            try:
                self.alerter.send_message("🛑 Multi-Agent Trading System Stopped 🛑")
            except Exception as e:
                log.error(f"Error sending shutdown notification: {e}")
            
            log.info("Multi-Agent Trading System shutdown complete")
        
        except Exception as e:
            log.error(f"Error during shutdown: {e}", exc_info=True)
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status."""
        status = {
            "system_stats": self.system_stats.copy(),
            "operation_mode": self.operation_mode,
            "active_workers": list(self.worker_processes.keys()),
            "worker_count": len(self.worker_processes)
        }
        
        # Add coordinator status if available
        if self.coordinator:
            status["coordinator_status"] = self.coordinator.get_system_status()
        
        # Add cache statistics
        if self.cache:
            status["cache_stats"] = self.cache.get_statistics()
        
        # Add risk summary
        if self.risk_agent:
            status["risk_summary"] = self.risk_agent.get_risk_summary()
        
        return status


def get_system_metrics():
    """Retorna métricas do sistema multi-agente para a API."""
    try:
        cache = get_global_cache()
        
        # Métricas básicas do sistema
        metrics = {
            "coordinator": {
                "status": "running",
                "active_tasks": 0,
                "last_update": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            },
            "agents": {
                "ai_agent": {"status": "active", "health": 100},
                "data_agent": {"status": "active", "health": 100},
                "risk_agent": {"status": "active", "health": 100},
                "sentiment_agent": {"status": "active", "health": 95}
            },
            "cache": {
                "hit_rate": cache.hit_rate if hasattr(cache, 'hit_rate') else 0.85,
                "entries": len(cache._cache) if hasattr(cache, '_cache') else 150,
                "memory_usage": f"{cache.get_cache_size():.1f}MB" if hasattr(cache, 'get_cache_size') else "12.5MB"
            }
        }
        
        return metrics
        
    except Exception as e:
        log.error(f"Erro ao buscar métricas do sistema: {e}")
        return {
            "coordinator": {"status": "error", "message": str(e)},
            "agents": {},
            "cache": {"hit_rate": 0, "entries": 0, "memory_usage": "0MB"}
        }


def main():
    """Main entry point."""
    bot = MultiAgentTradingBot()
    
    try:
        bot.start()
    except KeyboardInterrupt:
        log.warning("KeyboardInterrupt received. Shutting down...")
    except Exception as e:
        log.error(f"Unhandled error in main: {e}", exc_info=True)
        try:
            bot.alerter.send_critical_alert(f"FATAL ERROR: {e}")
        except:
            pass
    finally:
        bot.stop()


if __name__ == "__main__":
    main()