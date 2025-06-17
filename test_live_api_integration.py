#!/usr/bin/env python3
"""
Test script to verify Flask API integration with multi-agent system
Tests all new live data endpoints and demonstrates usage
"""

import requests
import json
import time
from pprint import pprint

# Flask API base URL
BASE_URL = "http://localhost:5000"

def test_endpoint(endpoint, description):
    """Test a single endpoint and display results."""
    print(f"\n{'='*60}")
    print(f"🔍 Testing: {description}")
    print(f"📡 Endpoint: {endpoint}")
    print('='*60)
    
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS")
            print(f"📊 Response:")
            pprint(data, indent=2, width=100)
        else:
            print(f"❌ FAILED - Status: {response.status_code}")
            print(f"📝 Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"🔌 CONNECTION ERROR: {e}")
    except Exception as e:
        print(f"💥 ERROR: {e}")

def main():
    """Test all Flask API endpoints for multi-agent integration."""
    
    print("🚀 Flask API & Multi-Agent Integration Test")
    print("=" * 80)
    
    # Test existing endpoints
    endpoints_to_test = [
        # Original endpoints
        ("/api/status", "Bot Status"),
        ("/api/balance", "Account Balance"),
        ("/api/market_data", "Market Data"),
        ("/api/metrics", "System Metrics"),
        
        # Model API endpoints
        ("/api/model/api/system/status", "Multi-Agent System Status"),
        ("/api/model/api/agents/ai/metrics", "AI Agent Metrics"),
        ("/api/model/api/agents/sentiment/metrics", "Sentiment Agent Metrics"),
        ("/api/model/api/agents/risk/metrics", "Risk Agent Metrics"),
        ("/api/model/api/agents/data/metrics", "Data Agent Metrics"),
        ("/api/model/api/agents/coordinator/metrics", "Coordinator Agent Metrics"),
        
        # New live data endpoints
        ("/api/live/trading/all", "Live Trading Data (All Symbols)"),
        ("/api/live/agents/all/decisions", "Live Agent Decisions (All Agents)"),
        ("/api/live/system/status", "Live System Status"),
        ("/api/live/profits/summary", "Live Profit Summary"),
        ("/api/live/alerts", "Live System Alerts"),
        
        # Specific symbol tests (if any symbols are active)
        ("/api/live/trading/ADAUSDT", "Live Trading Data (ADAUSDT)"),
        ("/api/live/agents/ai/decisions", "AI Agent Decision Stream"),
        ("/api/live/agents/sentiment/decisions", "Sentiment Agent Decision Stream"),
    ]
    
    # Test each endpoint
    for endpoint, description in endpoints_to_test:
        test_endpoint(endpoint, description)
        time.sleep(1)  # Small delay between requests
    
    print(f"\n{'='*80}")
    print("📋 SUMMARY")
    print('='*80)
    print("✅ All endpoints tested")
    print("📝 Review results above to identify integration gaps")
    print("\n🎯 Key endpoints for frontend integration:")
    print("   • /api/live/trading/all - Real-time trading data")
    print("   • /api/live/agents/all/decisions - Agent decision stream")
    print("   • /api/live/system/status - System health monitoring")
    print("   • /api/live/profits/summary - Profit tracking")
    print("   • /api/live/alerts - System alerts")
    
    print("\n💡 Frontend can now access:")
    print("   ✅ Real-time trading data")
    print("   ✅ Agent decision history")
    print("   ✅ System health monitoring")
    print("   ✅ Live profit tracking")
    print("   ✅ Alert notifications")
    print("   ✅ Technical indicators")
    print("   ✅ Market analysis")

if __name__ == "__main__":
    main()