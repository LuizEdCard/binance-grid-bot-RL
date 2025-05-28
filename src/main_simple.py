#!/usr/bin/env python3
# Backend API simplificado usando Flask

from flask import Flask, jsonify, request
from flask_cors import CORS
import yaml
import os
import sys

# Ensure the src directory is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Configuração Inicial
app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

# Carregar configuração
config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")
try:
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    print(f"Configuração carregada: {config_path}")
except Exception as e:
    print(f"Erro ao carregar config: {e}")
    config = {}

# Variáveis globais simplificadas
bots = {}
bot_threads = {}

# --- Rotas da API ---

@app.route("/", methods=["GET"])
def home():
    """Rota inicial para testar se a API está funcionando."""
    return jsonify({
        "message": "Backend Flask API está funcionando!",
        "status": "online",
        "version": "1.0.0"
    })

@app.route("/api/status", methods=["GET"])
def get_status():
    """Retorna o status geral da API e dos bots ativos."""
    active_bots_status = {
        symbol: "active" for symbol in bots.keys()
    }
    return jsonify({
        "api_status": "online", 
        "active_bots": active_bots_status,
        "config_loaded": bool(config)
    })

@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check simplificado."""
    return jsonify({
        "status": "healthy",
        "timestamp": "2025-05-28T15:20:00Z"
    })

@app.route("/api/market_data", methods=["GET"])
def get_market_data():
    """Retorna dados de mercado simulados (sem Binance por enquanto)."""
    try:
        # Dados simulados por enquanto
        mock_data = [
            {"symbol": "BTCUSDT", "price": "67500.00", "volume": "1234.56"},
            {"symbol": "ETHUSDT", "price": "3400.00", "volume": "5678.90"},
            {"symbol": "ADAUSDT", "price": "0.45", "volume": "9876.54"}
        ]
        return jsonify({
            "data": mock_data,
            "message": "Dados simulados - Binance API não inicializada"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/grid/config", methods=["POST"])
def configure_grid():
    """Recebe a configuração da grade do frontend."""
    try:
        data = request.json
        symbol = data.get("symbol")
        grid_config = data.get("config")

        if not symbol or not grid_config:
            return jsonify({"error": "Símbolo e configuração são obrigatórios"}), 400

        print(f"Configuração recebida para {symbol}: {grid_config}")
        
        return jsonify({
            "message": f"Configuração para {symbol} recebida com sucesso.",
            "received_config": grid_config,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Inicialização do Servidor
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Iniciando Backend Flask API Simplificado...")
    print(f"📁 Diretório: {os.getcwd()}")
    print(f"🐍 Python: {sys.version}")
    print(f"⚙️  Config carregada: {bool(config)}")
    print("🌐 Acesse: http://127.0.0.1:8080")
    print("📊 Status: http://127.0.0.1:8080/api/status")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=8080, debug=False)