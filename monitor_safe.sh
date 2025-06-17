#\!/bin/bash

# Script seguro para monitorar o sistema sem criar conflitos

# Função para mostrar logs em tempo real
monitor_logs() {
    echo "📊 Monitorando logs do sistema trading..."
    echo "🔄 Logs atualizados a cada 30 segundos (conforme configuração)"
    echo "❌ Para parar: Ctrl+C"
    echo "═══════════════════════════════════════════════════════════"
    
    # Criar arquivo temporário para marcar última visualização
    LAST_SEEN_FILE="/tmp/monitor_last_seen"
    
    while true; do
        # Limpar tela
        clear
        
        echo "🕒 $(date '+%H:%M:%S') - Monitor do Sistema Trading"
        echo "═══════════════════════════════════════════════════════════"
        
        # Mostrar status dos processos
        echo "📈 Processos Trading Ativos:"
        PROCESSES=$(ps aux  < /dev/null |  grep -E "multi_agent_bot|python.*bot" | grep -v grep | wc -l)
        if [ $PROCESSES -gt 0 ]; then
            echo "✅ $PROCESSES instâncias rodando"
            ps aux | grep -E "multi_agent_bot|python.*bot" | grep -v grep | head -3 | awk '{print "   PID:", $2, "CPU:", $3"%", "Mem:", $4"%", "Tempo:", $10}'
        else
            echo "❌ Nenhuma instância rodando"
        fi
        
        echo ""
        echo "📊 Logs de Pares (últimos 20 logs):"
        echo "═══════════════════════════════════════════════════════════"
        
        # Mostrar logs mais recentes dos pares
        if [ -d "logs/pairs" ]; then
            find logs/pairs -name "*.log" -not -name "multi_pair.log" -exec tail -5 {} \; | tail -20
        fi
        
        echo ""
        echo "📋 Última Atividade do Sistema:"
        echo "═══════════════════════════════════════════════════════════"
        
        # Mostrar log principal
        if [ -f "logs/bot.log" ]; then
            tail -10 logs/bot.log | grep -E "(ERROR|WARNING|INFO)" | tail -5
        else
            echo "❌ Log principal não encontrado"
        fi
        
        echo ""
        echo "🔄 Aguardando 30 segundos... (Ctrl+C para parar)"
        sleep 30
    done
}

# Função para ver status geral
show_status() {
    echo "🔍 Status Geral do Sistema Trading"
    echo "═══════════════════════════════════════════════════════════"
    
    # Status dos processos
    echo "📈 Processos:"
    PROCESSES=$(ps aux | grep -E "multi_agent_bot|python.*bot" | grep -v grep)
    if [ \! -z "$PROCESSES" ]; then
        echo "$PROCESSES" | awk '{print "  PID:", $2, "Iniciado:", $9, "CPU:", $3"%", "Mem:", $4"%"}'
    else
        echo "  ❌ Nenhuma instância rodando"
    fi
    
    echo ""
    echo "📊 Atividade de Trading:"
    if [ -f "data/trade_activities.json" ]; then
        echo "  ✅ Arquivo de atividades encontrado"
        python3 -c "
import json
import time
try:
    with open('data/trade_activities.json', 'r') as f:
        activities = json.load(f)
    
    current_time = time.time()
    for symbol, data in activities.items():
        last_trade = data['last_trade_time']
        hours_ago = (current_time - last_trade) / 3600
        status = '🔥 ATIVO' if hours_ago < 1 else '⏰ INATIVO'
        print(f'  {symbol}: {status} (última atividade: {hours_ago:.1f}h atrás)')
except Exception as e:
    print(f'  ❌ Erro lendo atividades: {e}')
"
    else
        echo "  ❌ Arquivo de atividades não encontrado"
    fi
    
    echo ""
    echo "💰 Logs de Lucros (últimas 3 entradas):"
    if [ -f "logs/trades/profits.log" ]; then
        tail -3 logs/trades/profits.log
    else
        echo "  ❌ Log de lucros não encontrado"
    fi
}

# Menu principal
case "$1" in
    "logs")
        monitor_logs
        ;;
    "status")
        show_status
        ;;
    *)
        echo "🤖 Monitor Seguro do Sistema Trading"
        echo "═══════════════════════════════════════════════════════════"
        echo ""
        echo "Comandos disponíveis:"
        echo "  ./monitor_safe.sh logs    - Monitorar logs em tempo real"
        echo "  ./monitor_safe.sh status  - Ver status geral do sistema"
        echo ""
        echo "⚠️  IMPORTANTE: Este monitor é apenas para visualização."
        echo "    Não interfere com o sistema de trading em execução."
        ;;
esac
