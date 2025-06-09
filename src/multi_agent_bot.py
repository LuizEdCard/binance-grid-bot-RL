# Multi-Agent Trading Bot - Main entry point using specialized agents
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
from integrations.ai_trading_integration import AITradingIntegration
from core.grid_logic import GridLogic
from core.pair_selector import PairSelector
from core.rl_agent import RLAgent
from utils.alerter import Alerter
from utils.api_client import APIClient
from utils.async_client import AsyncAPIClient
from utils.intelligent_cache import IntelligentCache, get_global_cache
from utils.logger import log, setup_logger

# Configuration
ROOT_DIR = os.path.dirname(SRC_DIR)
ENV_PATH = os.path.join(ROOT_DIR, "config", ".env")
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
        
        # Initialize intelligent cache
        self.cache = get_global_cache()
        self._setup_cache_callbacks()
        
        # Agents
        self.coordinator = None
        self.data_agent = None
        self.sentiment_agent = None
        self.risk_agent = None
        self.ai_agent = None
        self.ai_integration = None
        
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
                    log.info("AI Trading Integration initialized")
                except Exception as e:
                    log.warning(f"Failed to initialize AI Integration: {e}")
                    self.ai_integration = None
                    log.info("System will continue without AI integration")
            else:
                log.info("AI agent not available, skipping AI integration")
            
            # Initialize Pair Selector with sentiment integration
            self.pair_selector = PairSelector(
                self.config,
                self.api_client,
                get_sentiment_score_func=self._get_sentiment_score
            )
            
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
            
            # Start coordinator (this starts data and sentiment agents)
            self.coordinator.start_coordination()
            
            # Start risk agent
            self.risk_agent.start()
            
            # Send startup notification
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
            # Get selected pairs from pair selector
            selected_pairs = self.pair_selector.get_selected_pairs(force_update=True)
            
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
            
            # Create worker process
            process = multiprocessing.Process(
                target=self._trading_worker_main,
                args=(symbol, self.config, self.stop_event, self.global_trade_counter),
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
        global_trade_counter: multiprocessing.Value
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
            
            # Initialize grid logic
            grid_logic = GridLogic(symbol, config, api_client, operation_mode=operation_mode)
            
            # Initialize RL agent
            rl_agent = RLAgent(config, symbol)
            if not rl_agent.setup_agent(training=False):
                log.error(f"[{symbol}] Failed to setup RL agent")
                return
            
            # Trading loop
            cycle_interval = config.get("trading", {}).get("cycle_interval_seconds", 60)
            local_trade_count = 0
            
            while not stop_event.is_set():
                cycle_start = time.time()
                
                try:
                    log.info(f"[{symbol}] Starting trading cycle...")
                    
                    # Get market state for RL
                    market_state = grid_logic.get_market_state()
                    rl_action = None
                    
                    if market_state is not None:
                        try:
                            # Get sentiment if available
                            sentiment_config = config.get("sentiment_analysis", {})
                            if sentiment_config.get("rl_feature", {}).get("enabled", False):
                                # In a real implementation, we'd get this from shared memory or IPC
                                # For now, use a default value
                                sentiment_score = 0.0
                                rl_action = rl_agent.predict_action(market_state, sentiment_score=sentiment_score)
                            else:
                                rl_action = rl_agent.predict_action(market_state)
                            
                            log.debug(f"[{symbol}] RL action: {rl_action}")
                        
                        except Exception as e:
                            log.error(f"[{symbol}] Error getting RL action: {e}")
                    
                    # Execute trading logic
                    grid_logic.run_cycle(rl_action=rl_action)
                    
                    # Update trade counter
                    new_trade_count = grid_logic.total_trades
                    if new_trade_count > local_trade_count:
                        trades_made = new_trade_count - local_trade_count
                        with global_trade_counter.get_lock():
                            global_trade_counter.value += trades_made
                        local_trade_count = new_trade_count
                    
                    log.debug(f"[{symbol}] Trading cycle completed")
                
                except Exception as e:
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
        signal_name = signal.Signals(signum).name
        log.warning(f"Received signal {signal_name}. Initiating graceful shutdown...")
        self.stop()
    
    def stop(self) -> None:
        """Stop the multi-agent trading system."""
        if self.stop_event.is_set():
            log.info("Shutdown already in progress")
            return
        
        log.info("Stopping Multi-Agent Trading System...")
        self.stop_event.set()
        
        try:
            # Stop all trading workers
            log.info("Stopping trading workers...")
            for symbol in list(self.worker_processes.keys()):
                self._stop_trading_worker(symbol)
            
            # Stop risk agent
            if self.risk_agent:
                self.risk_agent.stop()
            
            # Stop coordinator (this stops other agents)
            if self.coordinator:
                self.coordinator.stop_coordination()
            
            # Shutdown cache
            if self.cache:
                self.cache.shutdown()
            
            # Send shutdown notification
            self.alerter.send_message("🛑 Multi-Agent Trading System Stopped 🛑")
            
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