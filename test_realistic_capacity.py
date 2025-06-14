#!/usr/bin/env python3
"""
Teste realístico da capacidade do sistema baseado na arquitetura atual
"""

import sys
import os
import time
import threading
import psutil
from concurrent.futures import ThreadPoolExecutor
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.capital_management import CapitalManager
import yaml

def test_api_performance(api, duration=10):
    """Testa performance da API com múltiplas chamadas."""
    start_time = time.time()
    calls = 0
    errors = 0
    
    while time.time() - start_time < duration:
        try:
            # Simular chamadas típicas do sistema
            api.get_futures_ticker('ADAUSDT')
            calls += 1
            time.sleep(0.1)  # 10 calls per second
        except Exception as e:
            errors += 1
            time.sleep(0.5)
    
    return {
        'calls': calls,
        'errors': errors,
        'calls_per_second': calls / duration,
        'error_rate': errors / max(calls, 1)
    }

def simulate_concurrent_workers(num_workers, duration=15):
    """Simula workers concorrentes fazendo chamadas API."""
    config = yaml.safe_load(open('src/config/config.yaml'))
    
    print(f"   🎯 Simulando {num_workers} workers por {duration}s...")
    
    # Medir recursos antes
    cpu_before = psutil.cpu_percent(interval=1)
    memory_before = psutil.virtual_memory().percent
    
    start_time = time.time()
    
    # Executar workers concorrentes
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        
        for i in range(num_workers):
            api = APIClient(config)
            future = executor.submit(test_api_performance, api, duration)
            futures.append(future)
        
        # Coletar resultados
        results = []
        for future in futures:
            try:
                result = future.result(timeout=duration + 5)
                results.append(result)
            except Exception as e:
                results.append({'error': str(e), 'calls': 0, 'errors': 1})
    
    # Medir recursos depois
    cpu_after = psutil.cpu_percent(interval=1)
    memory_after = psutil.virtual_memory().percent
    
    elapsed = time.time() - start_time
    
    # Calcular estatísticas
    total_calls = sum(r.get('calls', 0) for r in results)
    total_errors = sum(r.get('errors', 0) for r in results)
    successful_workers = len([r for r in results if r.get('calls', 0) > 0])
    
    return {
        'workers': num_workers,
        'successful_workers': successful_workers,
        'total_calls': total_calls,
        'total_errors': total_errors,
        'calls_per_second': total_calls / elapsed,
        'cpu_usage': cpu_after - cpu_before,
        'memory_usage': memory_after - memory_before,
        'success_rate': successful_workers / num_workers,
        'elapsed': elapsed
    }

def analyze_system_capacity():
    """Análise completa da capacidade do sistema."""
    print("🚀 ANÁLISE REALÍSTICA DE CAPACIDADE DO SISTEMA")
    print("=" * 60)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    print(f"\n1. 📊 RECURSOS DO SISTEMA:")
    cpu_count = psutil.cpu_count()
    memory_gb = psutil.virtual_memory().total / (1024**3)
    print(f"   🖥️  CPU Cores: {cpu_count}")
    print(f"   💾 RAM Total: {memory_gb:.1f} GB")
    
    print(f"\n2. 💰 ANÁLISE DE CAPITAL:")
    capital_manager = CapitalManager(api, config)
    balances = capital_manager.get_available_balances()
    
    print(f"   💵 Spot: ${balances['spot_usdt']:.2f}")
    print(f"   🚀 Futures: ${balances['futures_usdt']:.2f}")
    print(f"   💯 Total: ${balances['total_usdt']:.2f}")
    
    # Calcular capacidade por capital
    min_per_pair = 5.0
    safety_buffer = 0.9
    max_pairs_by_capital = int((balances['total_usdt'] * safety_buffer) / min_per_pair)
    print(f"   📈 Máximo por capital: {max_pairs_by_capital} pares")
    
    print(f"\n3. 🧪 TESTES DE PERFORMANCE:")
    
    # Testar diferentes números de workers
    worker_scenarios = [1, 3, 5, 8, 12, 15]
    if max_pairs_by_capital < 15:
        worker_scenarios = [w for w in worker_scenarios if w <= max_pairs_by_capital + 5]
    
    results = {}
    
    for num_workers in worker_scenarios:
        result = simulate_concurrent_workers(num_workers)
        results[num_workers] = result
        
        success_rate = result['success_rate'] * 100
        status = "🟢" if success_rate >= 90 else "🟡" if success_rate >= 70 else "🔴"
        
        print(f"   {status} {num_workers:2d} workers: {success_rate:5.1f}% sucesso, "
              f"{result['calls_per_second']:.1f} calls/s, CPU: +{result['cpu_usage']:.1f}%")
        
        time.sleep(2)  # Pausa entre testes
    
    print(f"\n4. 📈 ANÁLISE DE LIMITES:")
    
    # Encontrar limite estável
    max_stable_workers = 0
    for workers, data in results.items():
        if data['success_rate'] >= 0.9 and data['cpu_usage'] < 50 and data['calls_per_second'] > workers * 5:
            max_stable_workers = workers
    
    print(f"   🖥️  Limite por performance: {max_stable_workers} workers")
    print(f"   💰 Limite por capital: {max_pairs_by_capital} pares")
    
    # Teste de mercados simultâneos
    print(f"\n5. 🔄 TESTE DE MERCADOS SIMULTÂNEOS:")
    
    # Simular spot + futures workers
    print(f"   🎯 Testando 2 workers Spot + 2 workers Futures...")
    
    mixed_result = simulate_concurrent_workers(4, 10)  # 4 workers, 10 segundos
    
    mixed_success = mixed_result['success_rate'] * 100
    print(f"   ✅ Sucesso misto: {mixed_success:.1f}%")
    print(f"   ⚡ Performance: {mixed_result['calls_per_second']:.1f} calls/s")
    
    # Análise de rate limits da Binance
    print(f"\n6. ⚠️  LIMITAÇÕES DA BINANCE API:")
    print(f"   📊 Futures: 2400 requests/minuto (40/segundo)")
    print(f"   💱 Spot: 1200 requests/minuto (20/segundo)")
    print(f"   🔄 WebSocket: Conexões ilimitadas (dados em tempo real)")
    
    # Estimativa realística
    print(f"\n7. 🎯 ESTIMATIVA REALÍSTICA:")
    
    # Considerando rate limits da Binance
    # Cada par faz ~10 requests/minuto em operação normal
    max_by_rate_limit = min(240, 120)  # 240 futures ou 120 spot pairs
    
    # Considerando recursos do sistema
    max_by_system = max_stable_workers
    
    # Considerando capital
    max_by_capital = max_pairs_by_capital
    
    realistic_max = min(max_by_rate_limit, max_by_system, max_by_capital)
    
    print(f"   🚫 Limite rate API: {max_by_rate_limit} pares")
    print(f"   🖥️  Limite sistema: {max_by_system} pares")
    print(f"   💰 Limite capital: {max_by_capital} pares")
    print(f"   ✅ Máximo realístico: {realistic_max} pares")
    
    print(f"\n8. 🏁 CONCLUSÕES FINAIS:")
    
    can_do_15_pairs = realistic_max >= 15
    can_do_simultaneous = mixed_success >= 80
    
    print(f"   🎯 Pode operar 15 pares? {'✅ SIM' if can_do_15_pairs else '❌ NÃO'}")
    if not can_do_15_pairs:
        print(f"      💡 Máximo recomendado: {realistic_max} pares")
    
    print(f"   🔄 Spot + Futures simultâneo? {'✅ SIM' if can_do_simultaneous else '❌ NÃO'}")
    
    print(f"\n9. 💡 RECOMENDAÇÕES:")
    if realistic_max >= 10:
        print(f"   ✅ Sistema robusto - pode operar {realistic_max} pares")
        print(f"   📈 Configurar max_concurrent_pairs = {min(realistic_max, 15)}")
    elif realistic_max >= 5:
        print(f"   ⚠️  Sistema médio - limite a {realistic_max} pares")
        print(f"   🔧 Otimizar performance ou aumentar capital")
    else:
        print(f"   ❌ Sistema limitado - máximo {realistic_max} pares")
        print(f"   💰 Aumentar capital ou melhorar hardware")
    
    if can_do_simultaneous:
        print(f"   🔄 Usar allocation: 40% Spot, 60% Futures")
    else:
        print(f"   🎯 Focar em um mercado apenas (preferencialmente Futures)")
    
    return {
        'max_pairs': realistic_max,
        'can_do_15': can_do_15_pairs,
        'can_do_simultaneous': can_do_simultaneous,
        'limiting_factor': 'Capital' if max_by_capital < max_by_system else 'Performance'
    }

if __name__ == "__main__":
    analyze_system_capacity()