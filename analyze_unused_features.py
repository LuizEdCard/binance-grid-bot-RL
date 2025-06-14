#!/usr/bin/env python3
"""
Analisa funcionalidades implementadas que não estão sendo utilizadas
"""

import os
import re
import sys
from pathlib import Path

def analyze_implemented_features():
    """Analisa funcionalidades que existem mas podem não estar sendo usadas."""
    
    print("🔍 ANÁLISE DE FUNCIONALIDADES IMPLEMENTADAS MAS NÃO UTILIZADAS")
    print("=" * 80)
    
    # Funcionalidades para verificar
    features_to_check = {
        "WebSocket Client": {
            "files": ["src/utils/websocket_client.py"],
            "usage_patterns": ["BinanceWebSocketClient", "websocket_client"],
            "description": "Cliente WebSocket para dados em tempo real"
        },
        "Intelligent Cache": {
            "files": ["src/utils/intelligent_cache.py"],
            "usage_patterns": ["IntelligentCache", "get_global_cache"],
            "description": "Sistema de cache inteligente para otimização"
        },
        "Data Storage": {
            "files": ["src/utils/data_storage.py"],
            "usage_patterns": ["LocalDataStorage", "DataStorage"],
            "description": "Armazenamento local de dados para persistência"
        },
        "Hybrid Sentiment": {
            "files": ["src/utils/hybrid_sentiment_analyzer.py"],
            "usage_patterns": ["HybridSentimentAnalyzer"],
            "description": "Analisador híbrido de sentimento (Gemma + ONNX)"
        },
        "Async Client": {
            "files": ["src/utils/async_client.py"],
            "usage_patterns": ["AsyncAPIClient"],
            "description": "Cliente assíncrono para APIs"
        },
        "Fibonacci Calculator": {
            "files": ["src/utils/fibonacci_calculator.py"],
            "usage_patterns": ["FibonacciCalculator", "fibonacci"],
            "description": "Calculadora de níveis de Fibonacci"
        },
        "Candlestick Patterns": {
            "files": ["src/core/candlestick_patterns.py"],
            "usage_patterns": ["CandlestickPatterns", "candlestick"],
            "description": "Detecção de padrões de candlestick"
        },
        "Altcoin Correlation": {
            "files": ["src/core/altcoin_correlation.py"],
            "usage_patterns": ["AltcoinCorrelation", "correlation"],
            "description": "Análise de correlação entre altcoins"
        },
        "Model API Routes": {
            "files": ["src/routes/model_api.py"],
            "usage_patterns": ["model_api", "flask", "app.route"],
            "description": "APIs para modelos de ML"
        },
        "Tabular Model": {
            "files": ["src/models/tabular_model.py"],
            "usage_patterns": ["TabularModel"],
            "description": "Modelo tabular para ML"
        }
    }
    
    # Buscar por arquivos Python no diretório src
    src_files = []
    for root, dirs, files in os.walk("src"):
        for file in files:
            if file.endswith(".py"):
                src_files.append(os.path.join(root, file))
    
    unused_features = []
    partially_used = []
    fully_used = []
    
    for feature_name, feature_info in features_to_check.items():
        print(f"\n📋 Verificando: {feature_name}")
        print(f"   Descrição: {feature_info['description']}")
        
        # Verificar se o arquivo da funcionalidade existe
        feature_exists = False
        for feature_file in feature_info['files']:
            if os.path.exists(feature_file):
                feature_exists = True
                print(f"   ✅ Arquivo encontrado: {feature_file}")
                break
        
        if not feature_exists:
            print(f"   ❌ Arquivos não encontrados: {feature_info['files']}")
            continue
        
        # Verificar uso nos outros arquivos
        usage_count = 0
        usage_files = []
        
        for src_file in src_files:
            if src_file in feature_info['files']:
                continue  # Pular o próprio arquivo da funcionalidade
                
            try:
                with open(src_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern in feature_info['usage_patterns']:
                    if pattern in content:
                        usage_count += 1
                        if src_file not in usage_files:
                            usage_files.append(src_file)
                        break
            except Exception as e:
                continue
        
        print(f"   📊 Uso encontrado em {len(usage_files)} arquivos")
        
        if len(usage_files) == 0:
            print(f"   🚨 FUNCIONALIDADE NÃO UTILIZADA!")
            unused_features.append(feature_name)
        elif len(usage_files) < 3:
            print(f"   ⚠️  Uso limitado")
            partially_used.append((feature_name, usage_files))
        else:
            print(f"   ✅ Bem utilizada")
            fully_used.append(feature_name)
            
        # Mostrar arquivos que usam
        if usage_files:
            for file in usage_files[:3]:  # Mostrar apenas os 3 primeiros
                print(f"      - {file}")
            if len(usage_files) > 3:
                print(f"      ... e mais {len(usage_files) - 3} arquivos")
    
    # Resumo final
    print("\n" + "=" * 80)
    print("📈 RESUMO DA ANÁLISE")
    print("=" * 80)
    
    print(f"\n🔴 FUNCIONALIDADES NÃO UTILIZADAS ({len(unused_features)}):")
    for feature in unused_features:
        info = features_to_check[feature]
        print(f"   • {feature}: {info['description']}")
    
    print(f"\n🟡 FUNCIONALIDADES PARCIALMENTE UTILIZADAS ({len(partially_used)}):")
    for feature, files in partially_used:
        info = features_to_check[feature]
        print(f"   • {feature}: {info['description']}")
        print(f"     Usada em: {len(files)} arquivo(s)")
    
    print(f"\n🟢 FUNCIONALIDADES BEM UTILIZADAS ({len(fully_used)}):")
    for feature in fully_used:
        info = features_to_check[feature]
        print(f"   • {feature}: {info['description']}")
    
    # Verificações específicas para problemas conhecidos
    print("\n" + "=" * 80)
    print("🔧 VERIFICAÇÕES ESPECÍFICAS")
    print("=" * 80)
    
    # Verificar se WebSocket está sendo usado no multi_agent_bot
    print("\n📡 WebSocket Implementation:")
    try:
        with open("src/multi_agent_bot.py", 'r') as f:
            content = f.read()
            if "BinanceWebSocketClient" in content:
                print("   ✅ WebSocket importado no multi_agent_bot")
                if "ws_client.start()" in content:
                    print("   ✅ WebSocket sendo iniciado")
                else:
                    print("   ⚠️  WebSocket importado mas não iniciado")
            else:
                print("   ❌ WebSocket NÃO importado no multi_agent_bot")
    except Exception as e:
        print(f"   ❌ Erro ao verificar: {e}")
    
    # Verificar configuração de spacing
    print("\n📏 Grid Spacing Configuration:")
    try:
        with open("src/config/config.yaml", 'r') as f:
            content = f.read()
            if "initial_spacing_perc:" in content:
                match = re.search(r"initial_spacing_perc:\s*['\"]?([\d.]+)", content)
                if match:
                    spacing = float(match.group(1))
                    print(f"   📊 Spacing atual: {spacing*100:.1f}%")
                    if spacing <= 0.001:
                        print("   ✅ Configurado para micro-lucros (≤0.1%)")
                    elif spacing <= 0.005:
                        print("   ⚠️  Spacing moderado (0.1-0.5%)")
                    else:
                        print("   🚨 Spacing muito largo (>0.5%) - pode perder oportunidades")
    except Exception as e:
        print(f"   ❌ Erro ao verificar: {e}")
    
    # Verificar uso de _get_real_time_price
    print("\n⚡ Real-time Price Usage:")
    real_time_usage = 0
    for src_file in src_files:
        try:
            with open(src_file, 'r') as f:
                content = f.read()
                if "_get_real_time_price" in content:
                    real_time_usage += 1
        except:
            continue
    
    if real_time_usage > 1:
        print(f"   ✅ Método _get_real_time_price usado em {real_time_usage} arquivos")
    else:
        print("   ⚠️  Método _get_real_time_price não utilizado - usando polling")

if __name__ == "__main__":
    analyze_implemented_features()