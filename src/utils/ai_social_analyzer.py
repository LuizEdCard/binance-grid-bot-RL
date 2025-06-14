"""
AI-Powered Social Feed Analyzer
Usa IA local para análise avançada de feeds sociais e notícias
"""

import json
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)

@dataclass
class AIAnalysisResult:
    """Resultado da análise de IA."""
    symbols_detected: List[str]
    sentiment_score: float  # -1 to 1
    confidence: float  # 0 to 1
    market_signals: List[str]  # ['bullish', 'bearish', 'neutral', 'breakout', etc]
    risk_level: str  # 'low', 'medium', 'high'
    reasoning: str  # Explicação da análise
    key_phrases: List[str]
    recommended_action: str  # 'buy', 'sell', 'hold', 'watch'

class AISocialAnalyzer:
    """
    Analisador de feeds sociais powered by IA local.
    Usa modelos locais para análise avançada de sentiment, detecção de padrões e sinais de mercado.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.ai_config = config.get("ai_agent", {})
        self.social_config = config.get("social_feed_analysis", {})
        
        # Configurações da IA
        self.ai_base_url = self.ai_config.get("base_url", "http://127.0.0.1:11434")
        self.model_name = None  # Auto-detect
        self.analysis_cache = {}
        self.cache_expiry = 1800  # 30 minutos
        
        # Templates de prompts para diferentes tipos de análise
        self.analysis_prompts = {
            "sentiment_analysis": """
Analise o seguinte texto de trading/crypto e forneça:

TEXTO: {text}

Responda APENAS em JSON válido com esta estrutura:
{{
    "sentiment_score": <número de -1.0 a 1.0>,
    "confidence": <número de 0.0 a 1.0>,
    "symbols_mentioned": ["SYMBOL1", "SYMBOL2"],
    "market_signals": ["bullish", "bearish", "breakout", "consolidation"],
    "risk_level": "low|medium|high",
    "key_phrases": ["frase importante 1", "frase importante 2"],
    "reasoning": "explicação breve da análise"
}}
""",
            
            "influence_analysis": """
Analise este post de um influenciador de crypto e determine a qualidade e impacto potencial:

AUTOR: {author_type}
TEXTO: {text}
ENGAJAMENTO: {engagement}

Responda APENAS em JSON válido:
{{
    "influence_score": <número de 0.0 a 1.0>,
    "credibility": <número de 0.0 a 1.0>,
    "potential_impact": "low|medium|high",
    "symbols_focus": ["SYMBOL1"],
    "signal_strength": <número de 0.0 a 1.0>,
    "recommended_action": "buy|sell|hold|watch",
    "reasoning": "análise da qualidade e credibilidade"
}}
""",
            
            "news_analysis": """
Analise esta notícia de crypto e extraia informações relevantes para trading:

TÍTULO: {title}
CONTEÚDO: {content}
FONTE: {source}

Responda APENAS em JSON válido:
{{
    "impact_level": "low|medium|high",
    "time_sensitivity": "immediate|short_term|long_term",
    "affected_symbols": ["SYMBOL1", "SYMBOL2"],
    "market_direction": "bullish|bearish|neutral",
    "confidence": <número de 0.0 a 1.0>,
    "trading_signals": ["breakout", "dip_buy", "sell_pressure"],
    "key_information": ["info importante 1", "info importante 2"]
}}
""",
            
            "pattern_detection": """
Analise estes múltiplos posts/notícias sobre crypto e detecte padrões de mercado:

DADOS: {combined_data}

Identifique padrões, tendências e sinais emergentes. Responda em JSON:
{{
    "emerging_trends": ["trend1", "trend2"],
    "hot_symbols": ["SYMBOL1", "SYMBOL2"],
    "market_sentiment": "bullish|bearish|mixed|uncertain",
    "pattern_strength": <número de 0.0 a 1.0>,
    "timing_signals": ["now", "short_term", "wait"],
    "risk_assessment": "low|medium|high",
    "strategic_recommendations": ["recomendação 1", "recomendação 2"]
}}
"""
        }
        
        log.info("AISocialAnalyzer initialized with local AI integration")
    
    async def analyze_social_post(self, post_data: dict) -> Optional[AIAnalysisResult]:
        """Analisa um post de feed social usando IA."""
        try:
            text = post_data.get("content", "")
            author_type = post_data.get("author_type", "UNKNOWN")
            engagement = post_data.get("engagement", {})
            
            # Cache key
            cache_key = f"post_{hash(text)}"
            cached_result = self._get_cached_analysis(cache_key)
            if cached_result:
                return cached_result
            
            # Análise de sentiment
            sentiment_result = await self._analyze_with_ai("sentiment_analysis", {"text": text})
            
            # Análise de influência
            influence_result = await self._analyze_with_ai("influence_analysis", {
                "text": text,
                "author_type": author_type,
                "engagement": str(engagement)
            })
            
            if not sentiment_result or not influence_result:
                return None
            
            # Combinar resultados
            combined_result = self._combine_analysis_results(sentiment_result, influence_result)
            
            # Cache resultado
            self._cache_analysis(cache_key, combined_result)
            
            return combined_result
            
        except Exception as e:
            log.error(f"Error analyzing social post: {e}")
            return None
    
    async def analyze_news_article(self, article_data: dict) -> Optional[AIAnalysisResult]:
        """Analisa um artigo de notícia usando IA."""
        try:
            title = article_data.get("title", "")
            content = article_data.get("content", "")
            source = article_data.get("source", "")
            
            cache_key = f"news_{hash(title + content)}"
            cached_result = self._get_cached_analysis(cache_key)
            if cached_result:
                return cached_result
            
            # Análise de notícia
            news_result = await self._analyze_with_ai("news_analysis", {
                "title": title,
                "content": content,
                "source": source
            })
            
            if not news_result:
                return None
            
            # Converter para AIAnalysisResult
            result = self._convert_news_analysis_to_result(news_result)
            
            # Cache resultado
            self._cache_analysis(cache_key, result)
            
            return result
            
        except Exception as e:
            log.error(f"Error analyzing news article: {e}")
            return None
    
    async def detect_market_patterns(self, multiple_data: List[dict]) -> Optional[dict]:
        """Detecta padrões de mercado analisando múltiplos posts/notícias."""
        try:
            if not multiple_data:
                return None
            
            # Preparar dados combinados
            combined_texts = []
            for item in multiple_data:
                text = item.get("content", "") or item.get("title", "")
                source = item.get("source", "post")
                combined_texts.append(f"[{source.upper()}] {text}")
            
            combined_data = " | ".join(combined_texts[:10])  # Limitar para não sobrecarregar
            
            # Análise de padrões
            pattern_result = await self._analyze_with_ai("pattern_detection", {
                "combined_data": combined_data
            })
            
            return pattern_result
            
        except Exception as e:
            log.error(f"Error detecting market patterns: {e}")
            return None
    
    async def _analyze_with_ai(self, analysis_type: str, data: dict) -> Optional[dict]:
        """Executa análise com IA local."""
        try:
            # Verificar se IA está disponível
            if not await self._check_ai_availability():
                log.warning("Local AI not available, skipping AI analysis")
                return None
            
            # Construir prompt
            prompt_template = self.analysis_prompts.get(analysis_type)
            if not prompt_template:
                log.error(f"Unknown analysis type: {analysis_type}")
                return None
            
            prompt = prompt_template.format(**data)
            
            # Chamar IA local
            response = await self._call_local_ai(prompt)
            
            if not response:
                return None
            
            # Tentar parsear JSON
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError as e:
                log.error(f"Failed to parse AI response as JSON: {e}")
                log.debug(f"AI Response: {response}")
                return None
                
        except Exception as e:
            log.error(f"Error in AI analysis: {e}")
            return None
    
    async def _call_local_ai(self, prompt: str) -> Optional[str]:
        """Chama a IA local com o prompt."""
        try:
            import aiohttp
            
            # Detectar modelo ativo
            if not self.model_name:
                self.model_name = await self._detect_active_model()
            
            if not self.model_name:
                log.warning("No active AI model detected")
                return None
            
            # Preparar request
            data = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_k": 40,
                    "top_p": 0.9,
                    "num_predict": 1000
                }
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{self.ai_base_url}/api/generate", json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("response", "").strip()
                    else:
                        log.error(f"AI API error: {response.status}")
                        return None
                        
        except Exception as e:
            log.error(f"Error calling local AI: {e}")
            return None
    
    async def _detect_active_model(self) -> Optional[str]:
        """Detecta modelo ativo no Ollama."""
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Listar modelos disponíveis
                async with session.get(f"{self.ai_base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        
                        if models:
                            # Preferir modelos menores para análise rápida
                            preferred_models = ["gemma3:1b", "qwen2.5-coder:3b", "deepcoder:1.5b"]
                            
                            for preferred in preferred_models:
                                for model in models:
                                    if model.get("name", "").startswith(preferred):
                                        log.info(f"Selected AI model for social analysis: {model['name']}")
                                        return model["name"]
                            
                            # Se não encontrar preferido, usar o primeiro disponível
                            first_model = models[0]["name"]
                            log.info(f"Using first available AI model: {first_model}")
                            return first_model
            
            return None
            
        except Exception as e:
            log.debug(f"Error detecting AI model: {e}")
            return None
    
    async def _check_ai_availability(self) -> bool:
        """Verifica se a IA local está disponível."""
        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=5)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.ai_base_url}/api/tags") as response:
                    return response.status == 200
                    
        except Exception:
            return False
    
    def _combine_analysis_results(self, sentiment_result: dict, influence_result: dict) -> AIAnalysisResult:
        """Combina resultados de análise de sentiment e influência."""
        try:
            # Extrair símbolos de ambas análises
            symbols = list(set(
                sentiment_result.get("symbols_mentioned", []) + 
                influence_result.get("symbols_focus", [])
            ))
            
            # Calcular scores combinados
            sentiment_score = sentiment_result.get("sentiment_score", 0.0)
            influence_score = influence_result.get("influence_score", 0.5)
            
            # Confiança é a média ponderada
            confidence = (
                sentiment_result.get("confidence", 0.5) * 0.6 +
                influence_result.get("credibility", 0.5) * 0.4
            )
            
            # Combinar sinais de mercado
            market_signals = sentiment_result.get("market_signals", [])
            
            # Determinar ação recomendada
            recommended_action = influence_result.get("recommended_action", "hold")
            
            # Combinar raciocínio
            reasoning = f"Sentiment: {sentiment_result.get('reasoning', '')} | Influence: {influence_result.get('reasoning', '')}"
            
            return AIAnalysisResult(
                symbols_detected=symbols,
                sentiment_score=sentiment_score,
                confidence=confidence,
                market_signals=market_signals,
                risk_level=sentiment_result.get("risk_level", "medium"),
                reasoning=reasoning[:300],  # Limitar tamanho
                key_phrases=sentiment_result.get("key_phrases", []),
                recommended_action=recommended_action
            )
            
        except Exception as e:
            log.error(f"Error combining analysis results: {e}")
            # Retornar resultado básico em caso de erro
            return AIAnalysisResult(
                symbols_detected=[],
                sentiment_score=0.0,
                confidence=0.1,
                market_signals=[],
                risk_level="high",
                reasoning="Error in analysis combination",
                key_phrases=[],
                recommended_action="hold"
            )
    
    def _convert_news_analysis_to_result(self, news_result: dict) -> AIAnalysisResult:
        """Converte resultado de análise de notícia para AIAnalysisResult."""
        return AIAnalysisResult(
            symbols_detected=news_result.get("affected_symbols", []),
            sentiment_score=1.0 if news_result.get("market_direction") == "bullish" else -1.0 if news_result.get("market_direction") == "bearish" else 0.0,
            confidence=news_result.get("confidence", 0.5),
            market_signals=news_result.get("trading_signals", []),
            risk_level="high" if news_result.get("impact_level") == "high" else "medium" if news_result.get("impact_level") == "medium" else "low",
            reasoning=f"News impact: {news_result.get('impact_level', 'unknown')} | {' | '.join(news_result.get('key_information', []))}",
            key_phrases=news_result.get("key_information", []),
            recommended_action="watch"  # Notícias geralmente requerem observação
        )
    
    def _get_cached_analysis(self, cache_key: str) -> Optional[AIAnalysisResult]:
        """Obtém análise do cache se ainda válida."""
        if cache_key in self.analysis_cache:
            cached_data, timestamp = self.analysis_cache[cache_key]
            if (datetime.now().timestamp() - timestamp) < self.cache_expiry:
                return cached_data
        return None
    
    def _cache_analysis(self, cache_key: str, result: AIAnalysisResult):
        """Armazena análise no cache."""
        self.analysis_cache[cache_key] = (result, datetime.now().timestamp())
        
        # Limitar tamanho do cache
        if len(self.analysis_cache) > 100:
            # Remover entradas mais antigas
            oldest_keys = sorted(
                self.analysis_cache.keys(),
                key=lambda k: self.analysis_cache[k][1]
            )[:20]
            
            for key in oldest_keys:
                del self.analysis_cache[key]
    
    def get_statistics(self) -> dict:
        """Retorna estatísticas do analisador de IA."""
        return {
            "ai_base_url": self.ai_base_url,
            "active_model": self.model_name,
            "cached_analyses": len(self.analysis_cache),
            "cache_expiry_minutes": self.cache_expiry / 60,
            "available_analysis_types": list(self.analysis_prompts.keys())
        }

# Função helper para uso fácil
async def analyze_social_data_with_ai(config: dict, social_data: List[dict]) -> List[dict]:
    """
    Função helper para análise de dados sociais com IA.
    
    Args:
        config: Configuração do sistema
        social_data: Lista de posts/notícias para analisar
        
    Returns:
        Lista de resultados de análise
    """
    analyzer = AISocialAnalyzer(config)
    results = []
    
    for item in social_data:
        if item.get("type") == "news":
            result = await analyzer.analyze_news_article(item)
        else:
            result = await analyzer.analyze_social_post(item)
        
        if result:
            results.append({
                "original_data": item,
                "ai_analysis": result.__dict__
            })
    
    # Análise de padrões se temos múltiplos itens
    if len(social_data) > 3:
        pattern_analysis = await analyzer.detect_market_patterns(social_data)
        if pattern_analysis:
            results.append({
                "type": "pattern_analysis",
                "analysis": pattern_analysis
            })
    
    return results