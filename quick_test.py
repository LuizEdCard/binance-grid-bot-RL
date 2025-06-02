#!/usr/bin/env python3
"""
Script de teste rápido para execução durante desenvolvimento.
"""

import requests
import json

API_BASE = "http://localhost:5000/api"

def test_server():
    """Teste rápido do servidor."""
    print("🚀 Testando servidor...")
    
    try:
        response = requests.get(f"{API_BASE}/status", timeout=5)
        print(f"✅ Status: {response.status_code}")
        print(f"📝 Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_validations():
    """Testa algumas validações rapidamente."""
    print("\n🔍 Testando validações...")
    
    tests = [
        # (description, payload, expected_status)
        ("Config válida", {
            "symbol": "BTCUSDT",
            "config": {"initial_levels": 5, "spacing_perc": 0.5, "market_type": "spot"}
        }, 200),
        
        ("initial_levels negativo", {
            "symbol": "BTCUSDT", 
            "config": {"initial_levels": -5}
        }, 400),
        
        ("spacing_perc string", {
            "symbol": "BTCUSDT",
            "config": {"spacing_perc": "abc"}
        }, 400),
        
        ("market_type inválido", {
            "symbol": "BTCUSDT",
            "config": {"market_type": "invalid"}
        }, 400),
        
        ("Symbol ausente", {
            "config": {"initial_levels": 5}
        }, 400)
    ]
    
    for desc, payload, expected in tests:
        try:
            response = requests.post(f"{API_BASE}/grid/config", json=payload, timeout=5)
            status = "✅" if response.status_code == expected else "❌"
            print(f"{status} {desc}: {response.status_code} (esperado: {expected})")
            
            if response.status_code != expected:
                print(f"   Response: {response.text[:100]}")
                
        except Exception as e:
            print(f"❌ {desc}: Erro - {e}")

def test_edge_cases():
    """Testa alguns edge cases."""
    print("\n⚡ Testando edge cases...")
    
    # Símbolos malformados
    bad_symbols = ["", "X", "BTC@USD", "123", "!@#"]
    for symbol in bad_symbols:
        try:
            response = requests.get(f"{API_BASE}/grid/status/{symbol}", timeout=5)
            print(f"📊 Status '{symbol}': {response.status_code}")
        except Exception as e:
            print(f"❌ Status '{symbol}': {e}")
    
    # Valores extremos
    extreme_values = [
        {"initial_levels": 0},
        {"initial_levels": 999999},
        {"spacing_perc": 0},
        {"spacing_perc": float('inf')},
    ]
    
    for config in extreme_values:
        try:
            payload = {"symbol": "BTCUSDT", "config": config}
            response = requests.post(f"{API_BASE}/grid/config", json=payload, timeout=5)
            print(f"🔥 {config}: {response.status_code}")
        except Exception as e:
            print(f"❌ {config}: {e}")

if __name__ == "__main__":
    print("🔧 TESTE RÁPIDO DA API")
    print("=" * 30)
    
    if test_server():
        test_validations()
        test_edge_cases()
        print("\n✅ Testes concluídos!")
    else:
        print("\n❌ Servidor não disponível!")
        print("Execute: python src/main.py")