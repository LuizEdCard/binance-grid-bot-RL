#!/bin/bash

# Script para parar o sistema multi-agente de forma elegante
# Garante que todos os processos sejam finalizados corretamente

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Função para imprimir mensagens coloridas
print_status() {
    echo -e "${CYAN}[INFO]${NC} $1"
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

print_bot() {
    echo -e "${PURPLE}[BOT]${NC} $1"
}

print_api() {
    echo -e "${BLUE}[API]${NC} $1"
}

# Função para parar processos de forma elegante
stop_process_gracefully() {
    local pid=$1
    local name=$2
    local timeout=${3:-10}
    
    if kill -0 $pid 2>/dev/null; then
        print_status "Stopping $name (PID: $pid)..."
        
        # Enviar SIGTERM para parada elegante
        kill -TERM $pid 2>/dev/null
        
        # Aguardar até o timeout
        local count=0
        while kill -0 $pid 2>/dev/null && [ $count -lt $timeout ]; do
            sleep 1
            count=$((count + 1))
            echo -n "."
        done
        echo ""
        
        # Se ainda estiver rodando, forçar parada
        if kill -0 $pid 2>/dev/null; then
            print_warning "$name not responding, forcing termination..."
            kill -KILL $pid 2>/dev/null
            sleep 1
        fi
        
        # Verificar se parou
        if ! kill -0 $pid 2>/dev/null; then
            print_success "$name stopped successfully"
            return 0
        else
            print_error "Failed to stop $name"
            return 1
        fi
    else
        print_warning "$name (PID: $pid) is not running"
        return 0
    fi
}

# Função para parar processos por nome
stop_processes_by_name() {
    local process_name=$1
    local description=$2
    
    print_status "Looking for $description processes..."
    
    # Encontrar todos os PIDs do processo
    local pids=$(pgrep -f "$process_name" 2>/dev/null)
    
    if [ -z "$pids" ]; then
        print_warning "No $description processes found"
        return 0
    fi
    
    print_status "Found $description processes: $pids"
    
    # Parar cada processo
    for pid in $pids; do
        stop_process_gracefully $pid "$description"
    done
}

# Função principal
main() {
    print_status "Starting Multi-Agent System Shutdown..."
    echo ""
    
    # 1. Parar o sistema multi-agente principal
    print_bot "Stopping Multi-Agent Bot processes..."
    stop_processes_by_name "multi_agent_bot.py" "Multi-Agent Bot"
    
    # 2. Parar processos Python relacionados ao grid bot
    print_status "Stopping related Python processes..."
    stop_processes_by_name "python.*grid" "Grid Bot related"
    
    # 3. Parar a API Flask se estiver rodando
    print_api "Stopping Flask API processes..."
    stop_processes_by_name "src/main.py" "Flask API"
    
    # 4. Parar processos de monitoramento
    print_status "Stopping monitoring processes..."
    stop_processes_by_name "monitor" "Monitor"
    
    # 5. Limpar processos órfãos específicos do projeto
    print_status "Cleaning up orphaned processes..."
    
    # Parar processos que podem ter ficado órfãos
    local orphan_pids=$(ps aux | grep -E "(binance|grid|trading|agent)" | grep python | grep -v grep | awk '{print $2}' 2>/dev/null)
    
    if [ ! -z "$orphan_pids" ]; then
        print_warning "Found potential orphan processes: $orphan_pids"
        for pid in $orphan_pids; do
            # Verificar se o processo ainda está rodando e é relacionado ao nosso projeto
            if ps -p $pid -o cmd= 2>/dev/null | grep -q "binance-grid-bot-RL"; then
                stop_process_gracefully $pid "Orphan process"
            fi
        done
    fi
    
    # 6. Verificar se restam processos ativos
    print_status "Verifying shutdown completion..."
    
    local remaining_processes=$(ps aux | grep -E "(multi_agent_bot|src/main.py)" | grep -v grep | grep -v stop_multi_agent_system.sh)
    
    if [ -z "$remaining_processes" ]; then
        print_success "All Multi-Agent System processes stopped successfully!"
    else
        print_warning "Some processes may still be running:"
        echo "$remaining_processes"
        echo ""
        print_warning "You may need to manually stop them with:"
        echo "  pkill -f multi_agent_bot"
        echo "  pkill -f 'src/main.py'"
    fi
    
    # 7. Limpar arquivos temporários e locks
    print_status "Cleaning up temporary files..."
    
    # Remover arquivos de lock se existirem
    if [ -f "multi_agent_bot.lock" ]; then
        rm -f multi_agent_bot.lock
        print_status "Removed lock file"
    fi
    
    # Limpar arquivos PID se existirem
    if [ -f "multi_agent_bot.pid" ]; then
        rm -f multi_agent_bot.pid
        print_status "Removed PID file"
    fi
    
    echo ""
    print_success "Multi-Agent System shutdown completed!"
    print_status "To restart the system, use: ./start_multi_agent_bot.sh or ./start_complete_system.sh"
}

# Verificar se o script está sendo executado com privilégios adequados
if [ "$EUID" -eq 0 ]; then
    print_warning "Running as root. This is not recommended for stopping user processes."
fi

# Executar função principal
main

# Mostrar status final
echo ""
print_status "Current Python processes:"
ps aux | grep python | grep -v grep | head -5

echo ""
print_status "System status check complete."

