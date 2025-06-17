#!/usr/bin/env python3
"""
Test Live API Integration
Testa endpoints da API Flask para verificar se a integração frontend-backend está funcionando
"""

import requests
import json
import time
from typing import Dict, Any

# Base URL da API
BASE_URL = "http://localhost:5000"

def test_endpoint(endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """Testa um endpoint específico."""
    try:
        url = f"{BASE_URL}{endpoint}"
        
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            return {"success": False, "error": f"Método {method} não suportado"}
        
        return {
            "success": True,
            "status_code": response.status_code,
            "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Conexão recusada - API não está rodando"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Timeout - API demorou para responder"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    """Executa testes dos principais endpoints."""
    
    print("🧪 TESTE DE INTEGRAÇÃO - Flask API + Frontend")
    print("=" * 50)
    
    # Endpoints para testar
    endpoints_to_test = [
        # Endpoints básicos
        ("/api/status", "GET"),
        ("/api/live/system/status", "GET"),
        
        # Novos endpoints implementados
        ("/api/live/tpsl/status", "GET"),
        ("/api/live/margin/status", "GET"),
        ("/api/live/pair-rotation", "GET"),
        ("/api/live/system/health", "GET"),
        ("/api/live/alerts", "GET"),
    ]
    
    results = {}
    
    for endpoint, method in endpoints_to_test:
        print(f"\n📡 Testando {method} {endpoint}")
        result = test_endpoint(endpoint, method)
        results[endpoint] = result
        
        if result["success"]:
            print(f"✅ Status: {result['status_code']}")
            if result["status_code"] == 200:
                data = result["data"]
                if isinstance(data, dict):
                    if "success" in data:
                        print(f"   API Response Success: {data.get('success')}")
                    if "error" in data:
                        print(f"   API Error: {data.get('error')}")
                    # Preview dos dados (primeiras 3 chaves)
                    preview_keys = list(data.keys())[:3]
                    print(f"   Dados: {preview_keys}...")
        else:
            print(f"❌ Erro: {result['error']}")
    
    # Resumo
    print("\n" + "=" * 50)
    print("📊 RESUMO DOS TESTES")
    
    success_count = sum(1 for r in results.values() if r["success"] and r.get("status_code") == 200)
    total_count = len(results)
    
    print(f"✅ Sucessos: {success_count}/{total_count}")
    print(f"❌ Falhas: {total_count - success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 TODOS OS TESTES PASSARAM! Sistema integrado corretamente.")
    elif success_count > 0:
        print(f"\n⚠️  {success_count} endpoints funcionando, {total_count - success_count} com problemas.")
    else:
        print("\n🚨 NENHUM ENDPOINT FUNCIONANDO! Verifique se a API está rodando.")
        print("💡 Execute: python -m flask --app src.routes.live_data_api run --host=0.0.0.0 --port=5000")
    
    return success_count == total_count

if __name__ == "__main__":
    main()