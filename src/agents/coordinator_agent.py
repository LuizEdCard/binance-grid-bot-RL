# Coordinator Agent - Orchestrates all specialized agents
import multiprocessing
import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from agents.data_agent import DataAgent
from agents.sentiment_agent import SentimentAgent
from agents.ai_agent import AIAgent
from core.capital_management import CapitalManager
from utils.alerter import Alerter
from utils.api_client import APIClient
from utils.logger import setup_logger

log = setup_logger("coordinator_agent")


class AgentHealthMonitor:
    """Monitors health and performance of individual agents."""
    
    def __init__(self):
        self.agent_stats = defaultdict(dict)
        self.agent_last_update = defaultdict(float)
        self.health_thresholds = {
            'max_no_update_seconds': 300,  # 5 minutes
            'max_error_rate': 0.1,  # 10%
            'min_performance_score': 0.5
        }
    
    def update_agent_health(self, agent_name: str, stats: dict) -> None:
        """Update health stats for an agent."""
        self.agent_stats[agent_name] = stats
        self.agent_last_update[agent_name] = time.time()
    
    def check_agent_health(self, agent_name: str) -> Dict:
        """Check if an agent is healthy."""
        current_time = time.time()
        last_update = self.agent_last_update.get(agent_name, 0)
        stats = self.agent_stats.get(agent_name, {})
        
        health_status = {
            'is_healthy': True,
            'issues': [],
            'last_update_ago': current_time - last_update,
            'performance_score': 1.0
        }
        
        # Check if agent is responding
        if current_time - last_update > self.health_thresholds['max_no_update_seconds']:
            health_status['is_healthy'] = False
            health_status['issues'].append('No updates received recently')
        
        # Check error rate
        if 'errors' in stats and 'total_operations' in stats:
            if stats['total_operations'] > 0:
                error_rate = stats['errors'] / stats['total_operations']
                if error_rate > self.health_thresholds['max_error_rate']:
                    health_status['is_healthy'] = False
                    health_status['issues'].append(f'High error rate: {error_rate:.2%}')
        
        # Calculate performance score
        performance_factors = []
        
        if 'cache_hit_rate' in stats:
            performance_factors.append(stats['cache_hit_rate'] / 100)
        
        if 'avg_response_time' in stats:
            # Lower response time is better (inverse relationship)
            max_acceptable_time = 5.0  # seconds
            performance_factors.append(max(0, 1 - (stats['avg_response_time'] / max_acceptable_time)))
        
        if performance_factors:
            health_status['performance_score'] = sum(performance_factors) / len(performance_factors)
        
        if health_status['performance_score'] < self.health_thresholds['min_performance_score']:
            health_status['is_healthy'] = False
            health_status['issues'].append(f"Low performance score: {health_status['performance_score']:.2f}")
        
        return health_status
    
    def get_overall_system_health(self) -> Dict:
        """Get overall system health status."""
        total_agents = len(self.agent_stats)
        healthy_agents = 0
        total_performance = 0
        all_issues = []
        
        agent_healths = {}
        
        for agent_name in self.agent_stats.keys():
            health = self.check_agent_health(agent_name)
            agent_healths[agent_name] = health
            
            if health['is_healthy']:
                healthy_agents += 1
            else:
                all_issues.extend([f"{agent_name}: {issue}" for issue in health['issues']])
            
            total_performance += health['performance_score']
        
        system_health = healthy_agents / total_agents if total_agents > 0 else 0
        avg_performance = total_performance / total_agents if total_agents > 0 else 0
        
        return {
            'system_health_percentage': system_health * 100,
            'healthy_agents': healthy_agents,
            'total_agents': total_agents,
            'average_performance': avg_performance,
            'issues': all_issues,
            'agent_details': agent_healths
        }


class LoadBalancer:
    """Balances load across multiple workers and resources."""
    
    def __init__(self, max_concurrent_operations: int = 10):
        self.max_concurrent = max_concurrent_operations
        self.active_operations = 0
        self.operation_queue = []
        self.operation_lock = threading.Lock()
        
        # Resource utilization tracking
        self.cpu_usage_history = []
        self.memory_usage_history = []
        
    def can_accept_operation(self) -> bool:
        """Check if system can accept new operations."""
        with self.operation_lock:
            return self.active_operations < self.max_concurrent
    
    def start_operation(self, operation_id: str) -> bool:
        """Register start of a new operation."""
        with self.operation_lock:
            if self.active_operations < self.max_concurrent:
                self.active_operations += 1
                log.debug(f"Started operation {operation_id}. Active: {self.active_operations}")
                return True
            else:
                log.warning(f"Cannot start operation {operation_id}. Max concurrent reached.")
                return False
    
    def complete_operation(self, operation_id: str) -> None:
        """Register completion of an operation."""
        with self.operation_lock:
            if self.active_operations > 0:
                self.active_operations -= 1
                log.debug(f"Completed operation {operation_id}. Active: {self.active_operations}")
    
    def get_load_stats(self) -> Dict:
        """Get current load statistics."""
        with self.operation_lock:
            utilization = (self.active_operations / self.max_concurrent) * 100
            return {
                'active_operations': self.active_operations,
                'max_concurrent': self.max_concurrent,
                'utilization_percentage': utilization,
                'available_slots': self.max_concurrent - self.active_operations
            }


class CoordinatorAgent:
    """Main coordinator that orchestrates all specialized agents."""
    
    def __init__(self, config: dict, api_client: APIClient):
        self.config = config
        self.api_client = api_client
        self.alerter = Alerter(api_client)
        
        # Capital management
        self.capital_manager = CapitalManager(api_client, config)
        
        # Agent management
        self.agents = {}
        self.agent_threads = {}
        
        # Monitoring and balancing
        self.health_monitor = AgentHealthMonitor()
        self.load_balancer = LoadBalancer(
            max_concurrent_operations=config.get('coordinator', {}).get('max_concurrent_operations', 20)
        )
        
        # Communication channels
        self.inter_agent_channels = defaultdict(list)
        self.global_state = {
            'system_status': 'initializing',
            'active_pairs': [],
            'total_trades': 0,
            'system_performance': {}
        }
        self.state_lock = threading.RLock()
        
        # Control
        self.stop_event = threading.Event()
        self.coordinator_thread = None
        
        # Performance tracking
        self.performance_metrics = {
            'coordination_cycles': 0,
            'agent_restarts': 0,
            'load_balancing_events': 0,
            'inter_agent_messages': 0
        }
        
        log.info("CoordinatorAgent initialized")
    
    def initialize_agents(self) -> None:
        """Initialize all specialized agents."""
        log.info("Initializing specialized agents...")
        
        try:
            # Initialize Data Agent
            self.agents['data'] = DataAgent(self.config, self.api_client)
            log.info("Data Agent initialized")
            
            # Initialize Sentiment Agent
            self.agents['sentiment'] = SentimentAgent(self.config)
            log.info("Sentiment Agent initialized")
            
            # Initialize AI Agent (if enabled)
            ai_config = self.config.get("ai_agent", {})
            if ai_config.get("enabled", False):
                try:
                    ai_base_url = ai_config.get("base_url", "http://127.0.0.1:11434")
                    self.agents['ai'] = AIAgent(self.config, ai_base_url)
                    log.info("AI Agent initialized (will check availability on start)")
                except Exception as e:
                    log.warning(f"Failed to initialize AI Agent: {e}")
                    log.info("System will continue without AI functionality")
            else:
                log.info("AI Agent disabled in configuration")
            
            # Set up inter-agent communication
            self._setup_inter_agent_communication()
            
            log.info("All agents initialized successfully")
            
        except Exception as e:
            log.error(f"Error initializing agents: {e}", exc_info=True)
            raise
    
    def validate_trading_symbols(self, symbols: List[str]) -> List[str]:
        """
        Valida e filtra símbolos baseado no capital disponível.
        """
        log.info(f"Validating {len(symbols)} symbols for trading based on available capital...")
        
        # Obter alocações de capital
        allocations = self.capital_manager.calculate_optimal_allocations(symbols)
        
        if not allocations:
            log.warning("No symbols can be traded with current capital")
            return []
        
        valid_symbols = [alloc.symbol for alloc in allocations]
        
        if len(valid_symbols) < len(symbols):
            log.warning(f"Capital limited trading to {len(valid_symbols)} of {len(symbols)} requested symbols")
            log.info(f"Trading symbols: {valid_symbols}")
            
            # Log capital status
            self.capital_manager.log_capital_status()
        
        return valid_symbols
    
    def start_coordination(self) -> None:
        """Start the coordination system."""
        log.info("Starting coordination system...")
        
        with self.state_lock:
            self.global_state['system_status'] = 'starting'
        
        # Start all agents
        for agent_name, agent in self.agents.items():
            try:
                log.info(f"Starting {agent_name} agent...")
                if agent_name == 'ai':
                    # AI agent needs async start
                    import asyncio
                    asyncio.run(agent.start())
                else:
                    agent.start()
                log.info(f"{agent_name} agent started successfully")
            except Exception as e:
                if agent_name == 'ai':
                    log.warning(f"AI agent failed to start: {e}")
                    log.info("System will continue without AI functionality")
                    # Remove AI agent from agents dict to prevent issues
                    if 'ai' in self.agents:
                        del self.agents['ai']
                else:
                    log.error(f"Error starting {agent_name} agent: {e}")
                    self.alerter.send_critical_alert(f"Failed to start {agent_name} agent: {e}")
        
        # Start coordination loop
        self.stop_event.clear()
        self.coordinator_thread = threading.Thread(
            target=self._coordination_loop,
            daemon=True,
            name="CoordinatorAgent-Main"
        )
        self.coordinator_thread.start()
        
        with self.state_lock:
            self.global_state['system_status'] = 'running'
        
        log.info("Coordination system started")
        self.alerter.send_message("🤖 Multi-Agent Trading System Started 🤖")
    
    def stop_coordination(self) -> None:
        """Stop the coordination system."""
        log.info("Stopping coordination system...")
        
        with self.state_lock:
            self.global_state['system_status'] = 'stopping'
        
        self.stop_event.set()
        
        # Stop coordination thread
        if self.coordinator_thread and self.coordinator_thread.is_alive():
            self.coordinator_thread.join(timeout=10)
        
        # Stop all agents
        for agent_name, agent in self.agents.items():
            try:
                log.info(f"Stopping {agent_name} agent...")
                agent.stop()
                log.info(f"{agent_name} agent stopped")
            except Exception as e:
                log.error(f"Error stopping {agent_name} agent: {e}")
        
        with self.state_lock:
            self.global_state['system_status'] = 'stopped'
        
        log.info("Coordination system stopped")
        self.alerter.send_message("🛑 Multi-Agent Trading System Stopped 🛑")
    
    def _setup_inter_agent_communication(self) -> None:
        """Set up communication channels between agents."""
        # Data Agent -> Sentiment Agent (market data for context)
        if 'data' in self.agents and 'sentiment' in self.agents:
            self.agents['data'].subscribe_to_symbol(
                'BTCUSDT',  # Example symbol for general market context
                self._relay_market_data_to_sentiment
            )
        
        # Sentiment Agent -> Coordinator (sentiment updates)
        if 'sentiment' in self.agents:
            self.agents['sentiment'].register_sentiment_callback(
                self._handle_sentiment_update
            )
        
        log.info("Inter-agent communication channels established")
    
    def _relay_market_data_to_sentiment(self, data_package: dict) -> None:
        """Relay market data to sentiment agent for context."""
        try:
            # This could be used by sentiment agent to weight analysis based on market conditions
            self.inter_agent_channels['data_to_sentiment'].append({
                'timestamp': time.time(),
                'market_data': data_package,
                'message_type': 'market_context'
            })
            self.performance_metrics['inter_agent_messages'] += 1
        except Exception as e:
            log.error(f"Error relaying market data to sentiment: {e}")
    
    def _handle_sentiment_update(self, sentiment_data: dict) -> None:
        """Handle sentiment updates from sentiment agent."""
        try:
            with self.state_lock:
                self.global_state['latest_sentiment'] = sentiment_data
            
            # Check for significant sentiment changes
            if abs(sentiment_data.get('raw_score', 0)) > 0.7:
                self.alerter.send_message(
                    f"📊 Significant Sentiment Change: {sentiment_data['raw_score']:.2f}",
                    level="INFO"
                )
            
            self.performance_metrics['inter_agent_messages'] += 1
        except Exception as e:
            log.error(f"Error handling sentiment update: {e}")
    
    def _coordination_loop(self) -> None:
        """Main coordination loop."""
        coordination_interval = 30  # seconds
        
        while not self.stop_event.is_set():
            cycle_start = time.time()
            
            try:
                # Monitor agent health
                self._monitor_agent_health()
                
                # Balance system load
                self._balance_system_load()
                
                # Update global state
                self._update_global_state()
                
                # Process market overview for AI efficiency (every 5 cycles)
                if self.performance_metrics['coordination_cycles'] % 5 == 0:
                    self._process_market_overview()
                
                # Check for system-wide issues
                self._check_system_issues()
                
                # Update performance metrics
                self.performance_metrics['coordination_cycles'] += 1
                
                # Log periodic status
                if self.performance_metrics['coordination_cycles'] % 10 == 0:
                    self._log_system_status()
                
                # Wait for next cycle
                elapsed = time.time() - cycle_start
                wait_time = max(0, coordination_interval - elapsed)
                if wait_time > 0:
                    self.stop_event.wait(wait_time)
                
            except Exception as e:
                log.error(f"Error in coordination loop: {e}", exc_info=True)
                self.stop_event.wait(10)  # Wait before retry
    
    def _monitor_agent_health(self) -> None:
        """Monitor health of all agents."""
        for agent_name, agent in self.agents.items():
            try:
                if hasattr(agent, 'get_statistics'):
                    stats = agent.get_statistics()
                    self.health_monitor.update_agent_health(agent_name, stats)
                    
                    # Check if agent needs restart
                    health = self.health_monitor.check_agent_health(agent_name)
                    if not health['is_healthy'] and len(health['issues']) > 0:
                        log.warning(f"{agent_name} agent health issues: {health['issues']}")
                        
                        # Consider restarting agent if critical
                        if 'No updates received recently' in str(health['issues']):
                            self._restart_agent(agent_name)
                
            except Exception as e:
                log.error(f"Error monitoring {agent_name} agent health: {e}")
    
    def _restart_agent(self, agent_name: str) -> None:
        """Restart a specific agent."""
        log.warning(f"Attempting to restart {agent_name} agent...")
        
        try:
            agent = self.agents.get(agent_name)
            if agent:
                # Stop the agent
                agent.stop()
                time.sleep(2)  # Brief pause
                
                # Restart the agent
                agent.start()
                
                self.performance_metrics['agent_restarts'] += 1
                log.info(f"{agent_name} agent restarted successfully")
                
                self.alerter.send_message(
                    f"⚠️ {agent_name.capitalize()} Agent Restarted",
                    level="WARNING"
                )
            
        except Exception as e:
            log.error(f"Error restarting {agent_name} agent: {e}")
            self.alerter.send_critical_alert(f"Failed to restart {agent_name} agent: {e}")
    
    def _balance_system_load(self) -> None:
        """Balance system load and resources."""
        load_stats = self.load_balancer.get_load_stats()
        
        # If system is overloaded, take action
        if load_stats['utilization_percentage'] > 90:
            log.warning(f"High system load: {load_stats['utilization_percentage']:.1f}%")
            self.performance_metrics['load_balancing_events'] += 1
            
            # Could implement load reduction strategies here
            # e.g., reduce update frequencies, pause non-critical operations
    
    def _update_global_state(self) -> None:
        """Update global system state."""
        try:
            with self.state_lock:
                # Update system performance metrics
                self.global_state['system_performance'] = {
                    'coordination_cycles': self.performance_metrics['coordination_cycles'],
                    'agent_restarts': self.performance_metrics['agent_restarts'],
                    'load_stats': self.load_balancer.get_load_stats(),
                    'health_stats': self.health_monitor.get_overall_system_health()
                }
        
        except Exception as e:
            log.error(f"Error updating global state: {e}")
    
    def _check_system_issues(self) -> None:
        """Check for system-wide issues."""
        try:
            system_health = self.health_monitor.get_overall_system_health()
            
            # Alert if system health is poor
            if system_health['system_health_percentage'] < 50:
                self.alerter.send_critical_alert(
                    f"Poor System Health: {system_health['system_health_percentage']:.1f}%. "
                    f"Issues: {', '.join(system_health['issues'][:3])}"
                )
            
            # Alert if load is consistently high
            load_stats = self.load_balancer.get_load_stats()
            if load_stats['utilization_percentage'] > 95:
                self.alerter.send_message(
                    f"⚠️ High System Load: {load_stats['utilization_percentage']:.1f}%",
                    level="WARNING"
                )
        
        except Exception as e:
            log.error(f"Error checking system issues: {e}")
    
    def _log_system_status(self) -> None:
        """Log periodic system status."""
        try:
            system_health = self.health_monitor.get_overall_system_health()
            load_stats = self.load_balancer.get_load_stats()
            
            log.info(
                f"System Status - Health: {system_health['system_health_percentage']:.1f}%, "
                f"Load: {load_stats['utilization_percentage']:.1f}%, "
                f"Healthy Agents: {system_health['healthy_agents']}/{system_health['total_agents']}, "
                f"Coordination Cycles: {self.performance_metrics['coordination_cycles']}"
            )
        
        except Exception as e:
            log.error(f"Error logging system status: {e}")
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status."""
        with self.state_lock:
            return {
                'global_state': self.global_state.copy(),
                'agent_health': self.health_monitor.get_overall_system_health(),
                'load_stats': self.load_balancer.get_load_stats(),
                'performance_metrics': self.performance_metrics.copy(),
                'inter_agent_channels': {
                    name: len(messages) for name, messages in self.inter_agent_channels.items()
                }
            }
    
    def get_agent(self, agent_name: str):
        """Get a specific agent instance."""
        return self.agents.get(agent_name)
    
    def broadcast_message(self, message: str, level: str = "INFO") -> None:
        """Broadcast a message through the alerter."""
        self.alerter.send_message(message, level=level)

    def _process_market_overview(self) -> None:
        """
        Processa visão geral do mercado usando dados agregados dos 471 pares USDT.
        Evita sobrecarga da IA analisando cada par individualmente.
        """
        try:
            if 'ai' not in self.agents:
                log.debug("AI agent not available for market overview")
                return
                
            ai_agent = self.agents['ai']
            if not ai_agent.is_available:
                log.debug("AI agent not ready for market overview")
                return
            
            # Obter resumo agregado do mercado via PairSelector
            if hasattr(self, '_pair_selector') and self._pair_selector:
                market_summary = self._pair_selector.get_market_summary()
            else:
                # Fallback: criar PairSelector temporário se necessário
                from core.pair_selector import PairSelector
                temp_selector = PairSelector(self.config, self.api_client)
                market_summary = temp_selector.get_market_summary()
            
            # Usar SmartTradingDecisionEngine para análise eficiente
            if hasattr(self, '_smart_engine') and self._smart_engine:
                import asyncio
                
                # Executar análise de visão geral do mercado
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    overview_analysis = loop.run_until_complete(
                        self._smart_engine.get_market_overview_analysis(market_summary)
                    )
                    
                    if overview_analysis:
                        # Armazenar resultado no estado global
                        with self.state_lock:
                            self.global_state['market_overview'] = {
                                'analysis': overview_analysis,
                                'summary_data': market_summary,
                                'timestamp': time.time()
                            }
                        
                        # Log resultado da análise
                        trend = overview_analysis.get('overall_trend', 'neutral')
                        strength = overview_analysis.get('market_strength', 0.5)
                        confidence = overview_analysis.get('confidence', 0.5)
                        
                        log.info(f"Market Overview - Trend: {trend}, Strength: {strength:.2f}, "
                               f"Confidence: {confidence:.2f}, Total pairs: {market_summary.get('total_pairs', 0)}")
                        
                        # Enviar alerta se mudança significativa
                        if confidence > 0.7 and (strength > 0.8 or strength < 0.2):
                            self.alerter.send_message(
                                f"📊 Market Overview Alert: {trend.upper()} trend detected "
                                f"(strength: {strength:.2f}, confidence: {confidence:.2f})"
                            )
                        
                        self.performance_metrics['market_overviews_processed'] = \
                            self.performance_metrics.get('market_overviews_processed', 0) + 1
                    
                    loop.close()
                    
                except Exception as async_error:
                    log.error(f"Error in async market overview analysis: {async_error}")
            else:
                log.debug("SmartTradingDecisionEngine not available for market overview")
                
        except Exception as e:
            log.error(f"Error processing market overview: {e}")
            self.performance_metrics['market_overview_errors'] = \
                self.performance_metrics.get('market_overview_errors', 0) + 1

    def initialize_smart_engine(self) -> None:
        """Inicializa o SmartTradingDecisionEngine para análise eficiente de mercado."""
        try:
            if 'ai' not in self.agents:
                log.warning("Cannot initialize SmartTradingDecisionEngine: AI agent not available")
                return
                
            from integrations.ai_trading_integration import SmartTradingDecisionEngine
            
            self._smart_engine = SmartTradingDecisionEngine(
                ai_agent=self.agents['ai'],
                api_client=self.api_client,
                config=self.config
            )
            
            log.info("SmartTradingDecisionEngine initialized for efficient market analysis")
            
        except Exception as e:
            log.error(f"Error initializing SmartTradingDecisionEngine: {e}")
            self._smart_engine = None