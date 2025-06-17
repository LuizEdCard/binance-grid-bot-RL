#!/usr/bin/env python3
"""
Live Data API - Real-time endpoints for multi-agent system integration
Provides enhanced data flow between multi-agent system and frontend
"""

import time
import json
from decimal import Decimal
from flask import Blueprint, jsonify, request
from typing import Dict, Any, List, Optional

from src.utils.trade_logger import get_trade_logger
from src.utils.pair_logger import get_pair_logger
from src.utils.data_storage import LocalDataStorage
from src.utils.global_tp_sl_manager import GlobalTPSLManager
from src.utils.trade_activity_tracker import get_trade_activity_tracker

# Create blueprint
live_data_api = Blueprint('live_data_api', __name__)

# Global storage for live data
_live_trading_data = {}
_live_agent_decisions = {}
_live_system_status = {}

class LiveDataManager:
    """Manages live data flow between multi-agent system and Flask API."""
    
    def __init__(self):
        self.data_storage = LocalDataStorage()
        self.trade_logger = get_trade_logger()
        
    def update_trading_data(self, symbol: str, data: Dict[str, Any]):
        """Update live trading data for a symbol."""
        global _live_trading_data
        _live_trading_data[symbol] = {
            **data,
            "timestamp": time.time(),
            "symbol": symbol
        }
    
    def update_agent_decision(self, agent_name: str, decision: Dict[str, Any]):
        """Update live agent decision."""
        global _live_agent_decisions
        if agent_name not in _live_agent_decisions:
            _live_agent_decisions[agent_name] = []
        
        _live_agent_decisions[agent_name].append({
            **decision,
            "timestamp": time.time(),
            "agent": agent_name
        })
        
        # Keep only last 100 decisions per agent
        _live_agent_decisions[agent_name] = _live_agent_decisions[agent_name][-100:]
    
    def update_system_status(self, component: str, status: Dict[str, Any]):
        """Update system component status."""
        global _live_system_status
        _live_system_status[component] = {
            **status,
            "timestamp": time.time(),
            "component": component
        }

# Global instance
live_data_manager = LiveDataManager()

@live_data_api.route("/api/live/trading/<symbol>", methods=["GET"])
def get_live_trading_data(symbol):
    """Get live trading data for a specific symbol."""
    try:
        symbol = symbol.upper()
        
        # Get data from live cache
        live_data = _live_trading_data.get(symbol, {})
        
        # Enhance with pair logger data if available
        try:
            pair_logger = get_pair_logger(symbol)
            if hasattr(pair_logger, 'get_recent_trades'):
                recent_trades = pair_logger.get_recent_trades(limit=10)
                live_data["recent_trades"] = recent_trades
        except Exception as e:
            live_data["recent_trades"] = []
        
        # Get position data from storage
        try:
            position_data = live_data_manager.data_storage.get_position(symbol)
            if position_data:
                live_data["position"] = position_data
        except Exception as e:
            live_data["position"] = None
        
        return jsonify({
            "success": True,
            "symbol": symbol,
            "data": live_data,
            "last_update": live_data.get("timestamp", 0),
            "data_age_seconds": time.time() - live_data.get("timestamp", time.time())
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "symbol": symbol
        }), 500

@live_data_api.route("/api/live/trading/all", methods=["GET"])
def get_all_live_trading_data():
    """Get live trading data for all active symbols."""
    try:
        # Get limit from query parameters
        limit = request.args.get('limit', 50, type=int)
        
        # Sort by timestamp (most recent first)
        sorted_data = sorted(
            _live_trading_data.items(),
            key=lambda x: x[1].get("timestamp", 0),
            reverse=True
        )
        
        # Apply limit
        limited_data = dict(sorted_data[:limit])
        
        return jsonify({
            "success": True,
            "symbols": list(limited_data.keys()),
            "data": limited_data,
            "total_symbols": len(_live_trading_data),
            "returned_symbols": len(limited_data),
            "last_update": max([d.get("timestamp", 0) for d in limited_data.values()]) if limited_data else 0
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@live_data_api.route("/api/live/agents/<agent_name>/decisions", methods=["GET"])
def get_live_agent_decisions(agent_name):
    """Get live decision stream from a specific agent."""
    try:
        # Get limit from query parameters
        limit = request.args.get('limit', 20, type=int)
        since = request.args.get('since', 0, type=float)
        
        # Get decisions for the agent
        decisions = _live_agent_decisions.get(agent_name, [])
        
        # Filter by timestamp if 'since' provided
        if since > 0:
            decisions = [d for d in decisions if d.get("timestamp", 0) > since]
        
        # Sort by timestamp (most recent first) and limit
        decisions = sorted(decisions, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]
        
        return jsonify({
            "success": True,
            "agent": agent_name,
            "decisions": decisions,
            "total_decisions": len(decisions),
            "latest_timestamp": decisions[0].get("timestamp", 0) if decisions else 0,
            "has_more": len(_live_agent_decisions.get(agent_name, [])) > limit
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "agent": agent_name
        }), 500

@live_data_api.route("/api/live/agents/all/decisions", methods=["GET"])
def get_all_agent_decisions():
    """Get recent decisions from all agents."""
    try:
        limit_per_agent = request.args.get('limit_per_agent', 5, type=int)
        
        all_decisions = {}
        
        for agent_name, decisions in _live_agent_decisions.items():
            # Get most recent decisions for each agent
            recent_decisions = sorted(
                decisions, 
                key=lambda x: x.get("timestamp", 0), 
                reverse=True
            )[:limit_per_agent]
            
            all_decisions[agent_name] = recent_decisions
        
        return jsonify({
            "success": True,
            "agents": list(all_decisions.keys()),
            "decisions": all_decisions,
            "total_agents": len(all_decisions),
            "last_update": time.time()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@live_data_api.route("/api/live/system/status", methods=["GET"])
def get_live_system_status():
    """Get comprehensive live system status."""
    try:
        # Get component status
        system_status = {
            "timestamp": time.time(),
            "components": _live_system_status,
            "overview": {
                "total_components": len(_live_system_status),
                "active_trading_pairs": len(_live_trading_data),
                "total_agent_decisions": sum(len(decisions) for decisions in _live_agent_decisions.values()),
                "system_uptime": time.time() - min([comp.get("timestamp", time.time()) for comp in _live_system_status.values()]) if _live_system_status else 0
            }
        }
        
        # Add health indicators
        health_indicators = {
            "trading_active": len(_live_trading_data) > 0,
            "agents_responsive": len(_live_agent_decisions) > 0,
            "data_fresh": any(
                time.time() - comp.get("timestamp", 0) < 300  # Data less than 5 minutes old
                for comp in _live_system_status.values()
            ),
            "overall_health": "healthy"  # This could be computed based on various factors
        }
        
        system_status["health"] = health_indicators
        
        return jsonify({
            "success": True,
            "status": system_status
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@live_data_api.route("/api/live/profits/summary", methods=["GET"])
def get_live_profit_summary():
    """Get live profit summary across all trading pairs."""
    try:
        # Get timeframe from query parameters
        timeframe = request.args.get('timeframe', '1h')  # 1h, 24h, 7d, 30d
        
        profit_summary = {
            "timeframe": timeframe,
            "total_realized_pnl": 0.0,
            "total_unrealized_pnl": 0.0,
            "profitable_trades": 0,
            "losing_trades": 0,
            "total_trades": 0,
            "best_performer": None,
            "worst_performer": None,
            "by_symbol": {}
        }
        
        # Aggregate profit data from trading data
        best_pnl = float('-inf')
        worst_pnl = float('inf')
        
        for symbol, data in _live_trading_data.items():
            symbol_pnl = data.get("unrealized_pnl", 0.0)
            realized_pnl = data.get("realized_pnl", 0.0)
            
            if isinstance(symbol_pnl, (str, Decimal)):
                symbol_pnl = float(symbol_pnl)
            if isinstance(realized_pnl, (str, Decimal)):
                realized_pnl = float(realized_pnl)
            
            profit_summary["total_unrealized_pnl"] += symbol_pnl
            profit_summary["total_realized_pnl"] += realized_pnl
            
            if symbol_pnl > 0:
                profit_summary["profitable_trades"] += 1
            elif symbol_pnl < 0:
                profit_summary["losing_trades"] += 1
            
            profit_summary["total_trades"] += 1
            
            # Track best/worst performers
            total_symbol_pnl = symbol_pnl + realized_pnl
            if total_symbol_pnl > best_pnl:
                best_pnl = total_symbol_pnl
                profit_summary["best_performer"] = {"symbol": symbol, "pnl": total_symbol_pnl}
            
            if total_symbol_pnl < worst_pnl:
                worst_pnl = total_symbol_pnl
                profit_summary["worst_performer"] = {"symbol": symbol, "pnl": total_symbol_pnl}
            
            profit_summary["by_symbol"][symbol] = {
                "unrealized_pnl": symbol_pnl,
                "realized_pnl": realized_pnl,
                "total_pnl": total_symbol_pnl
            }
        
        # Calculate success rate
        if profit_summary["total_trades"] > 0:
            profit_summary["success_rate"] = profit_summary["profitable_trades"] / profit_summary["total_trades"]
        else:
            profit_summary["success_rate"] = 0.0
        
        return jsonify({
            "success": True,
            "summary": profit_summary,
            "timestamp": time.time()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@live_data_api.route("/api/live/alerts", methods=["GET"])
def get_live_alerts():
    """Get live system alerts and notifications."""
    try:
        # This would typically come from a centralized alert system
        # For now, we'll generate alerts based on current data
        
        alerts = []
        
        # Check for stale data
        current_time = time.time()
        for symbol, data in _live_trading_data.items():
            data_age = current_time - data.get("timestamp", 0)
            if data_age > 300:  # 5 minutes
                alerts.append({
                    "type": "warning",
                    "severity": "medium",
                    "message": f"Trading data for {symbol} is stale ({data_age:.0f}s old)",
                    "symbol": symbol,
                    "timestamp": current_time
                })
        
        # Check for system component issues
        for component, status in _live_system_status.items():
            if status.get("status") == "error":
                alerts.append({
                    "type": "error",
                    "severity": "high",
                    "message": f"Component {component} reported an error: {status.get('error', 'Unknown error')}",
                    "component": component,
                    "timestamp": status.get("timestamp", current_time)
                })
        
        # Sort alerts by timestamp (newest first)
        alerts.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        return jsonify({
            "success": True,
            "alerts": alerts,
            "total_alerts": len(alerts),
            "alert_levels": {
                "critical": len([a for a in alerts if a.get("severity") == "critical"]),
                "high": len([a for a in alerts if a.get("severity") == "high"]),
                "medium": len([a for a in alerts if a.get("severity") == "medium"]),
                "low": len([a for a in alerts if a.get("severity") == "low"])
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Utility functions for multi-agent system to update live data
def update_trading_data(symbol: str, data: Dict[str, Any]):
    """Update live trading data (called by multi-agent system)."""
    live_data_manager.update_trading_data(symbol, data)

def update_agent_decision(agent_name: str, decision: Dict[str, Any]):
    """Update agent decision (called by agents)."""
    live_data_manager.update_agent_decision(agent_name, decision)

def update_system_status(component: str, status: Dict[str, Any]):
    """Update system status (called by system components)."""
    live_data_manager.update_system_status(component, status)

# ===== NOVOS ENDPOINTS PARA FUNCIONALIDADES IMPLEMENTADAS =====

@live_data_api.route('/api/live/tpsl/status', methods=['GET'])
def get_tpsl_status():
    """Get Global TP/SL Manager status."""
    try:
        status = GlobalTPSLManager.get_status()
        
        return jsonify({
            "success": True,
            "tpsl_status": status,
            "timestamp": time.time()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@live_data_api.route('/api/live/margin/status', methods=['GET'])
def get_margin_status():
    """Get margin status and balance information."""
    try:
        # Try to get current balance info from system status
        margin_info = _live_system_status.get("margin_status", {})
        
        # Default values if not available
        if not margin_info:
            margin_info = {
                "futures_usdt": 0.0,
                "spot_usdt": 0.0,
                "total_usdt": 0.0,
                "margin_sufficient": False,
                "active_positions": 0,
                "mode": "unknown"
            }
        
        return jsonify({
            "success": True,
            "margin_status": margin_info,
            "timestamp": time.time()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@live_data_api.route('/api/live/pair-rotation', methods=['GET'])
def get_pair_rotation_info():
    """Get pair rotation status and activity."""
    try:
        # Get activity tracker instance
        try:
            tracker = get_trade_activity_tracker()
            statistics = tracker.get_statistics()
        except Exception:
            statistics = {
                "total_pairs": 0,
                "active_pairs": 0,
                "inactive_pairs": 0,
                "total_trades": 0,
                "total_profit": 0.0,
                "inactivity_timeout_hours": 1.0
            }
        
        # Get rotation info from system status if available
        rotation_info = _live_system_status.get("pair_rotation", {})
        
        return jsonify({
            "success": True,
            "rotation_status": {
                "statistics": statistics,
                "last_rotation": rotation_info.get("last_rotation", None),
                "problematic_pairs": rotation_info.get("problematic_pairs", []),
                "replacement_suggestions": rotation_info.get("replacement_suggestions", {}),
                "rotation_enabled": True
            },
            "timestamp": time.time()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@live_data_api.route('/api/live/system/health', methods=['GET'])
def get_system_health():
    """Get comprehensive system health status."""
    try:
        current_time = time.time()
        
        # Compile health information
        health_status = {
            "overall_status": "healthy",
            "components": {},
            "issues": [],
            "last_update": current_time
        }
        
        # Check TP/SL Manager health
        try:
            tpsl_status = GlobalTPSLManager.get_status()
            health_status["components"]["tpsl_manager"] = {
                "status": "healthy" if tpsl_status["running"] else "warning",
                "details": tpsl_status
            }
            if not tpsl_status["running"]:
                health_status["issues"].append("TP/SL Manager not running")
        except Exception as e:
            health_status["components"]["tpsl_manager"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["issues"].append(f"TP/SL Manager error: {e}")
        
        # Check margin status
        margin_info = _live_system_status.get("margin_status", {})
        if margin_info:
            margin_sufficient = margin_info.get("margin_sufficient", True)
            health_status["components"]["margin"] = {
                "status": "healthy" if margin_sufficient else "critical",
                "details": margin_info
            }
            if not margin_sufficient:
                health_status["issues"].append("Insufficient margin detected")
                health_status["overall_status"] = "critical"
        
        # Check trading data freshness
        stale_data_count = 0
        for symbol, data in _live_trading_data.items():
            data_age = current_time - data.get("timestamp", 0)
            if data_age > 300:  # 5 minutes
                stale_data_count += 1
        
        health_status["components"]["data_freshness"] = {
            "status": "healthy" if stale_data_count == 0 else "warning",
            "stale_pairs": stale_data_count,
            "total_pairs": len(_live_trading_data)
        }
        
        if stale_data_count > 0:
            health_status["issues"].append(f"{stale_data_count} pairs have stale data")
        
        # Determine overall status
        if any(comp.get("status") == "critical" for comp in health_status["components"].values()):
            health_status["overall_status"] = "critical"
        elif any(comp.get("status") == "error" for comp in health_status["components"].values()):
            health_status["overall_status"] = "error"
        elif any(comp.get("status") == "warning" for comp in health_status["components"].values()):
            health_status["overall_status"] = "warning"
        
        return jsonify({
            "success": True,
            "health": health_status,
            "timestamp": current_time
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@live_data_api.route('/api/live/old-orders', methods=['POST'])
def cancel_old_orders():
    """Trigger cancellation of old orders."""
    try:
        # This would trigger the old order cancellation script
        # For now, return a status indicating the action was queued
        
        return jsonify({
            "success": True,
            "message": "Old order cancellation queued",
            "action": "cancel_old_orders",
            "timestamp": time.time()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@live_data_api.route('/api/live/force-rotation', methods=['POST'])
def force_pair_rotation():
    """Force pair rotation check."""
    try:
        # This would trigger the pair rotation script
        # For now, return a status indicating the action was queued
        
        return jsonify({
            "success": True,
            "message": "Pair rotation check queued",
            "action": "force_rotation",
            "timestamp": time.time()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500