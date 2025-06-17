#!/usr/bin/env python3
"""
Script para limpar logs antigos e manter apenas logs relevantes
"""

import os
import sys
import glob
from datetime import datetime

def clean_old_logs():
    """Limpa logs antigos e grandes, mantendo apenas arquivos recentes pequenos."""
    
    log_dirs = [
        "logs/",
        "src/logs/",
        "logs/pairs/",
        "src/logs/pairs/",
        "logs/trades/",
        "src/logs/trades/"
    ]
    
    total_removed = 0
    total_size_freed = 0
    
    print("🧹 Limpando logs antigos...")
    
    for log_dir in log_dirs:
        if not os.path.exists(log_dir):
            continue
            
        print(f"\n📁 Processando: {log_dir}")
        
        # Buscar todos os arquivos .log
        log_files = glob.glob(os.path.join(log_dir, "*.log*"))
        
        for log_file in log_files:
            try:
                file_size = os.path.getsize(log_file)
                
                # Remover arquivos maiores que 10MB ou arquivos de backup (.log.1, .log.2, etc.)
                should_remove = False
                reason = ""
                
                if file_size > 10 * 1024 * 1024:  # 10MB
                    should_remove = True
                    reason = f"muito grande ({file_size/1024/1024:.1f}MB)"
                elif ".log." in log_file:  # Arquivos de backup
                    should_remove = True
                    reason = "arquivo de backup"
                
                if should_remove:
                    os.remove(log_file)
                    total_removed += 1
                    total_size_freed += file_size
                    print(f"  ❌ Removido: {os.path.basename(log_file)} - {reason}")
                else:
                    print(f"  ✅ Mantido: {os.path.basename(log_file)} ({file_size/1024:.1f}KB)")
                    
            except Exception as e:
                print(f"  ⚠️  Erro processando {log_file}: {e}")
    
    print(f"\n🏁 Limpeza concluída:")
    print(f"   📊 {total_removed} arquivos removidos")
    print(f"   💾 {total_size_freed/1024/1024:.1f}MB liberados")
    
    # Truncar logs principais para começar frescos
    main_logs = [
        "logs/bot.log",
        "src/logs/bot.log",
        "logs/flask_api.log",
        "logs/flask_startup.log"
    ]
    
    print(f"\n🔄 Truncando logs principais...")
    for main_log in main_logs:
        if os.path.exists(main_log):
            try:
                # Truncar arquivo (limpar conteúdo mas manter arquivo)
                with open(main_log, 'w') as f:
                    f.write(f"# Log reiniciado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                print(f"  ✅ Truncado: {main_log}")
            except Exception as e:
                print(f"  ⚠️  Erro truncando {main_log}: {e}")

def filter_logs_from_9am():
    """Cria um filtro para mostrar apenas logs de hoje a partir das 9h."""
    
    today = datetime.now().strftime("%Y-%m-%d")
    filter_time = f"{today} 09:"
    
    filter_script = f'''#!/bin/bash
# Script para filtrar logs a partir das 9h de hoje
# Gerado automaticamente em {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

echo "📊 Mostrando logs a partir de {filter_time}..."
echo "==============================================="

# Função para filtrar logs
filter_log() {{
    local file="$1"
    if [ -f "$file" ]; then
        echo "📁 $file:"
        grep -E "{today} (09:|1[0-9]:|2[0-3]:)" "$file" | tail -100
        echo ""
    fi
}}

# Filtrar logs principais
filter_log "logs/bot.log"
filter_log "src/logs/bot.log"

# Filtrar logs de pares mais importantes
for pair in ADAUSDT DOGEUSDT XRPUSDT TRXUSDT XLMUSDT ONTUSDT DENTUSDT ICXUSDT POLUSDT; do
    filter_log "logs/pairs/${{pair,,}}.log"
    filter_log "src/logs/pairs/${{pair,,}}.log"
done

echo "✅ Filtro de logs concluído!"
'''
    
    with open("view_today_logs.sh", "w") as f:
        f.write(filter_script)
    
    os.chmod("view_today_logs.sh", 0o755)
    print(f"📜 Script criado: view_today_logs.sh")
    print(f"   Execute: ./view_today_logs.sh para ver logs de hoje após 9h")

if __name__ == "__main__":
    print("🔧 Iniciando limpeza e configuração de logs...")
    
    clean_old_logs()
    filter_logs_from_9am()
    
    print(f"\n✅ Configuração concluída!")
    print(f"   🔄 Logs configurados para rotação agressiva")
    print(f"   📊 Use ./view_today_logs.sh para ver logs relevantes")