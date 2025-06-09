# AI Trading Integration - Specific integrations between AI Agent and trading components
import asyncio
import time
from typing import Dict, List, Optional, Any

from utils.logger import setup_logger

log = setup_logger("ai_trading_integration")


class AIGridOptimizer:
    """AI-powered grid strategy optimizer."""
    
    def __init__(self, ai_agent):
        self.ai_agent = ai_agent
        self.optimization_history = []
        self.last_optimization = {}
    
    async def optimize_grid_parameters(self, symbol: str, current_params: Dict, market_data: Dict) -> Optional[Dict]:
        """Get AI-optimized grid parameters."""
        if not self.ai_agent.is_available:
            return None
        
        try:
            # Prepare comprehensive context
            market_context = {
                "symbol": symbol,
                "current_price": market_data.get("current_price", 0),
                "volatility_24h": market_data.get("atr_percentage", 0),
                "volume_24h": market_data.get("volume_24h", 0),
                "trend_strength": market_data.get("adx", 0),
                "rsi": market_data.get("rsi", 50),
                "price_change_24h": market_data.get("price_change_24h", 0),
                "recent_performance": current_params.get("recent_pnl", 0)
            }
            
            # Get AI recommendations
            recommendations = await self.ai_agent.optimize_grid_strategy(current_params, market_context)
            
            if recommendations:
                # Process and validate recommendations
                optimized_params = self._process_recommendations(recommendations, current_params)
                
                # Store optimization history
                self.optimization_history.append({
                    "timestamp": time.time(),
                    "symbol": symbol,
                    "original_params": current_params.copy(),
                    "recommended_params": optimized_params,
                    "market_context": market_context,
                    "ai_reasoning": recommendations.get("reasoning", "")
                })
                
                self.last_optimization[symbol] = optimized_params
                
                log.info(f"AI grid optimization completed for {symbol}")
                return optimized_params
            
        except Exception as e:
            log.error(f"Error in AI grid optimization for {symbol}: {e}")
        
        return None
    
    def _process_recommendations(self, recommendations: Dict, current_params: Dict) -> Dict:
        """Process and validate AI recommendations."""
        optimized = current_params.copy()
        
        try:
            # Process spacing recommendation
            if "grid_spacing_percent" in recommendations:
                new_spacing = float(recommendations["grid_spacing_percent"])
                # Validate range (0.1% to 5%)
                if 0.1 <= new_spacing <= 5.0:
                    optimized["spacing_perc"] = new_spacing / 100
                    log.info(f"AI recommended spacing: {new_spacing}%")
            
            # Process levels recommendation
            if "grid_levels" in recommendations:
                new_levels = int(recommendations["grid_levels"])
                # Validate range (5 to 50 levels)
                if 5 <= new_levels <= 50:
                    optimized["levels"] = new_levels
                    log.info(f"AI recommended levels: {new_levels}")
            
            # Process risk adjustment
            if "risk_multiplier" in recommendations:
                risk_mult = float(recommendations["risk_multiplier"])
                # Validate range (0.5x to 2.0x)
                if 0.5 <= risk_mult <= 2.0:
                    optimized["risk_multiplier"] = risk_mult
                    log.info(f"AI recommended risk multiplier: {risk_mult}x")
        
        except (ValueError, KeyError) as e:
            log.warning(f"Error processing AI recommendations: {e}")
        
        return optimized


class AIMarketAnalyzer:
    """AI-powered market analysis for trading decisions."""
    
    def __init__(self, ai_agent):
        self.ai_agent = ai_agent
        self.analysis_cache = {}
        self.trend_alerts = []
    
    async def analyze_entry_opportunity(self, symbol: str, market_data: Dict, sentiment_data: Dict) -> Optional[Dict]:
        """Analyze if current conditions are good for entry."""
        if not self.ai_agent.is_available:
            return None
        
        try:
            # Combine market and sentiment data
            comprehensive_data = {
                **market_data,
                "sentiment_score": sentiment_data.get("smoothed_score", 0),
                "sentiment_sources": sentiment_data.get("source_scores", {})
            }
            
            # Get AI analysis
            analysis = await self.ai_agent.analyze_market(comprehensive_data)
            
            if analysis:
                # Extract actionable insights
                entry_analysis = self._extract_entry_insights(analysis, symbol)
                
                # Cache analysis
                self.analysis_cache[symbol] = {
                    "analysis": entry_analysis,
                    "timestamp": time.time()
                }
                
                return entry_analysis
            
        except Exception as e:
            log.error(f"Error in AI entry analysis for {symbol}: {e}")
        
        return None
    
    def _extract_entry_insights(self, ai_analysis: Dict, symbol: str) -> Dict:
        """Extract actionable entry insights from AI analysis."""
        insights = {
            "symbol": symbol,
            "timestamp": time.time(),
            "entry_recommendation": "neutral",  # hold, buy, sell
            "confidence_score": 0.5,
            "key_factors": [],
            "risk_level": "medium",
            "time_horizon": "short",  # short, medium, long
            "ai_reasoning": ""
        }
        
        try:
            # Process AI analysis
            if isinstance(ai_analysis, dict):
                # Extract recommendation
                if "recommendation" in ai_analysis:
                    insights["entry_recommendation"] = ai_analysis["recommendation"].lower()
                
                # Extract confidence
                if "confidence" in ai_analysis:
                    insights["confidence_score"] = float(ai_analysis["confidence"])
                
                # Extract key factors
                if "key_factors" in ai_analysis:
                    insights["key_factors"] = ai_analysis["key_factors"]
                
                # Extract risk assessment
                if "risk_level" in ai_analysis:
                    insights["risk_level"] = ai_analysis["risk_level"].lower()
                
                # Store full reasoning
                if "analysis" in ai_analysis:
                    insights["ai_reasoning"] = ai_analysis["analysis"]
                
                log.info(f"Entry analysis for {symbol}: {insights['entry_recommendation']} (confidence: {insights['confidence_score']:.2f})")
        
        except Exception as e:
            log.warning(f"Error extracting insights from AI analysis: {e}")
        
        return insights


class AIDecisionExplainer:
    """AI-powered explanation system for trading decisions."""
    
    def __init__(self, ai_agent):
        self.ai_agent = ai_agent
        self.explanation_history = []
    
    async def explain_trade_decision(self, decision_data: Dict) -> Optional[str]:
        """Get AI explanation for a trade decision."""
        if not self.ai_agent.is_available:
            return None
        
        try:
            # Prepare decision context
            decision_context = {
                "action": decision_data.get("action", "unknown"),  # buy, sell, hold
                "symbol": decision_data.get("symbol", ""),
                "price": decision_data.get("price", 0),
                "quantity": decision_data.get("quantity", 0),
                "reasoning_factors": decision_data.get("factors", []),
                "market_conditions": decision_data.get("market_data", {}),
                "risk_metrics": decision_data.get("risk_data", {}),
                "sentiment_score": decision_data.get("sentiment", 0)
            }
            
            # Get AI explanation
            explanation = await self.ai_agent.explain_decision(decision_context)
            
            if explanation:
                # Store explanation history
                self.explanation_history.append({
                    "timestamp": time.time(),
                    "decision": decision_data,
                    "explanation": explanation
                })
                
                # Keep only recent explanations
                if len(self.explanation_history) > 100:
                    self.explanation_history = self.explanation_history[-100:]
                
                log.info(f"AI explanation generated for {decision_data.get('action', 'unknown')} decision")
                return explanation
            
        except Exception as e:
            log.error(f"Error generating AI explanation: {e}")
        
        return None


class AIReportGenerator:
    """AI-powered report generation system."""
    
    def __init__(self, ai_agent):
        self.ai_agent = ai_agent
        self.report_schedule = {}
        self.last_reports = {}
    
    async def generate_daily_report(self, trading_data: Dict, market_data: Dict, performance_data: Dict) -> Optional[str]:
        """Generate comprehensive daily trading report."""
        if not self.ai_agent.is_available:
            return None
        
        try:
            # Compile comprehensive data
            comprehensive_data = {
                "trading_summary": {
                    "total_trades": trading_data.get("total_trades", 0),
                    "profitable_trades": trading_data.get("profitable_trades", 0),
                    "total_pnl": trading_data.get("total_pnl", 0),
                    "active_pairs": trading_data.get("active_pairs", []),
                    "best_performing_pair": trading_data.get("best_pair", ""),
                    "worst_performing_pair": trading_data.get("worst_pair", "")
                },
                "market_overview": {
                    "market_trend": market_data.get("overall_trend", "neutral"),
                    "volatility_level": market_data.get("avg_volatility", 0),
                    "volume_analysis": market_data.get("volume_analysis", {}),
                    "key_events": market_data.get("significant_events", [])
                },
                "performance_metrics": {
                    "sharpe_ratio": performance_data.get("sharpe_ratio", 0),
                    "max_drawdown": performance_data.get("max_drawdown", 0),
                    "win_rate": performance_data.get("win_rate", 0),
                    "avg_trade_duration": performance_data.get("avg_duration", 0)
                },
                "risk_assessment": {
                    "current_exposure": performance_data.get("total_exposure", 0),
                    "correlation_risks": performance_data.get("correlation_risks", []),
                    "liquidity_status": performance_data.get("liquidity_status", "good")
                }
            }
            
            # Generate AI report
            report = await self.ai_agent.generate_market_report(comprehensive_data)
            
            if report:
                self.last_reports["daily"] = {
                    "timestamp": time.time(),
                    "report": report,
                    "data": comprehensive_data
                }
                
                log.info("Daily AI report generated successfully")
                return report
            
        except Exception as e:
            log.error(f"Error generating daily AI report: {e}")
        
        return None
    
    async def generate_pair_analysis_report(self, symbol: str, pair_data: Dict) -> Optional[str]:
        """Generate detailed analysis report for a specific trading pair."""
        if not self.ai_agent.is_available:
            return None
        
        try:
            # Prepare pair-specific data
            pair_analysis_data = {
                "symbol": symbol,
                "performance": {
                    "total_trades": pair_data.get("trades", 0),
                    "success_rate": pair_data.get("success_rate", 0),
                    "total_pnl": pair_data.get("pnl", 0),
                    "best_trade": pair_data.get("best_trade", 0),
                    "worst_trade": pair_data.get("worst_trade", 0)
                },
                "market_behavior": {
                    "avg_volatility": pair_data.get("volatility", 0),
                    "trading_volume": pair_data.get("volume", 0),
                    "price_range": pair_data.get("price_range", {}),
                    "correlation_with_btc": pair_data.get("btc_correlation", 0)
                },
                "strategy_effectiveness": {
                    "grid_efficiency": pair_data.get("grid_efficiency", 0),
                    "optimal_spacing": pair_data.get("optimal_spacing", 0),
                    "risk_adjusted_return": pair_data.get("risk_adj_return", 0)
                }
            }
            
            # Generate focused report
            report = await self.ai_agent.generate_market_report(pair_analysis_data)
            
            if report:
                log.info(f"Pair analysis report generated for {symbol}")
                return report
            
        except Exception as e:
            log.error(f"Error generating pair analysis report for {symbol}: {e}")
        
        return None


class AITradingIntegration:
    """Main integration class that combines all AI trading functionalities."""
    
    def __init__(self, ai_agent):
        self.ai_agent = ai_agent
        
        # Initialize components
        self.grid_optimizer = AIGridOptimizer(ai_agent)
        self.market_analyzer = AIMarketAnalyzer(ai_agent)
        self.decision_explainer = AIDecisionExplainer(ai_agent)
        self.report_generator = AIReportGenerator(ai_agent)
        
        # Integration state
        self.integration_stats = {
            "optimizations_performed": 0,
            "analyses_completed": 0,
            "decisions_explained": 0,
            "reports_generated": 0,
            "errors": 0
        }
        
        log.info("AI Trading Integration initialized")
    
    async def process_trading_cycle(self, symbol: str, trading_data: Dict) -> Dict:
        """Process a complete trading cycle with AI assistance."""
        results = {
            "symbol": symbol,
            "timestamp": time.time(),
            "ai_insights": {},
            "optimizations": {},
            "recommendations": {}
        }
        
        try:
            market_data = trading_data.get("market_data", {})
            sentiment_data = trading_data.get("sentiment_data", {})
            current_params = trading_data.get("grid_params", {})
            
            # 1. Market Analysis
            if market_data and sentiment_data:
                entry_analysis = await self.market_analyzer.analyze_entry_opportunity(
                    symbol, market_data, sentiment_data
                )
                if entry_analysis:
                    results["ai_insights"]["entry_analysis"] = entry_analysis
                    self.integration_stats["analyses_completed"] += 1
            
            # 2. Grid Optimization (if needed)
            if current_params and market_data:
                optimization = await self.grid_optimizer.optimize_grid_parameters(
                    symbol, current_params, market_data
                )
                if optimization:
                    results["optimizations"]["grid_params"] = optimization
                    self.integration_stats["optimizations_performed"] += 1
            
            # 3. Decision Explanation (if decision was made)
            if trading_data.get("decision_made"):
                explanation = await self.decision_explainer.explain_trade_decision(
                    trading_data.get("decision_data", {})
                )
                if explanation:
                    results["ai_insights"]["decision_explanation"] = explanation
                    self.integration_stats["decisions_explained"] += 1
            
            return results
        
        except Exception as e:
            log.error(f"Error in AI trading cycle processing for {symbol}: {e}")
            self.integration_stats["errors"] += 1
            return results
    
    async def generate_comprehensive_report(self, system_data: Dict) -> Optional[str]:
        """Generate comprehensive system report."""
        try:
            trading_data = system_data.get("trading_data", {})
            market_data = system_data.get("market_data", {})
            performance_data = system_data.get("performance_data", {})
            
            report = await self.report_generator.generate_daily_report(
                trading_data, market_data, performance_data
            )
            
            if report:
                self.integration_stats["reports_generated"] += 1
                return report
            
        except Exception as e:
            log.error(f"Error generating comprehensive report: {e}")
            self.integration_stats["errors"] += 1
        
        return None
    
    def get_integration_statistics(self) -> Dict:
        """Get integration statistics."""
        ai_stats = self.ai_agent.get_statistics() if self.ai_agent else {}
        
        return {
            "integration_stats": self.integration_stats,
            "ai_agent_stats": ai_stats,
            "components": {
                "grid_optimizer": len(self.grid_optimizer.optimization_history),
                "market_analyzer": len(self.market_analyzer.analysis_cache),
                "decision_explainer": len(self.decision_explainer.explanation_history),
                "report_generator": len(self.report_generator.last_reports)
            }
        }