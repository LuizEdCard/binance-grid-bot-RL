# AI Trading Integration - Specific integrations between AI Agent and trading components
import asyncio
import time
from typing import Dict, List, Optional, Any

from utils.logger import setup_logger

log = setup_logger("ai_trading_integration")


class SmartTradingDecisionEngine:
    """
    Mecanismo inteligente de decisão que combina:
    - Análise de IA baseada em dados de mercado em tempo real
    - Validação e ajuste dinâmico de ordens (DynamicOrderSizer)  
    - Substituição do RL inativo por decisões de IA
    """
    
    def __init__(self, ai_agent, api_client, config: dict):
        self.ai_agent = ai_agent
        self.api_client = api_client
        self.config = config
        
        # Import DynamicOrderSizer
        from core.capital_management import DynamicOrderSizer
        self.order_sizer = DynamicOrderSizer(api_client, config)
        
        # Cache para evitar análises desnecessárias
        self.analysis_cache = {}
        self.cache_expiry = 300  # 5 minutos
        
        # Histórico de decisões para aprendizado
        self.decision_history = []
        
        log.info("SmartTradingDecisionEngine initialized with AI + DynamicOrderSizer")
    
    async def get_smart_trading_action(self, symbol: str, market_data: dict, 
                                     current_grid_params: dict, available_balance: float) -> dict:
        """
        Obtém ação de trading inteligente baseada em análise de IA + validação dinâmica.
        
        Args:
            symbol: Par de trading
            market_data: Dados de mercado atual (preço, volume, indicadores)
            current_grid_params: Parâmetros atuais do grid
            available_balance: Saldo disponível para trading
            
        Returns:
            dict com ação, parâmetros ajustados e reasoning
        """
        try:
            # Verificar cache
            cache_key = f"{symbol}_{hash(str(market_data))}"
            if self._is_analysis_cached(cache_key):
                cached_result = self.analysis_cache[cache_key]
                log.debug(f"[{symbol}] Using cached AI analysis")
                return cached_result["result"]
            
            if not self.ai_agent.is_available:
                return self._fallback_decision(symbol, market_data, current_grid_params)
            
            # 1. Análise de mercado pela IA
            ai_analysis = await self._get_ai_market_analysis(symbol, market_data)
            
            # 2. IA sugere parâmetros de trading  
            suggested_params = await self._get_ai_trading_suggestions(symbol, ai_analysis, current_grid_params)
            
            # 3. DynamicOrderSizer valida e ajusta sugestões
            validated_params = self._validate_and_adjust_parameters(
                symbol, suggested_params, available_balance, market_data["current_price"]
            )
            
            # 4. Determinar ação final
            trading_action = self._determine_trading_action(ai_analysis, validated_params)
            
            # 5. Criar resultado estruturado
            result = {
                "action": trading_action["action"],  # 0-9 (compatível com RL)
                "confidence": ai_analysis.get("confidence", 0.5),
                "reasoning": ai_analysis.get("reasoning", "AI analysis"),
                "suggested_params": validated_params,
                "market_analysis": ai_analysis,
                "timestamp": time.time(),
                "source": "ai_smart_engine"
            }
            
            # Cache resultado
            self.analysis_cache[cache_key] = {
                "result": result,
                "timestamp": time.time()
            }
            
            # Armazenar no histórico
            self.decision_history.append(result)
            if len(self.decision_history) > 100:  # Manter apenas últimas 100 decisões
                self.decision_history.pop(0)
            
            log.info(f"[{symbol}] Smart trading action: {trading_action['action']} "
                    f"(confidence: {result['confidence']:.2f})")
            
            return result
            
        except Exception as e:
            log.error(f"Error in smart trading decision for {symbol}: {e}", exc_info=True)
            return self._fallback_decision(symbol, market_data, current_grid_params)
    
    async def _get_ai_market_analysis(self, symbol: str, market_data: dict) -> dict:
        """Solicita análise de mercado da IA."""
        try:
            # Preparar contexto rico para a IA
            analysis_prompt = f"""
            Analise os dados de mercado para {symbol} e forneça insights para trading:
            
            Dados atuais:
            - Preço: ${market_data.get('current_price', 0):.4f}
            - Volume 24h: ${market_data.get('volume_24h', 0):,.0f}
            - Mudança 24h: {market_data.get('price_change_24h', 0):.2f}%
            - RSI: {market_data.get('rsi', 50):.1f}
            - ATR: {market_data.get('atr_percentage', 0):.2f}%
            - ADX: {market_data.get('adx', 0):.1f}
            
            Responda em JSON com:
            {{
                "trend_direction": "bullish|bearish|neutral",
                "volatility_level": "low|medium|high", 
                "momentum": "strong|weak|neutral",
                "confidence": 0.0-1.0,
                "key_signals": ["sinal1", "sinal2"],
                "risk_level": "low|medium|high",
                "reasoning": "explicação detalhada"
            }}
            """
            
            # Chamar IA
            ai_response = await self.ai_agent.analyze_market_text(analysis_prompt)
            
            if ai_response and isinstance(ai_response, dict):
                return ai_response
            else:
                # Fallback: análise baseada em indicadores
                return self._technical_analysis_fallback(market_data)
                
        except Exception as e:
            log.error(f"Error getting AI market analysis: {e}")
            return self._technical_analysis_fallback(market_data)
    
    async def _get_ai_trading_suggestions(self, symbol: str, ai_analysis: dict, current_params: dict) -> dict:
        """IA sugere parâmetros específicos de trading."""
        try:
            suggestion_prompt = f"""
            Com base na análise de mercado para {symbol}, sugira parâmetros otimizados de grid trading:
            
            Análise atual:
            - Tendência: {ai_analysis.get('trend_direction', 'neutral')}
            - Volatilidade: {ai_analysis.get('volatility_level', 'medium')}
            - Momentum: {ai_analysis.get('momentum', 'neutral')}
            - Confiança: {ai_analysis.get('confidence', 0.5):.2f}
            
            Parâmetros atuais:
            - Níveis: {current_params.get('num_levels', 10)}
            - Espaçamento: {current_params.get('spacing_perc', 0.005)*100:.2f}%
            
            Responda em JSON com parâmetros otimizados:
            {{
                "grid_levels": 5-30,
                "spacing_percentage": 0.1-3.0,
                "position_bias": "long|short|neutral",
                "urgency": "low|medium|high",
                "risk_adjustment": 0.5-1.5,
                "reasoning": "justificativa das escolhas"
            }}
            """
            
            ai_suggestions = await self.ai_agent.analyze_market_text(suggestion_prompt)
            
            if ai_suggestions and isinstance(ai_suggestions, dict):
                return ai_suggestions
            else:
                return self._parameter_suggestion_fallback(ai_analysis, current_params)
                
        except Exception as e:
            log.error(f"Error getting AI trading suggestions: {e}")
            return self._parameter_suggestion_fallback(ai_analysis, current_params)
    
    def _validate_and_adjust_parameters(self, symbol: str, suggested_params: dict, 
                                      available_balance: float, current_price: float) -> dict:
        """Usa DynamicOrderSizer para validar e ajustar sugestões da IA."""
        try:
            # Extrair parâmetros sugeridos
            grid_levels = int(suggested_params.get("grid_levels", 10))
            spacing_pct = float(suggested_params.get("spacing_percentage", 1.0))
            
            # Determinar tipo de mercado baseado no saldo
            market_type = "futures" if available_balance > 50 else "spot"
            
            # Calcular alocação por nível
            allocation_per_level = available_balance / grid_levels
            
            # Validar com DynamicOrderSizer
            order_validation = self.order_sizer.get_optimized_order_size(
                symbol=symbol,
                market_type=market_type,
                available_balance=allocation_per_level,
                price=current_price,
                target_percentage=1.0  # Usar toda a alocação do nível
            )
            
            validated_params = {
                "grid_levels": grid_levels,
                "spacing_percentage": spacing_pct / 100,  # Converter para decimal
                "market_type": market_type,
                "order_size": order_validation["quantity"] if order_validation["is_valid"] else 0,
                "notional_per_level": order_validation["notional_value"] if order_validation["is_valid"] else 0,
                "is_valid": order_validation["is_valid"],
                "position_bias": suggested_params.get("position_bias", "neutral"),
                "risk_adjustment": suggested_params.get("risk_adjustment", 1.0)
            }
            
            if not order_validation["is_valid"]:
                log.warning(f"[{symbol}] AI suggestions failed validation: {order_validation.get('error')}")
                # Ajustar parâmetros para serem válidos
                validated_params = self._adjust_for_validation_failure(
                    validated_params, available_balance, current_price
                )
            
            return validated_params
            
        except Exception as e:
            log.error(f"Error validating parameters for {symbol}: {e}")
            return self._safe_parameter_fallback(available_balance)
    
    def _determine_trading_action(self, ai_analysis: dict, validated_params: dict) -> dict:
        """Converte análise de IA em ação numerica compatível com RL."""
        try:
            trend = ai_analysis.get("trend_direction", "neutral")
            volatility = ai_analysis.get("volatility_level", "medium")
            momentum = ai_analysis.get("momentum", "neutral")
            confidence = ai_analysis.get("confidence", 0.5)
            
            # Mapeamento de análise para ações (0-9 compatível com RL)
            action = 0  # Default: no change
            
            if not validated_params.get("is_valid", False):
                return {"action": 0, "reason": "invalid_parameters"}
            
            # Lógica de decisão baseada na análise
            if confidence > 0.7:
                if trend == "bullish" and momentum == "strong":
                    if volatility == "high":
                        action = 8  # Aggressive bullish setup
                    else:
                        action = 5  # Shift grid bullish
                elif trend == "bearish" and momentum == "strong":
                    if volatility == "high":
                        action = 9  # Aggressive bearish setup  
                    else:
                        action = 6  # Shift grid bearish
                elif volatility == "high":
                    action = 1  # Increase levels for high volatility
                elif volatility == "low":
                    action = 4  # Decrease spacing for low volatility
            elif confidence > 0.4:
                if trend == "bullish":
                    action = 5  # Shift bullish
                elif trend == "bearish":
                    action = 6  # Shift bearish
                else:
                    action = 7  # Reset to balanced
            
            return {
                "action": action,
                "reason": f"trend={trend}, volatility={volatility}, momentum={momentum}, confidence={confidence:.2f}"
            }
            
        except Exception as e:
            log.error(f"Error determining trading action: {e}")
            return {"action": 0, "reason": "error_in_decision"}
    
    def _is_analysis_cached(self, cache_key: str) -> bool:
        """Verifica se análise está em cache e ainda válida."""
        if cache_key not in self.analysis_cache:
            return False
        
        cached_data = self.analysis_cache[cache_key]
        age = time.time() - cached_data["timestamp"]
        return age < self.cache_expiry
    
    def _fallback_decision(self, symbol: str, market_data: dict, current_params: dict) -> dict:
        """Decisão de fallback quando IA não está disponível."""
        return {
            "action": 0,
            "confidence": 0.3,
            "reasoning": "AI not available, maintaining current parameters",
            "suggested_params": current_params,
            "market_analysis": {"trend_direction": "neutral"},
            "timestamp": time.time(),
            "source": "fallback"
        }
    
    def _technical_analysis_fallback(self, market_data: dict) -> dict:
        """Análise técnica simples quando IA falha."""
        rsi = market_data.get("rsi", 50)
        price_change = market_data.get("price_change_24h", 0)
        atr = market_data.get("atr_percentage", 0)
        
        # Lógica simples baseada em indicadores
        if rsi > 70:
            trend = "bearish"
        elif rsi < 30:
            trend = "bullish"
        else:
            trend = "neutral"
        
        volatility = "high" if atr > 3 else "low" if atr < 1 else "medium"
        momentum = "strong" if abs(price_change) > 5 else "weak" if abs(price_change) < 1 else "neutral"
        
        return {
            "trend_direction": trend,
            "volatility_level": volatility,
            "momentum": momentum,
            "confidence": 0.4,
            "reasoning": "Technical analysis fallback",
            "key_signals": [f"RSI={rsi:.1f}", f"24h_change={price_change:.2f}%"]
        }
    
    def _parameter_suggestion_fallback(self, ai_analysis: dict, current_params: dict) -> dict:
        """Sugestão de parâmetros de fallback."""
        volatility = ai_analysis.get("volatility_level", "medium")
        
        if volatility == "high":
            levels = min(current_params.get("num_levels", 10) + 2, 20)
            spacing = min(current_params.get("spacing_perc", 0.005) * 1.5, 0.03)
        elif volatility == "low":
            levels = max(current_params.get("num_levels", 10) - 1, 5)
            spacing = max(current_params.get("spacing_perc", 0.005) * 0.8, 0.001)
        else:
            levels = current_params.get("num_levels", 10)
            spacing = current_params.get("spacing_perc", 0.005)
        
        return {
            "grid_levels": levels,
            "spacing_percentage": spacing * 100,
            "position_bias": "neutral",
            "reasoning": f"Fallback based on {volatility} volatility"
        }
    
    def _adjust_for_validation_failure(self, params: dict, available_balance: float, price: float) -> dict:
        """Ajusta parâmetros quando validação falha."""
        # Reduzir níveis para aumentar capital por nível
        adjusted_levels = max(5, params["grid_levels"] // 2)
        
        params.update({
            "grid_levels": adjusted_levels,
            "spacing_percentage": max(0.005, params["spacing_percentage"]),
            "is_valid": True  # Assumir que ajuste resolve
        })
        
        return params
    
    def _safe_parameter_fallback(self, available_balance: float) -> dict:
        """Parâmetros seguros para quando tudo falha."""
        return {
            "grid_levels": 5,
            "spacing_percentage": 0.01,  # 1%
            "market_type": "futures" if available_balance > 50 else "spot",
            "order_size": 0,
            "is_valid": False,
            "position_bias": "neutral",
            "risk_adjustment": 1.0
        }
    
    def get_decision_statistics(self) -> dict:
        """Retorna estatísticas das decisões tomadas."""
        if not self.decision_history:
            return {"total_decisions": 0}
        
        actions = [d["action"] for d in self.decision_history]
        confidences = [d["confidence"] for d in self.decision_history]
        
        return {
            "total_decisions": len(self.decision_history),
            "avg_confidence": sum(confidences) / len(confidences),
            "action_distribution": {str(i): actions.count(i) for i in range(10)},
            "recent_decisions": self.decision_history[-5:] if len(self.decision_history) >= 5 else self.decision_history
        }

    async def get_batch_trading_actions(self, symbols_data: list) -> dict:
        """
        Processa múltiplos pares em lote para otimizar análise da IA.
        
        Args:
            symbols_data: Lista de dicts com {symbol, market_data, grid_params, balance}
            
        Returns:
            dict: {symbol: decision_result}
        """
        if not self.ai_agent.is_available:
            log.debug("AI not available, using fallback for all symbols")
            return {
                data["symbol"]: self._fallback_decision(
                    data["symbol"], data["market_data"], data["grid_params"]
                )
                for data in symbols_data
            }
        
        try:
            # Preparar análise em lote
            batch_results = {}
            
            # Processar em chunks para evitar sobrecarga
            chunk_size = min(3, len(symbols_data))  # Máximo 3 por vez
            
            for i in range(0, len(symbols_data), chunk_size):
                chunk = symbols_data[i:i + chunk_size]
                
                # Processar chunk concorrentemente
                tasks = []
                for data in chunk:
                    task = self.get_smart_trading_action(
                        data["symbol"], 
                        data["market_data"], 
                        data["grid_params"], 
                        data["balance"]
                    )
                    tasks.append(task)
                
                # Executar tarefas concorrentemente
                chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Processar resultados
                for j, result in enumerate(chunk_results):
                    symbol = chunk[j]["symbol"]
                    if isinstance(result, Exception):
                        log.warning(f"Error in batch analysis for {symbol}: {result}")
                        batch_results[symbol] = self._fallback_decision(
                            symbol, chunk[j]["market_data"], chunk[j]["grid_params"]
                        )
                    else:
                        batch_results[symbol] = result
                
                # Pausa entre chunks para não sobrecarregar
                if i + chunk_size < len(symbols_data):
                    await asyncio.sleep(0.5)
            
            log.info(f"Batch analysis completed for {len(symbols_data)} symbols")
            return batch_results
            
        except Exception as e:
            log.error(f"Error in batch trading actions: {e}")
            # Fallback para processamento individual
            return {
                data["symbol"]: self._fallback_decision(
                    data["symbol"], data["market_data"], data["grid_params"]
                )
                for data in symbols_data
            }

    async def get_market_overview_analysis(self, market_summary: dict) -> dict:
        """
        Análise de visão geral do mercado com dados agregados de todos os pares.
        Mais eficiente que analisar 471 pares individualmente.
        
        Args:
            market_summary: Dados agregados {
                'total_pairs': 471,
                'avg_volume': 1000000,
                'high_volume_pairs': ['BTC', 'ETH'],
                'market_trend': 'bullish/bearish/neutral',
                'volatility_distribution': {...}
            }
        """
        if not self.ai_agent.is_available:
            return {"trend": "neutral", "confidence": 0.3, "reasoning": "AI not available"}
        
        try:
            # Criar prompt otimizado para visão geral
            overview_prompt = f"""
            Analise o mercado crypto baseado nos dados agregados de {market_summary.get('total_pairs', 471)} pares USDT:
            
            Resumo do Mercado:
            - Total de pares: {market_summary.get('total_pairs', 471)}
            - Volume médio: ${market_summary.get('avg_volume', 0):,.0f}
            - Pares de alto volume: {market_summary.get('high_volume_pairs', [])}
            - Tendência predominante: {market_summary.get('market_trend', 'neutral')}
            - Volatilidade média: {market_summary.get('avg_volatility', 0):.2f}%
            
            Responda em JSON:
            {{
                "overall_trend": "bullish|bearish|neutral",
                "market_strength": 0.0-1.0,
                "recommended_strategy": "aggressive|conservative|balanced",
                "risk_level": "low|medium|high",
                "top_opportunities": ["pair1", "pair2", "pair3"],
                "confidence": 0.0-1.0,
                "reasoning": "análise detalhada"
            }}
            """
            
            # Chamar IA com dados agregados
            analysis = await self.ai_agent.analyze_market_text(overview_prompt)
            
            if analysis and isinstance(analysis, dict):
                log.info(f"Market overview analysis completed - Trend: {analysis.get('overall_trend', 'neutral')}")
                return analysis
            else:
                return self._market_overview_fallback(market_summary)
                
        except Exception as e:
            log.error(f"Error in market overview analysis: {e}")
            return self._market_overview_fallback(market_summary)

    def _market_overview_fallback(self, market_summary: dict) -> dict:
        """Fallback para análise de visão geral quando IA falha."""
        avg_volume = market_summary.get('avg_volume', 0)
        avg_volatility = market_summary.get('avg_volatility', 0)
        
        # Lógica simples baseada em métricas
        if avg_volume > 5000000 and avg_volatility > 3:
            trend = "bullish"
            strength = 0.7
            strategy = "aggressive"
        elif avg_volume < 1000000 or avg_volatility < 1:
            trend = "bearish"
            strength = 0.3
            strategy = "conservative"
        else:
            trend = "neutral"
            strength = 0.5
            strategy = "balanced"
        
        return {
            "overall_trend": trend,
            "market_strength": strength,
            "recommended_strategy": strategy,
            "risk_level": "medium",
            "top_opportunities": market_summary.get('high_volume_pairs', [])[:3],
            "confidence": 0.4,
            "reasoning": f"Fallback analysis based on volume ({avg_volume:,.0f}) and volatility ({avg_volatility:.2f}%)"
        }


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