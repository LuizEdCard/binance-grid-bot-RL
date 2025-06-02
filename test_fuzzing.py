#!/usr/bin/env python3
"""
Script de fuzzing para encontrar vulnerabilidades e edge cases na API.
Gera dados aleatórios e testa comportamentos inesperados.
"""

import requests
import random
import string
import json
import time
from itertools import product

API_BASE = "http://localhost:5000/api"

class FuzzTester:
    def __init__(self):
        self.errors_found = []
        self.interesting_responses = []
    
    def log_finding(self, test_type, payload, response):
        """Registra descobertas interessantes."""
        if response.status_code >= 500:
            self.errors_found.append({
                "type": test_type,
                "payload": payload,
                "status": response.status_code,
                "response": response.text[:200]
            })
        elif response.status_code not in [200, 400, 404]:
            self.interesting_responses.append({
                "type": test_type,
                "payload": payload,
                "status": response.status_code,
                "response": response.text[:200]
            })
    
    def generate_random_string(self, length=10):
        """Gera string aleatória."""
        return ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=length))
    
    def generate_random_symbol(self):
        """Gera símbolos de trading aleatórios."""
        templates = [
            "{}USDT", "{}BTC", "{}ETH", "{}/{}", "{}@{}", 
            "{}.{}", "{}_{}", "{}-{}", "{}+{}", "{}={}"
        ]
        base = random.choice(["BTC", "ETH", "ADA", "XRP", "DOT", "LINK", "UNI"])
        template = random.choice(templates)
        
        if "{}" in template:
            if template.count("{}") == 1:
                return template.format(base)
            else:
                return template.format(base, random.choice(["USDT", "BTC", "ETH"]))
        return base
    
    def fuzz_config_values(self):
        """Testa valores de configuração aleatórios."""
        print("🎯 Fuzzing config values...")
        
        # Tipos de dados maliciosos
        malicious_values = [
            None, [], {}, "", "null", "undefined",
            float('inf'), float('-inf'), float('nan'),
            2**31, -2**31, 2**63, -2**63,
            "SELECT * FROM users", "<script>alert('xss')</script>",
            "'; DROP TABLE users; --", "\x00\x01\x02",
            "\n\r\t", "🚀💥🔥", "null\\u0000",
            {"$gt": ""}, {"$ne": None}
        ]
        
        for _ in range(50):
            config = {}
            
            # Randomizar campos
            fields = ["initial_levels", "spacing_perc", "market_type", "stop_loss", "take_profit"]
            for field in random.sample(fields, random.randint(1, len(fields))):
                config[field] = random.choice(malicious_values)
            
            payload = {
                "symbol": self.generate_random_symbol(),
                "config": config
            }
            
            try:
                response = requests.post(f"{API_BASE}/grid/config", json=payload, timeout=5)
                self.log_finding("fuzz_config", payload, response)
            except Exception as e:
                print(f"Request failed: {e}")
    
    def fuzz_symbols(self):
        """Testa símbolos malformados."""
        print("🎯 Fuzzing symbols...")
        
        # Símbolos especiais
        special_symbols = [
            "../../../etc/passwd", "CON", "PRN", "AUX", "NUL",
            "..\\..\\..\\windows\\system32", "%2e%2e%2f",
            "\0", "\x00", "\xff\xfe", "\\x00\\x01",
            "A" * 1000, "SELECT", "DROP", "UNION"
        ]
        
        for symbol in special_symbols:
            try:
                response = requests.get(f"{API_BASE}/grid/status/{symbol}", timeout=5)
                self.log_finding("fuzz_symbol", symbol, response)
            except Exception as e:
                print(f"Request failed for {symbol}: {e}")
    
    def stress_test_rapid_requests(self):
        """Teste de stress com requisições rápidas."""
        print("🎯 Stress testing with rapid requests...")
        
        start_time = time.time()
        for i in range(100):
            try:
                # Requisições alternadas
                if i % 2 == 0:
                    requests.get(f"{API_BASE}/status", timeout=1)
                else:
                    requests.post(f"{API_BASE}/grid/config", json={
                        "symbol": f"TEST{i}",
                        "config": {"initial_levels": i % 10 + 1}
                    }, timeout=1)
                
                if i % 10 == 0:
                    print(f"Completed {i}/100 rapid requests")
                    
            except Exception as e:
                self.errors_found.append({
                    "type": "rapid_requests",
                    "payload": f"Request {i}",
                    "error": str(e)
                })
        
        elapsed = time.time() - start_time
        print(f"Completed 100 requests in {elapsed:.2f} seconds")
    
    def test_boundary_values(self):
        """Testa valores nos limites."""
        print("🎯 Testing boundary values...")
        
        boundary_tests = [
            # Integer boundaries
            {"initial_levels": 0}, {"initial_levels": 1}, {"initial_levels": -1},
            {"initial_levels": 2**31 - 1}, {"initial_levels": -2**31},
            {"initial_levels": 2**63 - 1}, {"initial_levels": -2**63},
            
            # Float boundaries
            {"spacing_perc": 0.0}, {"spacing_perc": 0.000001}, 
            {"spacing_perc": 999999.999999}, {"spacing_perc": -0.000001},
            {"spacing_perc": 1e-10}, {"spacing_perc": 1e10},
        ]
        
        for config in boundary_tests:
            payload = {"symbol": "BTCUSDT", "config": config}
            try:
                response = requests.post(f"{API_BASE}/grid/config", json=payload, timeout=5)
                self.log_finding("boundary_test", config, response)
            except Exception as e:
                print(f"Boundary test failed: {e}")
    
    def test_unicode_and_encoding(self):
        """Testa diferentes encodings e unicode."""
        print("🎯 Testing unicode and encoding...")
        
        unicode_strings = [
            "BTCUSDT", "BTC♠USDT", "BTC🚀USDT", "BTC💎USDT",
            "БTCUSDT", "βTCUSDT", "中文USDT", "🇺🇸USDT",
            "\\u0041\\u0042", "\\x41\\x42", "\\042\\041"
        ]
        
        for symbol in unicode_strings:
            try:
                response = requests.get(f"{API_BASE}/grid/status/{symbol}", timeout=5)
                self.log_finding("unicode_test", symbol, response)
            except Exception as e:
                print(f"Unicode test failed for {symbol}: {e}")
    
    def test_content_type_manipulation(self):
        """Testa diferentes content-types."""
        print("🎯 Testing content-type manipulation...")
        
        payload = {"symbol": "BTCUSDT", "config": {"initial_levels": 5}}
        
        content_types = [
            "application/json",
            "text/plain",
            "application/xml",
            "multipart/form-data",
            "application/x-www-form-urlencoded",
            "text/html",
            "",
            "application/json; charset=utf-8",
            "application/json; boundary=something"
        ]
        
        for ct in content_types:
            try:
                headers = {"Content-Type": ct} if ct else {}
                response = requests.post(f"{API_BASE}/grid/config", 
                                       json=payload, headers=headers, timeout=5)
                if response.status_code >= 500:
                    self.log_finding("content_type", ct, response)
            except Exception as e:
                print(f"Content-type test failed for {ct}: {e}")
    
    def run_fuzzing_tests(self):
        """Executa todos os testes de fuzzing."""
        print("🔥 INICIANDO TESTES DE FUZZING")
        print("=" * 50)
        
        # Verificar servidor
        try:
            response = requests.get(f"{API_BASE}/status", timeout=5)
            print(f"✅ Servidor detectado (Status: {response.status_code})")
        except:
            print("❌ Servidor não está rodando!")
            return
        
        # Executar testes
        self.fuzz_config_values()
        self.fuzz_symbols()
        self.test_boundary_values()
        self.test_unicode_and_encoding()
        self.test_content_type_manipulation()
        self.stress_test_rapid_requests()
        
        # Relatório
        print("\n" + "=" * 50)
        print("🔍 RELATÓRIO DE FUZZING")
        print("=" * 50)
        
        print(f"🚨 Erros críticos encontrados: {len(self.errors_found)}")
        print(f"🔍 Respostas interessantes: {len(self.interesting_responses)}")
        
        if self.errors_found:
            print("\n💥 ERROS CRÍTICOS:")
            for error in self.errors_found[:10]:  # Primeiros 10
                print(f"  • {error['type']}: Status {error.get('status', 'N/A')}")
                print(f"    Payload: {str(error['payload'])[:100]}...")
        
        if self.interesting_responses:
            print("\n🔍 RESPOSTAS INTERESSANTES:")
            for resp in self.interesting_responses[:5]:  # Primeiros 5
                print(f"  • {resp['type']}: Status {resp['status']}")
                print(f"    Payload: {str(resp['payload'])[:100]}...")

if __name__ == "__main__":
    fuzzer = FuzzTester()
    fuzzer.run_fuzzing_tests()