#!/usr/bin/env python3
"""
Script de testes abrangente para a API do bot de trading.
Testa cenários normais, edge cases e possíveis falhas.
"""

import requests
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import sys

# Configuração da API
API_BASE = "http://localhost:5000/api"
TIMEOUT = 10

class APITester:
    def __init__(self):
        self.results = {
            "passed": 0,
            "failed": 0,
            "errors": []
        }
    
    def log_result(self, test_name, passed, details=""):
        """Registra resultado do teste."""
        if passed:
            self.results["passed"] += 1
            print(f"✅ {test_name}")
        else:
            self.results["failed"] += 1
            print(f"❌ {test_name}: {details}")
            self.results["errors"].append(f"{test_name}: {details}")
    
    def test_request(self, method, endpoint, data=None, expected_status=200, description=""):
        """Executa um teste de request HTTP."""
        try:
            url = f"{API_BASE}{endpoint}"
            if method == "GET":
                response = requests.get(url, timeout=TIMEOUT)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=TIMEOUT)
            
            passed = response.status_code == expected_status
            details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            self.log_result(f"{method} {endpoint} - {description}", passed, details)
            return response
        except Exception as e:
            self.log_result(f"{method} {endpoint} - {description}", False, str(e))
            return None
    
    def test_basic_endpoints(self):
        """Testa endpoints básicos."""
        print("\n=== TESTES BÁSICOS ===")
        
        # Status da API
        self.test_request("GET", "/status", description="Status da API")
        
        # Market data
        self.test_request("GET", "/market_data", description="Dados de mercado")
    
    def test_grid_config_validation(self):
        """Testa validações de configuração da grade."""
        print("\n=== TESTES DE VALIDAÇÃO DE CONFIGURAÇÃO ===")
        
        # Dados ausentes
        self.test_request("POST", "/grid/config", {}, 400, "Dados ausentes")
        
        # Symbol ausente
        self.test_request("POST", "/grid/config", {"config": {}}, 400, "Symbol ausente")
        
        # Config ausente
        self.test_request("POST", "/grid/config", {"symbol": "BTCUSDT"}, 400, "Config ausente")
        
        # initial_levels negativo
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT",
            "config": {"initial_levels": -5}
        }, 400, "initial_levels negativo")
        
        # initial_levels string
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT", 
            "config": {"initial_levels": "abc"}
        }, 400, "initial_levels string")
        
        # spacing_perc negativo
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT",
            "config": {"spacing_perc": -0.5}
        }, 400, "spacing_perc negativo")
        
        # spacing_perc string
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT",
            "config": {"spacing_perc": "abc"}
        }, 400, "spacing_perc string")
        
        # market_type inválido
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT",
            "config": {"market_type": "invalid"}
        }, 400, "market_type inválido")
        
        # Configuração válida
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT",
            "config": {
                "initial_levels": 5,
                "spacing_perc": 0.5,
                "market_type": "spot"
            }
        }, 200, "Configuração válida")
    
    def test_edge_cases(self):
        """Testa casos extremos."""
        print("\n=== TESTES DE EDGE CASES ===")
        
        # Valores extremos
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT",
            "config": {"initial_levels": 999999}
        }, 400, "initial_levels muito grande")
        
        # Símbolos malformados
        invalid_symbols = ["", "X", "BTCUSD@", "BTC/USD/EUR", "123", "!", "@#$%"]
        for symbol in invalid_symbols:
            self.test_request("GET", f"/grid/status/{symbol}", None, 400, f"Símbolo inválido: {symbol}")
        
        # JSON malformado (simulado com string inválida como float)
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT",
            "config": {"spacing_perc": float('inf')}
        }, 400, "spacing_perc infinito")
        
        # Valores zero
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT",
            "config": {"initial_levels": 0}
        }, 400, "initial_levels zero")
        
        self.test_request("POST", "/grid/config", {
            "symbol": "BTCUSDT", 
            "config": {"spacing_perc": 0}
        }, 400, "spacing_perc zero")
    
    def test_concurrent_requests(self):
        """Testa requisições concorrentes."""
        print("\n=== TESTES DE CONCORRÊNCIA ===")
        
        def make_request():
            return requests.get(f"{API_BASE}/status", timeout=TIMEOUT)
        
        try:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_request) for _ in range(20)]
                responses = [f.result() for f in futures]
                
            success_count = sum(1 for r in responses if r.status_code == 200)
            self.log_result("Requisições concorrentes", success_count >= 18, 
                          f"{success_count}/20 sucessos")
        except Exception as e:
            self.log_result("Requisições concorrentes", False, str(e))
    
    def test_memory_leak_simulation(self):
        """Simula cenários que podem causar vazamentos de memória."""
        print("\n=== TESTES DE VAZAMENTO DE MEMÓRIA ===")
        
        # Múltiplas configurações para o mesmo símbolo
        for i in range(50):
            response = self.test_request("POST", "/grid/config", {
                "symbol": "BTCUSDT",
                "config": {
                    "initial_levels": 5,
                    "spacing_perc": 0.5,
                    "market_type": "spot"
                }
            }, 200, f"Config repetida {i+1}")
            
            if i % 10 == 0:
                time.sleep(0.1)  # Pequena pausa para evitar sobrecarga
    
    def test_large_payloads(self):
        """Testa payloads grandes."""
        print("\n=== TESTES DE PAYLOADS GRANDES ===")
        
        # Configuração com muitos campos extras
        large_config = {
            "symbol": "BTCUSDT",
            "config": {
                "initial_levels": 5,
                "spacing_perc": 0.5,
                "market_type": "spot"
            }
        }
        
        # Adicionar campos desnecessários
        for i in range(1000):
            large_config["config"][f"extra_field_{i}"] = f"value_{i}"
        
        self.test_request("POST", "/grid/config", large_config, 200, "Payload grande")
    
    def test_injection_attempts(self):
        """Testa tentativas de injeção."""
        print("\n=== TESTES DE SEGURANÇA ===")
        
        injection_payloads = [
            {"symbol": "'; DROP TABLE users; --", "config": {}},
            {"symbol": "<script>alert('xss')</script>", "config": {}},
            {"symbol": "BTCUSDT", "config": {"initial_levels": "'; DROP TABLE users; --"}},
            {"symbol": "BTCUSDT", "config": {"spacing_perc": "<script>alert('xss')</script>"}},
        ]
        
        for payload in injection_payloads:
            self.test_request("POST", "/grid/config", payload, 400, 
                            f"Tentativa de injeção: {str(payload)[:50]}")
    
    def run_all_tests(self):
        """Executa todos os testes."""
        print("🚀 INICIANDO TESTES ABRANGENTES DA API")
        print("=" * 50)
        
        # Verificar se servidor está rodando
        try:
            response = requests.get(f"{API_BASE}/status", timeout=5)
            print(f"✅ Servidor detectado (Status: {response.status_code})")
        except:
            print("❌ Servidor não está rodando! Execute: python src/main.py")
            return {'passed': 0, 'failed': 1, 'errors': ['Servidor não está rodando']}
        
        # Executar todos os testes
        self.test_basic_endpoints()
        self.test_grid_config_validation()
        self.test_edge_cases()
        self.test_concurrent_requests()
        self.test_memory_leak_simulation()
        self.test_large_payloads()
        self.test_injection_attempts()
        
        # Relatório final
        print("\n" + "=" * 50)
        print("📊 RELATÓRIO FINAL")
        print("=" * 50)
        print(f"✅ Testes passou: {self.results['passed']}")
        print(f"❌ Testes falharam: {self.results['failed']}")
        print(f"📈 Taxa de sucesso: {self.results['passed']/(self.results['passed']+self.results['failed'])*100:.1f}%")
        
        if self.results['errors']:
            print(f"\n🔍 ERROS ENCONTRADOS ({len(self.results['errors'])}):")
            for error in self.results['errors']:
                print(f"  • {error}")
        
        return self.results

if __name__ == "__main__":
    tester = APITester()
    results = tester.run_all_tests()
    
    # Exit code baseado nos resultados
    sys.exit(0 if results['failed'] == 0 else 1)