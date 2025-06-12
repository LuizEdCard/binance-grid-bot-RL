#!/usr/bin/env python3
"""
Teste da integração de notícias da Binance com análise de sentimentos.
"""
import asyncio
import sys
import os
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.binance_news_listener import BinanceNewsListener
from utils.sentiment_analyzer import SentimentAnalyzer
from agents.sentiment_agent import BinanceNewsSentimentSource


async def test_binance_news_listener():
    """Testa o listener de notícias da Binance."""
    print("🔍 Testing Binance News Listener")
    print("=" * 40)
    
    async with BinanceNewsListener() as listener:
        # Test connection
        print("1. Testing connection...")
        is_connected = await listener.test_connection()
        if is_connected:
            print("✅ Successfully connected to Binance")
        else:
            print("❌ Failed to connect to Binance")
            return False
        
        # Test fetching news
        print("\n2. Fetching latest news...")
        try:
            news_items = await listener.fetch_all_recent_news(hours_back=24)
            print(f"✅ Fetched {len(news_items)} news items")
            
            if news_items:
                print("\n📰 Sample news items:")
                for i, news in enumerate(news_items[:3]):  # Show first 3
                    print(f"\n{i+1}. {news.title}")
                    print(f"   Type: {news.type}")
                    print(f"   Published: {news.published_time}")
                    print(f"   Relevance: {news.relevance_score}")
                    print(f"   URL: {news.url}")
                    print(f"   Body preview: {news.body[:100]}...")
            
            return True
            
        except Exception as e:
            print(f"❌ Error fetching news: {e}")
            return False


async def test_binance_sentiment_analysis():
    """Testa a análise de sentimento das notícias da Binance."""
    print("\n\n🧠 Testing Binance News Sentiment Analysis")
    print("=" * 50)
    
    analyzer = SentimentAnalyzer()
    
    # Test general news sentiment
    print("1. Analyzing general Binance news sentiment...")
    try:
        sentiment_result = await analyzer.analyze_binance_news(
            symbols=None,  # All news
            hours_back=24,
            min_relevance=0.1
        )
        
        print("✅ General sentiment analysis completed:")
        print(f"   Overall sentiment: {sentiment_result['overall_sentiment']}")
        print(f"   Weighted score: {sentiment_result['weighted_score']}")
        print(f"   News analyzed: {sentiment_result['news_count']}")
        print(f"   Positive news: {sentiment_result['stats']['positive_count']}")
        print(f"   Negative news: {sentiment_result['stats']['negative_count']}")
        print(f"   Neutral news: {sentiment_result['stats']['neutral_count']}")
        
        if sentiment_result['news_items']:
            print(f"\n📊 Sample analyzed news:")
            for news in sentiment_result['news_items'][:2]:
                print(f"   • {news['title']}")
                print(f"     Sentiment: {news['sentiment']} ({news['sentiment_score']:.3f})")
                print(f"     Relevance: {news['relevance_score']}")
        
    except Exception as e:
        print(f"❌ Error in general sentiment analysis: {e}")
    
    # Test specific symbol sentiment
    print("\n2. Analyzing BTC-specific news sentiment...")
    try:
        btc_sentiment = await analyzer.get_symbol_sentiment_from_news('BTC', hours_back=24)
        
        print("✅ BTC sentiment analysis completed:")
        print(f"   Symbol: {btc_sentiment['symbol']}")
        print(f"   Sentiment: {btc_sentiment['symbol_sentiment']}")
        print(f"   Score: {btc_sentiment['symbol_score']}")
        print(f"   Mentions: {btc_sentiment['mentions_count']}")
        
    except Exception as e:
        print(f"❌ Error in BTC sentiment analysis: {e}")
    
    # Test multiple symbols
    print("\n3. Analyzing multiple symbols sentiment...")
    try:
        symbols = ['BTC', 'ETH', 'ADA']
        multi_sentiment = analyzer.analyze_multiple_symbols(symbols, hours_back=24)
        
        print("✅ Multiple symbols analysis completed:")
        for symbol, data in multi_sentiment.items():
            if 'error' not in data:
                print(f"   {symbol}: {data['symbol_sentiment']} ({data['symbol_score']:.3f}) - {data['mentions_count']} mentions")
            else:
                print(f"   {symbol}: Error - {data['error']}")
        
    except Exception as e:
        print(f"❌ Error in multiple symbols analysis: {e}")


def test_sentiment_agent_integration():
    """Testa a integração com o agente de sentimentos."""
    print("\n\n🤖 Testing Sentiment Agent Integration")
    print("=" * 45)
    
    # Test Binance news source
    print("1. Testing Binance news sentiment source...")
    try:
        source = BinanceNewsSentimentSource()
        
        # Mock config
        config = {
            "binance_news": {
                "enabled": True,
                "hours_back": 12,
                "min_relevance_score": 0.2,
                "max_news_per_fetch": 10
            }
        }
        
        texts = source.fetch_data(config)
        print(f"✅ Binance news source collected {len(texts)} texts")
        
        if texts:
            print("📄 Sample texts:")
            for i, text in enumerate(texts[:3]):
                print(f"   {i+1}. {text[:80]}...")
        
    except Exception as e:
        print(f"❌ Error testing sentiment agent integration: {e}")


async def test_performance():
    """Testa a performance da integração."""
    print("\n\n⚡ Testing Performance")
    print("=" * 25)
    
    start_time = datetime.now()
    
    try:
        async with BinanceNewsListener() as listener:
            # Measure news fetching time
            fetch_start = datetime.now()
            news_items = await listener.fetch_all_recent_news(hours_back=6)
            fetch_time = (datetime.now() - fetch_start).total_seconds()
            
            print(f"📈 Performance metrics:")
            print(f"   News fetching: {fetch_time:.2f}s for {len(news_items)} items")
            print(f"   Rate: {len(news_items)/fetch_time:.1f} news/second")
            
            # Test statistics
            stats = listener.get_statistics()
            print(f"   Total fetched: {stats['total_fetched']}")
            print(f"   Fetch errors: {stats['fetch_errors']}")
            print(f"   Keywords count: {stats['keywords_count']}")
            
    except Exception as e:
        print(f"❌ Error in performance test: {e}")
    
    total_time = (datetime.now() - start_time).total_seconds()
    print(f"\n⏱️  Total test time: {total_time:.2f}s")


async def main():
    """Execute all tests."""
    print("🧪 Binance News Integration Test Suite")
    print("=====================================\n")
    
    # Run tests sequentially
    tests = [
        test_binance_news_listener(),
        test_binance_sentiment_analysis(),
        test_performance()
    ]
    
    for test in tests:
        try:
            await test
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
        
        print("\n" + "-" * 50)
    
    # Run synchronous test
    test_sentiment_agent_integration()
    
    print("\n✅ All tests completed!")
    print("\n💡 Next steps:")
    print("   1. Configure binance_news settings in config.yaml")
    print("   2. Enable binance_news source in sentiment analysis")
    print("   3. Monitor sentiment data in bot logs")


if __name__ == "__main__":
    asyncio.run(main())