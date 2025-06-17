#!/usr/bin/env python3
"""
Script para diagnosticar o estado atual do sistema de trading
Identifica problemas com cache, configurações e pair selection
"""

import os
import json
import yaml
import sqlite3
import glob
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def load_config():
    """Carrega a configuração atual."""
    config_path = "src/config/config.yaml"
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        log.error(f"Erro ao carregar config: {e}")
        return {}

def check_grid_states():
    """Verifica estados dos grids salvos."""
    log.info("🔍 VERIFICANDO GRID STATES")
    log.info("-" * 40)
    
    state_dirs = ["data/grid_states", "src/data/grid_states"]
    all_states = {}
    
    for state_dir in state_dirs:
        if os.path.exists(state_dir):
            pattern = os.path.join(state_dir, "*_state.json")
            state_files = glob.glob(pattern)
            
            log.info(f"📁 {state_dir}: {len(state_files)} arquivos de estado")
            
            for state_file in state_files:
                try:
                    with open(state_file, 'r') as f:
                        state_data = json.load(f)
                    
                    symbol = os.path.basename(state_file).replace('_state.json', '')
                    timestamp = state_data.get('timestamp', 0)
                    
                    if timestamp:
                        state_time = datetime.fromtimestamp(timestamp)
                        age_hours = (datetime.now() - state_time).total_seconds() / 3600
                        
                        all_states[symbol] = {
                            'file': state_file,
                            'timestamp': state_time,
                            'age_hours': age_hours,
                            'grid_levels': len(state_data.get('grid_levels', [])),
                            'active_orders': len(state_data.get('active_orders', [])),
                            'mode': state_data.get('mode', 'unknown')
                        }
                        
                        status = "🟢 ATIVO" if age_hours < 24 else "🟡 ANTIGO" if age_hours < 72 else "🔴 MUITO ANTIGO"
                        log.info(f"  {symbol}: {status} - {age_hours:.1f}h - {len(state_data.get('grid_levels', []))} níveis - {len(state_data.get('active_orders', []))} ordens")
                    
                except Exception as e:
                    log.warning(f"  ❌ Erro ao ler {state_file}: {e}")
        else:
            log.info(f"📁 {state_dir}: Diretório não existe")
    
    return all_states

def check_current_config():
    """Verifica configuração atual."""
    log.info("\n🔧 VERIFICANDO CONFIGURAÇÃO ATUAL")
    log.info("-" * 40)
    
    config = load_config()
    
    # Verificar configurações críticas
    trading_config = config.get('trading', {})
    pair_config = config.get('pair_selection', {})
    grid_config = config.get('grid', {})
    
    log.info(f"💰 Capital por par: ${trading_config.get('capital_per_pair_usd', 'N/A')}")
    log.info(f"🔢 Max pares concorrentes: {trading_config.get('max_concurrent_pairs', 'N/A')}")
    log.info(f"📊 Níveis de grid: {grid_config.get('initial_levels', 'N/A')} (min: {grid_config.get('min_levels', 'N/A')}, max: {grid_config.get('max_levels', 'N/A')})")
    log.info(f"📏 Espaçamento inicial: {grid_config.get('initial_spacing_perc', 'N/A')}%")
    log.info(f"🔄 Intervalo de atualização: {pair_config.get('update_interval_hours', 'N/A')}h")
    
    # Verificar pares preferidos
    futures_pairs = pair_config.get('futures_pairs', {}).get('preferred_symbols', [])
    spot_pairs = pair_config.get('spot_pairs', {}).get('preferred_symbols', [])
    
    log.info(f"🎯 Pares futures preferidos: {len(futures_pairs)}")
    for pair in futures_pairs[:5]:  # Mostrar primeiros 5
        log.info(f"    {pair}")
    if len(futures_pairs) > 5:
        log.info(f"    ... e mais {len(futures_pairs) - 5}")
    
    log.info(f"🎯 Pares spot preferidos: {len(spot_pairs)}")
    for pair in spot_pairs[:3]:  # Mostrar primeiros 3
        log.info(f"    {pair}")
    if len(spot_pairs) > 3:
        log.info(f"    ... e mais {len(spot_pairs) - 3}")
    
    return config

def check_market_data_db():
    """Verifica banco de dados de market data."""
    log.info("\n💾 VERIFICANDO MARKET DATA DATABASE")
    log.info("-" * 40)
    
    db_paths = [
        "data/market_data.db",
        "src/data/cache/market_data.db", 
        "data/cache/market_data.db"
    ]
    
    for db_path in db_paths:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Verificar tabelas
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                log.info(f"📊 {db_path}: {len(tables)} tabelas")
                
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    
                    # Verificar timestamp mais recente se existe coluna timestamp
                    try:
                        cursor.execute(f"SELECT MAX(timestamp) FROM {table_name}")
                        latest_ts = cursor.fetchone()[0]
                        if latest_ts:
                            latest_time = datetime.fromtimestamp(latest_ts)
                            age = (datetime.now() - latest_time).total_seconds() / 3600
                            log.info(f"    {table_name}: {count} registros (último: {age:.1f}h atrás)")
                        else:
                            log.info(f"    {table_name}: {count} registros")
                    except:
                        log.info(f"    {table_name}: {count} registros")
                
                conn.close()
                
            except Exception as e:
                log.warning(f"❌ Erro ao verificar {db_path}: {e}")
        else:
            log.info(f"📊 {db_path}: Não existe")

def check_active_processes():
    """Verifica processos ativos do sistema."""
    log.info("\n🏃 VERIFICANDO PROCESSOS ATIVOS")
    log.info("-" * 40)
    
    import subprocess
    
    # Verificar processos Python relacionados ao trading
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        trading_processes = []
        for line in lines:
            if 'python' in line.lower() and any(keyword in line.lower() for keyword in ['bot', 'trading', 'multi_agent', 'main.py']):
                trading_processes.append(line.strip())
        
        if trading_processes:
            log.info(f"🟢 {len(trading_processes)} processos de trading encontrados:")
            for process in trading_processes:
                # Extrair PID e comando principal
                parts = process.split()
                if len(parts) >= 11:
                    pid = parts[1]
                    cmd = ' '.join(parts[10:])[:80] + "..." if len(' '.join(parts[10:])) > 80 else ' '.join(parts[10:])
                    log.info(f"    PID {pid}: {cmd}")
        else:
            log.info("🔴 Nenhum processo de trading ativo encontrado")
            
    except Exception as e:
        log.warning(f"❌ Erro ao verificar processos: {e}")

def check_log_activity():
    """Verifica atividade recente nos logs."""
    log.info("\n📄 VERIFICANDO ATIVIDADE DOS LOGS")
    log.info("-" * 40)
    
    log_files = glob.glob("logs/*.log") + glob.glob("*.log")
    
    recent_activity = []
    
    for log_file in log_files:
        try:
            stat = os.stat(log_file)
            mod_time = datetime.fromtimestamp(stat.st_mtime)
            size_mb = stat.st_size / (1024 * 1024)
            age_hours = (datetime.now() - mod_time).total_seconds() / 3600
            
            recent_activity.append({
                'file': log_file,
                'mod_time': mod_time,
                'age_hours': age_hours,
                'size_mb': size_mb
            })
            
        except Exception as e:
            log.warning(f"Erro ao verificar {log_file}: {e}")
    
    # Ordenar por mais recente
    recent_activity.sort(key=lambda x: x['age_hours'])
    
    for log_info in recent_activity[:10]:  # Mostrar top 10
        status = "🟢 ATIVO" if log_info['age_hours'] < 1 else "🟡 RECENTE" if log_info['age_hours'] < 24 else "🔴 ANTIGO"
        log.info(f"    {log_info['file']}: {status} - {log_info['age_hours']:.1f}h - {log_info['size_mb']:.1f}MB")

def get_system_recommendations(grid_states, config):
    """Gera recomendações baseadas no estado atual."""
    log.info("\n💡 RECOMENDAÇÕES")
    log.info("-" * 40)
    
    recommendations = []
    
    # Verificar idade dos estados
    old_states = [s for s in grid_states.values() if s['age_hours'] > 24]
    if old_states:
        recommendations.append(f"🧹 {len(old_states)} estados de grid antigos - Execute: python clear_all_caches.py")
    
    # Verificar número de pares ativos vs configuração
    active_pairs = [s for s in grid_states.values() if s['age_hours'] < 1]
    max_pairs = config.get('trading', {}).get('max_concurrent_pairs', 10)
    
    if len(active_pairs) < max_pairs:
        recommendations.append(f"📈 Apenas {len(active_pairs)}/{max_pairs} pares ativos - Sistema pode aceitar mais pares")
    
    # Verificar se há ordens ativas
    total_orders = sum(s['active_orders'] for s in grid_states.values())
    if total_orders == 0:
        recommendations.append("⚠️  Nenhuma ordem ativa encontrada - Verifique se o bot está rodando em modo Production")
    
    # Verificar configuração HFT
    spacing = float(config.get('grid', {}).get('initial_spacing_perc', '0.001'))
    levels = config.get('grid', {}).get('initial_levels', 25)
    
    if spacing > 0.001:  # > 0.1%
        recommendations.append(f"⚡ Espaçamento atual ({spacing*100:.2f}%) pode ser muito largo para HFT - Considere reduzir")
    
    if levels < 30:
        recommendations.append(f"⚡ Níveis atuais ({levels}) podem ser poucos para HFT - Considere aumentar para 35+")
    
    if not recommendations:
        recommendations.append("✅ Sistema aparenta estar configurado corretamente")
    
    for rec in recommendations:
        log.info(f"    {rec}")

def main():
    """Função principal de diagnóstico."""
    log.info("🔬 DIAGNÓSTICO COMPLETO DO SISTEMA DE TRADING")
    log.info("=" * 60)
    
    try:
        # 1. Verificar configuração
        config = check_current_config()
        
        # 2. Verificar grid states
        grid_states = check_grid_states()
        
        # 3. Verificar market data
        check_market_data_db()
        
        # 4. Verificar processos
        check_active_processes()
        
        # 5. Verificar logs
        check_log_activity()
        
        # 6. Gerar recomendações
        get_system_recommendations(grid_states, config)
        
        log.info("\n" + "=" * 60)
        log.info("✅ DIAGNÓSTICO COMPLETO!")
        log.info("📋 Resumo:")
        log.info(f"    - {len(grid_states)} pares com estado salvo")
        log.info(f"    - Configuração carregada com sucesso")
        log.info(f"    - Execute clear_all_caches.py se houver problemas")
        log.info("=" * 60)
        
    except Exception as e:
        log.error(f"❌ Erro durante diagnóstico: {e}")
        raise

if __name__ == "__main__":
    main()