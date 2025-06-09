#!/usr/bin/env python3
"""
Teste rápido para verificar se modo Shadow está coletando dados.
"""

import requests
import time
import os

API_BASE = "http://localhost:5000/api"

def quick_test():
    print("🚀 TESTE RÁPIDO DO MODO SHADOW")
    print("=" * 40)
    
    # 1. Verificar servidor
    try:
        response = requests.get(f"{API_BASE}/status", timeout=3)
        print(f"✅ Servidor: {response.status_code}")
    except:
        print("❌ Servidor offline")
        return False
    
    # 2. Configurar grid
    print("🔧 Configurando grid...")
    config_response = requests.post(f"{API_BASE}/grid/config", json={
        "symbol": "BTCUSDT",
        "config": {
            "initial_levels": 4,
            "spacing_perc": 0.5,
            "market_type": "spot"
        }
    }, timeout=5)
    print(f"   Config: {config_response.status_code}")
    
    # 3. Iniciar bot (por poucos segundos)
    print("🤖 Iniciando bot temporariamente...")
    start_response = requests.post(f"{API_BASE}/grid/start", json={
        "symbol": "BTCUSDT",
        "config": {
            "initial_levels": 4,
            "spacing_perc": 0.5,
            "market_type": "spot"
        }
    }, timeout=5)
    print(f"   Start: {start_response.status_code}")
    
    if start_response.status_code == 200:
        print("⏳ Aguardando 15 segundos para coleta de dados...")
        time.sleep(15)
        
        # 4. Parar bot
        print("⏹️ Parando bot...")
        stop_response = requests.post(f"{API_BASE}/grid/stop", json={
            "symbol": "BTCUSDT"
        }, timeout=5)
        print(f"   Stop: {stop_response.status_code}")
    
    # 5. Verificar dados coletados
    print("\n📊 Verificando dados coletados...")
    data_files = ["shadow_trades.jsonl", "market_states.jsonl", "rl_actions.jsonl"]
    
    total_data = 0
    for file in data_files:
        filepath = os.path.join("data", file)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                count = sum(1 for _ in f)
            total_data += count
            print(f"   📄 {file}: {count} entradas")
        else:
            print(f"   📄 {file}: não existe")
    
    # 6. Resultado
    if total_data > 0:
        print(f"\n🎉 SUCESSO! {total_data} entradas coletadas")
        print("✅ Modo Shadow funcionando!")
        return True
    else:
        print("\n⚠️ Nenhum dado coletado")
        print("🔧 Verificar logs para diagnóstico")
        return False

if __name__ == "__main__":
    success = quick_test()
    
    if success:
        print("\n💡 Próximos passos:")
        print("   • Deixar bot rodando por mais tempo")
        print("   • Analisar dados coletados")
        print("   • Usar dados para treinar RL")
    else:
        print("\n🔍 Verificar:")
        print("   • Logs do servidor (tail -f logs/bot.log)")
        print("   • Chaves API no .env")
        print("   • Configuração do modo Shadow")