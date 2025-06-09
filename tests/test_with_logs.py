#!/usr/bin/env python3
"""
Script de teste que monitora logs em tempo real.
"""

import requests
import time
import threading
import subprocess
import os
import signal

API_BASE = "http://localhost:5000/api"
LOG_FILE = "/home/luiz/Área de trabalho/bot/backend_consolidated/logs/bot.log"

class LogMonitor:
    def __init__(self):
        self.monitoring = False
        self.log_process = None
    
    def start_monitoring(self):
        """Inicia monitoramento de logs."""
        print("📝 Iniciando monitoramento de logs...")
        self.monitoring = True
        
        # Usar tail -f para seguir o log
        self.log_process = subprocess.Popen(
            ['tail', '-f', LOG_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        def read_logs():
            while self.monitoring and self.log_process:
                try:
                    line = self.log_process.stdout.readline()
                    if line:
                        # Filtrar apenas logs da API Flask
                        if "flask_api" in line:
                            print(f"🔍 LOG: {line.strip()}")
                except:
                    break
        
        threading.Thread(target=read_logs, daemon=True).start()
    
    def stop_monitoring(self):
        """Para monitoramento de logs."""
        self.monitoring = False
        if self.log_process:
            self.log_process.terminate()
            self.log_process = None
        print("📝 Monitoramento de logs parado.")

def test_with_logs():
    """Executa testes enquanto monitora logs."""
    monitor = LogMonitor()
    
    try:
        monitor.start_monitoring()
        time.sleep(1)  # Aguardar início do monitoramento
        
        print("🚀 Executando testes com monitoramento de logs...")
        print("=" * 60)
        
        # Teste 1: Configuração válida
        print("\n1️⃣ Testando configuração válida...")
        response = requests.post(f"{API_BASE}/grid/config", json={
            "symbol": "BTCUSDT",
            "config": {
                "initial_levels": 5,
                "spacing_perc": 0.5,
                "market_type": "spot"
            }
        })
        print(f"   Response: {response.status_code}")
        time.sleep(0.5)
        
        # Teste 2: Validação com erro
        print("\n2️⃣ Testando initial_levels negativo...")
        response = requests.post(f"{API_BASE}/grid/config", json={
            "symbol": "ETHUSDT",
            "config": {"initial_levels": -5}
        })
        print(f"   Response: {response.status_code}")
        time.sleep(0.5)
        
        # Teste 3: Symbol inválido
        print("\n3️⃣ Testando símbolo inválido...")
        response = requests.get(f"{API_BASE}/grid/status/123")
        print(f"   Response: {response.status_code}")
        time.sleep(0.5)
        
        # Teste 4: Múltiplas requisições
        print("\n4️⃣ Testando múltiplas requisições...")
        for i in range(5):
            response = requests.post(f"{API_BASE}/grid/config", json={
                "symbol": f"TEST{i}",
                "config": {"initial_levels": i + 1}
            })
            print(f"   Request {i+1}: {response.status_code}")
            time.sleep(0.2)
        
        # Teste 5: Status da API
        print("\n5️⃣ Testando status da API...")
        response = requests.get(f"{API_BASE}/status")
        print(f"   Response: {response.status_code}")
        time.sleep(0.5)
        
        print("\n✅ Testes concluídos!")
        print("📝 Aguardando logs finais...")
        time.sleep(2)
        
    except KeyboardInterrupt:
        print("\n⚠️ Testes interrompidos pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro durante os testes: {e}")
    finally:
        monitor.stop_monitoring()

def show_recent_logs():
    """Mostra logs recentes."""
    print("\n📋 LOGS RECENTES (últimas 10 linhas):")
    print("=" * 60)
    
    try:
        result = subprocess.run(['tail', '-10', LOG_FILE], 
                              capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        else:
            print("Nenhum log encontrado.")
    except Exception as e:
        print(f"Erro ao ler logs: {e}")

if __name__ == "__main__":
    print("🔧 TESTE COM MONITORAMENTO DE LOGS")
    print("=" * 50)
    
    # Verificar se servidor está rodando
    try:
        response = requests.get(f"{API_BASE}/status", timeout=5)
        print(f"✅ Servidor disponível (Status: {response.status_code})")
    except:
        print("❌ Servidor não está rodando!")
        print("Execute: python src/main.py")
        exit(1)
    
    # Verificar se arquivo de log existe
    if not os.path.exists(LOG_FILE):
        print(f"⚠️ Arquivo de log não encontrado: {LOG_FILE}")
        print("O servidor pode não estar gerando logs.")
    else:
        print(f"✅ Arquivo de log encontrado: {LOG_FILE}")
    
    print("\n🚀 Iniciando testes...")
    print("Pressione Ctrl+C para interromper")
    
    test_with_logs()
    show_recent_logs()