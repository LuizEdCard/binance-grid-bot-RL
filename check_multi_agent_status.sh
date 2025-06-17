#!/bin/bash

# Script para verificar o status do sistema multi-agente
# Mostra informações detalhadas sobre processos ativos e recursos

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

# Função para verificar se um processo está rodando
check_process() {
    local process_name=$1
    local description=$2
    
    local pids=$(pgrep -f "$process_name" 2>/dev/null)
    
    if [ -z "$pids" ]; then
        print_error "$description: NOT RUNNING"
        return 1
    else
        print_success "$description: RUNNING (PIDs: $pids)"
        
        # Mostrar informações detalhadas dos processos
        for pid in $pids; do
            if ps -p $pid > /dev/null 2>&1; then
                local mem_usage=$(ps -p $pid -o rss= | awk '{print $1/1024 " MB"}')
                local cpu_usage=$(ps -p $pid -o pcpu= | awk '{print $1"%"}')
                local start_time=$(ps -p $pid -o lstart= | awk '{print $1, $2, $3, $4}')
                echo "    PID $pid: CPU: $cpu_usage, Memory: $mem_usage, Started: $start_time"
            fi
        done
        return 0
    fi
}

# Função para verificar portas
check_port() {
    local port=$1
    local description=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        local pid=$(lsof -Pi :$port -sTCP:LISTEN -t)
        print_success "Port $port ($description): ACTIVE (PID: $pid)"
        return 0
    else
        print_error "Port $port ($description): NOT ACTIVE"
        return 1
    fi
}

# Função para verificar logs
check_logs() {
    local log_file=$1
    local description=$2
    
    if [ -f "$log_file" ]; then
        local size=$(du -h "$log_file" | cut -f1)
        local last_mod=$(stat -c %y "$log_file" | cut -d'.' -f1)
        print_success "$description log: EXISTS ($size, last modified: $last_mod)"
        
        # Mostrar últimas linhas se houver erros recentes
        local recent_errors=$(tail -n 20 "$log_file" | grep -i "error\|critical\|fatal" | wc -l)
        if [ $recent_errors -gt 0 ]; then
            print_warning "  ⚠️  Found $recent_errors recent error(s) in log"
        fi
        return 0
    else
        print_error "$description log: NOT FOUND"
        return 1
    fi
}

# Função para mostrar uso de recursos
show_system_resources() {
    print_status "System Resources:"
    
    # CPU usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    echo "  CPU Usage: ${cpu_usage}%"
    
    # Memory usage
    local mem_info=$(free -h | grep "Mem:")
    local mem_used=$(echo $mem_info | awk '{print $3}')
    local mem_total=$(echo $mem_info | awk '{print $2}')
    echo "  Memory: $mem_used / $mem_total"
    
    # Disk usage for project directory
    local disk_usage=$(df -h . | tail -1 | awk '{print $5}')
    echo "  Disk Usage (current dir): $disk_usage"
    
    # Load average
    local load_avg=$(uptime | awk -F'load average:' '{print $2}')
    echo "  Load Average:$load_avg"
}

# Função para verificar conectividade
check_connectivity() {
    print_status "Connectivity Check:"
    
    # Testar conexão com Binance API
    if curl -s --connect-timeout 5 "https://api.binance.com/api/v3/ping" >/dev/null; then
        print_success "  Binance API: REACHABLE"
    else
        print_error "  Binance API: UNREACHABLE"
    fi
    
    # Verificar se localhost API está respondendo
    if curl -s --connect-timeout 2 "http://localhost:5000/health" >/dev/null; then
        print_success "  Local API: RESPONDING"
    else
        print_warning "  Local API: NOT RESPONDING (may be normal if not running)"
    fi
}

# Função principal
main() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}  Multi-Agent System Status${NC}"
    echo -e "${CYAN}================================${NC}"
    echo ""
    
    # 1. Verificar processos principais
    print_status "Checking Core Processes:"
    echo ""
    
    local multi_agent_running=false
    local api_running=false
    
    # Multi-Agent Bot
    if check_process "multi_agent_bot.py" "Multi-Agent Bot"; then
        multi_agent_running=true
    fi
    echo ""
    
    # Flask API
    if check_process "src/main.py" "Flask API"; then
        api_running=true
    fi
    echo ""
    
    # 2. Verificar portas
    print_status "Checking Network Ports:"
    echo ""
    check_port 5000 "Flask API"
    echo ""
    
    # 3. Verificar logs
    print_status "Checking Log Files:"
    echo ""
    check_logs "logs/multi_agent_bot.log" "Multi-Agent Bot"
    check_logs "logs/flask_api.log" "Flask API"
    check_logs "logs/trading.log" "Trading"
    echo ""
    
    # 4. Verificar arquivos de configuração
    print_status "Checking Configuration:"
    echo ""
    if [ -f "src/config/config.yaml" ]; then
        print_success "Configuration file: EXISTS"
    else
        print_error "Configuration file: NOT FOUND"
    fi
    
    if [ -f "secrets/.env" ]; then
        print_success "Environment file: EXISTS"
    else
        print_warning "Environment file: NOT FOUND (may need setup)"
    fi
    echo ""
    
    # 5. Mostrar recursos do sistema
    show_system_resources
    echo ""
    
    # 6. Verificar conectividade
    check_connectivity
    echo ""
    
    # 7. Resumo do status
    print_status "System Status Summary:"
    echo ""
    
    if $multi_agent_running && $api_running; then
        print_success "✅ FULLY OPERATIONAL - All core components running"
    elif $multi_agent_running; then
        print_warning "⚠️  PARTIALLY OPERATIONAL - Bot running, API stopped"
    elif $api_running; then
        print_warning "⚠️  PARTIALLY OPERATIONAL - API running, Bot stopped"
    else
        print_error "❌ SYSTEM STOPPED - No core components running"
    fi
    
    echo ""
    print_status "Management Commands:"
    echo "  Start system: ./start_multi_agent_bot.sh or ./start_complete_system.sh"
    echo "  Stop system:  ./stop_multi_agent_system.sh"
    echo "  View logs:    tail -f logs/*.log"
    echo "  Monitor:      ./monitor_bot.sh"
    
    echo ""
    echo -e "${CYAN}================================${NC}"
}

# Executar função principal
main

