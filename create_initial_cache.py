#!/usr/bin/env python3
"""
Create initial cache with valid symbols to avoid recalculations
"""

import json
import os
import time

def main():
    print("🗃️ Creating Initial Pair Selection Cache")
    print("=" * 40)
    
    # Create data directory
    os.makedirs("data", exist_ok=True)
    
    # Valid symbols that we know work
    valid_symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
    
    cache_data = {
        "selected_pairs": valid_symbols,
        "timestamp": time.time()
    }
    
    cache_file = "data/pair_selection_cache.json"
    
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)
    
    print(f"✅ Created cache file: {cache_file}")
    print(f"📋 Cached pairs: {valid_symbols}")
    print(f"⏰ Timestamp: {cache_data['timestamp']}")
    print(f"🕒 Valid for 6 hours")
    
    # Also create market analysis cache to avoid AI recalculations
    market_cache = "data/market_analysis_cache.json"
    market_data = {
        "market_trend": "neutral",
        "market_strength": 0.5,
        "confidence": 0.8,
        "analysis": "Stable market conditions suitable for grid trading",
        "timestamp": time.time(),
        "pairs_analyzed": len(valid_symbols)
    }
    
    with open(market_cache, 'w') as f:
        json.dump(market_data, f, indent=2)
    
    print(f"✅ Created market analysis cache: {market_cache}")
    print("🚀 Bot should now start much faster!")

if __name__ == "__main__":
    main()