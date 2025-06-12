import asyncio
import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request

from models.tabular_model import TabularTradingModel, prepare_features
from rl.agent import RLTradingAgent

# Global reference to AI agent (will be set by main app)
_ai_agent = None

def set_ai_agent(ai_agent):
    """Set the global AI agent reference."""
    global _ai_agent
    _ai_agent = ai_agent

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
    if not _ai_agent:
        return jsonify({"error": "AI agent not available", "models": []}), 503
    
    try:
        model_info = _ai_agent.get_model_info()
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
    if not _ai_agent:
        return jsonify({"error": "AI agent not available"}), 503
    
    try:
        # Run async method in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_ai_agent.force_model_check())
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@model_api.route("/ai/status", methods=["GET"])
def get_ai_status():
    """Get comprehensive AI agent status."""
    if not _ai_agent:
        return jsonify({
            "error": "AI agent not available",
            "is_available": False,
            "current_model": None,
            "available_models": []
        }), 503
    
    try:
        stats = _ai_agent.get_statistics()
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
    if not _ai_agent:
        return jsonify({"error": "AI agent not available"}), 503
    
    try:
        _ai_agent.reset_model_change_flag()
        return jsonify({"success": True, "message": "Model change flag reset"})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500
