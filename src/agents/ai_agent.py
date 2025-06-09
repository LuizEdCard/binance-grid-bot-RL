# AI Agent - Integration with local AI for advanced market analysis
import asyncio
import json
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Any, Tuple

import aiohttp
import numpy as np
import pandas as pd

from utils.logger import setup_logger

log = setup_logger("ai_agent")


class LocalAIClient:
    """Client for communicating with local AI server."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:1234"):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.timeout = aiohttp.ClientTimeout(total=30, connect=5)
        
        # Performance tracking
        self.stats = {
            "requests_made": 0,
            "requests_failed": 0,
            "avg_response_time": 0.0,
            "total_tokens_processed": 0
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()
    
    async def start_session(self) -> None:
        """Start the aiohttp session."""
        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers={"Content-Type": "application/json"}
        )
    
    async def close_session(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> bool:
        """Check if the local AI is available."""
        try:
            if not self.session:
                await self.start_session()
            
            async with self.session.get(f"{self.base_url}/health") as response:
                return response.status == 200
        except Exception as e:
            log.debug(f"AI health check failed: {e}")
            return False
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "local-model",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Optional[Dict]:
        """Send chat completion request to local AI."""
        start_time = time.time()
        
        try:
            if not self.session:
                await self.start_session()
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
            
            async with self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    # Update stats
                    self.stats["requests_made"] += 1
                    response_time = time.time() - start_time
                    self.stats["avg_response_time"] = (
                        (self.stats["avg_response_time"] * (self.stats["requests_made"] - 1) + response_time)
                        / self.stats["requests_made"]
                    )
                    
                    # Track tokens if available
                    if "usage" in result:
                        self.stats["total_tokens_processed"] += result["usage"].get("total_tokens", 0)
                    
                    return result
                else:
                    error_text = await response.text()
                    log.error(f"AI request failed with status {response.status}: {error_text}")
                    self.stats["requests_failed"] += 1
                    return None
        
        except Exception as e:
            log.error(f"Error in AI chat completion: {e}")
            self.stats["requests_failed"] += 1
            return None
    
    def get_statistics(self) -> Dict:
        """Get client statistics."""
        return self.stats.copy()


class MarketAnalysisAI:
    """AI-powered market analysis module."""
    
    def __init__(self, ai_client: LocalAIClient):
        self.ai_client = ai_client
    
    async def analyze_market_patterns(self, market_data: Dict) -> Optional[Dict]:
        """Analyze market patterns using AI."""
        try:
            # Prepare market data summary
            data_summary = self._prepare_market_summary(market_data)
            
            messages = [
                {
                    "role": "system",
                    "content": """You are an expert cryptocurrency market analyst. Analyze the provided market data and identify:
1. Key patterns and trends
2. Support and resistance levels
3. Market anomalies or unusual behavior
4. Short-term price predictions (next 1-4 hours)
5. Risk factors to consider

Provide your analysis in JSON format with specific, actionable insights."""
                },
                {
                    "role": "user",
                    "content": f"Analyze this market data: {data_summary}"
                }
            ]
            
            response = await self.ai_client.chat_completion(
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=800
            )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                try:
                    # Try to parse JSON response
                    analysis = json.loads(content)
                    return analysis
                except json.JSONDecodeError:
                    # If not JSON, return as text analysis
                    return {"analysis": content, "format": "text"}
            
            return None
        
        except Exception as e:
            log.error(f"Error in market pattern analysis: {e}")
            return None
    
    async def optimize_grid_parameters(self, current_params: Dict, market_context: Dict) -> Optional[Dict]:
        """Get AI recommendations for grid parameter optimization."""
        try:
            context_summary = {
                "current_grid_spacing": current_params.get("spacing_perc", 0.5),
                "current_levels": current_params.get("levels", 10),
                "market_volatility": market_context.get("atr_percentage", 0),
                "trend_strength": market_context.get("adx", 0),
                "recent_performance": market_context.get("recent_pnl", 0)
            }
            
            messages = [
                {
                    "role": "system",
                    "content": """You are an expert in grid trading strategy optimization. Based on current market conditions and grid parameters, provide recommendations for:
1. Optimal grid spacing percentage
2. Number of grid levels
3. Risk adjustments needed
4. Entry/exit timing suggestions

Respond in JSON format with specific numerical recommendations and reasoning."""
                },
                {
                    "role": "user",
                    "content": f"Current grid parameters and market context: {json.dumps(context_summary)}"
                }
            ]
            
            response = await self.ai_client.chat_completion(
                messages=messages,
                temperature=0.2,
                max_tokens=600
            )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                try:
                    recommendations = json.loads(content)
                    return recommendations
                except json.JSONDecodeError:
                    return {"recommendations": content, "format": "text"}
            
            return None
        
        except Exception as e:
            log.error(f"Error in grid optimization: {e}")
            return None
    
    async def analyze_sentiment_context(self, sentiment_data: Dict, market_data: Dict) -> Optional[Dict]:
        """Analyze sentiment in market context using AI."""
        try:
            context = {
                "sentiment_score": sentiment_data.get("smoothed_score", 0),
                "sentiment_sources": sentiment_data.get("source_scores", {}),
                "price_change_24h": market_data.get("price_change_percent", 0),
                "volume_change": market_data.get("volume_change_percent", 0),
                "market_cap_rank": market_data.get("rank", "unknown")
            }
            
            messages = [
                {
                    "role": "system",
                    "content": """You are a market sentiment analyst expert in crypto markets. Analyze the correlation between sentiment and price action. Provide insights on:
1. How current sentiment aligns with price movement
2. Potential sentiment-driven price movements
3. Sentiment momentum (strengthening/weakening)
4. Risk of sentiment reversal
5. Trading recommendations based on sentiment-price divergence

Respond in JSON format with actionable insights."""
                },
                {
                    "role": "user",
                    "content": f"Sentiment and market context: {json.dumps(context)}"
                }
            ]
            
            response = await self.ai_client.chat_completion(
                messages=messages,
                temperature=0.4,
                max_tokens=700
            )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                try:
                    analysis = json.loads(content)
                    return analysis
                except json.JSONDecodeError:
                    return {"analysis": content, "format": "text"}
            
            return None
        
        except Exception as e:
            log.error(f"Error in sentiment context analysis: {e}")
            return None
    
    def _prepare_market_summary(self, market_data: Dict) -> str:
        """Prepare a concise market data summary for AI analysis."""
        summary_parts = []
        
        # Price information
        if "current_price" in market_data:
            summary_parts.append(f"Current price: ${market_data['current_price']}")
        
        if "price_change_24h" in market_data:
            summary_parts.append(f"24h change: {market_data['price_change_24h']:.2f}%")
        
        # Technical indicators
        if "rsi" in market_data:
            summary_parts.append(f"RSI: {market_data['rsi']:.1f}")
        
        if "atr_percentage" in market_data:
            summary_parts.append(f"ATR: {market_data['atr_percentage']:.2f}%")
        
        # Volume
        if "volume_24h" in market_data:
            summary_parts.append(f"24h volume: ${market_data['volume_24h']:,.0f}")
        
        # Recent price action (if available)
        if "recent_prices" in market_data:
            prices = market_data["recent_prices"][-10:]  # Last 10 prices
            summary_parts.append(f"Recent price trend: {prices}")
        
        return "; ".join(summary_parts)


class DecisionSupportAI:
    """AI-powered decision support system."""
    
    def __init__(self, ai_client: LocalAIClient):
        self.ai_client = ai_client
    
    async def explain_trading_decision(self, decision_context: Dict) -> Optional[str]:
        """Get AI explanation for a trading decision."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are an expert trading advisor. Explain trading decisions in clear, educational terms. Focus on:
1. Why this decision makes sense given the market conditions
2. What factors were most important in this decision
3. Potential risks and how they're being managed
4. What to watch for going forward

Keep explanations concise but informative."""
                },
                {
                    "role": "user",
                    "content": f"Explain this trading decision: {json.dumps(decision_context)}"
                }
            ]
            
            response = await self.ai_client.chat_completion(
                messages=messages,
                temperature=0.5,
                max_tokens=400
            )
            
            if response and "choices" in response:
                return response["choices"][0]["message"]["content"]
            
            return None
        
        except Exception as e:
            log.error(f"Error in decision explanation: {e}")
            return None
    
    async def generate_market_report(self, comprehensive_data: Dict) -> Optional[str]:
        """Generate a comprehensive market report."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are a professional market analyst. Create a concise but comprehensive market report including:
1. Current market overview
2. Key trends and patterns
3. Risk assessment
4. Strategic recommendations
5. Outlook for next 24 hours

Format as a professional report suitable for traders."""
                },
                {
                    "role": "user",
                    "content": f"Generate market report based on: {json.dumps(comprehensive_data)}"
                }
            ]
            
            response = await self.ai_client.chat_completion(
                messages=messages,
                temperature=0.4,
                max_tokens=800
            )
            
            if response and "choices" in response:
                return response["choices"][0]["message"]["content"]
            
            return None
        
        except Exception as e:
            log.error(f"Error generating market report: {e}")
            return None


class AIAgent:
    """Main AI Agent that integrates local AI capabilities."""
    
    def __init__(self, config: dict, ai_base_url: str = "http://127.0.0.1:1234"):
        self.config = config
        self.ai_config = config.get("ai_agent", {})
        self.ai_base_url = ai_base_url
        
        # AI components
        self.ai_client = LocalAIClient(ai_base_url)
        self.market_analysis = MarketAnalysisAI(self.ai_client)
        self.decision_support = DecisionSupportAI(self.ai_client)
        
        # State
        self.is_available = False
        self.last_health_check = 0
        self.analysis_cache = {}
        self.analysis_history = deque(maxlen=100)
        
        # Threading
        self.stop_event = threading.Event()
        self.health_check_thread = None
        
        # Callbacks
        self.analysis_callbacks = []
        self.report_callbacks = []
        
        # Performance
        self.stats = {
            "analyses_performed": 0,
            "decisions_explained": 0,
            "reports_generated": 0,
            "avg_analysis_time": 0.0,
            "cache_hits": 0
        }
        
        log.info(f"AIAgent initialized for {ai_base_url}")
    
    async def start(self) -> None:
        """Start the AI agent."""
        log.info("Starting AI Agent...")
        
        # Check if AI is available
        await self._check_ai_availability()
        
        if not self.is_available:
            log.warning("Local AI not available. AI Agent will run in limited mode (no functionality).")
            log.info("Bot will continue operating normally without AI assistance.")
            # Don't return, continue to start health check thread
        else:
            log.info("AI Agent fully operational with local AI")
        
        # Start health check thread
        self.stop_event.clear()
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="AIAgent-HealthCheck"
        )
        self.health_check_thread.start()
        
        log.info("AI Agent started successfully")
    
    def stop(self) -> None:
        """Stop the AI agent."""
        log.info("Stopping AI Agent...")
        self.stop_event.set()
        
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(timeout=5)
        
        log.info("AI Agent stopped")
    
    async def _check_ai_availability(self) -> None:
        """Check if local AI is available."""
        try:
            async with self.ai_client:
                self.is_available = await self.ai_client.health_check()
                
            if self.is_available:
                log.info("Local AI is available and responding")
            else:
                log.warning("Local AI is not responding")
                
        except Exception as e:
            log.error(f"Error checking AI availability: {e}")
            self.is_available = False
    
    def _health_check_loop(self) -> None:
        """Background health check loop."""
        check_interval = 60  # Check every minute
        
        while not self.stop_event.is_set():
            try:
                asyncio.run(self._check_ai_availability())
                self.last_health_check = time.time()
                
            except Exception as e:
                log.error(f"Error in health check loop: {e}")
            
            self.stop_event.wait(check_interval)
    
    async def analyze_market(self, market_data: Dict, force_refresh: bool = False) -> Optional[Dict]:
        """Perform AI-powered market analysis."""
        if not self.is_available:
            log.debug("AI not available, skipping market analysis")
            return None
        
        # Check cache first
        cache_key = f"market_analysis_{hash(str(market_data))}"
        if not force_refresh and cache_key in self.analysis_cache:
            cache_entry = self.analysis_cache[cache_key]
            if time.time() - cache_entry["timestamp"] < 300:  # 5 minutes cache
                self.stats["cache_hits"] += 1
                return cache_entry["data"]
        
        start_time = time.time()
        
        try:
            async with self.ai_client:
                analysis = await self.market_analysis.analyze_market_patterns(market_data)
                
                if analysis:
                    # Cache the result
                    self.analysis_cache[cache_key] = {
                        "data": analysis,
                        "timestamp": time.time()
                    }
                    
                    # Update stats
                    self.stats["analyses_performed"] += 1
                    analysis_time = time.time() - start_time
                    self.stats["avg_analysis_time"] = (
                        (self.stats["avg_analysis_time"] * (self.stats["analyses_performed"] - 1) + analysis_time)
                        / self.stats["analyses_performed"]
                    )
                    
                    # Store in history
                    self.analysis_history.append({
                        "timestamp": time.time(),
                        "analysis": analysis,
                        "market_data": market_data
                    })
                    
                    # Notify callbacks
                    await self._notify_analysis_callbacks(analysis, market_data)
                    
                    log.info(f"Market analysis completed in {analysis_time:.2f}s")
                    return analysis
                
        except Exception as e:
            log.error(f"Error in market analysis: {e}")
        
        return None
    
    async def optimize_grid_strategy(self, current_params: Dict, market_context: Dict) -> Optional[Dict]:
        """Get AI recommendations for grid strategy optimization."""
        if not self.is_available:
            log.debug("AI not available, skipping grid optimization")
            return None
        
        try:
            async with self.ai_client:
                recommendations = await self.market_analysis.optimize_grid_parameters(
                    current_params, market_context
                )
                
                if recommendations:
                    log.info("Grid optimization recommendations received")
                    return recommendations
                
        except Exception as e:
            log.error(f"Error in grid optimization: {e}")
        
        return None
    
    async def analyze_sentiment_context(self, sentiment_data: Dict, market_data: Dict) -> Optional[Dict]:
        """Analyze sentiment in market context."""
        if not self.is_available:
            log.debug("AI not available, skipping sentiment context analysis")
            return None
        
        try:
            async with self.ai_client:
                analysis = await self.market_analysis.analyze_sentiment_context(
                    sentiment_data, market_data
                )
                
                if analysis:
                    log.info("Sentiment context analysis completed")
                    return analysis
                
        except Exception as e:
            log.error(f"Error in sentiment analysis: {e}")
        
        return None
    
    async def explain_decision(self, decision_context: Dict) -> Optional[str]:
        """Get AI explanation for a trading decision."""
        if not self.is_available:
            log.debug("AI not available, skipping decision explanation")
            return None
        
        try:
            async with self.ai_client:
                explanation = await self.decision_support.explain_trading_decision(decision_context)
                
                if explanation:
                    self.stats["decisions_explained"] += 1
                    log.debug("Decision explanation generated")
                    return explanation
                
        except Exception as e:
            log.error(f"Error explaining decision: {e}")
        
        return None
    
    async def generate_market_report(self, comprehensive_data: Dict) -> Optional[str]:
        """Generate comprehensive market report."""
        if not self.is_available:
            log.debug("AI not available, skipping market report generation")
            return None
        
        try:
            async with self.ai_client:
                report = await self.decision_support.generate_market_report(comprehensive_data)
                
                if report:
                    self.stats["reports_generated"] += 1
                    log.info("Market report generated")
                    
                    # Notify callbacks
                    await self._notify_report_callbacks(report, comprehensive_data)
                    return report
                
        except Exception as e:
            log.error(f"Error generating market report: {e}")
        
        return None
    
    def register_analysis_callback(self, callback) -> None:
        """Register callback for analysis updates."""
        self.analysis_callbacks.append(callback)
    
    def register_report_callback(self, callback) -> None:
        """Register callback for report generation."""
        self.report_callbacks.append(callback)
    
    async def _notify_analysis_callbacks(self, analysis: Dict, market_data: Dict) -> None:
        """Notify analysis callbacks."""
        for callback in self.analysis_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(analysis, market_data)
                else:
                    callback(analysis, market_data)
            except Exception as e:
                log.error(f"Error in analysis callback: {e}")
    
    async def _notify_report_callbacks(self, report: str, data: Dict) -> None:
        """Notify report callbacks."""
        for callback in self.report_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(report, data)
                else:
                    callback(report, data)
            except Exception as e:
                log.error(f"Error in report callback: {e}")
    
    def get_statistics(self) -> Dict:
        """Get AI agent statistics."""
        ai_stats = self.ai_client.get_statistics() if self.is_available else {}
        
        return {
            "is_available": self.is_available,
            "ai_base_url": self.ai_base_url,
            "last_health_check": self.last_health_check,
            "cached_analyses": len(self.analysis_cache),
            "analysis_history_size": len(self.analysis_history),
            "ai_client_stats": ai_stats,
            **self.stats
        }
    
    def get_recent_analyses(self, limit: int = 10) -> List[Dict]:
        """Get recent analysis history."""
        return list(self.analysis_history)[-limit:]