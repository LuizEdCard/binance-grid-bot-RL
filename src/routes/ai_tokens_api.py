#!/usr/bin/env python3
"""
API para monitoramento de tokens usados pela IA local (Ollama)
"""

from flask import Flask, jsonify, request
import time
import threading
import psutil
import requests
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional

from utils.logger import setup_logger

log = setup_logger("ai_tokens_api")


class AITokensMonitor:
    """Monitor de tokens e uso da IA local."""
    
    def __init__(self, ollama_base_url: str = "http://127.0.0.1:11434"):
        self.ollama_url = ollama_base_url
        
        # Estatísticas de tokens
        self.token_stats = {
            "total_tokens_used": 0,
            "tokens_per_minute": deque(maxlen=60),  # Últimos 60 minutos
            "tokens_per_hour": deque(maxlen=24),    # Últimas 24 horas
            "requests_count": 0,
            "models_used": defaultdict(int),
            "tokens_by_model": defaultdict(int),
            "session_start": time.time()
        }
        
        # Histórico de requests
        self.request_history = deque(maxlen=1000)  # Últimos 1000 requests
        
        # Sistema
        self.system_stats = {
            "cpu_usage": [],
            "memory_usage": [],
            "gpu_usage": None  # Para futuro suporte GPU
        }
        
        # Thread para monitoramento
        self.monitoring = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Inicia monitoramento contínuo."""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            log.info("AI Tokens monitoring started")
    
    def stop_monitoring(self):
        """Para monitoramento."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        log.info("AI Tokens monitoring stopped")
    
    def _monitor_loop(self):
        """Loop principal de monitoramento."""
        last_minute_update = 0
        last_hour_update = 0
        
        while self.monitoring:
            try:
                current_time = time.time()
                
                # Atualizar estatísticas por minuto
                if current_time - last_minute_update >= 60:
                    self._update_minute_stats()
                    last_minute_update = current_time
                
                # Atualizar estatísticas por hora
                if current_time - last_hour_update >= 3600:
                    self._update_hour_stats()
                    last_hour_update = current_time
                
                # Coletar estatísticas do sistema
                self._collect_system_stats()
                
                time.sleep(10)  # Verificar a cada 10 segundos
                
            except Exception as e:
                log.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def _update_minute_stats(self):
        """Atualiza estatísticas por minuto."""
        # Contar tokens do último minuto
        current_time = time.time()
        minute_ago = current_time - 60
        
        tokens_last_minute = sum(
            req.get('tokens_used', 0) 
            for req in self.request_history 
            if req.get('timestamp', 0) > minute_ago
        )
        
        self.token_stats['tokens_per_minute'].append({
            'timestamp': current_time,
            'tokens': tokens_last_minute
        })
    
    def _update_hour_stats(self):
        """Atualiza estatísticas por hora."""
        # Contar tokens da última hora
        current_time = time.time()
        hour_ago = current_time - 3600
        
        tokens_last_hour = sum(
            req.get('tokens_used', 0) 
            for req in self.request_history 
            if req.get('timestamp', 0) > hour_ago
        )
        
        self.token_stats['tokens_per_hour'].append({
            'timestamp': current_time,
            'tokens': tokens_last_hour
        })
    
    def _collect_system_stats(self):
        """Coleta estatísticas do sistema."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_stats['cpu_usage'].append({
                'timestamp': time.time(),
                'cpu_percent': cpu_percent
            })
            
            # Manter apenas últimas 100 amostras (10 minutos)
            if len(self.system_stats['cpu_usage']) > 100:
                self.system_stats['cpu_usage'].pop(0)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_stats['memory_usage'].append({
                'timestamp': time.time(),
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'memory_total_gb': memory.total / (1024**3)
            })
            
            # Manter apenas últimas 100 amostras
            if len(self.system_stats['memory_usage']) > 100:
                self.system_stats['memory_usage'].pop(0)
                
        except Exception as e:
            log.error(f"Error collecting system stats: {e}")
    
    def log_request(self, model: str, prompt_tokens: int, completion_tokens: int, 
                   total_tokens: int, response_time: float):
        """Registra um request da IA."""
        request_data = {
            'timestamp': time.time(),
            'model': model,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'tokens_used': total_tokens,
            'response_time': response_time
        }
        
        # Adicionar ao histórico
        self.request_history.append(request_data)
        
        # Atualizar estatísticas globais
        self.token_stats['total_tokens_used'] += total_tokens
        self.token_stats['requests_count'] += 1
        self.token_stats['models_used'][model] += 1
        self.token_stats['tokens_by_model'][model] += total_tokens
        
        log.debug(f"AI request logged: {model} - {total_tokens} tokens in {response_time:.2f}s")
    
    def get_ollama_models(self) -> List[str]:
        """Obtém lista de modelos disponíveis no Ollama."""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except Exception as e:
            log.error(f"Error getting Ollama models: {e}")
            return []
    
    def get_current_stats(self) -> Dict:
        """Retorna estatísticas atuais."""
        current_time = time.time()
        session_duration = current_time - self.token_stats['session_start']
        
        # Calcular médias
        avg_tokens_per_minute = (
            self.token_stats['total_tokens_used'] / (session_duration / 60) 
            if session_duration > 60 else 0
        )
        
        avg_tokens_per_request = (
            self.token_stats['total_tokens_used'] / self.token_stats['requests_count']
            if self.token_stats['requests_count'] > 0 else 0
        )
        
        # Últimos 10 requests
        recent_requests = list(self.request_history)[-10:] if self.request_history else []
        
        return {
            "session": {
                "start_time": datetime.fromtimestamp(self.token_stats['session_start']).isoformat(),
                "duration_minutes": session_duration / 60,
                "total_tokens": self.token_stats['total_tokens_used'],
                "total_requests": self.token_stats['requests_count'],
                "avg_tokens_per_minute": round(avg_tokens_per_minute, 2),
                "avg_tokens_per_request": round(avg_tokens_per_request, 2)
            },
            "models": {
                "available": self.get_ollama_models(),
                "used": dict(self.token_stats['models_used']),
                "tokens_by_model": dict(self.token_stats['tokens_by_model'])
            },
            "recent_activity": {
                "last_10_requests": recent_requests,
                "tokens_last_minute": sum(
                    req.get('tokens_used', 0) 
                    for req in self.request_history 
                    if req.get('timestamp', 0) > current_time - 60
                ),
                "requests_last_minute": sum(
                    1 for req in self.request_history 
                    if req.get('timestamp', 0) > current_time - 60
                )
            },
            "system": {
                "cpu_current": self.system_stats['cpu_usage'][-1]['cpu_percent'] if self.system_stats['cpu_usage'] else 0,
                "memory_current": self.system_stats['memory_usage'][-1]['memory_percent'] if self.system_stats['memory_usage'] else 0,
                "cpu_history": self.system_stats['cpu_usage'][-20:],  # Últimos 20 pontos
                "memory_history": self.system_stats['memory_usage'][-20:]
            },
            "timestamp": current_time
        }


# Instância global do monitor
ai_monitor = AITokensMonitor()


def create_ai_tokens_api(app: Optional[Flask] = None) -> Flask:
    """Cria API Flask para monitoramento de tokens da IA."""
    
    if app is None:
        app = Flask(__name__)
    
    @app.route('/api/ai-tokens/stats', methods=['GET'])
    def get_ai_stats():
        """Retorna estatísticas atuais da IA."""
        try:
            stats = ai_monitor.get_current_stats()
            return jsonify({
                "success": True,
                "data": stats
            })
        except Exception as e:
            log.error(f"Error getting AI stats: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/ai-tokens/models', methods=['GET'])
    def get_models():
        """Retorna modelos disponíveis no Ollama."""
        try:
            models = ai_monitor.get_ollama_models()
            return jsonify({
                "success": True,
                "data": {
                    "available_models": models,
                    "models_count": len(models)
                }
            })
        except Exception as e:
            log.error(f"Error getting models: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/ai-tokens/history', methods=['GET'])
    def get_history():
        """Retorna histórico de requests."""
        try:
            limit = request.args.get('limit', 100, type=int)
            limit = min(limit, 1000)  # Máximo 1000
            
            history = list(ai_monitor.request_history)[-limit:]
            
            return jsonify({
                "success": True,
                "data": {
                    "requests": history,
                    "count": len(history),
                    "total_tokens": sum(req.get('tokens_used', 0) for req in history)
                }
            })
        except Exception as e:
            log.error(f"Error getting history: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/ai-tokens/test', methods=['POST'])
    def test_ai_request():
        """Simula um request da IA para teste."""
        try:
            data = request.get_json() or {}
            
            model = data.get('model', 'test-model')
            prompt_tokens = data.get('prompt_tokens', 50)
            completion_tokens = data.get('completion_tokens', 30)
            response_time = data.get('response_time', 1.5)
            
            total_tokens = prompt_tokens + completion_tokens
            
            ai_monitor.log_request(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                response_time=response_time
            )
            
            return jsonify({
                "success": True,
                "data": {
                    "message": "Test request logged",
                    "tokens_used": total_tokens
                }
            })
        except Exception as e:
            log.error(f"Error in test request: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/ai-tokens/reset', methods=['POST'])
    def reset_stats():
        """Reseta estatísticas (apenas para desenvolvimento)."""
        try:
            global ai_monitor
            ai_monitor = AITokensMonitor()
            ai_monitor.start_monitoring()
            
            return jsonify({
                "success": True,
                "data": {"message": "Statistics reset successfully"}
            })
        except Exception as e:
            log.error(f"Error resetting stats: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    return app


def start_ai_tokens_monitoring():
    """Inicia monitoramento de tokens da IA."""
    ai_monitor.start_monitoring()


def log_ai_request(model: str, prompt_tokens: int, completion_tokens: int, 
                  total_tokens: int, response_time: float):
    """Função helper para registrar requests da IA."""
    ai_monitor.log_request(model, prompt_tokens, completion_tokens, total_tokens, response_time)


if __name__ == "__main__":
    # Teste standalone
    app = create_ai_tokens_api()
    start_ai_tokens_monitoring()
    
    print("🚀 AI Tokens API running on http://localhost:5001")
    print("📊 Endpoints available:")
    print("   GET  /api/ai-tokens/stats   - Current statistics")
    print("   GET  /api/ai-tokens/models  - Available models")
    print("   GET  /api/ai-tokens/history - Request history")
    print("   POST /api/ai-tokens/test    - Test request logging")
    print("   POST /api/ai-tokens/reset   - Reset statistics")
    
    app.run(host='0.0.0.0', port=5001, debug=True)