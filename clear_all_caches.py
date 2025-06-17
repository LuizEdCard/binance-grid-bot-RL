#!/usr/bin/env python3
"""
Script para limpar TODOS os caches do sistema de trading
Execute este script sempre que fizer alterações na configuração
"""

import os
import shutil
import sqlite3
import json
import glob
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def clear_cache_directory(directory_path: str, description: str):
    """Limpa um diretório de cache específico."""
    try:
        if os.path.exists(directory_path):
            if os.path.isdir(directory_path):
                file_count = len(os.listdir(directory_path))
                shutil.rmtree(directory_path)
                os.makedirs(directory_path, exist_ok=True)
                log.info(f"✅ {description}: {file_count} arquivos removidos de {directory_path}")
            else:
                os.remove(directory_path)
                log.info(f"✅ {description}: Arquivo {directory_path} removido")
        else:
            log.info(f"⚠️  {description}: {directory_path} não existe")
    except Exception as e:
        log.error(f"❌ Erro ao limpar {description}: {e}")

def clear_file_pattern(pattern: str, description: str):
    """Remove arquivos que correspondem a um padrão."""
    try:
        files = glob.glob(pattern)
        count = 0
        for file_path in files:
            try:
                os.remove(file_path)
                count += 1
            except Exception as e:
                log.warning(f"Erro ao remover {file_path}: {e}")
        
        if count > 0:
            log.info(f"✅ {description}: {count} arquivos removidos")
        else:
            log.info(f"⚠️  {description}: Nenhum arquivo encontrado ({pattern})")
    except Exception as e:
        log.error(f"❌ Erro ao limpar {description}: {e}")

def clear_sqlite_database(db_path: str, description: str):
    """Limpa tabelas de um banco SQLite."""
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Obter lista de tabelas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            table_count = 0
            for table in tables:
                table_name = table[0]
                if table_name != 'sqlite_sequence':  # Não mexer na tabela do sistema
                    cursor.execute(f"DELETE FROM {table_name}")
                    table_count += 1
            
            conn.commit()
            conn.close()
            log.info(f"✅ {description}: {table_count} tabelas limpas em {db_path}")
        else:
            log.info(f"⚠️  {description}: {db_path} não existe")
    except Exception as e:
        log.error(f"❌ Erro ao limpar {description}: {e}")

def clear_json_cache_file(file_path: str, description: str):
    """Limpa um arquivo JSON de cache específico."""
    try:
        if os.path.exists(file_path):
            # Criar cache vazio
            empty_cache = {}
            with open(file_path, 'w') as f:
                json.dump(empty_cache, f, indent=2)
            log.info(f"✅ {description}: Cache resetado em {file_path}")
        else:
            log.info(f"⚠️  {description}: {file_path} não existe")
    except Exception as e:
        log.error(f"❌ Erro ao limpar {description}: {e}")

def clear_python_cache():
    """Remove cache de Python (__pycache__)."""
    cache_dirs = []
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                cache_dirs.append(os.path.join(root, dir_name))
    
    count = 0
    for cache_dir in cache_dirs:
        try:
            shutil.rmtree(cache_dir)
            count += 1
        except Exception as e:
            log.warning(f"Erro ao remover {cache_dir}: {e}")
    
    if count > 0:
        log.info(f"✅ Python Cache: {count} diretórios __pycache__ removidos")
    else:
        log.info("⚠️  Python Cache: Nenhum __pycache__ encontrado")

def clear_all_caches():
    """Função principal para limpar TODOS os caches."""
    log.info("🧹 INICIANDO LIMPEZA COMPLETA DE CACHES")
    log.info("=" * 60)
    
    # 1. Grid States (JSON) - CRÍTICO para mudanças de configuração
    clear_cache_directory("data/grid_states", "Grid States (data/)")
    clear_cache_directory("src/data/grid_states", "Grid States (src/data/)")
    clear_file_pattern("*_state.json", "Grid States (arquivos soltos)")
    
    # 2. Market Analysis Cache (JSON)
    clear_json_cache_file("data/market_analysis_cache.json", "Market Analysis Cache")
    clear_json_cache_file("src/data/market_analysis_cache.json", "Market Analysis Cache (src/)")
    
    # 3. SQLite Databases - Market Data
    clear_sqlite_database("data/market_data.db", "Market Data DB (data/)")
    clear_sqlite_database("src/data/cache/market_data.db", "Market Data DB (src/cache/)")
    clear_sqlite_database("data/cache/market_data.db", "Market Data DB (cache/)")
    
    # 4. Shadow Trading Data
    clear_file_pattern("data/shadow_trades.jsonl", "Shadow Trades")
    clear_file_pattern("data/market_states.jsonl", "Market States")
    clear_file_pattern("data/rl_actions.jsonl", "RL Actions")
    clear_file_pattern("data/performance.jsonl", "Performance Data")
    
    # 5. WebSocket Cache Directories
    clear_cache_directory("data/cache", "Data Cache Directory")
    clear_cache_directory("src/data/cache", "Src Data Cache Directory")
    
    # 6. Temporary files and patterns
    clear_file_pattern("*.tmp", "Temporary Files")
    clear_file_pattern("*.lock", "Lock Files")
    clear_file_pattern("data/*.json", "JSON Data Files")
    clear_file_pattern("src/data/*.json", "Src JSON Data Files")
    
    # 7. Logs antigos (manter apenas logs atuais)
    log.info("📄 Mantendo logs atuais, mas removendo logs antigos...")
    clear_file_pattern("logs/*.log.*", "Rotated Log Files")
    clear_file_pattern("*.log.old", "Old Log Files")
    
    # 8. Python Cache
    clear_python_cache()
    
    # 9. Criar diretórios necessários
    directories_to_create = [
        "data",
        "data/grid_states", 
        "data/cache",
        "src/data",
        "src/data/grid_states",
        "src/data/cache",
        "logs"
    ]
    
    for directory in directories_to_create:
        os.makedirs(directory, exist_ok=True)
    
    log.info("=" * 60)
    log.info("✅ LIMPEZA COMPLETA FINALIZADA!")
    log.info("🔄 Agora reinicie o sistema para aplicar as configurações atuais")
    log.info("💡 Use: ./start_multi_agent_bot.sh ou python src/multi_agent_bot.py")

def backup_important_data():
    """Backup de dados importantes antes da limpeza."""
    backup_dir = f"backup_cache_{int(__import__('time').time())}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Backup apenas de configs importantes
    important_files = [
        "src/config/config.yaml",
        ".env",
        "secrets/.env"
    ]
    
    for file_path in important_files:
        if os.path.exists(file_path):
            try:
                dest = os.path.join(backup_dir, os.path.basename(file_path))
                shutil.copy2(file_path, dest)
                log.info(f"📋 Backup: {file_path} -> {dest}")
            except Exception as e:
                log.warning(f"Erro no backup de {file_path}: {e}")

if __name__ == "__main__":
    try:
        # Opcional: fazer backup de configs importantes
        # backup_important_data()
        
        # Executar limpeza completa
        clear_all_caches()
        
        print("\n" + "="*60)
        print("🎉 SISTEMA LIMPO COM SUCESSO!")
        print("📝 Próximos passos:")
        print("   1. Verifique src/config/config.yaml está correto")
        print("   2. Reinicie o sistema: ./start_multi_agent_bot.sh")
        print("   3. Monitore logs para confirmar novos pares")
        print("="*60)
        
    except KeyboardInterrupt:
        log.info("❌ Limpeza interrompida pelo usuário")
    except Exception as e:
        log.error(f"❌ Erro durante limpeza: {e}")
        raise