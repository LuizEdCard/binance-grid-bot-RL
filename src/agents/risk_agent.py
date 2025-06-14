# Risk Management Agent - Proactive risk monitoring and management
import threading
import time
from collections import defaultdict, deque
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from utils.alerter import Alerter
from utils.api_client import APIClient
from utils.logger import setup_logger

log = setup_logger("risk_agent")

try:
    import talib
    talib_available = True
except ImportError:
    talib_available = False


class RiskMetrics:
    """Calculates and tracks various risk metrics."""
    
    def __init__(self, history_length: int = 100):
        self.history_length = history_length
        self.price_history = defaultdict(lambda: deque(maxlen=history_length))
        self.pnl_history = defaultdict(lambda: deque(maxlen=history_length))
        self.volume_history = defaultdict(lambda: deque(maxlen=history_length))
        self.correlation_matrix = {}
        self.last_calculation = {}
    
    def update_data(self, symbol: str, price: float, pnl: float, volume: float) -> None:
        """Update historical data for risk calculations."""
        self.price_history[symbol].append(price)
        self.pnl_history[symbol].append(pnl)
        self.volume_history[symbol].append(volume)
        self.last_calculation[symbol] = time.time()
    
    def calculate_var(self, symbol: str, confidence_level: float = 0.95, time_horizon: int = 1) -> Optional[float]:
        """Calculate Value at Risk (VaR)."""
        if symbol not in self.pnl_history or len(self.pnl_history[symbol]) < 30:
            return None
        
        try:
            pnl_returns = list(self.pnl_history[symbol])
            pnl_array = np.array(pnl_returns)
            
            # Calculate daily returns
            returns = np.diff(pnl_array) / np.abs(pnl_array[:-1])
            returns = returns[~np.isnan(returns)]
            
            if len(returns) < 10:
                return None
            
            # Calculate VaR
            var_percentile = (1 - confidence_level) * 100
            var = np.percentile(returns, var_percentile)
            
            # Scale for time horizon
            var_scaled = var * np.sqrt(time_horizon)
            
            return float(var_scaled)
        
        except Exception as e:
            log.error(f"Error calculating VaR for {symbol}: {e}")
            return None
    
    def calculate_sharpe_ratio(self, symbol: str, risk_free_rate: float = 0.02) -> Optional[float]:
        """Calculate Sharpe ratio."""
        if symbol not in self.pnl_history or len(self.pnl_history[symbol]) < 30:
            return None
        
        try:
            pnl_returns = list(self.pnl_history[symbol])
            pnl_array = np.array(pnl_returns)
            
            # Calculate returns
            returns = np.diff(pnl_array) / np.abs(pnl_array[:-1])
            returns = returns[~np.isnan(returns)]
            
            if len(returns) < 10:
                return None
            
            # Annualized return and volatility
            mean_return = np.mean(returns) * 365  # Daily to annual
            volatility = np.std(returns) * np.sqrt(365)  # Daily to annual
            
            if volatility == 0:
                return None
            
            sharpe = (mean_return - risk_free_rate) / volatility
            return float(sharpe)
        
        except Exception as e:
            log.error(f"Error calculating Sharpe ratio for {symbol}: {e}")
            return None
    
    def calculate_max_drawdown(self, symbol: str) -> Optional[float]:
        """Calculate maximum drawdown."""
        if symbol not in self.pnl_history or len(self.pnl_history[symbol]) < 10:
            return None
        
        try:
            pnl_values = np.array(list(self.pnl_history[symbol]))
            
            # Calculate cumulative PnL
            cumulative_pnl = np.cumsum(pnl_values)
            
            # Calculate running maximum
            running_max = np.maximum.accumulate(cumulative_pnl)
            
            # Calculate drawdown
            drawdown = (cumulative_pnl - running_max) / np.abs(running_max)
            drawdown = np.where(running_max == 0, 0, drawdown)
            
            max_dd = np.min(drawdown)
            return float(max_dd)
        
        except Exception as e:
            log.error(f"Error calculating max drawdown for {symbol}: {e}")
            return None
    
    def calculate_correlation(self, symbols: List[str]) -> Dict:
        """Calculate correlation matrix between symbols."""
        if len(symbols) < 2:
            return {}
        
        try:
            # Prepare price data
            price_data = {}
            min_length = float('inf')
            
            for symbol in symbols:
                if symbol in self.price_history and len(self.price_history[symbol]) > 30:
                    prices = list(self.price_history[symbol])
                    price_data[symbol] = prices
                    min_length = min(min_length, len(prices))
            
            if len(price_data) < 2 or min_length < 30:
                return {}
            
            # Calculate returns for each symbol
            returns_data = {}
            for symbol, prices in price_data.items():
                prices_array = np.array(prices[-min_length:])
                returns = np.diff(prices_array) / prices_array[:-1]
                returns_data[symbol] = returns[~np.isnan(returns)]
            
            # Calculate correlation matrix
            correlation_matrix = {}
            for i, symbol1 in enumerate(returns_data.keys()):
                correlation_matrix[symbol1] = {}
                for j, symbol2 in enumerate(returns_data.keys()):
                    if i == j:
                        correlation_matrix[symbol1][symbol2] = 1.0
                    else:
                        corr = np.corrcoef(returns_data[symbol1], returns_data[symbol2])[0, 1]
                        correlation_matrix[symbol1][symbol2] = float(corr) if not np.isnan(corr) else 0.0
            
            self.correlation_matrix = correlation_matrix
            return correlation_matrix
        
        except Exception as e:
            log.error(f"Error calculating correlation matrix: {e}")
            return {}


class PortfolioRiskManager:
    """Manages portfolio-level risk."""
    
    def __init__(self, config: dict):
        self.config = config
        self.risk_config = config.get("risk_management", {})
        
        # Risk limits
        self.max_portfolio_var = Decimal(str(self.risk_config.get("max_portfolio_var", "0.05")))
        self.max_correlation_exposure = Decimal(str(self.risk_config.get("max_correlation_exposure", "0.7")))
        self.max_single_asset_weight = Decimal(str(self.risk_config.get("max_single_asset_weight", "0.3")))
        self.min_diversification_score = Decimal(str(self.risk_config.get("min_diversification_score", "0.5")))
        
        # Position tracking
        self.position_weights = {}
        self.total_portfolio_value = Decimal("0")
        
        # Risk state
        self.portfolio_var = None
        self.diversification_score = None
        self.risk_alerts = []
    
    def update_positions(self, positions: Dict[str, Dict]) -> None:
        """Update portfolio positions."""
        try:
            total_value = Decimal("0")
            position_values = {}
            
            for symbol, position in positions.items():
                value = abs(Decimal(str(position.get("notional", 0))))
                position_values[symbol] = value
                total_value += value
            
            # Calculate weights
            if total_value > 0:
                self.position_weights = {
                    symbol: value / total_value 
                    for symbol, value in position_values.items()
                }
            else:
                self.position_weights = {}
            
            self.total_portfolio_value = total_value
            
        except Exception as e:
            log.error(f"Error updating portfolio positions: {e}")
    
    def calculate_portfolio_risk(self, risk_metrics: RiskMetrics, symbols: List[str]) -> Dict:
        """Calculate portfolio-level risk metrics."""
        try:
            # Calculate diversification score
            self.diversification_score = self._calculate_diversification_score()
            
            # Calculate portfolio VaR
            self.portfolio_var = self._calculate_portfolio_var(risk_metrics, symbols)
            
            # Check concentration risk
            concentration_risk = self._check_concentration_risk()
            
            # Check correlation risk
            correlation_risk = self._check_correlation_risk(risk_metrics, symbols)
            
            return {
                "diversification_score": float(self.diversification_score or 0),
                "portfolio_var": float(self.portfolio_var or 0),
                "concentration_risk": concentration_risk,
                "correlation_risk": correlation_risk,
                "total_portfolio_value": float(self.total_portfolio_value),
                "position_count": len(self.position_weights)
            }
        
        except Exception as e:
            log.error(f"Error calculating portfolio risk: {e}")
            return {}
    
    def _calculate_diversification_score(self) -> Optional[Decimal]:
        """Calculate portfolio diversification score."""
        if not self.position_weights:
            return None
        
        try:
            # Herfindahl-Hirschman Index for diversification
            hhi = sum(weight ** 2 for weight in self.position_weights.values())
            
            # Convert to diversification score (1 = perfectly diversified, 0 = concentrated)
            n_positions = len(self.position_weights)
            max_hhi = Decimal("1")  # Most concentrated (one position)
            min_hhi = Decimal("1") / Decimal(str(n_positions))  # Most diversified
            
            if max_hhi == min_hhi:
                return Decimal("1")
            
            diversification = (max_hhi - hhi) / (max_hhi - min_hhi)
            return max(Decimal("0"), min(Decimal("1"), diversification))
        
        except Exception as e:
            log.error(f"Error calculating diversification score: {e}")
            return None
    
    def _calculate_portfolio_var(self, risk_metrics: RiskMetrics, symbols: List[str]) -> Optional[Decimal]:
        """Calculate portfolio Value at Risk."""
        if not self.position_weights or len(symbols) < 2:
            return None
        
        try:
            # Get individual VaRs
            individual_vars = {}
            for symbol in symbols:
                var = risk_metrics.calculate_var(symbol)
                if var is not None:
                    individual_vars[symbol] = var
            
            if len(individual_vars) < 2:
                return None
            
            # Get correlation matrix
            correlation_matrix = risk_metrics.calculate_correlation(list(individual_vars.keys()))
            if not correlation_matrix:
                return None
            
            # Calculate portfolio VaR using correlation
            portfolio_var_squared = Decimal("0")
            
            for symbol1 in individual_vars:
                for symbol2 in individual_vars:
                    weight1 = self.position_weights.get(symbol1, Decimal("0"))
                    weight2 = self.position_weights.get(symbol2, Decimal("0"))
                    var1 = Decimal(str(individual_vars[symbol1]))
                    var2 = Decimal(str(individual_vars[symbol2]))
                    corr = Decimal(str(correlation_matrix.get(symbol1, {}).get(symbol2, 0)))
                    
                    portfolio_var_squared += weight1 * weight2 * var1 * var2 * corr
            
            portfolio_var = portfolio_var_squared.sqrt() if portfolio_var_squared > 0 else Decimal("0")
            return portfolio_var
        
        except Exception as e:
            log.error(f"Error calculating portfolio VaR: {e}")
            return None
    
    def _check_concentration_risk(self) -> List[str]:
        """Check for concentration risk."""
        risks = []
        
        for symbol, weight in self.position_weights.items():
            if weight > self.max_single_asset_weight:
                risks.append(f"High concentration in {symbol}: {weight*100:.1f}%")
        
        return risks
    
    def _check_correlation_risk(self, risk_metrics: RiskMetrics, symbols: List[str]) -> List[str]:
        """Check for correlation risk."""
        risks = []
        
        correlation_matrix = risk_metrics.calculate_correlation(symbols)
        if not correlation_matrix:
            return risks
        
        # Check for high correlations
        high_corr_threshold = 0.8
        for symbol1 in correlation_matrix:
            for symbol2 in correlation_matrix[symbol1]:
                if symbol1 != symbol2:
                    corr = correlation_matrix[symbol1][symbol2]
                    if abs(corr) > high_corr_threshold:
                        weight1 = self.position_weights.get(symbol1, Decimal("0"))
                        weight2 = self.position_weights.get(symbol2, Decimal("0"))
                        combined_weight = weight1 + weight2
                        
                        if combined_weight > self.max_correlation_exposure:
                            risks.append(
                                f"High correlation risk: {symbol1}-{symbol2} "
                                f"(corr: {corr:.2f}, combined weight: {combined_weight*100:.1f}%)"
                            )
        
        return risks


class RiskAgent:
    """Proactive risk management agent."""
    
    def __init__(self, config: dict, api_client: APIClient, alerter: Alerter):
        self.config = config
        self.api_client = api_client
        self.alerter = alerter
        
        # Risk components
        self.risk_metrics = RiskMetrics()
        self.portfolio_manager = PortfolioRiskManager(config)
        
        # Monitoring
        self.monitored_symbols = set()
        self.risk_alerts = defaultdict(list)
        self.alert_cooldown = {}  # symbol -> last_alert_time
        
        # Threading
        self.stop_event = threading.Event()
        self.risk_thread = None
        
        # Performance
        self.stats = {
            "risk_checks": 0,
            "alerts_sent": 0,
            "positions_monitored": 0,
            "avg_check_time": 0.0
        }
        
        # Configuration
        self.check_interval = config.get("risk_agent", {}).get("check_interval_seconds", 30)
        self.alert_cooldown_minutes = config.get("risk_agent", {}).get("alert_cooldown_minutes", 15)
        
        log.info("RiskAgent initialized")
    
    def start(self) -> None:
        """Start the risk monitoring agent."""
        self.stop_event.clear()
        self.risk_thread = threading.Thread(
            target=self._risk_monitoring_loop,
            daemon=True,
            name="RiskAgent-Monitor"
        )
        self.risk_thread.start()
        log.info("RiskAgent started")
    
    def stop(self) -> None:
        """Stop the risk monitoring agent."""
        log.info("Stopping RiskAgent...")
        self.stop_event.set()
        
        if self.risk_thread and self.risk_thread.is_alive():
            self.risk_thread.join(timeout=10)
        
        log.info("RiskAgent stopped")
    
    def add_symbol_monitoring(self, symbol: str) -> None:
        """Add a symbol to risk monitoring."""
        self.monitored_symbols.add(symbol)
        log.debug(f"Added {symbol} to risk monitoring")
    
    def remove_symbol_monitoring(self, symbol: str) -> None:
        """Remove a symbol from risk monitoring."""
        self.monitored_symbols.discard(symbol)
        log.debug(f"Removed {symbol} from risk monitoring")
    
    def _risk_monitoring_loop(self) -> None:
        """Main risk monitoring loop."""
        while not self.stop_event.is_set():
            check_start = time.time()
            
            try:
                # Monitor individual positions
                self._monitor_individual_risks()
                
                # Monitor portfolio risks
                self._monitor_portfolio_risks()
                
                # Check for system-wide risks
                self._monitor_system_risks()
                
                # Update statistics
                self.stats["risk_checks"] += 1
                check_time = time.time() - check_start
                self.stats["avg_check_time"] = (
                    (self.stats["avg_check_time"] * (self.stats["risk_checks"] - 1) + check_time)
                    / self.stats["risk_checks"]
                )
                
                # Log periodic status
                if self.stats["risk_checks"] % 20 == 0:
                    self._log_risk_status()
                
                # Wait for next check
                elapsed = time.time() - check_start
                wait_time = max(0, self.check_interval - elapsed)
                if wait_time > 0:
                    self.stop_event.wait(wait_time)
                
            except Exception as e:
                log.error(f"Error in risk monitoring loop: {e}", exc_info=True)
                self.stop_event.wait(30)  # Wait before retry
    
    def _monitor_individual_risks(self) -> None:
        """Monitor risks for individual positions."""
        positions_checked = 0
        
        for symbol in self.monitored_symbols:
            try:
                # Get position data
                position = self.api_client.get_futures_position(symbol)
                # Check if position is a list (multiple positions) and get the first one
                if isinstance(position, list):
                    position = position[0] if position else None
                
                if not position or Decimal(position.get("positionAmt", "0")) == 0:
                    continue
                
                # Update risk metrics
                current_price = Decimal(position.get("markPrice", "0"))
                unrealized_pnl = Decimal(position.get("unRealizedProfit", "0"))
                notional = abs(Decimal(position.get("notional", "0")))
                
                self.risk_metrics.update_data(
                    symbol,
                    float(current_price),
                    float(unrealized_pnl),
                    float(notional)
                )
                
                # Check individual risk metrics
                self._check_individual_risk_limits(symbol, position)
                positions_checked += 1
                
            except Exception as e:
                log.error(f"Error monitoring individual risk for {symbol}: {e}")
        
        self.stats["positions_monitored"] = positions_checked
    
    def _check_individual_risk_limits(self, symbol: str, position: Dict) -> None:
        """Check risk limits for an individual position."""
        try:
            # Check drawdown
            max_dd = self.risk_metrics.calculate_max_drawdown(symbol)
            if max_dd is not None and max_dd < -0.1:  # -10% max drawdown
                self._send_risk_alert(
                    symbol,
                    f"High drawdown detected: {max_dd*100:.1f}%",
                    "WARNING"
                )
            
            # Check VaR
            var = self.risk_metrics.calculate_var(symbol)
            if var is not None and var < -0.05:  # -5% daily VaR limit
                self._send_risk_alert(
                    symbol,
                    f"High VaR detected: {var*100:.1f}%",
                    "WARNING"
                )
            
            # Check Sharpe ratio
            sharpe = self.risk_metrics.calculate_sharpe_ratio(symbol)
            if sharpe is not None and sharpe < 0:  # Negative Sharpe ratio
                self._send_risk_alert(
                    symbol,
                    f"Poor risk-adjusted returns: Sharpe {sharpe:.2f}",
                    "INFO"
                )
            
            # Check position size relative to account
            position_value = abs(Decimal(position.get("notional", "0")))
            account_balance = self.api_client.get_futures_balance()
            if account_balance:
                # Handle both list and dict response formats for account balance
                if isinstance(account_balance, list):
                    # Find USDT balance in list format
                    usdt_balance = None
                    for asset in account_balance:
                        if asset.get("asset") == "USDT":
                            usdt_balance = asset
                            break
                    total_balance = Decimal(usdt_balance.get("totalWalletBalance", "0")) if usdt_balance else Decimal("0")
                else:
                    # Handle dict format
                    total_balance = Decimal(account_balance.get("totalWalletBalance", "0"))
                
                if total_balance > 0:
                    position_ratio = position_value / total_balance
                    if position_ratio > Decimal("0.5"):  # 50% of account in single position
                        self._send_risk_alert(
                            symbol,
                            f"Large position size: {position_ratio*100:.1f}% of account",
                            "WARNING"
                        )
        
        except Exception as e:
            log.error(f"Error checking individual risk limits for {symbol}: {e}")
    
    def _monitor_portfolio_risks(self) -> None:
        """Monitor portfolio-level risks."""
        try:
            # Get all positions
            positions = {}
            for symbol in self.monitored_symbols:
                position = self.api_client.get_futures_position(symbol)
                # Check if position is a list and get the first one
                if isinstance(position, list):
                    position = position[0] if position else None
                
                if position and Decimal(position.get("positionAmt", "0")) != 0:
                    positions[symbol] = position
            
            if len(positions) < 2:
                return  # Need at least 2 positions for portfolio risk
            
            # Update portfolio positions
            self.portfolio_manager.update_positions(positions)
            
            # Calculate portfolio risks
            portfolio_risk = self.portfolio_manager.calculate_portfolio_risk(
                self.risk_metrics, list(positions.keys())
            )
            
            # Check portfolio risk limits
            self._check_portfolio_risk_limits(portfolio_risk)
            
        except Exception as e:
            log.error(f"Error monitoring portfolio risks: {e}")
    
    def _check_portfolio_risk_limits(self, portfolio_risk: Dict) -> None:
        """Check portfolio-level risk limits."""
        try:
            # Check diversification
            diversification = portfolio_risk.get("diversification_score", 1.0)
            if diversification < 0.3:  # Poor diversification
                self._send_risk_alert(
                    "PORTFOLIO",
                    f"Poor diversification: {diversification*100:.1f}%",
                    "WARNING"
                )
            
            # Check concentration risks
            concentration_risks = portfolio_risk.get("concentration_risk", [])
            for risk in concentration_risks:
                self._send_risk_alert("PORTFOLIO", f"Concentration risk: {risk}", "WARNING")
            
            # Check correlation risks
            correlation_risks = portfolio_risk.get("correlation_risk", [])
            for risk in correlation_risks:
                self._send_risk_alert("PORTFOLIO", f"Correlation risk: {risk}", "WARNING")
            
            # Check portfolio VaR
            portfolio_var = portfolio_risk.get("portfolio_var", 0)
            if portfolio_var > 0.1:  # 10% portfolio VaR limit
                self._send_risk_alert(
                    "PORTFOLIO",
                    f"High portfolio VaR: {portfolio_var*100:.1f}%",
                    "CRITICAL"
                )
        
        except Exception as e:
            log.error(f"Error checking portfolio risk limits: {e}")
    
    def _monitor_system_risks(self) -> None:
        """Monitor system-wide risks."""
        try:
            # Check API connectivity
            current_time = time.time()
            
            # Check account balance
            balance = self.api_client.get_futures_account_balance()
            if balance:
                # Handle both list and dict response formats
                if isinstance(balance, list):
                    # Find USDT balance in list format
                    usdt_balance = None
                    for asset in balance:
                        if asset.get("asset") == "USDT":
                            usdt_balance = asset
                            break
                    if usdt_balance:
                        total_balance = Decimal(usdt_balance.get("walletBalance", "0"))
                        available_balance = Decimal(usdt_balance.get("availableBalance", "0"))
                    else:
                        log.warning("USDT balance not found in futures account")
                        return
                else:
                    # Handle dict format
                    total_balance = Decimal(balance.get("totalWalletBalance", "0"))
                    available_balance = Decimal(balance.get("availableBalance", "0"))
                
                # Check if running low on margin
                if total_balance > 0:
                    margin_ratio = available_balance / total_balance
                    if margin_ratio < Decimal("0.1"):  # Less than 10% available margin
                        self._send_risk_alert(
                            "SYSTEM",
                            f"Low available margin: {margin_ratio*100:.1f}%",
                            "CRITICAL"
                        )
        
        except Exception as e:
            log.error(f"Error monitoring system risks: {e}")
    
    def _send_risk_alert(self, context: str, message: str, level: str = "WARNING") -> None:
        """Send a risk alert with cooldown."""
        current_time = time.time()
        alert_key = f"{context}_{message}"
        
        # Check cooldown
        if alert_key in self.alert_cooldown:
            time_since_last = current_time - self.alert_cooldown[alert_key]
            if time_since_last < (self.alert_cooldown_minutes * 60):
                return  # Still in cooldown
        
        # Send alert
        try:
            if level == "CRITICAL":
                self.alerter.send_critical_alert(f"[{context}] {message}")
            else:
                self.alerter.send_message(f"⚠️ [{context}] {message}")
            
            self.alert_cooldown[alert_key] = current_time
            self.stats["alerts_sent"] += 1
            
            log.warning(f"Risk alert sent - [{context}] {message}")
        
        except Exception as e:
            log.error(f"Error sending risk alert: {e}")
    
    def _log_risk_status(self) -> None:
        """Log periodic risk status."""
        try:
            log.info(
                f"RiskAgent Status - Checks: {self.stats['risk_checks']}, "
                f"Positions: {self.stats['positions_monitored']}, "
                f"Alerts: {self.stats['alerts_sent']}, "
                f"Avg Check Time: {self.stats['avg_check_time']:.2f}s"
            )
        except Exception as e:
            log.error(f"Error logging risk status: {e}")
    
    def get_statistics(self) -> Dict:
        """Get risk agent statistics."""
        return {
            "risk_checks": self.stats["risk_checks"],
            "alerts_sent": self.stats["alerts_sent"],
            "positions_monitored": self.stats["positions_monitored"],
            "avg_check_time": self.stats["avg_check_time"],
            "monitored_symbols": list(self.monitored_symbols),
            "active_alerts": len(self.alert_cooldown)
        }
    
    def get_risk_summary(self) -> Dict:
        """Get current risk summary."""
        try:
            # Get portfolio summary
            positions = {}
            for symbol in self.monitored_symbols:
                position = self.api_client.get_futures_position(symbol)
                # Check if position is a list and get the first one
                if isinstance(position, list):
                    position = position[0] if position else None
                
                if position and Decimal(position.get("positionAmt", "0")) != 0:
                    positions[symbol] = position
            
            self.portfolio_manager.update_positions(positions)
            portfolio_risk = self.portfolio_manager.calculate_portfolio_risk(
                self.risk_metrics, list(positions.keys())
            )
            
            # Get individual risk metrics
            individual_risks = {}
            for symbol in self.monitored_symbols:
                individual_risks[symbol] = {
                    "var": self.risk_metrics.calculate_var(symbol),
                    "sharpe": self.risk_metrics.calculate_sharpe_ratio(symbol),
                    "max_drawdown": self.risk_metrics.calculate_max_drawdown(symbol)
                }
            
            return {
                "portfolio_risk": portfolio_risk,
                "individual_risks": individual_risks,
                "monitored_symbols": list(self.monitored_symbols),
                "last_update": time.time()
            }
        
        except Exception as e:
            log.error(f"Error getting risk summary: {e}")
            return {}
    
    def get_risk_history(self, limit: int = 20) -> Dict:
        """Get recent risk alert history."""
        history = {}
        for alert_key, timestamp in self.alert_cooldown.items():
            context, message = alert_key.split("_", 1)
            if context not in history:
                history[context] = []
            history[context].append({"message": message, "timestamp": timestamp})
        
        # Sort by timestamp and limit
        for context in history:
            history[context].sort(key=lambda x: x['timestamp'], reverse=True)
            history[context] = history[context][:limit]
            
        return history