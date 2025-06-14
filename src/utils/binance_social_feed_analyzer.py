"""
Binance Social Feed and News Analyzer
Analisa feeds de influenciadores e notícias da Binance para extrair símbolos em tendência
"""

import aiohttp
import asyncio
import re
import json
import time
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

log = logging.getLogger(__name__)

@dataclass
class TrendingSymbol:
    """Representa um símbolo em tendência detectado."""
    symbol: str
    source: str  # 'influencer', 'news', 'announcement'
    mentions: int
    sentiment_score: float  # -1 to 1
    confidence: float  # 0 to 1
    timestamp: datetime
    context: str  # Contexto onde foi mencionado
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "source": self.source,
            "mentions": self.mentions,
            "sentiment_score": self.sentiment_score,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context[:200]  # Limitar contexto
        }

class BinanceSocialFeedAnalyzer:
    """
    Analisa feeds sociais e notícias da Binance para identificar símbolos em tendência.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.social_config = config.get("social_feed_analysis", {})
        
        # URLs da API da Binance para feeds sociais e notícias
        self.binance_api_base = "https://www.binance.com/bapi"
        self.news_api_url = f"{self.binance_api_base}/composite/v1/public/cms/article/list/query"
        self.feed_api_url = f"{self.binance_api_base}/composite/v1/public/square/timeline"
        
        # Configurações
        self.max_news_hours = self.social_config.get("max_news_hours", 24)
        self.max_feed_items = self.social_config.get("max_feed_items", 50)
        self.min_mentions_threshold = self.social_config.get("min_mentions_threshold", 2)
        self.symbol_confidence_threshold = self.social_config.get("symbol_confidence_threshold", 0.3)
        
        # Cache
        self.trending_symbols_cache = {}
        self.cache_expiry = 3600  # 1 hora
        self.last_update = 0
        
        # Padrões para detecção de símbolos
        self.symbol_patterns = [
            r'\b([A-Z]{2,10}USDT?)\b',  # BTCUSDT, BTC
            r'\$([A-Z]{2,10})\b',       # $BTC, $ETH
            r'#([A-Z]{2,10})\b',        # #BTC, #ETH
        ]
        
        # Palavras-chave para contexto positivo/negativo
        self.positive_keywords = {
            'bullish', 'pump', 'moon', 'buy', 'long', 'breakout', 'surge', 
            'rally', 'up', 'gains', 'profit', 'bull', 'green', 'rise'
        }
        
        self.negative_keywords = {
            'bearish', 'dump', 'crash', 'sell', 'short', 'breakdown', 'drop',
            'fall', 'loss', 'bear', 'red', 'decline', 'dip'
        }
        
        # Session para requests HTTP
        self.session = None
        
        log.info("BinanceSocialFeedAnalyzer initialized")
    
    async def __aenter__(self):
        """Context manager para sessão HTTP."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Fechar sessão HTTP."""
        if self.session:
            await self.session.close()
    
    async def get_trending_symbols(self, force_refresh: bool = False) -> List[TrendingSymbol]:
        """
        Obtém símbolos em tendência de todas as fontes.
        
        Args:
            force_refresh: Forçar refresh do cache
            
        Returns:
            Lista de símbolos em tendência ordenados por relevância
        """
        current_time = time.time()
        
        # Verificar cache
        if not force_refresh and (current_time - self.last_update) < self.cache_expiry:
            if self.trending_symbols_cache:
                log.debug("Returning cached trending symbols")
                return list(self.trending_symbols_cache.values())
        
        log.info("Fetching trending symbols from multiple sources...")
        
        try:
            # Buscar dados de múltiplas fontes
            news_symbols = await self._analyze_binance_news()
            feed_symbols = await self._analyze_binance_feed()
            
            # Combinar e rankear símbolos
            all_symbols = news_symbols + feed_symbols
            ranked_symbols = self._rank_and_filter_symbols(all_symbols)
            
            # Usar IA para análise avançada se habilitada
            if self.social_config.get("use_ai_analysis", True) and ranked_symbols:
                try:
                    from utils.ai_social_analyzer import AISocialAnalyzer
                    
                    ai_analyzer = AISocialAnalyzer(self.config)
                    enhanced_symbols = await self._enhance_with_ai_analysis(ai_analyzer, ranked_symbols, all_symbols)
                    ranked_symbols = enhanced_symbols
                    
                    log.info(f"AI analysis enhanced {len(ranked_symbols)} symbols")
                    
                except Exception as e:
                    log.warning(f"AI analysis failed, using basic analysis: {e}")
            
            # Atualizar cache
            self.trending_symbols_cache = {s.symbol: s for s in ranked_symbols}
            self.last_update = current_time
            
            log.info(f"Found {len(ranked_symbols)} trending symbols from {len(all_symbols)} total mentions")
            
            return ranked_symbols
            
        except Exception as e:
            log.error(f"Error fetching trending symbols: {e}")
            return list(self.trending_symbols_cache.values())
    
    async def _analyze_binance_news(self) -> List[TrendingSymbol]:
        """Analisa notícias da Binance para extrair símbolos mencionados."""
        symbols = []
        
        try:
            # Parâmetros para buscar notícias recentes
            params = {
                "type": 1,  # Notícias
                "pageNo": 1,
                "pageSize": 20,
                "catalogId": 48,  # Categoria geral de crypto
            }
            
            async with self.session.get(self.news_api_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get("data", {}).get("articles", [])
                    
                    for article in articles:
                        symbols.extend(self._extract_symbols_from_news_article(article))
                        
        except Exception as e:
            log.warning(f"Error analyzing Binance news: {e}")
        
        return symbols
    
    async def _analyze_binance_feed(self) -> List[TrendingSymbol]:
        """Analisa feed social da Binance Square para extrair símbolos mencionados."""
        symbols = []
        
        try:
            # Parâmetros para buscar posts recentes do feed
            params = {
                "size": self.max_feed_items,
                "listType": "TRENDING"  # Posts em tendência
            }
            
            async with self.session.get(self.feed_api_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    posts = data.get("data", {}).get("list", [])
                    
                    for post in posts:
                        symbols.extend(self._extract_symbols_from_feed_post(post))
                        
        except Exception as e:
            log.warning(f"Error analyzing Binance feed: {e}")
        
        return symbols
    
    def _extract_symbols_from_news_article(self, article: dict) -> List[TrendingSymbol]:
        """Extrai símbolos de um artigo de notícia."""
        symbols = []
        
        try:
            title = article.get("title", "")
            summary = article.get("summary", "")
            content = f"{title} {summary}"
            
            # Extrair símbolos usando padrões regex
            detected_symbols = self._extract_symbols_from_text(content)
            
            for symbol in detected_symbols:
                # Calcular sentiment baseado no contexto
                sentiment = self._calculate_sentiment(content)
                confidence = 0.8  # Alta confiança para notícias oficiais
                
                symbols.append(TrendingSymbol(
                    symbol=symbol,
                    source="news",
                    mentions=1,
                    sentiment_score=sentiment,
                    confidence=confidence,
                    timestamp=datetime.now(),
                    context=content[:200]
                ))
                
        except Exception as e:
            log.debug(f"Error extracting symbols from news article: {e}")
        
        return symbols
    
    def _extract_symbols_from_feed_post(self, post: dict) -> List[TrendingSymbol]:
        """Extrai símbolos de um post do feed social."""
        symbols = []
        
        try:
            content = post.get("summary", "")
            author_type = post.get("authorType", "")
            
            # Dar mais peso para posts de influenciadores verificados
            is_influencer = author_type in ["KOL", "VERIFIED", "OFFICIAL"]
            
            # Extrair símbolos
            detected_symbols = self._extract_symbols_from_text(content)
            
            for symbol in detected_symbols:
                sentiment = self._calculate_sentiment(content)
                confidence = 0.9 if is_influencer else 0.6
                
                symbols.append(TrendingSymbol(
                    symbol=symbol,
                    source="influencer" if is_influencer else "community",
                    mentions=1,
                    sentiment_score=sentiment,
                    confidence=confidence,
                    timestamp=datetime.now(),
                    context=content[:200]
                ))
                
        except Exception as e:
            log.debug(f"Error extracting symbols from feed post: {e}")
        
        return symbols
    
    def _extract_symbols_from_text(self, text: str) -> Set[str]:
        """Extrai símbolos de trading de um texto usando regex."""
        symbols = set()
        
        for pattern in self.symbol_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Normalizar símbolo
                symbol = match.upper()
                
                # Adicionar USDT se não tiver
                if not symbol.endswith('USDT'):
                    symbol += 'USDT'
                
                # Filtrar símbolos muito curtos ou muito longos
                base_symbol = symbol.replace('USDT', '')
                if 2 <= len(base_symbol) <= 6:
                    symbols.add(symbol)
        
        return symbols
    
    def _calculate_sentiment(self, text: str) -> float:
        """Calcula sentiment score de -1 (negativo) a 1 (positivo)."""
        text_lower = text.lower()
        
        positive_count = sum(1 for word in self.positive_keywords if word in text_lower)
        negative_count = sum(1 for word in self.negative_keywords if word in text_lower)
        
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words == 0:
            return 0.0  # Neutro
        
        sentiment_score = (positive_count - negative_count) / total_sentiment_words
        return max(-1.0, min(1.0, sentiment_score))
    
    def _rank_and_filter_symbols(self, symbols: List[TrendingSymbol]) -> List[TrendingSymbol]:
        """Rankeia e filtra símbolos por relevância."""
        if not symbols:
            return []
        
        # Agrupar por símbolo para combinar mentions
        symbol_groups = {}
        
        for symbol_obj in symbols:
            symbol = symbol_obj.symbol
            
            if symbol not in symbol_groups:
                symbol_groups[symbol] = {
                    'mentions': 0,
                    'total_sentiment': 0.0,
                    'total_confidence': 0.0,
                    'sources': set(),
                    'contexts': [],
                    'latest_timestamp': symbol_obj.timestamp
                }
            
            group = symbol_groups[symbol]
            group['mentions'] += 1
            group['total_sentiment'] += symbol_obj.sentiment_score
            group['total_confidence'] += symbol_obj.confidence
            group['sources'].add(symbol_obj.source)
            group['contexts'].append(symbol_obj.context)
            
            if symbol_obj.timestamp > group['latest_timestamp']:
                group['latest_timestamp'] = symbol_obj.timestamp
        
        # Criar símbolos rankeados
        ranked_symbols = []
        
        for symbol, group in symbol_groups.items():
            mentions = group['mentions']
            
            # Filtrar símbolos com poucas menções
            if mentions < self.min_mentions_threshold:
                continue
            
            avg_sentiment = group['total_sentiment'] / mentions
            avg_confidence = group['total_confidence'] / mentions
            
            # Filtrar por confiança
            if avg_confidence < self.symbol_confidence_threshold:
                continue
            
            # Calcular score final
            diversity_bonus = len(group['sources']) * 0.1  # Bonus por múltiplas fontes
            recency_bonus = self._calculate_recency_bonus(group['latest_timestamp'])
            
            final_score = (mentions * 0.4) + (avg_sentiment * 0.3) + (avg_confidence * 0.2) + diversity_bonus + recency_bonus
            
            ranked_symbols.append(TrendingSymbol(
                symbol=symbol,
                source=f"combined({','.join(group['sources'])})",
                mentions=mentions,
                sentiment_score=avg_sentiment,
                confidence=avg_confidence,
                timestamp=group['latest_timestamp'],
                context=f"Score: {final_score:.2f} | " + " | ".join(group['contexts'][:2])
            ))
        
        # Ordenar por relevância (score implícito nos cálculos acima)
        ranked_symbols.sort(key=lambda x: (x.mentions, x.confidence, x.sentiment_score), reverse=True)
        
        return ranked_symbols[:10]  # Top 10 símbolos
    
    async def _enhance_with_ai_analysis(self, ai_analyzer, ranked_symbols: List[TrendingSymbol], all_symbols: List[TrendingSymbol]) -> List[TrendingSymbol]:
        """
        Usa IA para melhorar a análise dos símbolos trending.
        
        Args:
            ai_analyzer: Instância do analisador de IA
            ranked_symbols: Símbolos já rankeados pela análise básica
            all_symbols: Todos os símbolos detectados
            
        Returns:
            Lista de símbolos com análise de IA aprimorada
        """
        try:
            enhanced_symbols = []
            
            # Preparar dados para análise de IA
            social_data = []
            for symbol in all_symbols:
                social_data.append({
                    "content": symbol.context,
                    "source": symbol.source,
                    "author_type": "INFLUENCER" if "influencer" in symbol.source else "NEWS" if "news" in symbol.source else "COMMUNITY",
                    "symbol": symbol.symbol,
                    "mentions": symbol.mentions,
                    "type": "news" if "news" in symbol.source else "post"
                })
            
            # Análise de IA para cada símbolo top
            for symbol in ranked_symbols[:15]:  # Analisar top 15 com IA
                try:
                    # Filtrar dados relevantes para este símbolo
                    symbol_data = [item for item in social_data if item["symbol"] == symbol.symbol]
                    
                    if not symbol_data:
                        enhanced_symbols.append(symbol)
                        continue
                    
                    # Análise de IA
                    ai_result = None
                    if symbol_data[0]["type"] == "news":
                        ai_result = await ai_analyzer.analyze_news_article(symbol_data[0])
                    else:
                        ai_result = await ai_analyzer.analyze_social_post(symbol_data[0])
                    
                    if ai_result:
                        # Ajustar scores baseado na análise de IA
                        ai_confidence = ai_result.confidence
                        ai_sentiment = ai_result.sentiment_score
                        ai_risk = ai_result.risk_level
                        
                        # Recalcular confidence baseado na IA
                        new_confidence = (symbol.confidence * 0.7) + (ai_confidence * 0.3)
                        
                        # Ajustar sentiment
                        new_sentiment = (symbol.sentiment_score * 0.6) + (ai_sentiment * 0.4)
                        
                        # Penalizar símbolos de alto risco
                        risk_penalty = 0.8 if ai_risk == "high" else 1.0 if ai_risk == "medium" else 1.1
                        new_confidence *= risk_penalty
                        
                        # Criar símbolo aprimorado
                        enhanced_symbol = TrendingSymbol(
                            symbol=symbol.symbol,
                            source=f"{symbol.source}+AI",
                            mentions=symbol.mentions,
                            sentiment_score=new_sentiment,
                            confidence=min(1.0, new_confidence),  # Cap em 1.0
                            timestamp=symbol.timestamp,
                            context=f"AI: {ai_result.reasoning[:100]}... | Original: {symbol.context[:100]}..."
                        )
                        
                        enhanced_symbols.append(enhanced_symbol)
                        
                        log.debug(f"AI enhanced {symbol.symbol}: confidence {symbol.confidence:.2f} -> {new_confidence:.2f}, sentiment {symbol.sentiment_score:.2f} -> {new_sentiment:.2f}")
                    
                    else:
                        # Se IA falhou, manter símbolo original
                        enhanced_symbols.append(symbol)
                        
                except Exception as e:
                    log.debug(f"AI analysis failed for {symbol.symbol}: {e}")
                    enhanced_symbols.append(symbol)
            
            # Análise de padrões para detectar tendências emergentes
            if len(social_data) > 5:
                try:
                    pattern_analysis = await ai_analyzer.detect_market_patterns(social_data[:20])
                    
                    if pattern_analysis:
                        hot_symbols = pattern_analysis.get("hot_symbols", [])
                        pattern_strength = pattern_analysis.get("pattern_strength", 0.0)
                        
                        log.info(f"AI detected market patterns: {pattern_analysis.get('emerging_trends', [])} | Hot symbols: {hot_symbols}")
                        
                        # Dar bonus para símbolos detectados como "hot" pela IA
                        for enhanced_symbol in enhanced_symbols:
                            if enhanced_symbol.symbol in hot_symbols and pattern_strength > 0.7:
                                enhanced_symbol.confidence = min(1.0, enhanced_symbol.confidence * 1.2)
                                enhanced_symbol.context = f"🔥AI_HOT: {enhanced_symbol.context}"
                                log.info(f"🔥 AI marked {enhanced_symbol.symbol} as HOT symbol")
                
                except Exception as e:
                    log.debug(f"Pattern analysis failed: {e}")
            
            # Re-ordenar por confidence atualizada
            enhanced_symbols.sort(key=lambda x: (x.confidence, x.mentions, x.sentiment_score), reverse=True)
            
            return enhanced_symbols[:10]  # Top 10 após análise de IA
            
        except Exception as e:
            log.error(f"Error in AI enhancement: {e}")
            return ranked_symbols  # Fallback para análise básica
    
    def _calculate_recency_bonus(self, timestamp: datetime) -> float:
        """Calcula bonus baseado na recência da menção."""
        hours_ago = (datetime.now() - timestamp).total_seconds() / 3600
        
        if hours_ago < 1:
            return 0.3  # Muito recente
        elif hours_ago < 6:
            return 0.2  # Recente
        elif hours_ago < 24:
            return 0.1  # Moderadamente recente
        else:
            return 0.0  # Antigo
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do analisador."""
        return {
            "cached_symbols": len(self.trending_symbols_cache),
            "cache_age_minutes": (time.time() - self.last_update) / 60,
            "last_update": datetime.fromtimestamp(self.last_update).isoformat() if self.last_update else None,
            "config": {
                "max_news_hours": self.max_news_hours,
                "max_feed_items": self.max_feed_items,
                "min_mentions_threshold": self.min_mentions_threshold,
                "symbol_confidence_threshold": self.symbol_confidence_threshold
            }
        }

# Função helper para uso direto
async def get_binance_trending_symbols(config: dict, force_refresh: bool = False) -> List[dict]:
    """
    Função helper para obter símbolos em tendência.
    
    Returns:
        Lista de dicionários com símbolos em tendência
    """
    async with BinanceSocialFeedAnalyzer(config) as analyzer:
        trending_symbols = await analyzer.get_trending_symbols(force_refresh)
        return [symbol.to_dict() for symbol in trending_symbols]

if __name__ == "__main__":
    # Teste básico
    import yaml
    
    config = {
        "social_feed_analysis": {
            "max_news_hours": 24,
            "max_feed_items": 50,
            "min_mentions_threshold": 2,
            "symbol_confidence_threshold": 0.3
        }
    }
    
    async def test():
        async with BinanceSocialFeedAnalyzer(config) as analyzer:
            symbols = await analyzer.get_trending_symbols()
            
            print("📈 SÍMBOLOS EM TENDÊNCIA:")
            for symbol in symbols:
                print(f"  {symbol.symbol} - {symbol.mentions} menções - Sentiment: {symbol.sentiment_score:.2f} - Fonte: {symbol.source}")
    
    asyncio.run(test())