"""
Binance News Listener - Integração com API de notícias e anúncios da Binance
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from .logger import log


class NewsType(Enum):
    """Tipos de notícias da Binance."""
    ANNOUNCEMENT = "announcement"
    NEWS = "news" 
    LATEST = "latest"
    NEW_CRYPTO = "new_crypto"
    ACTIVITIES = "activities"
    PRODUCT = "product"


@dataclass
class BinanceNewsItem:
    """Representa um item de notícia da Binance."""
    id: str
    title: str
    body: str
    type: str
    published_time: datetime
    tags: List[str]
    url: str
    relevance_score: float = 0.0
    sentiment_score: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body[:500] + "..." if len(self.body) > 500 else self.body,
            "type": self.type,
            "published_time": self.published_time.isoformat(),
            "tags": self.tags,
            "url": self.url,
            "relevance_score": self.relevance_score,
            "sentiment_score": self.sentiment_score
        }


class BinanceNewsListener:
    """
    Coleta notícias, anúncios e feeds da Binance para análise de sentimentos.
    
    Endpoints utilizados:
    - Notícias gerais: https://www.binance.com/bapi/composite/v1/public/cms/article/list/query
    - Anúncios: https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1
    - API Announcements: https://api.binance.com/api/v3/news
    """
    
    def __init__(self, session: aiohttp.ClientSession = None):
        self.session = session
        self.should_close_session = False
        if not session:
            self.session = None
            self.should_close_session = True
            
        # URLs base da Binance
        self.base_url = "https://www.binance.com"
        self.api_url = "https://api.binance.com"
        
        # Cache para evitar notícias duplicadas
        self.processed_news_ids = set()
        self.last_fetch_time = None
        
        # Configurações
        self.max_news_per_fetch = 20
        self.fetch_interval_minutes = 30
        
        # Palavras-chave para filtrar notícias relevantes
        self.crypto_keywords = [
            "bitcoin", "btc", "ethereum", "eth", "binance", "crypto", "cryptocurrency",
            "trading", "market", "price", "bull", "bear", "pump", "dump", "moon",
            "ada", "cardano", "bnb", "usdt", "usdc", "defi", "nft", "altcoin",
            "spot", "futures", "margin", "leverage", "liquidation"
        ]
        
        # Estatísticas
        self.stats = {
            "total_fetched": 0,
            "total_processed": 0,
            "last_fetch_time": None,
            "fetch_errors": 0,
            "avg_sentiment": 0.0
        }
    
    async def __aenter__(self):
        """Context manager entry."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.should_close_session and self.session:
            await self.session.close()
    
    async def fetch_binance_cms_news(
        self, 
        news_type: str = "1", 
        page_size: int = 20,
        hours_back: int = 24
    ) -> List[Dict]:
        """
        Busca notícias do CMS da Binance.
        
        Args:
            news_type: "1" para anúncios, "0" para notícias gerais
            page_size: Número de notícias por página
            hours_back: Buscar notícias das últimas X horas
        """
        try:
            # Parâmetros simplificados para evitar HTTP 400
            params = {
                "type": news_type,
                "pageNo": 1,
                "pageSize": page_size
            }
            
            url = f"{self.base_url}/bapi/composite/v1/public/cms/article/list/query"
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success") and "data" in data:
                        articles = data["data"].get("articles", [])
                        log.info(f"Fetched {len(articles)} articles from Binance CMS (type: {news_type})")
                        return articles
                    else:
                        log.warning(f"Binance CMS returned unsuccessful response: {data}")
                        return []
                else:
                    log.error(f"Failed to fetch Binance CMS news: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            log.error(f"Error fetching Binance CMS news: {e}")
            self.stats["fetch_errors"] += 1
            return []
    
    async def fetch_latest_announcements(self, hours_back: int = 24) -> List[BinanceNewsItem]:
        """Busca os últimos anúncios da Binance."""
        announcements = await self.fetch_binance_cms_news(
            news_type="1",  # Anúncios
            page_size=self.max_news_per_fetch,
            hours_back=hours_back
        )
        
        return self._parse_cms_articles(announcements, "announcement")
    
    async def fetch_latest_news(self, hours_back: int = 24) -> List[BinanceNewsItem]:
        """Busca as últimas notícias gerais da Binance."""
        news = await self.fetch_binance_cms_news(
            news_type="0",  # Notícias gerais
            page_size=self.max_news_per_fetch,
            hours_back=hours_back
        )
        
        return self._parse_cms_articles(news, "news")
    
    async def fetch_trending_news(self) -> List[BinanceNewsItem]:
        """
        Busca notícias em destaque/trending da Binance.
        Usa endpoint diferente para conteúdo em destaque.
        """
        try:
            # Endpoint para conteúdo em destaque
            url = f"{self.base_url}/bapi/composite/v1/public/cms/article/catalog/list/query"
            params = {
                "catalogId": 48,  # ID para notícias crypto
                "pageNo": 1,
                "pageSize": 10
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success") and "data" in data:
                        articles = data["data"].get("articles", [])
                        log.info(f"Fetched {len(articles)} trending articles from Binance")
                        return self._parse_cms_articles(articles, "trending")
                    
        except Exception as e:
            log.error(f"Error fetching trending news: {e}")
            
        return []
    
    def _parse_cms_articles(self, articles: List[Dict], article_type: str) -> List[BinanceNewsItem]:
        """Converte artigos do CMS em objetos BinanceNewsItem."""
        parsed_items = []
        
        for article in articles:
            try:
                # Verificar se já processamos esta notícia
                article_id = str(article.get("id", ""))
                if article_id in self.processed_news_ids:
                    continue
                
                # Extrair informações do artigo
                title = article.get("title", "") or ""
                body = article.get("body", article.get("content", "")) or ""
                
                # Parse timestamp
                publish_time = article.get("publishTime", article.get("releaseDate"))
                if publish_time:
                    if isinstance(publish_time, str):
                        # Tentar diferentes formatos de data
                        try:
                            published_dt = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
                        except:
                            try:
                                published_dt = datetime.fromtimestamp(int(publish_time) / 1000)
                            except:
                                published_dt = datetime.now()
                    else:
                        published_dt = datetime.fromtimestamp(int(publish_time) / 1000)
                else:
                    published_dt = datetime.now()
                
                # Extrair tags/categorias
                tags = []
                if "tags" in article:
                    tags = article["tags"]
                elif "category" in article:
                    tags = [article["category"]]
                
                # Calcular relevância baseada em palavras-chave
                relevance = self._calculate_relevance(title, body)
                
                # URL do artigo
                url = f"{self.base_url}/en/support/announcement/{article.get('code', article_id)}"
                
                news_item = BinanceNewsItem(
                    id=article_id,
                    title=title,
                    body=body,
                    type=article_type,
                    published_time=published_dt,
                    tags=tags,
                    url=url,
                    relevance_score=relevance
                )
                
                parsed_items.append(news_item)
                self.processed_news_ids.add(article_id)
                
                # Manter cache de IDs limitado
                if len(self.processed_news_ids) > 1000:
                    # Remove IDs mais antigos
                    old_ids = list(self.processed_news_ids)[:500]
                    self.processed_news_ids -= set(old_ids)
                
            except Exception as e:
                log.error(f"Error parsing article {article.get('id', 'unknown')}: {e}")
                continue
        
        log.info(f"Parsed {len(parsed_items)} new {article_type} articles")
        return parsed_items
    
    def _calculate_relevance(self, title: str, body: str) -> float:
        """Calcula score de relevância baseado em palavras-chave crypto."""
        title = title or ""
        body = body or ""
        text = (title + " " + body).lower()
        
        keyword_matches = 0
        for keyword in self.crypto_keywords:
            if keyword in text:
                keyword_matches += 1
        
        # Score normalizado (0.0 - 1.0)
        relevance = min(keyword_matches / 5, 1.0)
        return round(relevance, 2)
    
    async def fetch_all_recent_news(self, hours_back: int = 24) -> List[BinanceNewsItem]:
        """
        Busca todas as notícias recentes (anúncios + notícias + trending).
        
        Args:
            hours_back: Buscar notícias das últimas X horas
        """
        log.info(f"Fetching all Binance news from last {hours_back} hours...")
        
        all_news = []
        
        try:
            # Buscar diferentes tipos de conteúdo em paralelo
            tasks = [
                self.fetch_latest_announcements(hours_back),
                self.fetch_latest_news(hours_back),
                self.fetch_trending_news()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    log.error(f"Error in task {i}: {result}")
                else:
                    all_news.extend(result)
            
            # Remover duplicatas baseado no ID
            unique_news = {}
            for news in all_news:
                if news.id not in unique_news:
                    unique_news[news.id] = news
            
            final_news = list(unique_news.values())
            
            # Ordenar por relevância e depois por data
            final_news.sort(key=lambda x: (x.relevance_score, x.published_time), reverse=True)
            
            # Atualizar estatísticas
            self.stats["total_fetched"] += len(final_news)
            self.stats["last_fetch_time"] = datetime.now().isoformat()
            
            log.info(f"Successfully fetched {len(final_news)} unique Binance news items")
            return final_news
            
        except Exception as e:
            log.error(f"Error fetching all recent news: {e}")
            self.stats["fetch_errors"] += 1
            return []
    
    async def get_crypto_specific_news(self, symbols: List[str], hours_back: int = 24) -> List[BinanceNewsItem]:
        """
        Busca notícias específicas para determinados símbolos crypto.
        
        Args:
            symbols: Lista de símbolos (ex: ['BTC', 'ETH', 'ADA'])
            hours_back: Horas para buscar no passado
        """
        all_news = await self.fetch_all_recent_news(hours_back)
        
        # Filtrar notícias que mencionam os símbolos
        relevant_news = []
        symbols_lower = [s.lower() for s in symbols]
        
        for news in all_news:
            text = (news.title + " " + news.body).lower()
            
            for symbol in symbols_lower:
                if symbol in text or f"{symbol}usdt" in text:
                    news.relevance_score += 0.3  # Boost para menções específicas
                    relevant_news.append(news)
                    break
        
        # Re-ordenar por relevância
        relevant_news.sort(key=lambda x: x.relevance_score, reverse=True)
        
        log.info(f"Found {len(relevant_news)} news items mentioning symbols: {symbols}")
        return relevant_news
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do listener."""
        return {
            **self.stats,
            "processed_news_count": len(self.processed_news_ids),
            "fetch_interval_minutes": self.fetch_interval_minutes,
            "keywords_count": len(self.crypto_keywords)
        }
    
    async def test_connection(self) -> bool:
        """Testa a conexão com a API da Binance."""
        try:
            if not self.session:
                async with aiohttp.ClientSession() as session:
                    # Testar endpoint público da API
                    async with session.get(f"{self.base_url}/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=48&pageNo=1&pageSize=1") as response:
                        return response.status == 200
            else:
                async with self.session.get(f"{self.base_url}/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=48&pageNo=1&pageSize=1") as response:
                    return response.status == 200
        except Exception as e:
            log.error(f"Binance connection test failed: {e}")
            return False