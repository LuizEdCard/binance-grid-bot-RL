#!/usr/bin/env python3
"""
Teste simplificado da integração de notícias da Binance.
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.binance_news_listener import BinanceNewsListener


async def simple_test():
    """Teste simples de conexão e busca de notícias."""
    print("🔍 Simple Binance News Test")
    print("=" * 30)
    
    try:
        async with BinanceNewsListener() as listener:
            print("1. Testing connection...")
            connected = await listener.test_connection()
            print(f"   Connection: {'✅ Success' if connected else '❌ Failed'}")
            
            if not connected:
                return
            
            print("\n2. Testing trending news...")
            trending = await listener.fetch_trending_news()
            print(f"   Trending news: {len(trending)} items")
            
            if trending:
                news = trending[0]
                print(f"   Sample: {news.title[:50]}...")
                print(f"   Type: {news.type}")
                print(f"   Relevance: {news.relevance_score}")
            
            print("\n3. Testing announcements...")
            announcements = await listener.fetch_latest_announcements(hours_back=48)
            print(f"   Announcements: {len(announcements)} items")
            
            print("\n4. Testing general news...")
            general_news = await listener.fetch_latest_news(hours_back=48)
            print(f"   General news: {len(general_news)} items")
            
            print(f"\n✅ Test completed successfully!")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(simple_test())