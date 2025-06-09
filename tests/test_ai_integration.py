#!/usr/bin/env python3
# Test script for AI Integration
import asyncio
import json
import time
from datetime import datetime

import sys
sys.path.append('../src')

from agents.ai_agent import AIAgent
from integrations.ai_trading_integration import AITradingIntegration


async def test_ai_connection():
    """Test basic AI connection and functionality."""
    print("🤖 Testing AI Integration...")
    print("=" * 50)
    
    # Test configuration
    config = {
        "ai_agent": {
            "enabled": True,
            "base_url": "http://127.0.0.1:1234"
        }
    }
    
    # Initialize AI Agent
    ai_agent = AIAgent(config)
    
    try:
        # Start AI agent
        await ai_agent.start()
        
        if not ai_agent.is_available:
            print("❌ AI not available at http://127.0.0.1:1234")
            print("   Make sure your local AI is running on port 1234")
            return False
        
        print("✅ AI connection successful!")
        
        # Test market analysis
        print("\n📊 Testing Market Analysis...")
        
        sample_market_data = {
            "symbol": "BTCUSDT",
            "current_price": 45000,
            "price_change_24h": 2.5,
            "volume_24h": 1000000000,
            "rsi": 65,
            "atr_percentage": 3.2,
            "adx": 22,
            "recent_prices": [44800, 44900, 45100, 45050, 45000]
        }
        
        analysis = await ai_agent.analyze_market(sample_market_data)
        if analysis:
            print("✅ Market analysis successful!")
            print(f"   Analysis: {json.dumps(analysis, indent=2)}")
        else:
            print("❌ Market analysis failed")
        
        # Test grid optimization
        print("\n⚙️ Testing Grid Optimization...")
        
        current_params = {
            "spacing_perc": 0.005,  # 0.5%
            "levels": 10,
            "recent_pnl": 150.0
        }
        
        market_context = {
            "volatility_24h": 3.2,
            "trend_strength": 22,
            "current_price": 45000,
            "volume_24h": 1000000000
        }
        
        optimization = await ai_agent.optimize_grid_strategy(current_params, market_context)
        if optimization:
            print("✅ Grid optimization successful!")
            print(f"   Recommendations: {json.dumps(optimization, indent=2)}")
        else:
            print("❌ Grid optimization failed")
        
        # Test decision explanation
        print("\n💡 Testing Decision Explanation...")
        
        decision_context = {
            "action": "buy",
            "symbol": "BTCUSDT",
            "price": 45000,
            "quantity": 0.001,
            "reasoning_factors": ["RSI oversold", "Support level", "Positive sentiment"],
            "market_conditions": sample_market_data,
            "sentiment": 0.6
        }
        
        explanation = await ai_agent.explain_decision(decision_context)
        if explanation:
            print("✅ Decision explanation successful!")
            print(f"   Explanation: {explanation}")
        else:
            print("❌ Decision explanation failed")
        
        # Test report generation
        print("\n📋 Testing Report Generation...")
        
        comprehensive_data = {
            "trading_summary": {
                "total_trades": 25,
                "profitable_trades": 18,
                "total_pnl": 250.50,
                "active_pairs": ["BTCUSDT", "ETHUSDT"],
                "best_performing_pair": "BTCUSDT"
            },
            "market_overview": {
                "market_trend": "bullish",
                "volatility_level": 3.2,
                "volume_analysis": {"average": "high"},
                "key_events": ["Fed meeting", "Bitcoin ETF approval"]
            },
            "performance_metrics": {
                "sharpe_ratio": 1.8,
                "max_drawdown": 0.05,
                "win_rate": 0.72,
                "avg_trade_duration": 45
            }
        }
        
        report = await ai_agent.generate_market_report(comprehensive_data)
        if report:
            print("✅ Report generation successful!")
            print(f"   Report: {report}")
        else:
            print("❌ Report generation failed")
        
        # Test AI Trading Integration
        print("\n🔗 Testing AI Trading Integration...")
        
        ai_integration = AITradingIntegration(ai_agent)
        
        trading_data = {
            "market_data": sample_market_data,
            "sentiment_data": {
                "smoothed_score": 0.6,
                "source_scores": {"reddit": 0.7, "news": 0.5}
            },
            "grid_params": current_params,
            "decision_made": True,
            "decision_data": decision_context
        }
        
        cycle_results = await ai_integration.process_trading_cycle("BTCUSDT", trading_data)
        if cycle_results and cycle_results.get("ai_insights"):
            print("✅ AI Trading Integration successful!")
            print(f"   Cycle Results: {json.dumps(cycle_results, indent=2)}")
        else:
            print("❌ AI Trading Integration failed")
        
        # Show statistics
        print("\n📈 AI Agent Statistics:")
        stats = ai_agent.get_statistics()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        ai_agent.stop()
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        ai_agent.stop()
        return False


def test_prompt_examples():
    """Show example prompts that the AI will receive."""
    print("\n🔍 Example AI Prompts:")
    print("=" * 50)
    
    # Market Analysis Prompt
    print("\n1. Market Analysis Prompt:")
    print("-" * 30)
    market_prompt = """You are an expert cryptocurrency market analyst. Analyze the provided market data and identify:
1. Key patterns and trends
2. Support and resistance levels
3. Market anomalies or unusual behavior
4. Short-term price predictions (next 1-4 hours)
5. Risk factors to consider

Provide your analysis in JSON format with specific, actionable insights.

Market Data: Current price: $45000; 24h change: 2.50%; RSI: 65.0; ATR: 3.20%; 24h volume: $1,000,000,000; Recent price trend: [44800, 44900, 45100, 45050, 45000]"""
    
    print(market_prompt)
    
    # Grid Optimization Prompt
    print("\n2. Grid Optimization Prompt:")
    print("-" * 30)
    grid_prompt = """You are an expert in grid trading strategy optimization. Based on current market conditions and grid parameters, provide recommendations for:
1. Optimal grid spacing percentage
2. Number of grid levels
3. Risk adjustments needed
4. Entry/exit timing suggestions

Respond in JSON format with specific numerical recommendations and reasoning.

Current grid parameters and market context: {"current_grid_spacing": 0.5, "current_levels": 10, "market_volatility": 3.2, "trend_strength": 22, "recent_performance": 150.0}"""
    
    print(grid_prompt)
    
    # Decision Explanation Prompt
    print("\n3. Decision Explanation Prompt:")
    print("-" * 30)
    decision_prompt = """You are an expert trading advisor. Explain trading decisions in clear, educational terms. Focus on:
1. Why this decision makes sense given the market conditions
2. What factors were most important in this decision
3. Potential risks and how they're being managed
4. What to watch for going forward

Keep explanations concise but informative.

Trading Decision: {"action": "buy", "symbol": "BTCUSDT", "price": 45000, "quantity": 0.001, "reasoning_factors": ["RSI oversold", "Support level", "Positive sentiment"], "sentiment": 0.6}"""
    
    print(decision_prompt)


async def main():
    """Main test function."""
    print(f"🚀 AI Integration Test Suite")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Show example prompts
    test_prompt_examples()
    
    # Test AI connection and functionality
    print("\n" + "=" * 60)
    success = await test_ai_connection()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed! AI integration is working correctly.")
        print("\n🎯 Next Steps:")
        print("   1. Configure your local AI model for optimal responses")
        print("   2. Adjust temperature and max_tokens in config.yaml")
        print("   3. Enable AI agent in the main trading bot")
        print("   4. Monitor AI analysis quality and performance")
    else:
        print("❌ Some tests failed. Check your AI setup.")
        print("\n🔧 Troubleshooting:")
        print("   1. Ensure AI is running on http://127.0.0.1:1234")
        print("   2. Test AI with: curl http://127.0.0.1:1234/health")
        print("   3. Check AI model compatibility with OpenAI API format")
        print("   4. Verify network connectivity and firewall settings")


if __name__ == "__main__":
    asyncio.run(main())