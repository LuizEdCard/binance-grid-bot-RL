#!/usr/bin/env python3
"""
Script para testar o sistema de dados Shadow e verificar se está salvando corretamente.
"""

import requests
import time
import os
import json
from datetime import datetime

API_BASE = "http://localhost:5000/api"
DATA_DIR = "data"

def test_shadow_data_collection():
    """Testa se o modo Shadow está coletando dados corretamente."""
    print("🔬 TESTANDO COLETA DE DADOS NO MODO SHADOW")
    print("=" * 60)
    
    # Verificar se servidor está rodando
    try:
        response = requests.get(f"{API_BASE}/status", timeout=5)
        print(f"✅ Servidor disponível (Status: {response.status_code})")
    except:
        print("❌ Servidor não está rodando!")
        return False
    
    # Verificar arquivos de dados antes
    data_files = [
        "shadow_trades.jsonl",
        "market_states.jsonl", 
        "rl_actions.jsonl",
        "performance.jsonl"
    ]
    
    print(f"\n📁 Verificando diretório de dados: {DATA_DIR}/")
    
    initial_counts = {}
    for file in data_files:
        filepath = os.path.join(DATA_DIR, file)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                count = sum(1 for _ in f)
            initial_counts[file] = count
            print(f"   📄 {file}: {count} entradas")
        else:
            initial_counts[file] = 0
            print(f"   📄 {file}: arquivo não existe")
    
    # Executar alguns testes para gerar dados
    print(f"\n🚀 Executando testes para gerar dados Shadow...")
    
    # Teste 1: Configurar grid (deve gerar estado de mercado)
    print("1️⃣ Configurando grid para BTCUSDT...")
    config_response = requests.post(f"{API_BASE}/grid/config", json={
        "symbol": "BTCUSDT",
        "config": {
            "initial_levels": 6,
            "spacing_perc": 1.0,
            "market_type": "spot"
        }
    })
    print(f"   Configuração: {config_response.status_code}")
    time.sleep(1)
    
    # Teste 2: Tentar iniciar bot (deve gerar dados)
    print("2️⃣ Tentando iniciar bot (pode falhar sem API keys - normal)...")
    start_response = requests.post(f"{API_BASE}/grid/start", json={
        "symbol": "BTCUSDT",
        "config": {
            "initial_levels": 6,
            "spacing_perc": 1.0,
            "market_type": "spot"
        }
    })
    print(f"   Inicialização: {start_response.status_code}")
    print(f"   Response: {start_response.text[:200]}...")
    time.sleep(2)
    
    # Verificar arquivos de dados depois
    print(f"\n📊 Verificando dados coletados...")
    
    final_counts = {}
    new_data_found = False
    
    for file in data_files:
        filepath = os.path.join(DATA_DIR, file)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                count = sum(1 for _ in f)
            final_counts[file] = count
            
            new_entries = count - initial_counts[file]
            if new_entries > 0:
                new_data_found = True
                print(f"   ✅ {file}: +{new_entries} novas entradas ({count} total)")
                
                # Mostrar exemplo de entrada
                try:
                    with open(filepath, 'r') as f:
                        lines = f.readlines()
                        if lines:
                            last_entry = json.loads(lines[-1].strip())
                            print(f"      📄 Última entrada: {last_entry.get('timestamp', 'N/A')}")
                            if 'symbol' in last_entry:
                                print(f"         Symbol: {last_entry['symbol']}")
                            if 'action' in last_entry:
                                print(f"         Action: {last_entry['action']}")
                            if 'price' in last_entry:
                                print(f"         Price: {last_entry['price']}")
                except:
                    print(f"      ⚠️ Erro ao ler exemplo")
            else:
                print(f"   ⚪ {file}: sem novas entradas ({count} total)")
        else:
            final_counts[file] = 0
            print(f"   ❌ {file}: arquivo ainda não existe")
    
    # Verificar se modo Shadow está funcionando
    print(f"\n🔍 DIAGNÓSTICO:")
    
    if new_data_found:
        print("   ✅ Modo Shadow está coletando dados!")
        print("   ✅ Sistema de persistência funcionando")
        
        # Verificar tipos específicos de dados
        if final_counts.get("shadow_trades.jsonl", 0) > initial_counts.get("shadow_trades.jsonl", 0):
            print("   ✅ Trades simulados sendo salvos")
        if final_counts.get("market_states.jsonl", 0) > initial_counts.get("market_states.jsonl", 0):
            print("   ✅ Estados de mercado sendo capturados")
        if final_counts.get("rl_actions.jsonl", 0) > initial_counts.get("rl_actions.jsonl", 0):
            print("   ✅ Ações RL sendo registradas")
            
    else:
        print("   ⚠️ Nenhum dado novo coletado")
        print("   🔧 Possíveis problemas:")
        print("      - Modo Shadow pode não estar ativo")
        print("      - API keys podem estar ausentes")
        print("      - Bot pode não ter inicializado corretamente")
        print("      - Sistema de logging pode ter erro")
    
    return new_data_found

def show_data_stats():
    """Mostra estatísticas dos dados coletados."""
    print(f"\n📈 ESTATÍSTICAS DE DADOS COLETADOS")
    print("=" * 40)
    
    data_files = {
        "shadow_trades.jsonl": "Trades Simulados",
        "market_states.jsonl": "Estados de Mercado", 
        "rl_actions.jsonl": "Ações RL",
        "performance.jsonl": "Métricas de Performance"
    }
    
    total_entries = 0
    
    for file, description in data_files.items():
        filepath = os.path.join(DATA_DIR, file)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                count = sum(1 for _ in f)
            total_entries += count
            print(f"📊 {description}: {count:,} entradas")
            
            # Mostrar período de dados se houver
            if count > 0:
                try:
                    with open(filepath, 'r') as f:
                        first_line = f.readline().strip()
                        f.seek(0)
                        lines = f.readlines()
                        last_line = lines[-1].strip()
                    
                    first_entry = json.loads(first_line)
                    last_entry = json.loads(last_line)
                    
                    first_time = first_entry.get('timestamp', 'N/A')
                    last_time = last_entry.get('timestamp', 'N/A')
                    
                    print(f"   ⏰ Período: {first_time} até {last_time}")
                except:
                    print(f"   ⚠️ Erro ao ler timestamps")
        else:
            print(f"📊 {description}: 0 entradas (arquivo não existe)")
    
    print(f"\n📊 Total de entradas: {total_entries:,}")
    
    if total_entries > 0:
        print(f"✅ Sistema de coleta de dados funcionando!")
        print(f"💡 Use estes dados para treinar o agente RL")
    else:
        print(f"⚠️ Nenhum dado coletado ainda")

if __name__ == "__main__":
    success = test_shadow_data_collection()
    show_data_stats()
    
    if success:
        print(f"\n🎉 TESTE CONCLUÍDO: Sistema Shadow funcionando!")
    else:
        print(f"\n⚠️ TESTE CONCLUÍDO: Verificar configuração Shadow")