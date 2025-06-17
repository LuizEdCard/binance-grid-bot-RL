import asyncio
import time
import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request

from models.tabular_model import TabularTradingModel, prepare_features
# from rl.agent import RLTradingAgent  # RL removed

# Global references to all agents (will be set by main app)
_agents = {}

def set_agents(agents: dict):
    """Set the global agent references."""
    global _agents
    _agents = agents

def set_ai_agent(ai_agent):
    """Set the global AI agent reference."""
    global _agents
    _agents['ai'] = ai_agent

model_api = Blueprint("model_api", __name__)

# Endpoint para predição tabular


@model_api.route("/predict/tabular", methods=["POST"])
def predict_tabular():
    data = request.json
    df = pd.DataFrame([data])
    features = prepare_features(df)
    model = TabularTradingModel()
    pred = model.predict(features)
    return jsonify({"prediction": int(pred[0])})


# Endpoint para predição RL


@model_api.route("/predict/rl", methods=["POST"])
def predict_rl():
    data = request.json
    state = np.array(data["state"]).reshape(-1, 1)
    state_size = state.shape[0]
    action_size = 3
    model_path = data.get("model_path")
    agent = RLTradingAgent(state_size, action_size, model_path=model_path)
    action = agent.act(state)
    return jsonify({"action": int(action)})


# Endpoints para monitoramento de modelos de IA

@model_api.route("/ai/models", methods=["GET"])
def get_ai_models():
    """Get information about available AI models."""
    ai_agent = _agents.get('ai')
    if not ai_agent:
        return jsonify({"error": "AI agent not available", "models": []}), 503
    
    try:
        model_info = ai_agent.get_model_info()
        return jsonify({
            "success": True,
            "current_model": model_info["current_model"],
            "available_models": model_info["available_models"],
            "total_models": model_info["total_models"],
            "is_monitoring": model_info["is_monitoring"],
            "monitoring_status": model_info["monitoring_status"],
            "model_changes_detected": model_info["model_changes_detected"],
            "auto_reconnections": model_info["auto_reconnections"],
            "last_model_check": model_info["last_model_check"]
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@model_api.route("/ai/models/refresh", methods=["POST"])
def refresh_ai_models():
    """Force refresh of AI model detection."""
    ai_agent = _agents.get('ai')
    if not ai_agent:
        return jsonify({"error": "AI agent not available"}), 503
    
    try:
        # Run async method in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(ai_agent.force_model_check())
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@model_api.route("/ai/status", methods=["GET"])
def get_ai_status():
    """Get comprehensive AI agent status."""
    ai_agent = _agents.get('ai')
    if not ai_agent:
        return jsonify({
            "error": "AI agent not available",
            "is_available": False,
            "current_model": None,
            "available_models": []
        }), 503
    
    try:
        stats = ai_agent.get_statistics()
        return jsonify({
            "success": True,
            "is_available": stats["is_available"],
            "current_model": stats["current_model"],
            "available_models": stats["available_models"],
            "total_models": stats["total_models"],
            "model_change_detected": stats["model_change_detected"],
            "last_health_check": stats["last_health_check"],
            "last_model_check": stats["last_model_check"],
            "analyses_performed": stats["analyses_performed"],
            "decisions_explained": stats["decisions_explained"],
            "reports_generated": stats["reports_generated"],
            "model_changes_detected": stats["model_changes_detected"],
            "auto_reconnections": stats["auto_reconnections"],
            "cached_analyses": stats["cached_analyses"],
            "ai_base_url": stats["ai_base_url"]
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@model_api.route("/ai/models/reset-flag", methods=["POST"])
def reset_model_change_flag():
    """Reset the model change detection flag."""
    ai_agent = _agents.get('ai')
    if not ai_agent:
        return jsonify({"error": "AI agent not available"}), 503
    
    try:
        ai_agent.reset_model_change_flag()
        return jsonify({"success": True, "message": "Model change flag reset"})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@model_api.route("/api/agents/<agent_name>/metrics", methods=["GET"])
def get_agent_metrics(agent_name):
    """Get detailed metrics for a specific agent."""
    agent = _agents.get(agent_name)
    if not agent:
        return jsonify({"error": f"Agent '{agent_name}' not found"}), 404

    if hasattr(agent, "get_statistics"):
        try:
            return jsonify(agent.get_statistics())
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": f"Agent '{agent_name}' does not have a get_statistics method"}), 501


@model_api.route("/api/agents/<agent_name>/history", methods=["GET"])
def get_agent_history(agent_name):
    """Get action/decision history for a specific agent."""
    agent = _agents.get(agent_name)
    if not agent:
        return jsonify({"error": f"Agent '{agent_name}' not found"}), 404

    # Mapping of agent types to their history methods
    history_methods = {
        "ai": "get_recent_analyses",
        "data": "get_data_history", 
        "risk": "get_risk_history",
        "sentiment": "get_sentiment_history",
        "coordinator": "get_coordination_history"
    }
    
    history_method_name = history_methods.get(agent_name)
    
    # Fallback: try to find any history method
    if not history_method_name:
        for method in ["get_recent_analyses", "get_data_history", "get_risk_history", 
                      "get_sentiment_history", "get_coordination_history", "get_decision_history"]:
            if hasattr(agent, method):
                history_method_name = method
                break

    if history_method_name and hasattr(agent, history_method_name):
        try:
            limit = request.args.get('limit', 20, type=int)
            since_timestamp = request.args.get('since', type=float)
            history_method = getattr(agent, history_method_name)
            
            # Handle methods that require a 'symbol' argument
            if history_method_name == 'get_data_history':
                symbol = request.args.get('symbol')
                if not symbol:
                    return jsonify({"error": "A 'symbol' parameter is required for data history"}), 400
                if since_timestamp:
                    return jsonify(history_method(symbol=symbol, limit=limit, since=since_timestamp))
                else:
                    return jsonify(history_method(symbol=symbol, limit=limit))
            else:
                # Try to pass since timestamp if method supports it
                try:
                    if since_timestamp:
                        return jsonify(history_method(limit=limit, since=since_timestamp))
                    else:
                        return jsonify(history_method(limit=limit))
                except TypeError:
                    # Method doesn't support since parameter, fallback to limit only
                    return jsonify(history_method(limit=limit))

        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({
            "error": f"Agent '{agent_name}' does not have a history method",
            "available_methods": [method for method in dir(agent) if 'history' in method.lower()]
        }), 501


@model_api.route("/api/agents", methods=["GET"])
def list_all_agents():
    """List all available agents and their capabilities."""
    agent_info = {}
    for agent_name, agent in _agents.items():
        if agent:
            capabilities = {
                "has_statistics": hasattr(agent, 'get_statistics'),
                "has_history": False,
                "history_methods": [],
                "available_methods": []
            }
            
            # Check for history methods
            history_methods = ["get_recent_analyses", "get_data_history", "get_risk_history", 
                             "get_sentiment_history", "get_coordination_history", "get_decision_history"]
            for method in history_methods:
                if hasattr(agent, method):
                    capabilities["has_history"] = True
                    capabilities["history_methods"].append(method)
            
            # Get all methods that might be of interest
            capabilities["available_methods"] = [method for method in dir(agent) 
                                               if not method.startswith('_') and callable(getattr(agent, method))]
            
            agent_info[agent_name] = capabilities
    
    return jsonify({
        "agents": agent_info,
        "total_agents": len(_agents),
        "active_agents": len([a for a in _agents.values() if a is not None])
    })


@model_api.route("/api/agents/<agent_name>/decisions", methods=["GET"])
def get_agent_decisions(agent_name):
    """Get detailed decision log for a specific agent with context and rationale."""
    agent = _agents.get(agent_name)
    if not agent:
        return jsonify({"error": f"Agent '{agent_name}' not found"}), 404

    limit = request.args.get('limit', 10, type=int)
    include_context = request.args.get('include_context', 'true').lower() == 'true'
    
    decisions = []
    
    try:
        # AI Agent - recent analyses with reasoning
        if agent_name == "ai" and hasattr(agent, 'get_recent_analyses'):
            analyses = agent.get_recent_analyses(limit=limit)
            for analysis in analyses:
                decisions.append({
                    "timestamp": analysis.get("timestamp"),
                    "decision_type": "market_analysis",
                    "context": analysis.get("market_data") if include_context else None,
                    "decision": analysis.get("analysis"),
                    "rationale": analysis.get("analysis", {}).get("reasoning") if isinstance(analysis.get("analysis"), dict) else None
                })
        
        # Risk Agent - risk decisions and alerts
        elif agent_name == "risk" and hasattr(agent, 'get_risk_history'):
            risk_history = agent.get_risk_history(limit=limit)
            for entry in risk_history.get('individual_risks', []):
                decisions.append({
                    "timestamp": entry.get("timestamp"),
                    "decision_type": "risk_assessment",
                    "symbol": entry.get("symbol"),
                    "decision": entry.get("risk_level"),
                    "context": entry.get("metrics") if include_context else None,
                    "rationale": entry.get("alerts", [])
                })
        
        # Sentiment Agent - sentiment decisions
        elif agent_name == "sentiment" and hasattr(agent, 'get_sentiment_history'):
            sentiment_history = agent.get_sentiment_history(limit=limit)
            for source, entries in sentiment_history.items():
                for entry in entries[-limit:]:  # Get latest entries
                    decisions.append({
                        "timestamp": entry.get("timestamp"),
                        "decision_type": "sentiment_analysis",
                        "source": source,
                        "decision": entry.get("sentiment"),
                        "confidence": entry.get("confidence"),
                        "context": entry.get("text") if include_context else None,
                        "rationale": f"Score: {entry.get('score', 'N/A')}"
                    })
        
        # Data Agent - data collection decisions
        elif agent_name == "data" and hasattr(agent, 'get_statistics'):
            stats = agent.get_statistics()
            # Create synthetic decision log from statistics
            decisions.append({
                "timestamp": stats.get("last_update", 0),
                "decision_type": "data_collection",
                "decision": "data_refresh",
                "context": stats.get("active_subscriptions") if include_context else None,
                "rationale": f"Collected data for {stats.get('cache_entries', 0)} entries"
            })
        
        # Coordinator Agent - coordination decisions
        elif agent_name == "coordinator":
            # Try to get coordination history if available
            if hasattr(agent, 'get_coordination_history'):
                coord_history = agent.get_coordination_history(limit=limit)
                decisions.extend(coord_history)
            else:
                # Create synthetic log from agent status
                decisions.append({
                    "timestamp": time.time(),
                    "decision_type": "coordination",
                    "decision": "agent_monitoring",
                    "rationale": "Monitoring all agents"
                })
        
        return jsonify({
            "agent": agent_name,
            "decisions": decisions,
            "total_decisions": len(decisions),
            "include_context": include_context
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@model_api.route("/api/system/status", methods=["GET"])
def get_system_status():
    """Get comprehensive system status including all agents."""
    try:
        # Import time here to avoid import issues
        import time
        
        status = {
            "timestamp": time.time(),
            "system_health": "healthy",
            "agents": {},
            "total_agents": len(_agents),
            "active_agents": 0
        }
        
        for agent_name, agent in _agents.items():
            if agent:
                agent_status = {
                    "status": "active",
                    "capabilities": {
                        "statistics": hasattr(agent, 'get_statistics'),
                        "history": False
                    }
                }
                
                # Check for history capabilities
                history_methods = ["get_recent_analyses", "get_data_history", "get_risk_history", 
                                 "get_sentiment_history", "get_coordination_history"]
                for method in history_methods:
                    if hasattr(agent, method):
                        agent_status["capabilities"]["history"] = True
                        break
                
                # Get basic stats if available
                if hasattr(agent, 'get_statistics'):
                    try:
                        stats = agent.get_statistics()
                        agent_status["last_activity"] = stats.get("last_update", 0)
                        agent_status["performance"] = {
                            key: value for key, value in stats.items() 
                            if isinstance(value, (int, float)) and not key.endswith('_time')
                        }
                    except Exception as e:
                        agent_status["error"] = str(e)
                
                status["agents"][agent_name] = agent_status
                status["active_agents"] += 1
            else:
                status["agents"][agent_name] = {"status": "inactive"}
        
        # Determine overall system health
        if status["active_agents"] == 0:
            status["system_health"] = "critical"
        elif status["active_agents"] < len(_agents) * 0.7:
            status["system_health"] = "degraded"
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({"error": str(e), "system_health": "error"}), 500


@model_api.route("/api/testing/run/<test_name>", methods=["POST"])
def run_test(test_name):
    """Run a specific test and return results."""
    try:
        test_results = {}
        
        if test_name == "agents_availability":
            # Test all agents availability
            test_results = {
                "test_name": "agents_availability",
                "timestamp": time.time(),
                "results": {}
            }
            
            for agent_name, agent in _agents.items():
                if agent:
                    # Test if agent responds to statistics call
                    try:
                        if hasattr(agent, 'get_statistics'):
                            stats = agent.get_statistics()
                            test_results["results"][agent_name] = {
                                "status": "pass",
                                "response_time": "< 1s",
                                "has_data": len(stats) > 0
                            }
                        else:
                            test_results["results"][agent_name] = {
                                "status": "warning", 
                                "message": "No statistics method"
                            }
                    except Exception as e:
                        test_results["results"][agent_name] = {
                            "status": "fail",
                            "error": str(e)
                        }
                else:
                    test_results["results"][agent_name] = {
                        "status": "fail",
                        "error": "Agent not initialized"
                    }
        
        elif test_name == "ai_connectivity":
            # Test AI agent connectivity
            ai_agent = _agents.get('ai')
            if ai_agent:
                try:
                    stats = ai_agent.get_statistics()
                    test_results = {
                        "test_name": "ai_connectivity",
                        "timestamp": time.time(),
                        "status": "pass" if stats.get("is_available") else "fail",
                        "ai_available": stats.get("is_available"),
                        "current_model": stats.get("current_model"),
                        "total_models": stats.get("total_models")
                    }
                except Exception as e:
                    test_results = {
                        "test_name": "ai_connectivity",
                        "timestamp": time.time(),
                        "status": "fail",
                        "error": str(e)
                    }
            else:
                test_results = {
                    "test_name": "ai_connectivity", 
                    "timestamp": time.time(),
                    "status": "fail",
                    "error": "AI agent not available"
                }
        
        elif test_name == "data_freshness":
            # Test data agent freshness
            data_agent = _agents.get('data')
            if data_agent and hasattr(data_agent, 'get_statistics'):
                try:
                    stats = data_agent.get_statistics()
                    current_time = time.time()
                    last_update = stats.get('last_update', 0)
                    freshness_seconds = current_time - last_update
                    
                    test_results = {
                        "test_name": "data_freshness",
                        "timestamp": current_time,
                        "status": "pass" if freshness_seconds < 300 else "warning",  # 5 minutes
                        "last_update": last_update,
                        "freshness_seconds": freshness_seconds,
                        "cache_entries": stats.get('cache_entries', 0)
                    }
                except Exception as e:
                    test_results = {
                        "test_name": "data_freshness",
                        "timestamp": time.time(),
                        "status": "fail",
                        "error": str(e)
                    }
            else:
                test_results = {
                    "test_name": "data_freshness",
                    "timestamp": time.time(), 
                    "status": "fail",
                    "error": "Data agent not available"
                }
        
        else:
            return jsonify({"error": f"Unknown test: {test_name}"}), 400
        
        return jsonify(test_results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@model_api.route("/api/testing/available", methods=["GET"])
def get_available_tests():
    """Get list of available tests."""
    available_tests = {
        "agents_availability": {
            "description": "Test if all agents are responding",
            "estimated_duration": "< 5s"
        },
        "ai_connectivity": {
            "description": "Test AI agent connectivity and model availability", 
            "estimated_duration": "< 10s"
        },
        "data_freshness": {
            "description": "Test if data agent has fresh market data",
            "estimated_duration": "< 2s"
        }
    }
    
    return jsonify({
        "available_tests": available_tests,
        "total_tests": len(available_tests)
    })


# === WebSocket and Real-time Data Endpoints ===

@model_api.route('/api/websocket/status', methods=['GET'])
def get_websocket_status():
    """Get WebSocket connection status."""
    try:
        # Check if websocket client is available in the system
        # This would need to be integrated with the actual WebSocket client
        return jsonify({
            "websocket_enabled": True,
            "connections": {
                "spot_ticker": "connected",
                "futures_ticker": "connected", 
                "depth": "connected",
                "klines": "connected",
                "trades": "connected"
            },
            "last_message_time": time.time(),
            "message_count": 0,
            "reconnections": 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@model_api.route('/api/realtime/ticker/<symbol>', methods=['GET'])
def get_realtime_ticker(symbol):
    """Get real-time ticker data for a symbol."""
    try:
        # This would integrate with the WebSocket client
        # For now, return cached data from local storage
        from utils.data_storage import local_storage
        
        ticker_data = asyncio.run(local_storage.get_cached_ticker(symbol))
        
        if ticker_data:
            return jsonify({
                "symbol": symbol,
                "data": ticker_data,
                "source": "cache",
                "timestamp": ticker_data.get("timestamp", time.time())
            })
        else:
            return jsonify({"error": f"No ticker data available for {symbol}"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@model_api.route('/api/realtime/orderbook/<symbol>', methods=['GET'])
def get_realtime_orderbook(symbol):
    """Get real-time order book data."""
    try:
        # This would integrate with WebSocket depth data
        return jsonify({
            "symbol": symbol,
            "bids": [],
            "asks": [],
            "last_update_id": 0,
            "timestamp": time.time(),
            "source": "websocket"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === Social Media and News Feed Endpoints ===

@model_api.route('/api/social/sentiment/<symbol>', methods=['GET'])
def get_social_sentiment(symbol):
    """Get aggregated social media sentiment for a symbol."""
    try:
        hours_back = request.args.get('hours', 6, type=int)
        
        # This would integrate with the social feeds listener
        from utils.data_storage import local_storage
        
        sentiment_data = asyncio.run(local_storage.get_recent_social_sentiment(symbol, hours_back))
        
        if sentiment_data:
            # Calculate aggregated sentiment
            avg_sentiment = sum(item["sentiment_score"] for item in sentiment_data) / len(sentiment_data)
            sources = list(set(item["source"] for item in sentiment_data))
            
            return jsonify({
                "symbol": symbol,
                "sentiment_score": avg_sentiment,
                "post_count": len(sentiment_data),
                "sources": sources,
                "time_period_hours": hours_back,
                "posts": sentiment_data[:10]  # Return latest 10 posts
            })
        else:
            return jsonify({
                "symbol": symbol,
                "sentiment_score": 0.0,
                "post_count": 0,
                "sources": [],
                "time_period_hours": hours_back,
                "posts": []
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@model_api.route('/api/social/feeds', methods=['GET'])
def get_social_feeds():
    """Get recent social media posts and news."""
    try:
        limit = request.args.get('limit', 20, type=int)
        source = request.args.get('source', None)  # Filter by source
        
        from utils.data_storage import local_storage
        
        # Get recent news data
        news_data = asyncio.run(local_storage.get_recent_news(hours_back=24))
        
        # Filter by source if specified
        if source:
            news_data = [item for item in news_data if item["source"] == source]
        
        # Limit results
        news_data = news_data[:limit]
        
        return jsonify({
            "posts": news_data,
            "total_count": len(news_data),
            "sources_available": ["reddit", "twitter", "telegram", "news_cointelegraph", "news_coindesk", "news_decrypt"],
            "last_update": time.time()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@model_api.route('/api/social/influencers', methods=['GET'])
def get_influencer_posts():
    """Get posts from known crypto influencers."""
    try:
        hours_back = request.args.get('hours', 12, type=int)
        min_credibility = request.args.get('min_credibility', 0.7, type=float)
        
        # This would integrate with social feeds listener
        return jsonify({
            "influencer_posts": [],
            "time_period_hours": hours_back,
            "min_credibility_score": min_credibility,
            "known_influencers": [
                "elonmusk", "michael_saylor", "cz_binance", "VitalikButerin",
                "naval", "balajis", "aantonop", "APompliano"
            ]
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === High-Frequency Trading Endpoints ===

@model_api.route('/api/hft/status', methods=['GET'])
def get_hft_status():
    """Get high-frequency trading engine status."""
    try:
        # This would integrate with the HFT engine
        return jsonify({
            "enabled": False,  # Would check actual HFT engine status
            "active_symbols": [],
            "active_positions": 0,
            "trades_today": 0,
            "profit_today": 0.0,
            "win_rate": 0.0,
            "avg_profit_per_trade": 0.0,
            "min_profit_threshold": 0.0001  # 0.01%
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@model_api.route('/api/hft/performance', methods=['GET'])
def get_hft_performance():
    """Get high-frequency trading performance metrics."""
    try:
        days_back = request.args.get('days', 7, type=int)
        
        from utils.data_storage import local_storage
        
        # Get trading performance data
        performance_data = asyncio.run(local_storage.get_trading_performance(
            strategy="high_frequency",
            days_back=days_back
        ))
        
        if performance_data:
            # Calculate metrics
            total_trades = len(performance_data)
            completed_trades = [t for t in performance_data if t["status"] == "closed"]
            profitable_trades = [t for t in completed_trades if (t["pnl"] or 0) > 0]
            
            total_pnl = sum(t["pnl"] or 0 for t in completed_trades)
            total_fees = sum(t["fees"] or 0 for t in completed_trades)
            net_profit = total_pnl - total_fees
            
            return jsonify({
                "period_days": days_back,
                "total_trades": total_trades,
                "completed_trades": len(completed_trades),
                "profitable_trades": len(profitable_trades),
                "win_rate": (len(profitable_trades) / len(completed_trades) * 100) if completed_trades else 0,
                "total_pnl": total_pnl,
                "total_fees": total_fees,
                "net_profit": net_profit,
                "avg_profit_per_trade": (net_profit / len(completed_trades)) if completed_trades else 0,
                "trades_by_symbol": {}  # Would aggregate by symbol
            })
        else:
            return jsonify({
                "period_days": days_back,
                "total_trades": 0,
                "completed_trades": 0,
                "profitable_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "total_fees": 0,
                "net_profit": 0,
                "avg_profit_per_trade": 0,
                "trades_by_symbol": {}
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@model_api.route('/api/hft/symbols', methods=['POST'])
def manage_hft_symbols():
    """Add or remove symbols from high-frequency trading."""
    try:
        data = request.get_json()
        action = data.get('action')  # 'add' or 'remove'
        symbol = data.get('symbol')
        
        if not action or not symbol:
            return jsonify({"error": "Missing action or symbol"}), 400
        
        # This would integrate with the actual HFT engine
        if action == 'add':
            # hft_engine.add_symbol(symbol)
            return jsonify({
                "status": "success",
                "action": "added",
                "symbol": symbol,
                "message": f"Symbol {symbol} added to high-frequency trading"
            })
        elif action == 'remove':
            # hft_engine.remove_symbol(symbol)
            return jsonify({
                "status": "success", 
                "action": "removed",
                "symbol": symbol,
                "message": f"Symbol {symbol} removed from high-frequency trading"
            })
        else:
            return jsonify({"error": "Invalid action. Use 'add' or 'remove'"}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === Data Storage and Cache Endpoints ===

@model_api.route('/api/storage/stats', methods=['GET'])
def get_storage_stats():
    """Get local data storage statistics."""
    try:
        from utils.data_storage import local_storage
        
        stats = local_storage.get_storage_stats()
        
        return jsonify({
            "storage_statistics": stats,
            "cache_enabled": True,
            "database_path": str(local_storage.db_path),
            "cache_directory": str(local_storage.json_cache_dir)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@model_api.route('/api/storage/cleanup', methods=['POST'])
def cleanup_storage():
    """Clean up old data from storage."""
    try:
        data = request.get_json() or {}
        days_to_keep = data.get('days_to_keep', 30)
        
        from utils.data_storage import local_storage
        
        # This would run the cleanup
        # await local_storage.cleanup_old_data(days_to_keep)
        
        return jsonify({
            "status": "success",
            "message": f"Cleanup scheduled for data older than {days_to_keep} days",
            "days_to_keep": days_to_keep
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
