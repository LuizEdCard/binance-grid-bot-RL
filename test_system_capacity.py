#!/usr/bin/env python3
"""
Teste da capacidade do sistema para operar múltiplos pares simultaneamente
"""

import sys
import os
import time
import threading
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.capital_management import CapitalManager
from core.pair_selector import PairSelector
from core.grid_logic import GridLogic
from core.rl_agent import RLAgent
import yaml

def test_single_pair_performance(symbol, config, api, duration=30):
    """Testa performance de um único par."""
    try:
        start_time = time.time()
        cycles = 0
        errors = 0
        
        # Simular trading worker para o símbolo
        grid_logic = GridLogic(
            symbol=symbol,
            api_client=api,
            config=config,
            operation_mode=config.get('operation_mode', 'production').lower(),
            market_type='futures'
        )
        
        rl_agent = RLAgent(symbol=symbol, config=config)
        
        while time.time() - start_time < duration:
            try:
                # Simular ciclo de trading
                rl_action = rl_agent.get_action([0.5] * 30)  # Estado dummy
                grid_logic.run_cycle(rl_action=rl_action)
                cycles += 1
                time.sleep(1)  # Intervalo de 1 segundo
            except Exception as e:
                errors += 1
                time.sleep(0.5)
        
        elapsed = time.time() - start_time
        return {
            'symbol': symbol,
            'cycles': cycles,
            'errors': errors,
            'cycles_per_second': cycles / elapsed,
            'error_rate': errors / max(cycles, 1),
            'elapsed': elapsed
        }
        
    except Exception as e:
        return {
            'symbol': symbol,
            'cycles': 0,
            'errors': 1,
            'cycles_per_second': 0,
            'error_rate': 1.0,
            'elapsed': duration,
            'error_msg': str(e)
        }

def test_concurrent_pairs_capacity():
    """Testa capacidade para múltiplos pares simultâneos."""
    print("🚀 TESTE DE CAPACIDADE DO SISTEMA PARA MÚLTIPLOS PARES")
    print("=" * 60)
    
    # Carregar configuração
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    # Símbolos para teste
    test_symbols = [
        'ADAUSDT', 'XRPUSDT', 'DOGEUSDT', 'TRXUSDT', 'XLMUSDT',
        'KAIAUSDT', 'MATICUSDT', 'DOTUSDT', 'LINKUSDT', 'LTCUSDT',
        'ATOMUSDT', 'FILUSDT', 'AVAXUSDT', 'NEARUSDT', 'ALGOUSDT'
    ]
    
    print(f"\n1. 📊 ANÁLISE INICIAL DO SISTEMA:")
    
    # Recursos do sistema
    cpu_count = psutil.cpu_count()
    memory_gb = psutil.virtual_memory().total / (1024**3)
    
    print(f"   🖥️  CPU Cores: {cpu_count}")
    print(f"   💾 RAM Total: {memory_gb:.1f} GB")
    print(f"   🔧 Python Threads: Unlimited (GIL considerations)")
    
    # Análise de capital
    capital_manager = CapitalManager(api, config)
    balances = capital_manager.get_available_balances()
    
    print(f"\n   💰 ANÁLISE DE CAPITAL:")
    print(f"   💵 Spot: ${balances['spot_usdt']:.2f}")
    print(f"   🚀 Futures: ${balances['futures_usdt']:.2f}")
    print(f"   💯 Total: ${balances['total_usdt']:.2f}")
    
    # Calcular capacidade teórica
    min_per_pair = 5.0  # $5 mínimo por par
    safety_buffer = 0.9  # 10% buffer
    theoretical_max_pairs = int((balances['total_usdt'] * safety_buffer) / min_per_pair)
    
    print(f"   📈 Capacidade teórica: {theoretical_max_pairs} pares")
    print(f"   💡 Baseado em ${min_per_pair} mínimo por par + 10% buffer")
    
    print(f"\n2. 🧪 TESTES DE PERFORMANCE:")
    
    test_scenarios = [1, 3, 5, 10, 15]
    results = {}
    
    for num_pairs in test_scenarios:
        if num_pairs > len(test_symbols):
            continue
            
        print(f"\n   🎯 Testando {num_pairs} pares simultâneos...")
        
        # Selecionar símbolos para teste
        selected_symbols = test_symbols[:num_pairs]
        
        # Medir recursos antes do teste
        cpu_before = psutil.cpu_percent(interval=1)
        memory_before = psutil.virtual_memory().percent
        
        start_time = time.time()
        
        # Executar teste concorrente
        with ThreadPoolExecutor(max_workers=num_pairs) as executor:
            futures = [
                executor.submit(test_single_pair_performance, symbol, config, api, 15)  # 15 segundos
                for symbol in selected_symbols
            ]
            
            # Coletar resultados
            pair_results = []
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=20)
                    pair_results.append(result)
                except Exception as e:
                    pair_results.append({'error': str(e)})
        
        # Medir recursos após o teste
        cpu_after = psutil.cpu_percent(interval=1)
        memory_after = psutil.virtual_memory().percent
        
        elapsed = time.time() - start_time
        
        # Calcular estatísticas
        successful_pairs = [r for r in pair_results if 'cycles' in r and r['cycles'] > 0]
        total_cycles = sum(r['cycles'] for r in successful_pairs)
        total_errors = sum(r['errors'] for r in successful_pairs)
        avg_cycles_per_second = sum(r['cycles_per_second'] for r in successful_pairs) / max(len(successful_pairs), 1)
        
        results[num_pairs] = {
            'pairs': num_pairs,
            'successful_pairs': len(successful_pairs),
            'total_cycles': total_cycles,
            'total_errors': total_errors,
            'avg_cycles_per_second': avg_cycles_per_second,
            'cpu_usage': cpu_after - cpu_before,
            'memory_usage': memory_after - memory_before,
            'elapsed': elapsed,
            'success_rate': len(successful_pairs) / num_pairs
        }
        
        print(f"      ✅ Pares bem-sucedidos: {len(successful_pairs)}/{num_pairs}")
        print(f"      🔄 Total de ciclos: {total_cycles}")
        print(f"      ⚡ Ciclos/segundo médio: {avg_cycles_per_second:.2f}")
        print(f"      🖥️  CPU adicional: +{cpu_after - cpu_before:.1f}%")
        print(f"      💾 RAM adicional: +{memory_after - memory_before:.1f}%")
        
        # Pequena pausa entre testes
        time.sleep(2)
    
    print(f"\n3. 📈 ANÁLISE DE ESCALABILIDADE:")
    
    for num_pairs, data in results.items():
        success_rate = data['success_rate'] * 100
        efficiency = data['avg_cycles_per_second'] / max(num_pairs, 1)
        
        status = "🟢" if success_rate >= 90 else "🟡" if success_rate >= 70 else "🔴"
        
        print(f"   {status} {num_pairs:2d} pares: {success_rate:5.1f}% sucesso, {efficiency:.2f} ciclos/par/seg")
    
    # Encontrar limite recomendado
    max_stable_pairs = 0
    for num_pairs, data in results.items():
        if data['success_rate'] >= 0.9 and data['cpu_usage'] < 50:  # 90% sucesso, <50% CPU
            max_stable_pairs = num_pairs
    
    print(f"\n4. 🎯 RECOMENDAÇÕES:")
    print(f"   💰 Limite por capital: {theoretical_max_pairs} pares")
    print(f"   🖥️  Limite por performance: {max_stable_pairs} pares")
    print(f"   ✅ Recomendado: {min(theoretical_max_pairs, max_stable_pairs)} pares")
    
    # Teste de mercados simultâneos
    print(f"\n5. 🔄 TESTE DE MERCADOS SIMULTÂNEOS (SPOT + FUTURES):")
    
    # Simular operação em ambos mercados
    spot_symbols = ['ADAUSDT', 'XRPUSDT']
    futures_symbols = ['DOGEUSDT', 'TRXUSDT'] 
    
    print(f"   🎯 Testando 2 pares Spot + 2 pares Futures...")
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Spot workers
        spot_futures = [
            executor.submit(test_single_pair_performance, symbol, 
                          {**config, 'default_market_type': 'spot'}, api, 10)
            for symbol in spot_symbols
        ]
        
        # Futures workers  
        futures_futures = [
            executor.submit(test_single_pair_performance, symbol,
                          {**config, 'default_market_type': 'futures'}, api, 10)
            for symbol in futures_symbols
        ]
        
        all_futures = spot_futures + futures_futures
        market_results = []
        
        for future in as_completed(all_futures):
            try:
                result = future.result(timeout=15)
                market_results.append(result)
            except Exception as e:
                market_results.append({'error': str(e)})
    
    successful_markets = [r for r in market_results if 'cycles' in r and r['cycles'] > 0]
    market_success_rate = len(successful_markets) / 4 * 100
    
    print(f"   ✅ Sucesso em mercados simultâneos: {market_success_rate:.1f}%")
    
    if market_success_rate >= 75:
        print(f"   🟢 Sistema PODE operar Spot + Futures simultaneamente")
    else:
        print(f"   🔴 Sistema pode ter problemas operando ambos mercados")
    
    print(f"\n6. 🏁 CONCLUSÃO FINAL:")
    
    recommended_pairs = min(theoretical_max_pairs, max_stable_pairs, 15)
    
    print(f"   🎯 O sistema PODE operar até {recommended_pairs} pares simultaneamente")
    print(f"   💰 Limitado principalmente por: {'Capital' if theoretical_max_pairs < max_stable_pairs else 'Performance'}")
    print(f"   🔄 Pode operar Spot e Futures simultaneamente: {'✅ SIM' if market_success_rate >= 75 else '❌ NÃO'}")
    print(f"   ⚡ Performance esperada: ~{avg_cycles_per_second:.1f} ciclos/segundo por par")

if __name__ == "__main__":
    test_concurrent_pairs_capacity()