#!/bin/bash

# Script automatizado para resolver problemas de cache e pares limitados
# Execute este script sempre que fizer mudanças na configuração

echo "🔧 SCRIPT DE CORREÇÃO DO SISTEMA DE TRADING"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: Stop any running trading processes
print_status "Parando processos de trading ativos..."
pkill -f "multi_agent_bot.py" 2>/dev/null
pkill -f "main.py" 2>/dev/null
sleep 3
print_success "Processos parados"

# Step 2: Clear all caches
print_status "Limpando todos os caches..."
if [ -f "clear_all_caches.py" ]; then
    python clear_all_caches.py
    print_success "Caches limpos com sucesso"
else
    print_error "Script clear_all_caches.py não encontrado"
    exit 1
fi

# Step 3: Verify configuration
print_status "Verificando configuração atual..."
if [ -f "src/config/config.yaml" ]; then
    # Count preferred symbols
    FUTURES_PAIRS=$(grep -A 20 "preferred_symbols:" src/config/config.yaml | grep "USDT" | wc -l)
    MAX_PAIRS=$(grep "max_concurrent_pairs:" src/config/config.yaml | awk '{print $2}')
    
    print_success "Configuração encontrada:"
    echo "    - Pares preferidos: $FUTURES_PAIRS"
    echo "    - Máximo de pares: $MAX_PAIRS"
    
    if [ "$FUTURES_PAIRS" -ge 8 ]; then
        print_success "Número de pares preferidos adequado ($FUTURES_PAIRS >= 8)"
    else
        print_warning "Poucos pares preferidos ($FUTURES_PAIRS < 8)"
    fi
else
    print_error "Arquivo de configuração não encontrado"
    exit 1
fi

# Step 4: Test pair selection
print_status "Testando seleção de pares..."
if [ -f "force_pair_update.py" ]; then
    python force_pair_update.py > /tmp/pair_test.log 2>&1
    
    if [ $? -eq 0 ]; then
        SELECTED_PAIRS=$(grep "Lista final:" /tmp/pair_test.log | tail -1)
        print_success "Teste de seleção concluído"
        echo "    $SELECTED_PAIRS"
    else
        print_warning "Teste de seleção teve problemas - verifique logs"
        echo "    Log: /tmp/pair_test.log"
    fi
else
    print_error "Script force_pair_update.py não encontrado"
fi

# Step 5: Start the system
print_status "Iniciando sistema de trading..."

if [ -f "start_multi_agent_bot.sh" ]; then
    print_status "Usando start_multi_agent_bot.sh..."
    chmod +x start_multi_agent_bot.sh
    ./start_multi_agent_bot.sh &
    TRADING_PID=$!
    sleep 5
    
    # Check if process is still running
    if kill -0 $TRADING_PID 2>/dev/null; then
        print_success "Sistema multi-agent iniciado (PID: $TRADING_PID)"
    else
        print_error "Sistema multi-agent falhou ao iniciar"
        echo "Tentando método alternativo..."
        cd src && python multi_agent_bot.py &
        ALT_PID=$!
        sleep 3
        if kill -0 $ALT_PID 2>/dev/null; then
            print_success "Sistema iniciado com método alternativo (PID: $ALT_PID)"
        else
            print_error "Falha ao iniciar sistema"
            exit 1
        fi
    fi
else
    print_warning "start_multi_agent_bot.sh não encontrado, usando método direto"
    cd src && python multi_agent_bot.py &
    DIRECT_PID=$!
    sleep 3
    if kill -0 $DIRECT_PID 2>/dev/null; then
        print_success "Sistema iniciado diretamente (PID: $DIRECT_PID)"
    else
        print_error "Falha ao iniciar sistema"
        exit 1
    fi
fi

# Step 6: Monitor system startup
print_status "Monitorando inicialização do sistema..."
sleep 10

# Check for trading processes
TRADING_PROCESSES=$(ps aux | grep -E "(multi_agent_bot|main\.py)" | grep -v grep | wc -l)

if [ "$TRADING_PROCESSES" -gt 0 ]; then
    print_success "Sistema de trading está rodando ($TRADING_PROCESSES processos)"
    
    # Show running processes
    echo ""
    print_status "Processos ativos:"
    ps aux | grep -E "(multi_agent_bot|main\.py)" | grep -v grep | while read line; do
        echo "    $line"
    done
else
    print_error "Nenhum processo de trading detectado"
fi

# Step 7: Check logs for activity
print_status "Verificando logs recentes..."
if [ -d "logs" ]; then
    RECENT_LOGS=$(find logs -name "*.log" -mmin -5 2>/dev/null | wc -l)
    if [ "$RECENT_LOGS" -gt 0 ]; then
        print_success "Logs recentes encontrados ($RECENT_LOGS arquivos)"
        
        # Show recent log activity
        echo ""
        print_status "Atividade recente nos logs:"
        find logs -name "*.log" -mmin -5 -exec tail -3 {} \; 2>/dev/null | head -10
    else
        print_warning "Nenhum log recente encontrado"
    fi
else
    print_warning "Diretório de logs não encontrado"
fi

# Step 8: Test API endpoints
print_status "Testando endpoints da API..."
sleep 5

# Test if Flask API is running
if curl -s "http://localhost:5000/api/live/system/status" > /dev/null 2>&1; then
    print_success "API Flask está respondendo"
    
    # Test specific endpoints
    echo ""
    print_status "Testando endpoints específicos:"
    
    # System status
    STATUS_RESPONSE=$(curl -s "http://localhost:5000/api/live/system/status" 2>/dev/null)
    if [ ! -z "$STATUS_RESPONSE" ]; then
        echo "    ✅ /api/live/system/status: OK"
    else
        echo "    ❌ /api/live/system/status: FAIL"
    fi
    
    # Trading data
    TRADING_RESPONSE=$(curl -s "http://localhost:5000/api/live/trading/all" 2>/dev/null)
    if [ ! -z "$TRADING_RESPONSE" ]; then
        echo "    ✅ /api/live/trading/all: OK"
    else
        echo "    ❌ /api/live/trading/all: FAIL"
    fi
    
else
    print_warning "API Flask não está respondendo ainda (normal nos primeiros minutos)"
fi

# Final summary
echo ""
echo "=========================================="
print_success "SCRIPT DE CORREÇÃO CONCLUÍDO!"
echo ""
print_status "📋 RESUMO:"
echo "    ✅ Caches limpos"
echo "    ✅ Configuração verificada"
echo "    ✅ Sistema iniciado"
echo ""
print_status "💡 PRÓXIMOS PASSOS:"
echo "    1. Monitore logs: tail -f logs/bot.log"
echo "    2. Verifique pares ativos: curl localhost:5000/api/live/trading/all"
echo "    3. Monitor sistema: curl localhost:5000/api/live/system/status"
echo "    4. Aguarde ~15 minutos para ver novas ordens"
echo ""
print_status "🔧 COMANDOS ÚTEIS:"
echo "    - Verificar processos: ps aux | grep python"
echo "    - Parar sistema: pkill -f multi_agent_bot.py"
echo "    - Limpar cache: python clear_all_caches.py"
echo "    - Testar pares: python force_pair_update.py"
echo ""
print_status "📊 ENDPOINTS DE GERENCIAMENTO:"
echo "    - POST /api/system/clear_cache"
echo "    - POST /api/system/reload_config"
echo "    - POST /api/system/force_pair_update"
echo ""
echo "=========================================="