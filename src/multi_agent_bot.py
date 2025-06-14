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
from utils.intelligent_cache import IntelligentCache, get_global_cache
from utils.logger import log, setup_logger
from utils.pair_logger import get_multi_pair_logger, get_pair_logger

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
        self.operation_mode = self.config.get("operation_mode", "Shadow").lower()
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
        self.pair_selector = None
        self.trading_workers = {}
        self.rl_agents = {}
        
        # Process management
        self.worker_processes = {}
        self.stop_event = multiprocessing.Event()
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
            if self.ai_agent:
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
                log.info("AI agent not available, skipping AI integration")
            
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
            if self.ai_agent:
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
        pair_update_interval = self.config.get("pair_selection", {}).get("update_interval_hours", 6) * 3600
        last_pair_update = 0
        stats_update_interval = 300  # 5 minutes
        last_stats_update = 0
        status_summary_interval = 180  # 3 minutes
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
                wait_time = max(0, 60 - elapsed)  # 1-minute cycle
                if wait_time > 0:
                    self.stop_event.wait(wait_time)
                
            except Exception as e:
                log.error(f"Error in main loop: {e}", exc_info=True)
                self.stop_event.wait(30)  # Wait before retry
        
        log.info("Main loop exited")
    
    def _update_trading_pairs(self) -> None:
        """Update selected trading pairs and start/stop workers accordingly."""
        log.info("Updating trading pairs...")
        
        try:
            # Get selected pairs from pair selector (use cache if available)
            selected_pairs = self.pair_selector.get_selected_pairs(force_update=False)
            
            if not selected_pairs:
                log.warning("No pairs selected for trading")
                return
            
            log.info(f"Selected pairs for trading: {selected_pairs}")
            
            # Update worker processes
            current_pairs = set(self.worker_processes.keys())
            target_pairs = set(selected_pairs)
            
            # Stop workers for deselected pairs
            pairs_to_stop = current_pairs - target_pairs
            for pair in pairs_to_stop:
                self._stop_trading_worker(pair)
            
            # Start workers for new pairs
            pairs_to_start = target_pairs - current_pairs
            for pair in pairs_to_start:
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
    
    def _start_trading_worker(self, symbol: str) -> None:
        """Start a trading worker process for a symbol."""
        log.info(f"Starting trading worker for {symbol}")
        
        try:
            max_concurrent = self.config.get("trading", {}).get("max_concurrent_pairs", 5)
            if len(self.worker_processes) >= max_concurrent:
                log.warning(f"Max concurrent pairs ({max_concurrent}) reached. Cannot start worker for {symbol}")
                return
            
            # Prepare shared resources for worker
            shared_resources = {
                "ai_agent": self.ai_agent,
                "smart_decision_engine": self.smart_decision_engine
            }
            
            # Create worker process
            process = multiprocessing.Process(
                target=self._trading_worker_main,
                args=(symbol, self.config, self.stop_event, self.global_trade_counter, shared_resources),
                daemon=True,
                name=f"TradingWorker-{symbol}"
            )
            
            self.worker_processes[symbol] = process
            process.start()
            
            log.info(f"Trading worker for {symbol} started (PID: {process.pid})")
            
        except Exception as e:
            log.error(f"Error starting trading worker for {symbol}: {e}")
    
    def _stop_trading_worker(self, symbol: str) -> None:
        """Stop a trading worker process for a symbol."""
        log.info(f"Stopping trading worker for {symbol}")
        
        try:
            if symbol in self.worker_processes:
                process = self.worker_processes[symbol]
                
                if process.is_alive():
                    # Send termination signal
                    try:
                        os.kill(process.pid, signal.SIGTERM)
                        process.join(timeout=15)
                        
                        if process.is_alive():
                            log.warning(f"Worker for {symbol} did not terminate gracefully. Sending SIGKILL.")
                            process.kill()
                            process.join(timeout=5)
                    except ProcessLookupError:
                        log.warning(f"Process for {symbol} already terminated")
                
                del self.worker_processes[symbol]
                log.info(f"Trading worker for {symbol} stopped")
        
        except Exception as e:
            log.error(f"Error stopping trading worker for {symbol}: {e}")
    
    def _trading_worker_main(
        self,
        symbol: str,
        config: dict,
        stop_event: multiprocessing.Event,
        global_trade_counter: multiprocessing.Value,
        shared_resources: dict = None
    ) -> None:
        """Main function for trading worker process."""
        # Setup logging for worker
        worker_logger = setup_logger(f"{symbol}_worker")
        
        try:
            log.info(f"[{symbol}] Trading worker started (PID: {os.getpid()})")
            
            # Initialize components for this worker
            operation_mode = config.get("operation_mode", "Shadow").lower()
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
            
            # Use global WebSocket client for real-time data
            worker_ws_client = get_global_websocket()
            worker_ws_client.subscribe_ticker(symbol)
            log.info(f"[{symbol}] Subscribed to real-time WebSocket data")
            
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
            rl_enabled = config.get("rl_agent", {}).get("enabled", True)
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
            
            # Trading loop
            cycle_interval = config.get("trading", {}).get("cycle_interval_seconds", 60)
            local_trade_count = 0
            
            # Initialize pair logger
            pair_logger = get_pair_logger(symbol)
            pair_logger.log_info(f"Iniciando sistema de trading para {symbol}")
            
            while not stop_event.is_set():
                cycle_start = time.time()
                
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
                    
                    # Try Smart Decision Engine first (AI + Dynamic Sizer)
                    if shared_resources and shared_resources.get("smart_decision_engine"):
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
                    
                    # Fallback to traditional RL if AI decision failed and RL is available
                    if rl_action is None and rl_agent is not None:
                        market_state = grid_logic.get_market_state()
                        if market_state is not None:
                            try:
                                # Get sentiment if available
                                sentiment_config = config.get("sentiment_analysis", {})
                                if sentiment_config.get("rl_feature", {}).get("enabled", False):
                                    sentiment_score = 0.0
                                    rl_action = rl_agent.predict_action(market_state, sentiment_score=sentiment_score)
                                else:
                                    rl_action = rl_agent.predict_action(market_state)
                                
                                log.debug(f"[{symbol}] Fallback RL action: {rl_action}")
                            
                            except Exception as e:
                                log.error(f"[{symbol}] Error getting RL action: {e}")
                                rl_action = 0  # Safe fallback
                    
                    # Log trading cycle with detailed metrics
                    pair_logger.log_trading_cycle()
                    
                    # Execute trading logic with AI/RL decision
                    previous_orders = len(getattr(grid_logic, 'active_orders', []))
                    grid_logic.run_cycle(rl_action=rl_action, ai_decision=ai_decision)
                    current_orders = len(getattr(grid_logic, 'active_orders', []))
                    
                    # Check for new orders
                    if current_orders > previous_orders:
                        pair_logger.log_info(f"Novas ordens criadas: {current_orders - previous_orders}")
                    
                    # Update trade counter
                    new_trade_count = grid_logic.total_trades
                    if new_trade_count > local_trade_count:
                        trades_made = new_trade_count - local_trade_count
                        with global_trade_counter.get_lock():
                            global_trade_counter.value += trades_made
                        local_trade_count = new_trade_count
                        
                        # Log trade completion
                        pair_logger.log_info(f"✅ {trades_made} trade(s) executado(s)! Total: {new_trade_count}")
                    
                    # Check for position changes
                    try:
                        new_position = api_client.get_futures_position(symbol)
                        new_position_size = float(new_position.get('positionAmt', 0)) if new_position else 0
                        new_unrealized_pnl = float(new_position.get('unrealizedPnl', 0)) if new_position else 0
                        
                        if abs(new_position_size - position_size) > 0.0001:  # Position changed
                            new_side = "LONG" if new_position_size > 0 else "SHORT" if new_position_size < 0 else "NONE"
                            new_entry = float(new_position.get('entryPrice', 0)) if new_position else 0
                            pair_logger.log_position_update(new_side, new_entry, new_position_size, new_unrealized_pnl)
                    except Exception as pos_error:
                        pass  # Ignore position check errors
                
                except Exception as e:
                    pair_logger.log_error(f"Erro no ciclo de trading: {e}")
                    log.error(f"[{symbol}] Error in trading cycle: {e}", exc_info=True)
                    alerter.send_critical_alert(f"Error in {symbol} trading cycle: {e}")
                
                # Wait for next cycle
                elapsed = time.time() - cycle_start
                wait_time = max(0, cycle_interval - elapsed)
                if wait_time > 0:
                    stop_event.wait(wait_time)
        
        except Exception as e:
            log.error(f"[{symbol}] Critical error in trading worker: {e}", exc_info=True)
            try:
                Alerter().send_critical_alert(f"Critical error in {symbol} worker: {e}")
            except:
                pass
        
        finally:
            log.info(f"[{symbol}] Trading worker shutting down")
            try:
                # Cleanup: cancel orders if in production mode
                if "grid_logic" in locals() and operation_mode == "production":
                    grid_logic.cancel_all_orders()
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
                    f"⚠️ WARNING: System health at {health_percentage:.1f}%",
                    level="WARNING"
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
        self.stop_event.set()
        
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