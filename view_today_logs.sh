#!/bin/bash
# Script para filtrar logs a partir das 9h de hoje
# Gerado automaticamente em 2025-06-15 11:43:41

echo "📊 Mostrando logs a partir de 2025-06-15 09:..."
echo "==============================================="

# Função para filtrar logs
filter_log() {
    local file="$1"
    if [ -f "$file" ]; then
        echo "📁 $file:"
        grep -E "2025-06-15 (09:|1[0-9]:|2[0-3]:)" "$file" | tail -100
        echo ""
    fi
}

# Filtrar logs principais
filter_log "logs/bot.log"
filter_log "src/logs/bot.log"

# Filtrar logs de pares mais importantes
for pair in ADAUSDT DOGEUSDT XRPUSDT TRXUSDT XLMUSDT ONTUSDT DENTUSDT ICXUSDT POLUSDT; do
    filter_log "logs/pairs/${pair,,}.log"
    filter_log "src/logs/pairs/${pair,,}.log"
done

echo "✅ Filtro de logs concluído!"
