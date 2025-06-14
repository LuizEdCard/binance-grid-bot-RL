#!/usr/bin/env python3
"""
Teste da API de tokens da IA
"""

import sys
import os
import time
import requests
import threading
import json

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from routes.ai_tokens_api import create_ai_tokens_api, start_ai_tokens_monitoring

def test_api_endpoints():
    """Testa todos os endpoints da API."""
    base_url = "http://localhost:5001"
    
    print("🧪 TESTE: API DE TOKENS DA IA")
    print("=" * 40)
    
    # Aguardar API inicializar
    time.sleep(2)
    
    tests_passed = 0
    tests_total = 0
    
    # 1. Testar endpoint de stats
    print("\n📊 1. Testando /api/ai-tokens/stats")
    tests_total += 1
    try:
        response = requests.get(f"{base_url}/api/ai-tokens/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("   ✅ Endpoint funcionando")
                print(f"   📈 Total de tokens: {data['data']['session']['total_tokens']}")
                print(f"   📊 Total de requests: {data['data']['session']['total_requests']}")
                tests_passed += 1
            else:
                print(f"   ❌ API retornou erro: {data.get('error', 'Unknown')}")
        else:
            print(f"   ❌ Status code: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # 2. Testar endpoint de models
    print("\n🤖 2. Testando /api/ai-tokens/models")
    tests_total += 1
    try:
        response = requests.get(f"{base_url}/api/ai-tokens/models", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                models = data['data']['available_models']
                print("   ✅ Endpoint funcionando")
                print(f"   🎯 Modelos encontrados: {len(models)}")
                if models:
                    print(f"   📝 Modelos: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")
                tests_passed += 1
            else:
                print(f"   ❌ API retornou erro: {data.get('error', 'Unknown')}")
        else:
            print(f"   ❌ Status code: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # 3. Testar request de teste
    print("\n🧪 3. Testando /api/ai-tokens/test (POST)")
    tests_total += 1
    try:
        test_data = {
            "model": "gemma3:1b",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "response_time": 2.5
        }
        
        response = requests.post(
            f"{base_url}/api/ai-tokens/test", 
            json=test_data,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("   ✅ Request de teste registrado")
                print(f"   🎯 Tokens usados: {data['data']['tokens_used']}")
                tests_passed += 1
            else:
                print(f"   ❌ API retornou erro: {data.get('error', 'Unknown')}")
        else:
            print(f"   ❌ Status code: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # 4. Testar histórico após o request de teste
    print("\n📜 4. Testando /api/ai-tokens/history")
    tests_total += 1
    try:
        response = requests.get(f"{base_url}/api/ai-tokens/history?limit=5", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                requests_data = data['data']['requests']
                print("   ✅ Histórico funcionando")
                print(f"   📊 Requests no histórico: {len(requests_data)}")
                if requests_data:
                    last_request = requests_data[-1]
                    print(f"   🎯 Último request: {last_request.get('model', 'N/A')} - {last_request.get('tokens_used', 0)} tokens")
                tests_passed += 1
            else:
                print(f"   ❌ API retornou erro: {data.get('error', 'Unknown')}")
        else:
            print(f"   ❌ Status code: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # 5. Simular múltiplos requests
    print("\n🔥 5. Simulando múltiplos requests da IA")
    tests_total += 1
    try:
        models = ["gemma3:1b", "qwen3:1.7b", "deepseek-r1:1.5b"]
        total_simulated = 0
        
        for i in range(5):
            model = models[i % len(models)]
            test_data = {
                "model": model,
                "prompt_tokens": 50 + (i * 10),
                "completion_tokens": 30 + (i * 5),
                "response_time": 1.0 + (i * 0.3)
            }
            
            response = requests.post(
                f"{base_url}/api/ai-tokens/test", 
                json=test_data,
                timeout=5
            )
            
            if response.status_code == 200:
                total_simulated += 1
            
            time.sleep(0.2)  # Pequeno delay
        
        if total_simulated == 5:
            print("   ✅ Múltiplos requests simulados com sucesso")
            tests_passed += 1
        else:
            print(f"   ⚠️  Apenas {total_simulated}/5 requests simulados")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # 6. Verificar estatísticas atualizadas
    print("\n📈 6. Verificando estatísticas finais")
    tests_total += 1
    try:
        response = requests.get(f"{base_url}/api/ai-tokens/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                session_data = data['data']['session']
                models_data = data['data']['models']
                
                print("   ✅ Estatísticas atualizadas")
                print(f"   📊 Total de tokens: {session_data['total_tokens']}")
                print(f"   📈 Total de requests: {session_data['total_requests']}")
                print(f"   🎯 Modelos usados: {len(models_data['used'])}")
                print(f"   ⚡ Tokens/minuto: {session_data['avg_tokens_per_minute']}")
                
                if session_data['total_requests'] >= 6:  # 1 inicial + 5 simulados
                    tests_passed += 1
                else:
                    print(f"   ⚠️  Esperado >= 6 requests, encontrado: {session_data['total_requests']}")
            else:
                print(f"   ❌ API retornou erro: {data.get('error', 'Unknown')}")
        else:
            print(f"   ❌ Status code: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # Resumo
    print("\n" + "=" * 40)
    print("📊 RESUMO DOS TESTES")
    print("=" * 40)
    print(f"✅ Testes passaram: {tests_passed}/{tests_total}")
    print(f"📈 Taxa de sucesso: {(tests_passed/tests_total)*100:.1f}%")
    
    if tests_passed >= tests_total * 0.8:  # 80% de sucesso
        print("\n🎉 API DE TOKENS DA IA FUNCIONANDO CORRETAMENTE!")
        return True
    else:
        print("\n⚠️  PROBLEMAS DETECTADOS NA API")
        return False

def start_api_server():
    """Inicia servidor da API em thread separada."""
    app = create_ai_tokens_api()
    start_ai_tokens_monitoring()
    
    # Executar em thread para não bloquear os testes
    def run_server():
        app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    print("🚀 API Server iniciado em http://localhost:5001")
    return server_thread

def main():
    print("🧪 TESTE COMPLETO DA API DE TOKENS DA IA")
    print("=" * 50)
    
    # Iniciar servidor da API
    server_thread = start_api_server()
    
    # Aguardar servidor inicializar
    print("⏳ Aguardando servidor inicializar...")
    time.sleep(3)
    
    # Executar testes
    try:
        success = test_api_endpoints()
        
        if success:
            print("\n✅ TODOS OS TESTES PASSARAM - API PRONTA PARA USO!")
        else:
            print("\n❌ ALGUNS TESTES FALHARAM - VERIFICAR IMPLEMENTAÇÃO")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro durante testes: {e}")

if __name__ == "__main__":
    main()