# Social Media and Trader Analysis Feed Listener
import asyncio
import aiohttp
import json
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import tweepy
from bs4 import BeautifulSoup

from utils.logger import setup_logger
from utils.data_storage import local_storage
from utils.sentiment_analyzer import analyze_sentiment

log = setup_logger("social_feeds")


@dataclass
class SocialPost:
    """Represents a social media post with trading relevance."""
    id: str
    platform: str
    author: str
    content: str
    timestamp: datetime
    followers_count: int
    likes_count: int = 0
    retweets_count: int = 0
    mentions: List[str] = None
    symbols: List[str] = None
    sentiment_score: float = 0.0
    credibility_score: float = 0.0
    url: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "platform": self.platform,
            "author": self.author,
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "timestamp": self.timestamp.isoformat(),
            "followers_count": self.followers_count,
            "likes_count": self.likes_count,
            "retweets_count": self.retweets_count,
            "mentions": self.mentions or [],
            "symbols": self.symbols or [],
            "sentiment_score": self.sentiment_score,
            "credibility_score": self.credibility_score,
            "url": self.url
        }


class InfluencerTracker:
    """Tracks known crypto influencers and traders."""
    
    def __init__(self):
        # Known crypto influencers with their credibility scores
        self.influencers = {
            # Twitter handles and their credibility scores (0.0 - 1.0)
            "elonmusk": {"credibility": 0.9, "followers_weight": 1.5},
            "michael_saylor": {"credibility": 0.95, "followers_weight": 1.4},
            "cz_binance": {"credibility": 0.98, "followers_weight": 1.6},
            "VitalikButerin": {"credibility": 0.99, "followers_weight": 1.5},
            "naval": {"credibility": 0.85, "followers_weight": 1.3},
            "balajis": {"credibility": 0.9, "followers_weight": 1.4},
            "aantonop": {"credibility": 0.95, "followers_weight": 1.3},
            "APompliano": {"credibility": 0.8, "followers_weight": 1.2},
            "woonomic": {"credibility": 0.85, "followers_weight": 1.1},
            "documentingbtc": {"credibility": 0.75, "followers_weight": 1.1},
            "coingecko": {"credibility": 0.9, "followers_weight": 1.2},
            "coinmarketcap": {"credibility": 0.85, "followers_weight": 1.2},
            # YouTube/TikTok personalities
            "coin_bureau": {"credibility": 0.8, "followers_weight": 1.0},
            "investanswers": {"credibility": 0.75, "followers_weight": 1.0},
            # Trading groups
            "altcoindaily": {"credibility": 0.7, "followers_weight": 0.9},
            "crypto_rand": {"credibility": 0.65, "followers_weight": 0.8},
        }
        
        # Crypto symbols pattern for detection
        self.crypto_pattern = re.compile(
            r'\b(?:BTC|ETH|ADA|DOT|LINK|UNI|AAVE|SOL|MATIC|AVAX|LUNA|FTT|BNB|XRP|DOGE|SHIB|'
            r'USDT|USDC|BUSD|DAI|ATOM|ALGO|VET|FIL|THETA|XTZ|EOS|TRX|NEO|IOTA|MIOTA|'
            r'BITCOIN|ETHEREUM|CARDANO|POLKADOT|CHAINLINK|UNISWAP|SOLANA|POLYGON|AVALANCHE|'
            r'BINANCE|DOGECOIN|SHIBA)\b',
            re.IGNORECASE
        )
        
        # Trading-related keywords
        self.trading_keywords = [
            "bullish", "bearish", "pump", "dump", "moon", "rocket", "crash", "dip",
            "buy", "sell", "hold", "hodl", "long", "short", "leverage", "margin",
            "breakout", "support", "resistance", "TA", "technical analysis",
            "fundamentals", "news", "announcement", "partnership", "adoption",
            "regulation", "ban", "approve", "etf", "institutional", "whale"
        ]
        
        log.info(f"InfluencerTracker initialized with {len(self.influencers)} known influencers")
    
    def get_credibility_score(self, author: str, followers_count: int) -> float:
        """Calculate credibility score for an author."""
        base_score = 0.1  # Base score for unknown authors
        
        # Check if known influencer
        if author.lower() in self.influencers:
            influencer_data = self.influencers[author.lower()]
            base_score = influencer_data["credibility"]
            followers_weight = influencer_data["followers_weight"]
        else:
            followers_weight = 1.0
        
        # Adjust based on follower count
        if followers_count > 1000000:  # 1M+ followers
            follower_boost = 0.3 * followers_weight
        elif followers_count > 100000:  # 100K+ followers
            follower_boost = 0.2 * followers_weight
        elif followers_count > 10000:   # 10K+ followers
            follower_boost = 0.1 * followers_weight
        else:
            follower_boost = 0.0
        
        return min(base_score + follower_boost, 1.0)
    
    def extract_crypto_symbols(self, text: str) -> List[str]:
        """Extract cryptocurrency symbols from text."""
        matches = self.crypto_pattern.findall(text)
        # Normalize symbols
        symbols = []
        for match in matches:
            symbol = match.upper()
            # Convert common names to symbols
            symbol_map = {
                "BITCOIN": "BTC",
                "ETHEREUM": "ETH", 
                "CARDANO": "ADA",
                "POLKADOT": "DOT",
                "CHAINLINK": "LINK",
                "UNISWAP": "UNI",
                "SOLANA": "SOL",
                "POLYGON": "MATIC",
                "AVALANCHE": "AVAX",
                "BINANCE": "BNB",
                "DOGECOIN": "DOGE",
                "SHIBA": "SHIB"
            }
            symbols.append(symbol_map.get(symbol, symbol))
        
        return list(set(symbols))  # Remove duplicates
    
    def is_trading_relevant(self, text: str) -> bool:
        """Check if text is trading/crypto relevant."""
        text_lower = text.lower()
        
        # Check for crypto symbols
        if self.crypto_pattern.search(text):
            return True
        
        # Check for trading keywords
        for keyword in self.trading_keywords:
            if keyword in text_lower:
                return True
        
        return False


class SocialFeedsListener:
    """Aggregates social media feeds for crypto trading signals."""
    
    def __init__(self, config: dict):
        self.config = config
        self.influencer_tracker = InfluencerTracker()
        
        # Session for HTTP requests
        self.session = None
        
        # Data storage
        self.processed_posts = set()
        self.recent_posts = []
        
        # Statistics
        self.stats = {
            "posts_processed": 0,
            "trading_relevant_posts": 0,
            "influencer_posts": 0,
            "average_sentiment": 0.0,
            "last_update_time": None
        }
        
        # Platform configurations
        self.reddit_config = config.get("reddit", {})
        self.twitter_config = config.get("twitter", {})
        self.telegram_config = config.get("telegram", {})
        
        log.info("SocialFeedsListener initialized")
    
    async def start(self):
        """Start the social feeds listener."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        
        log.info("Social feeds listener started")
    
    async def stop(self):
        """Stop the social feeds listener."""
        if self.session:
            await self.session.close()
        log.info("Social feeds listener stopped")
    
    async def fetch_reddit_posts(self, subreddits: List[str] = None) -> List[SocialPost]:
        """Fetch posts from crypto-related subreddits."""
        if not subreddits:
            subreddits = [
                "cryptocurrency", "bitcoin", "ethereum", "cryptomarkets",
                "altcoin", "defi", "binance", "trading", "cryptomoonshots"
            ]
        
        posts = []
        
        for subreddit in subreddits:
            try:
                # Use Reddit JSON API (no auth required for public posts)
                url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for post_data in data.get("data", {}).get("children", []):
                            post = post_data.get("data", {})
                            
                            # Skip if already processed
                            post_id = f"reddit_{post.get('id', '')}"
                            if post_id in self.processed_posts:
                                continue
                            
                            # Extract post content
                            title = post.get("title", "")
                            selftext = post.get("selftext", "")
                            content = f"{title}\n{selftext}".strip()
                            
                            # Check relevance
                            if not self.influencer_tracker.is_trading_relevant(content):
                                continue
                            
                            # Create social post object
                            social_post = SocialPost(
                                id=post_id,
                                platform="reddit",
                                author=post.get("author", "unknown"),
                                content=content,
                                timestamp=datetime.fromtimestamp(post.get("created_utc", 0)),
                                followers_count=0,  # Reddit doesn't expose this easily
                                likes_count=post.get("ups", 0),
                                url=f"https://reddit.com{post.get('permalink', '')}"
                            )
                            
                            # Extract crypto symbols
                            social_post.symbols = self.influencer_tracker.extract_crypto_symbols(content)
                            
                            # Calculate sentiment and credibility
                            social_post.sentiment_score = analyze_sentiment(content)
                            social_post.credibility_score = 0.5  # Base Reddit credibility
                            
                            posts.append(social_post)
                            self.processed_posts.add(post_id)
                
                # Rate limit
                await asyncio.sleep(1)
                
            except Exception as e:
                log.error(f"Error fetching Reddit posts from r/{subreddit}: {e}")
                continue
        
        log.info(f"Fetched {len(posts)} relevant posts from Reddit")
        return posts
    
    async def fetch_twitter_mentions(self, keywords: List[str] = None) -> List[SocialPost]:
        """Fetch Twitter mentions and posts (requires Twitter API access)."""
        posts = []
        
        # This would require Twitter API v2 access
        # For now, return empty list - can be implemented with proper Twitter credentials
        
        try:
            # Placeholder for Twitter API implementation
            # Would need: bearer_token, api_key, api_secret from config
            
            if not keywords:
                keywords = ["$BTC", "$ETH", "#crypto", "#bitcoin", "#ethereum", "#trading"]
            
            # Twitter API implementation would go here
            log.info("Twitter integration requires API credentials (not implemented)")
            
        except Exception as e:
            log.error(f"Error fetching Twitter posts: {e}")
        
        return posts
    
    async def fetch_telegram_channels(self, channels: List[str] = None) -> List[SocialPost]:
        """Fetch posts from Telegram crypto channels."""
        posts = []
        
        # Telegram requires special setup - placeholder implementation
        try:
            # Would need Telegram API credentials and channel access
            log.info("Telegram integration requires API setup (not implemented)")
            
        except Exception as e:
            log.error(f"Error fetching Telegram posts: {e}")
        
        return posts
    
    async def fetch_crypto_news_sites(self) -> List[SocialPost]:
        """Fetch posts from crypto news websites."""
        posts = []
        
        news_sites = [
            {
                "name": "cointelegraph",
                "url": "https://cointelegraph.com/rss",
                "credibility": 0.8
            },
            {
                "name": "coindesk", 
                "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
                "credibility": 0.85
            },
            {
                "name": "decrypt",
                "url": "https://decrypt.co/feed",
                "credibility": 0.75
            }
        ]
        
        for site in news_sites:
            try:
                async with self.session.get(site["url"]) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Parse RSS feed
                        soup = BeautifulSoup(content, 'xml')
                        items = soup.find_all('item')
                        
                        for item in items[:10]:  # Limit to 10 per site
                            title = item.find('title')
                            description = item.find('description')
                            link = item.find('link')
                            pub_date = item.find('pubDate')
                            
                            if title and description:
                                content_text = f"{title.text}\n{description.text}"
                                
                                # Check relevance
                                if not self.influencer_tracker.is_trading_relevant(content_text):
                                    continue
                                
                                post_id = f"news_{site['name']}_{hash(title.text)}"
                                if post_id in self.processed_posts:
                                    continue
                                
                                # Parse date
                                try:
                                    timestamp = datetime.strptime(
                                        pub_date.text, 
                                        "%a, %d %b %Y %H:%M:%S %z"
                                    ) if pub_date else datetime.now()
                                except:
                                    timestamp = datetime.now()
                                
                                social_post = SocialPost(
                                    id=post_id,
                                    platform=f"news_{site['name']}",
                                    author=site['name'],
                                    content=content_text,
                                    timestamp=timestamp,
                                    followers_count=100000,  # Assume news sites have large reach
                                    url=link.text if link else ""
                                )
                                
                                social_post.symbols = self.influencer_tracker.extract_crypto_symbols(content_text)
                                social_post.sentiment_score = analyze_sentiment(content_text)
                                social_post.credibility_score = site["credibility"]
                                
                                posts.append(social_post)
                                self.processed_posts.add(post_id)
                
                await asyncio.sleep(1)  # Rate limit
                
            except Exception as e:
                log.error(f"Error fetching from {site['name']}: {e}")
                continue
        
        log.info(f"Fetched {len(posts)} posts from crypto news sites")
        return posts
    
    async def fetch_all_feeds(self) -> List[SocialPost]:
        """Fetch posts from all configured social feeds."""
        all_posts = []
        
        try:
            # Fetch from different sources concurrently
            tasks = [
                self.fetch_reddit_posts(),
                self.fetch_twitter_mentions(),
                self.fetch_telegram_channels(),
                self.fetch_crypto_news_sites()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    log.error(f"Error in task {i}: {result}")
                else:
                    all_posts.extend(result)
            
            # Sort by timestamp (newest first)
            all_posts.sort(key=lambda x: x.timestamp, reverse=True)
            
            # Update statistics
            self.stats["posts_processed"] += len(all_posts)
            self.stats["trading_relevant_posts"] = len(all_posts)
            
            influencer_posts = sum(1 for post in all_posts if post.credibility_score > 0.7)
            self.stats["influencer_posts"] += influencer_posts
            
            if all_posts:
                avg_sentiment = sum(post.sentiment_score for post in all_posts) / len(all_posts)
                self.stats["average_sentiment"] = avg_sentiment
            
            self.stats["last_update_time"] = datetime.now().isoformat()
            
            # Store to database
            for post in all_posts:
                await local_storage.store_social_sentiment(
                    symbol=",".join(post.symbols) if post.symbols else "GENERAL",
                    source=post.platform,
                    content=post.content,
                    sentiment_score=post.sentiment_score,
                    author=post.author,
                    followers_count=post.followers_count
                )
            
            # Keep recent posts in memory
            self.recent_posts = all_posts[:100]  # Keep last 100 posts
            
            log.info(f"Fetched {len(all_posts)} total social posts")
            return all_posts
            
        except Exception as e:
            log.error(f"Error fetching all feeds: {e}")
            return []
    
    async def get_symbol_sentiment(self, symbol: str, hours_back: int = 6) -> Dict:
        """Get aggregated sentiment for a specific symbol."""
        try:
            # Get recent sentiment from database
            sentiment_data = await local_storage.get_recent_social_sentiment(symbol, hours_back)
            
            if not sentiment_data:
                return {
                    "symbol": symbol,
                    "sentiment_score": 0.0,
                    "post_count": 0,
                    "credibility_weighted_sentiment": 0.0,
                    "sources": []
                }
            
            # Calculate aggregated metrics
            total_sentiment = sum(item["sentiment_score"] for item in sentiment_data)
            avg_sentiment = total_sentiment / len(sentiment_data)
            
            # Calculate credibility-weighted sentiment
            total_weight = 0
            weighted_sentiment = 0
            sources = set()
            
            for item in sentiment_data:
                # Estimate credibility from author and followers
                credibility = self.influencer_tracker.get_credibility_score(
                    item["author"], 
                    item["followers_count"] or 0
                )
                
                weighted_sentiment += item["sentiment_score"] * credibility
                total_weight += credibility
                sources.add(item["source"])
            
            credibility_weighted = (weighted_sentiment / total_weight) if total_weight > 0 else avg_sentiment
            
            return {
                "symbol": symbol,
                "sentiment_score": avg_sentiment,
                "post_count": len(sentiment_data),
                "credibility_weighted_sentiment": credibility_weighted,
                "sources": list(sources),
                "time_period_hours": hours_back
            }
            
        except Exception as e:
            log.error(f"Error getting symbol sentiment for {symbol}: {e}")
            return {
                "symbol": symbol,
                "sentiment_score": 0.0,
                "post_count": 0,
                "credibility_weighted_sentiment": 0.0,
                "sources": []
            }
    
    def get_statistics(self) -> Dict:
        """Get social feeds statistics."""
        return {
            **self.stats,
            "processed_posts_cache": len(self.processed_posts),
            "recent_posts_cache": len(self.recent_posts),
            "known_influencers": len(self.influencer_tracker.influencers)
        }
    
    async def cleanup_old_data(self, days_to_keep: int = 7):
        """Clean up old processed post IDs."""
        # Clean memory cache of processed posts (keep recent ones)
        if len(self.processed_posts) > 10000:
            # Keep only the most recent 5000 IDs
            recent_ids = list(self.processed_posts)[-5000:]
            self.processed_posts = set(recent_ids)
            log.info("Cleaned old processed post IDs from memory")


# Example usage and testing
async def test_social_feeds():
    """Test the social feeds listener."""
    config = {
        "reddit": {},
        "twitter": {},
        "telegram": {}
    }
    
    listener = SocialFeedsListener(config)
    await listener.start()
    
    try:
        # Fetch all feeds
        posts = await listener.fetch_all_feeds()
        print(f"Fetched {len(posts)} posts")
        
        # Get sentiment for specific symbols
        btc_sentiment = await listener.get_symbol_sentiment("BTC")
        print(f"BTC sentiment: {btc_sentiment}")
        
        # Get statistics
        stats = listener.get_statistics()
        print(f"Stats: {stats}")
        
    finally:
        await listener.stop()


if __name__ == "__main__":
    asyncio.run(test_social_feeds())