# AI Agent - Integration with local AI for advanced market analysis
import asyncio
import json
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Any, Tuple
from asyncio import Semaphore, Queue
from dataclasses import dataclass
from enum import Enum

import aiohttp
import numpy as np
import pandas as pd

from utils.logger import setup_logger

log = setup_logger("ai_agent")


class RequestPriority(Enum):
    """Request priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class QueuedRequest:
    """Represents a queued AI request."""
    messages: List[Dict[str, str]]
    model: str
    temperature: float
    max_tokens: int
    priority: RequestPriority
    future: asyncio.Future
    created_at: float
    timeout: int


class RequestQueue:
    """Thread-safe request queue with priority handling."""
    
    def __init__(self, max_concurrent: int = 1):
        self.queue = Queue()
        self.priority_queue = []  # For priority-based sorting
        self.semaphore = Semaphore(max_concurrent)
        self.active_requests = 0
        self.total_queued = 0
        self.stats = {
            "queued_requests": 0,
            "processed_requests": 0,
            "dropped_requests": 0,
            "avg_queue_time": 0.0,
            "priority_breakdown": {
                "critical": 0,
                "high": 0,
                "normal": 0,
                "low": 0
            }
        }
    
    async def enqueue(self, request: QueuedRequest) -> asyncio.Future:
        """Add request to queue with priority handling."""
        self.total_queued += 1
        self.stats["queued_requests"] += 1
        
        # Track priority stats
        priority_name = request.priority.name.lower()
        if priority_name in self.stats["priority_breakdown"]:
            self.stats["priority_breakdown"][priority_name] += 1
        
        # Use priority queue for high/critical requests, regular queue for others
        if request.priority in [RequestPriority.HIGH, RequestPriority.CRITICAL]:
            # Add to priority queue with sorting
            self.priority_queue.append(request)
            self.priority_queue.sort(key=lambda r: (r.priority.value, r.created_at), reverse=True)
        else:
            # Add to regular FIFO queue for normal/low priority
            await self.queue.put(request)
        
        return request.future
    
    async def dequeue(self) -> QueuedRequest:
        """Get next request from queue (priority-ordered)."""
        # First check priority queue for high/critical requests
        if self.priority_queue:
            # Get highest priority request (sorted in descending order)
            request = self.priority_queue.pop(0)
            return request
        
        # If no high priority requests, get from regular queue
        # This will wait if queue is empty
        try:
            request = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            return request
        except asyncio.TimeoutError:
            # No request available, raise so caller can handle
            raise asyncio.TimeoutError("No request available in queue")
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize() + len(self.priority_queue)
    
    def get_priority_stats(self) -> Dict:
        """Get priority breakdown statistics."""
        return {
            "priority_queue_size": len(self.priority_queue),
            "regular_queue_size": self.queue.qsize(),
            "total_queue_size": self.get_queue_size(),
            "priority_breakdown": self.stats["priority_breakdown"].copy()
        }


class CPUResourceManager:
    """Manages CPU resources for AI requests to prevent overload."""
    
    def __init__(self, max_concurrent: int = 1, max_queue_size: int = 10):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self.request_queue = RequestQueue(max_concurrent)
        self.rate_limiter = asyncio.Semaphore(max_concurrent)
        
        # Rate limiting (requests per time window)
        self.rate_limit_window = 60  # seconds
        self.max_requests_per_window = 20  # Conservative for CPU-only
        self.request_timestamps = deque()
        
        # Background processor
        self.processor_task = None
        self.stop_event = asyncio.Event()
        
        # System monitoring
        self.cpu_usage_threshold = 80  # Pause if CPU usage > 80%
        self.last_system_check = 0
        
    async def start(self):
        """Start the request processor."""
        if self.processor_task is None:
            self.processor_task = asyncio.create_task(self._process_requests())
            log.info(f"CPU Resource Manager started (max concurrent: {self.max_concurrent})")
    
    async def stop(self):
        """Stop the request processor."""
        if self.processor_task:
            self.stop_event.set()
            await self.processor_task
            self.processor_task = None
            log.info("CPU Resource Manager stopped")
    
    async def submit_request(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        priority: RequestPriority = RequestPriority.NORMAL,
        timeout: int = 60
    ) -> Optional[Dict]:
        """Submit a request with CPU resource management."""
        
        # Check rate limiting
        if not self._check_rate_limit():
            log.warning("Rate limit exceeded, dropping request")
            return None
        
        # Check queue capacity
        if self.request_queue.get_queue_size() >= self.max_queue_size:
            log.warning("Request queue full, dropping request")
            self.request_queue.stats["dropped_requests"] += 1
            return None
        
        # Create request
        future = asyncio.Future()
        request = QueuedRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            priority=priority,
            future=future,
            created_at=time.time(),
            timeout=timeout
        )
        
        # Enqueue request
        await self.request_queue.enqueue(request)
        
        try:
            # Wait for result with timeout (add buffer for queue wait time)
            result = await asyncio.wait_for(future, timeout=timeout + 20)
            return result
        except asyncio.TimeoutError:
            log.warning(f"Request timeout after {timeout + 20}s")
            return None
    
    async def _process_requests(self):
        """Background task to process queued requests."""
        while not self.stop_event.is_set():
            try:
                # Check system resources periodically
                if time.time() - self.last_system_check > 30:
                    await self._check_system_resources()
                    self.last_system_check = time.time()
                
                # Get next request
                try:
                    request = await asyncio.wait_for(
                        self.request_queue.dequeue(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Check if request expired
                queue_wait_time = time.time() - request.created_at
                if queue_wait_time > request.timeout:
                    log.warning(f"Request expired in queue after {queue_wait_time:.1f}s")
                    if not request.future.done():
                        request.future.set_result(None)
                    continue
                
                # Acquire semaphore to limit concurrency
                async with self.rate_limiter:
                    await self._execute_request(request)
                    
            except Exception as e:
                log.error(f"Error in request processor: {e}")
    
    async def _execute_request(self, request: QueuedRequest):
        """Execute a single request."""
        try:
            queue_time = time.time() - request.created_at
            
            # Update queue time stats
            stats = self.request_queue.stats
            stats["processed_requests"] += 1
            stats["avg_queue_time"] = (
                (stats["avg_queue_time"] * (stats["processed_requests"] - 1) + queue_time)
                / stats["processed_requests"]
            )
            
            if not request.future.done():
                # Execute the actual AI request via the client's direct method
                # This will be set by the LocalAIClient when it initializes the resource manager
                if hasattr(self, '_ai_client_ref'):
                    result = await self._ai_client_ref._execute_direct_request(
                        messages=request.messages,
                        model=request.model,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens
                    )
                    request.future.set_result(result)
                else:
                    # Fallback in case client reference not set
                    log.warning("AI client reference not set in resource manager")
                    request.future.set_result(None)
                
        except Exception as e:
            if not request.future.done():
                request.future.set_exception(e)
    
    def _check_rate_limit(self) -> bool:
        """Check if request is within rate limits."""
        now = time.time()
        
        # Remove old timestamps
        while (self.request_timestamps and 
               now - self.request_timestamps[0] > self.rate_limit_window):
            self.request_timestamps.popleft()
        
        # Check if we can make another request
        if len(self.request_timestamps) >= self.max_requests_per_window:
            return False
        
        # Add current timestamp
        self.request_timestamps.append(now)
        return True
    
    async def _check_system_resources(self):
        """Check system resources and adjust behavior."""
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            if cpu_percent > self.cpu_usage_threshold:
                log.warning(f"High CPU usage ({cpu_percent:.1f}%), pausing AI requests")
                await asyncio.sleep(5)  # Brief pause
            
            if memory_percent > 85:
                log.warning(f"High memory usage ({memory_percent:.1f}%)")
                
        except ImportError:
            # psutil not available, skip system monitoring
            pass
        except Exception as e:
            log.debug(f"System resource check failed: {e}")


class LocalAIClient:
    """Client for communicating with local AI server."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:11434", enable_cpu_management: bool = True):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.timeout = aiohttp.ClientTimeout(total=30, connect=5)
        
        # CPU Resource Management
        self.enable_cpu_management = enable_cpu_management
        self.resource_manager = None
        if enable_cpu_management:
            # Conservative settings for CPU-only systems
            max_concurrent = 1  # Only 1 request at a time
            max_queue_size = 5  # Small queue to prevent backlog
            self.resource_manager = CPUResourceManager(max_concurrent, max_queue_size)
            # Set reference to this client for actual request execution
            self.resource_manager._ai_client_ref = self
        
        # Model-specific timeout configurations
        self.model_timeouts = {
            # Fast models
            "qwen3:0.6b": 20,
            "gemma3:1b": 25,
            
            # Balanced models
            "qwen3:1.7b": 35,
            "gemma3:4b": 45,
            
            # Reasoning models (longer timeouts)
            "deepseek-r1:1.5b": 90,  # Reasoning models think more
            "qwen3:4b": 50,
            
            # Default fallback
            "default": 60
        }
        
        # Performance tracking
        self.stats = {
            "requests_made": 0,
            "requests_failed": 0,
            "timeouts": 0,
            "avg_response_time": 0.0,
            "total_tokens_processed": 0,
            "model_performance": {},  # Track per-model performance
            "queue_stats": {}  # Resource manager stats
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
        # Stop resource manager if running
        if self.resource_manager:
            await self.resource_manager.stop()
            
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> bool:
        """Check if the local AI is available (Ollama format)."""
        try:
            if not self.session:
                await self.start_session()
            
            # Use Ollama's API endpoint for checking available models
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                return response.status == 200
        except Exception as e:
            log.debug(f"AI health check failed: {e}")
            return False

    async def get_running_model(self) -> str | None:
        """Detect which model is currently running in Ollama."""
        try:
            if not self.session:
                await self.start_session()
            
            # First try to get running processes
            async with self.session.get(f"{self.base_url}/api/ps") as response:
                if response.status == 200:
                    result = await response.json()
                    models = result.get("models", [])
                    
                    if models:
                        # Return the first (most recently used) model
                        active_model = models[0].get("name", "")
                        log.info(f"Detected active model: {active_model}")
                        return active_model
            
            # If no model is running, try to detect from recent chat
            # Send a small test request to see which model responds
            log.debug("No model currently loaded, attempting to detect default model...")
            
            # Try a simple test with the most common models
            test_models = ["qwen3:1.7b", "deepseek-r1:1.5b", "qwen3:4b", "gemma3:4b", "qwen3:0.6b", "gemma3:1b"]
            
            for test_model in test_models:
                try:
                    test_payload = {
                        "model": test_model,
                        "prompt": "Hello",
                        "stream": False,
                        "options": {"num_predict": 1}
                    }
                    
                    async with self.session.post(
                        f"{self.base_url}/api/generate",
                        json=test_payload,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as test_response:
                        if test_response.status == 200:
                            log.info(f"Auto-detected available model: {test_model}")
                            return test_model
                except:
                    continue
                    
            # Final fallback: get any available model
            return await self._get_best_available_model()
                    
        except Exception as e:
            log.debug(f"Error detecting running model: {e}")
            return None

    async def _get_best_available_model(self) -> str | None:
        """Get the best available model from Ollama when none is running."""
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    result = await response.json()
                    models = result.get("models", [])
                    
                    if not models:
                        return None
                    
                    # Priority order for automatic selection
                    preferred_models = [
                        "qwen3:1.7b", "deepseek-r1:1.5b", "qwen3:4b", 
                        "gemma3:4b", "qwen3:0.6b", "gemma3:1b"
                    ]
                    
                    available_names = [model.get("name", "") for model in models]
                    
                    # Try to find preferred model
                    for preferred in preferred_models:
                        if preferred in available_names:
                            log.info(f"Auto-selected model: {preferred}")
                            return preferred
                    
                    # If no preferred model found, use the first available
                    first_model = available_names[0] if available_names else None
                    if first_model:
                        log.info(f"Using first available model: {first_model}")
                    return first_model
                    
        except Exception as e:
            log.debug(f"Error getting available models: {e}")
            return None
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,  # Auto-detect if not specified
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Optional[Dict]:
        """Send chat completion request to local AI (Ollama format)."""
        
        # Use CPU resource management if enabled
        if self.enable_cpu_management and self.resource_manager:
            # Start resource manager if not already running
            if self.resource_manager.processor_task is None:
                await self.resource_manager.start()
                
            # Submit request through resource manager
            return await self.resource_manager.submit_request(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
        
        # Direct execution (fallback when CPU management disabled)
        return await self._execute_direct_request(messages, model, temperature, max_tokens)
    
    async def _execute_direct_request(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Optional[Dict]:
        """Execute request directly without resource management."""
        start_time = time.time()
        
        try:
            if not self.session:
                await self.start_session()
            
            # Auto-detect model if not specified
            if model is None:
                model = await self.get_running_model()
                if model is None:
                    log.error("No model available in Ollama")
                    return None
            
            # Get adaptive timeout for this model
            model_timeout = self._get_model_timeout(model, max_tokens)
            log.debug(f"Using {model_timeout}s timeout for model {model}")
            
            # Convert messages to Ollama format
            prompt = self._convert_messages_to_prompt(messages)
            
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=model_timeout)
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    # Convert Ollama response to OpenAI format for compatibility
                    if "response" in result:
                        openai_format = {
                            "choices": [{
                                "message": {
                                    "content": result["response"],
                                    "role": "assistant"
                                },
                                "finish_reason": "stop"
                            }],
                            "usage": {
                                "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
                            }
                        }
                        
                        # Update stats
                        self.stats["requests_made"] += 1
                        response_time = time.time() - start_time
                        self.stats["avg_response_time"] = (
                            (self.stats["avg_response_time"] * (self.stats["requests_made"] - 1) + response_time)
                            / self.stats["requests_made"]
                        )
                        
                        # Track tokens if available
                        if "usage" in openai_format:
                            self.stats["total_tokens_processed"] += openai_format["usage"].get("total_tokens", 0)
                        
                        # Track model performance
                        self._update_model_performance(model, response_time, True)
                        
                        return openai_format
                    else:
                        return result
                else:
                    error_text = await response.text()
                    log.error(f"AI request failed with status {response.status}: {error_text}")
                    self.stats["requests_failed"] += 1
                    self._update_model_performance(model, time.time() - start_time, False)
                    return None
        
        except asyncio.TimeoutError:
            timeout_duration = time.time() - start_time
            log.warning(f"AI request timeout after {timeout_duration:.1f}s for model {model}")
            self.stats["requests_failed"] += 1
            self.stats["timeouts"] += 1
            self._update_model_performance(model, timeout_duration, False, is_timeout=True)
            return None
        except Exception as e:
            error_duration = time.time() - start_time
            log.error(f"Error in AI chat completion: {e}")
            self.stats["requests_failed"] += 1
            self._update_model_performance(model, error_duration, False)
            return None
    
    def _convert_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI-style messages to a single prompt for Ollama."""
        prompt_parts = []
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        # Add final prompt for assistant response
        prompt_parts.append("Assistant:")
        
        return "\n\n".join(prompt_parts)
    
    def _get_model_timeout(self, model: str, max_tokens: int) -> int:
        """Get adaptive timeout for a specific model."""
        # Base timeout from model configuration
        base_timeout = self.model_timeouts.get(model, self.model_timeouts["default"])
        
        # Adjust based on token count (more tokens = longer generation time)
        token_factor = max(1.0, max_tokens / 200)  # Scale based on token count
        
        # Check if we have performance history for this model
        if model in self.stats["model_performance"]:
            perf = self.stats["model_performance"][model]
            if perf["successful_requests"] > 0:
                # Use historical data to adjust timeout
                avg_time = perf["avg_response_time"]
                max_time = perf.get("max_response_time", avg_time)
                
                # Set timeout to 2x max observed time + buffer, but respect minimums
                historical_timeout = int(max_time * 2 + 15)
                base_timeout = max(base_timeout, historical_timeout)
        
        # Apply token factor and ensure reasonable bounds
        final_timeout = int(base_timeout * token_factor)
        final_timeout = max(15, min(final_timeout, 300))  # 15s min, 5min max
        
        return final_timeout
    
    def _update_model_performance(self, model: str, response_time: float, success: bool, is_timeout: bool = False):
        """Update performance tracking for a model."""
        if model not in self.stats["model_performance"]:
            self.stats["model_performance"][model] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "timeouts": 0,
                "avg_response_time": 0.0,
                "min_response_time": float('inf'),
                "max_response_time": 0.0,
                "total_response_time": 0.0
            }
        
        perf = self.stats["model_performance"][model]
        perf["total_requests"] += 1
        
        if success:
            perf["successful_requests"] += 1
            perf["total_response_time"] += response_time
            perf["avg_response_time"] = perf["total_response_time"] / perf["successful_requests"]
            perf["min_response_time"] = min(perf["min_response_time"], response_time)
            perf["max_response_time"] = max(perf["max_response_time"], response_time)
        else:
            perf["failed_requests"] += 1
            if is_timeout:
                perf["timeouts"] += 1

    def get_statistics(self) -> Dict:
        """Get client statistics."""
        stats = self.stats.copy()
        
        # Add resource manager stats if available
        if self.resource_manager:
            stats["resource_manager"] = {
                "queue_size": self.resource_manager.request_queue.get_queue_size(),
                "queue_stats": self.resource_manager.request_queue.stats.copy(),
                "priority_stats": self.resource_manager.request_queue.get_priority_stats(),
                "rate_limit_window": self.resource_manager.rate_limit_window,
                "max_requests_per_window": self.resource_manager.max_requests_per_window,
                "current_requests_in_window": len(self.resource_manager.request_timestamps),
                "cpu_management_enabled": True
            }
        else:
            stats["resource_manager"] = {
                "cpu_management_enabled": False
            }
        
        return stats


class MarketAnalysisAI:
    """AI-powered market analysis module."""
    
    def __init__(self, ai_client: LocalAIClient, model_name: str = None):
        self.ai_client = ai_client
        self.model_name = model_name  # None means auto-detect
    
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
            
            # Market analysis is high priority for trading decisions
            if hasattr(self.ai_client, 'resource_manager') and self.ai_client.resource_manager:
                response = await self.ai_client.resource_manager.submit_request(
                    messages=messages,
                    model=self.model_name,
                    temperature=0.3,
                    max_tokens=800,
                    priority=RequestPriority.HIGH
                )
            else:
                response = await self.ai_client.chat_completion(
                    messages=messages,
                    model=self.model_name,
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
            
            # Grid optimization is critical for performance
            if hasattr(self.ai_client, 'resource_manager') and self.ai_client.resource_manager:
                response = await self.ai_client.resource_manager.submit_request(
                    messages=messages,
                    model=self.model_name,
                    temperature=0.2,
                    max_tokens=600,
                    priority=RequestPriority.CRITICAL
                )
            else:
                response = await self.ai_client.chat_completion(
                    messages=messages,
                    model=self.model_name,
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
            
            # Sentiment analysis is normal priority
            if hasattr(self.ai_client, 'resource_manager') and self.ai_client.resource_manager:
                response = await self.ai_client.resource_manager.submit_request(
                    messages=messages,
                    model=self.model_name,
                    temperature=0.4,
                    max_tokens=700,
                    priority=RequestPriority.NORMAL
                )
            else:
                response = await self.ai_client.chat_completion(
                    messages=messages,
                    model=self.model_name,
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

    async def analyze_text_sentiment(self, text: str) -> Optional[Dict]:
        """Analyze sentiment of text using AI - can replace ONNX model."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are a sentiment analysis expert. Analyze the sentiment of the provided text and respond in JSON format with:
{
  "sentiment": "positive" | "negative" | "neutral",
  "confidence": float (0.0-1.0),
  "score": float (-1.0 to 1.0, where -1 is very negative, 0 is neutral, 1 is very positive),
  "reasoning": "brief explanation of the sentiment classification"
}

Focus specifically on financial/trading sentiment indicators."""
                },
                {
                    "role": "user",
                    "content": f"Analyze the sentiment of this text: {text[:500]}"  # Limit text size
                }
            ]
            
            # Text sentiment analysis is normal priority  
            if hasattr(self.ai_client, 'resource_manager') and self.ai_client.resource_manager:
                response = await self.ai_client.resource_manager.submit_request(
                    messages=messages,
                    model=self.model_name,
                    temperature=0.3,
                    max_tokens=200,
                    priority=RequestPriority.NORMAL
                )
            else:
                response = await self.ai_client.chat_completion(
                    messages=messages,
                    model=self.model_name,
                    temperature=0.3,
                    max_tokens=200
                )
            
            if response and "choices" in response:
                content = response["choices"][0]["message"]["content"]
                try:
                    sentiment_result = json.loads(content)
                    return sentiment_result
                except json.JSONDecodeError:
                    # Fallback parsing
                    return self._parse_sentiment_fallback(content)
            
            return None
        
        except Exception as e:
            log.error(f"Error in AI text sentiment analysis: {e}")
            return None
    
    def _parse_sentiment_fallback(self, text: str) -> Dict:
        """Fallback sentiment parsing when JSON fails."""
        text_lower = text.lower()
        
        if "positive" in text_lower:
            sentiment = "positive"
            score = 0.6
        elif "negative" in text_lower:
            sentiment = "negative"  
            score = -0.6
        else:
            sentiment = "neutral"
            score = 0.0
            
        return {
            "sentiment": sentiment,
            "confidence": 0.5,
            "score": score,
            "reasoning": "Fallback parsing"
        }
    
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
    
    def __init__(self, ai_client: LocalAIClient, model_name: str = None):
        self.ai_client = ai_client
        self.model_name = model_name  # None means auto-detect
    
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
            
            # Decision explanations are low priority (educational)
            if hasattr(self.ai_client, 'resource_manager') and self.ai_client.resource_manager:
                response = await self.ai_client.resource_manager.submit_request(
                    messages=messages,
                    model=self.model_name,
                    temperature=0.5,
                    max_tokens=400,
                    priority=RequestPriority.LOW
                )
            else:
                response = await self.ai_client.chat_completion(
                    messages=messages,
                    model=self.model_name,
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
            
            # Market reports are low priority (informational)
            if hasattr(self.ai_client, 'resource_manager') and self.ai_client.resource_manager:
                response = await self.ai_client.resource_manager.submit_request(
                    messages=messages,
                    model=self.model_name,
                    temperature=0.4,
                    max_tokens=800,
                    priority=RequestPriority.LOW
                )
            else:
                response = await self.ai_client.chat_completion(
                    messages=messages,
                    model=self.model_name,
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
    
    def __init__(self, config: dict, ai_base_url: str = "http://127.0.0.1:11434"):
        self.config = config
        self.ai_config = config.get("ai_agent", {})
        self.ai_base_url = ai_base_url
        self.model_name = None  # Auto-detect model dynamically
        
        # AI components  
        self.ai_client = LocalAIClient(ai_base_url)
        self.market_analysis = MarketAnalysisAI(self.ai_client, None)  # Auto-detect
        self.decision_support = DecisionSupportAI(self.ai_client, None)  # Auto-detect
        
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
    
    async def analyze_text_sentiment(self, text: str) -> Optional[Dict]:
        """Analyze sentiment of text using AI - replacement for ONNX model."""
        if not self.is_available:
            log.debug("AI not available, sentiment analysis not possible")
            return None
        
        try:
            async with self.ai_client:
                sentiment_result = await self.market_analysis.analyze_text_sentiment(text)
                
                if sentiment_result:
                    log.debug(f"AI sentiment analysis completed: {sentiment_result.get('sentiment', 'unknown')}")
                    return sentiment_result
                
        except Exception as e:
            log.error(f"Error in AI sentiment analysis: {e}")
        
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