#!/bin/bash

# Script central de gerenciamento do sistema multi-agente
# Fornece interface unificada para todas as operações

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

print_header() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}================================${NC}"
}

# Função para mostrar menu
show_menu() {
    clear
    print_header "Multi-Agent System Manager"
    echo ""
    echo -e "${YELLOW}Available Commands:${NC}"
    echo ""
    echo -e "  ${GREEN}1. start${NC}     - Start the complete multi-agent system"
    echo -e "  ${GREEN}2. stop${NC}      - Stop all multi-agent processes"
    echo -e "  ${GREEN}3. restart${NC}   - Restart the complete system"
    echo -e "  ${GREEN}4. status${NC}    - Check system status"
    echo -e "  ${GREEN}5. logs${NC}      - View real-time logs"
    echo -e "  ${GREEN}6. monitor${NC}   - Start monitoring mode"
    echo -e "  ${GREEN}7. health${NC}    - Quick health check"
    echo -e "  ${GREEN}8. cleanup${NC}   - Clean up logs and temporary files"
    echo -e "  ${GREEN}9. help${NC}      - Show detailed help"
    echo -e "  ${RED}0. exit${NC}      - Exit manager"
    echo ""
    echo -e "${CYAN}Current Status:${NC}"
    
    # Rápida verificação de status
    if pgrep -f "multi_agent_bot.py" >/dev/null; then
        echo -e "  ✅ Multi-Agent Bot: ${GREEN}RUNNING${NC}"
    else
        echo -e "  ❌ Multi-Agent Bot: ${RED}STOPPED${NC}"
    fi
    
    if pgrep -f "src/main.py" >/dev/null; then
        echo -e "  ✅ Flask API: ${GREEN}RUNNING${NC}"
    else
        echo -e "  ❌ Flask API: ${RED}STOPPED${NC}"
    fi
    
    echo ""
}

# Função para iniciar o sistema
start_system() {
    print_status "Starting Multi-Agent System..."
    
    # Verificar se já está rodando
    if pgrep -f "multi_agent_bot.py" >/dev/null; then
        print_warning "Multi-Agent Bot is already running!"
        read -p "Do you want to restart it? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
        stop_system
        sleep 2
    fi
    
    # Escolher script de inicialização
    echo ""
    echo "Choose startup mode:"
    echo "1. Complete System (Bot + API + Frontend)"
    echo "2. Multi-Agent Bot Only"
    echo "3. API Only"
    read -p "Enter choice (1-3): " choice
    
    case $choice in
        1)
            print_status "Starting complete system..."
            if [ -f "start_complete_system.sh" ]; then
                chmod +x start_complete_system.sh
                nohup ./start_complete_system.sh > system_startup.log 2>&1 &
                print_success "Complete system startup initiated"
            else
                print_error "start_complete_system.sh not found"
            fi
            ;;
        2)
            print_status "Starting multi-agent bot only..."
            if [ -f "start_multi_agent_bot.sh" ]; then
                chmod +x start_multi_agent_bot.sh
                nohup ./start_multi_agent_bot.sh > bot_startup.log 2>&1 &
                print_success "Multi-agent bot startup initiated"
            else
                print_error "start_multi_agent_bot.sh not found"
            fi
            ;;
        3)
            print_status "Starting API only..."
            cd src && python3 main.py &
            print_success "API startup initiated"
            ;;
        *)
            print_error "Invalid choice"
            return 1
            ;;
    esac
    
    sleep 3
    print_status "Waiting for services to start..."
    sleep 2
    
    # Verificar se iniciou com sucesso
    if pgrep -f "multi_agent_bot.py" >/dev/null || pgrep -f "src/main.py" >/dev/null; then
        print_success "System started successfully!"
    else
        print_error "Failed to start system. Check logs for details."
    fi
}

# Função para parar o sistema
stop_system() {
    print_status "Stopping Multi-Agent System..."
    
    if [ -f "stop_multi_agent_system.sh" ]; then
        chmod +x stop_multi_agent_system.sh
        ./stop_multi_agent_system.sh
    else
        # Fallback manual
        print_warning "stop_multi_agent_system.sh not found, using manual method"
        pkill -f multi_agent_bot.py
        pkill -f "src/main.py"
        print_success "Processes stopped"
    fi
}

# Função para reiniciar o sistema
restart_system() {
    print_status "Restarting Multi-Agent System..."
    stop_system
    sleep 3
    start_system
}

# Função para verificar status
check_status() {
    if [ -f "check_multi_agent_status.sh" ]; then
        chmod +x check_multi_agent_status.sh
        ./check_multi_agent_status.sh
    else
        # Status básico
        print_header "Basic System Status"
        echo ""
        
        if pgrep -f "multi_agent_bot.py" >/dev/null; then
            print_success "Multi-Agent Bot: RUNNING"
        else
            print_error "Multi-Agent Bot: STOPPED"
        fi
        
        if pgrep -f "src/main.py" >/dev/null; then
            print_success "Flask API: RUNNING"
        else
            print_error "Flask API: STOPPED"
        fi
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Função para visualizar logs
view_logs() {
    echo ""
    echo "Available logs:"
    echo "1. Multi-Agent Bot logs"
    echo "2. Flask API logs"
    echo "3. All logs (combined)"
    echo "4. Live tail (all logs)"
    read -p "Enter choice (1-4): " choice
    
    case $choice in
        1)
            if [ -f "logs/multi_agent_bot.log" ]; then
                less +F logs/multi_agent_bot.log
            else
                print_error "Multi-agent bot log not found"
            fi
            ;;
        2)
            if [ -f "logs/flask_api.log" ]; then
                less +F logs/flask_api.log
            else
                print_error "Flask API log not found"
            fi
            ;;
        3)
            if [ -d "logs" ]; then
                cat logs/*.log 2>/dev/null | less
            else
                print_error "Logs directory not found"
            fi
            ;;
        4)
            if [ -d "logs" ]; then
                tail -f logs/*.log
            else
                print_error "Logs directory not found"
            fi
            ;;
        *)
            print_error "Invalid choice"
            ;;
    esac
}

# Função para monitoramento
start_monitoring() {
    print_status "Starting monitoring mode..."
    
    if [ -f "monitor_bot.sh" ]; then
        chmod +x monitor_bot.sh
        ./monitor_bot.sh
    else
        print_status "Basic monitoring mode (press Ctrl+C to exit)"
        while true; do
            clear
            print_header "System Monitor"
            date
            echo ""
            
            if pgrep -f "multi_agent_bot.py" >/dev/null; then
                print_success "Multi-Agent Bot: RUNNING"
                echo "  PIDs: $(pgrep -f 'multi_agent_bot.py' | tr '\n' ' ')"
            else
                print_error "Multi-Agent Bot: STOPPED"
            fi
            
            if pgrep -f "src/main.py" >/dev/null; then
                print_success "Flask API: RUNNING"
                echo "  PIDs: $(pgrep -f 'src/main.py' | tr '\n' ' ')"
            else
                print_error "Flask API: STOPPED"
            fi
            
            echo ""
            echo "System Resources:"
            echo "  Memory: $(free -h | grep Mem: | awk '{print $3 "/" $2}')"
            echo "  CPU Load: $(uptime | awk -F'load average:' '{print $2}')"
            
            sleep 5
        done
    fi
}

# Função para health check
health_check() {
    print_header "Quick Health Check"
    echo ""
    
    # Processos
    if pgrep -f "multi_agent_bot.py" >/dev/null; then
        print_success "✅ Multi-Agent Bot is running"
    else
        print_error "❌ Multi-Agent Bot is not running"
    fi
    
    if pgrep -f "src/main.py" >/dev/null; then
        print_success "✅ Flask API is running"
    else
        print_error "❌ Flask API is not running"
    fi
    
    # Conectividade
    if curl -s --connect-timeout 3 "https://api.binance.com/api/v3/ping" >/dev/null; then
        print_success "✅ Binance API is reachable"
    else
        print_error "❌ Binance API is unreachable"
    fi
    
    # Arquivos de configuração
    if [ -f "src/config/config.yaml" ]; then
        print_success "✅ Configuration file exists"
    else
        print_error "❌ Configuration file missing"
    fi
    
    if [ -f "secrets/.env" ]; then
        print_success "✅ Environment file exists"
    else
        print_warning "⚠️  Environment file missing"
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Função para limpeza
cleanup_system() {
    print_status "Cleaning up system..."
    
    # Limpar logs antigos
    if [ -d "logs" ]; then
        find logs -name "*.log" -mtime +7 -delete 2>/dev/null
        print_status "Cleaned old log files (>7 days)"
    fi
    
    # Limpar arquivos temporários
    rm -f *.lock *.pid system_startup.log bot_startup.log 2>/dev/null
    print_status "Cleaned temporary files"
    
    # Limpar cache Python
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
    find . -name "*.pyc" -delete 2>/dev/null
    print_status "Cleaned Python cache files"
    
    print_success "System cleanup completed"
    echo ""
    read -p "Press Enter to continue..."
}

# Função para mostrar ajuda
show_help() {
    print_header "Multi-Agent System Manager Help"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo ""
    echo -e "  ${GREEN}start${NC}     - Start the multi-agent system"
    echo "             Offers choice between complete system or individual components"
    echo ""
    echo -e "  ${GREEN}stop${NC}      - Gracefully stop all multi-agent processes"
    echo "             Uses elegant shutdown procedures"
    echo ""
    echo -e "  ${GREEN}restart${NC}   - Stop and start the system"
    echo "             Equivalent to stop + start with safety delays"
    echo ""
    echo -e "  ${GREEN}status${NC}    - Comprehensive system status check"
    echo "             Shows processes, ports, logs, and configuration"
    echo ""
    echo -e "  ${GREEN}logs${NC}      - View system logs"
    echo "             Options for individual or combined log viewing"
    echo ""
    echo -e "  ${GREEN}monitor${NC}   - Real-time system monitoring"
    echo "             Continuous display of system status"
    echo ""
    echo -e "  ${GREEN}health${NC}    - Quick health check"
    echo "             Fast verification of critical components"
    echo ""
    echo -e "  ${GREEN}cleanup${NC}   - System maintenance"
    echo "             Removes old logs, temporary files, and caches"
    echo ""
    echo -e "${YELLOW}Files:${NC}"
    echo "  start_complete_system.sh   - Complete system startup"
    echo "  start_multi_agent_bot.sh   - Multi-agent bot only"
    echo "  stop_multi_agent_system.sh - Graceful shutdown"
    echo "  check_multi_agent_status.sh - Status checker"
    echo "  monitor_bot.sh             - System monitor"
    echo ""
    echo -e "${YELLOW}Direct Usage:${NC}"
    echo "  ./manage_multi_agent.sh [command]"
    echo "  Example: ./manage_multi_agent.sh start"
    echo ""
    read -p "Press Enter to continue..."
}

# Função principal
main() {
    # Se comando foi passado como argumento
    if [ $# -gt 0 ]; then
        case $1 in
            start)
                start_system
                ;;
            stop)
                stop_system
                ;;
            restart)
                restart_system
                ;;
            status)
                check_status
                ;;
            logs)
                view_logs
                ;;
            monitor)
                start_monitoring
                ;;
            health)
                health_check
                ;;
            cleanup)
                cleanup_system
                ;;
            help|--help|-h)
                show_help
                ;;
            *)
                print_error "Unknown command: $1"
                echo "Use 'help' for available commands"
                exit 1
                ;;
        esac
        return
    fi
    
    # Menu interativo
    while true; do
        show_menu
        read -p "Enter command (or number): " input
        
        case $input in
            1|start)
                start_system
                ;;
            2|stop)
                stop_system
                read -p "Press Enter to continue..."
                ;;
            3|restart)
                restart_system
                read -p "Press Enter to continue..."
                ;;
            4|status)
                check_status
                ;;
            5|logs)
                view_logs
                ;;
            6|monitor)
                start_monitoring
                ;;
            7|health)
                health_check
                ;;
            8|cleanup)
                cleanup_system
                ;;
            9|help)
                show_help
                ;;
            0|exit|quit)
                print_status "Goodbye!"
                exit 0
                ;;
            *)
                print_error "Invalid option: $input"
                sleep 1
                ;;
        esac
    done
}

# Verificar se estamos no diretório correto
if [ ! -f "src/multi_agent_bot.py" ]; then
    print_error "This script must be run from the project root directory"
    print_error "Expected to find src/multi_agent_bot.py"
    exit 1
fi

# Executar função principal
main "$@"

