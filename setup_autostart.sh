#!/bin/bash

# Script para configurar inicialização automática do sistema de trading
# Cria serviços systemd para auto-start no boot do sistema

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

echo -e "${CYAN}⚙️  Configurador de Auto-Start - Sistema de Trading${NC}"
echo "=================================================="
echo ""

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar se systemd está disponível
check_systemd() {
    print_status "Verificando systemd..."
    
    if ! command -v systemctl &> /dev/null; then
        print_error "systemctl não encontrado. Este sistema não usa systemd."
        exit 1
    fi
    
    print_status "systemd encontrado"
}

# Criar diretório para serviços do usuário
create_user_systemd_dir() {
    print_status "Criando diretório para serviços systemd do usuário..."
    
    mkdir -p "$USER_SYSTEMD_DIR"
    
    print_status "Diretório criado: $USER_SYSTEMD_DIR"
}

# Criar serviço systemd para o sistema de trading
create_trading_service() {
    print_status "Criando serviço systemd para o sistema de trading..."
    
    cat > "$USER_SYSTEMD_DIR/trading-system.service" << EOF
[Unit]
Description=Sistema Completo de Trading - Flask API + Multi-Agent Bot
After=network.target
Wants=network-online.target

[Service]
Type=forking
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=HOME=$HOME
Environment=USER=$USER
Environment=PATH=$PATH
ExecStart=$PROJECT_DIR/start_persistent_bot.sh
ExecStop=/usr/bin/tmux kill-session -t trading-api; /usr/bin/tmux kill-session -t trading-bot
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=trading-system

[Install]
WantedBy=default.target
EOF
    
    print_status "Serviço criado: trading-system.service"
}

# Criar serviço Timer para restart diário (opcional)
create_timer_service() {
    print_status "Criando timer para restart diário (opcional)..."
    
    cat > "$USER_SYSTEMD_DIR/trading-system-restart.service" << EOF
[Unit]
Description=Restart Trading System Daily
Requires=trading-system.service

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl --user restart trading-system.service
EOF
    
    cat > "$USER_SYSTEMD_DIR/trading-system-restart.timer" << EOF
[Unit]
Description=Restart Trading System Daily at 4 AM
Requires=trading-system-restart.service

[Timer]
OnCalendar=daily
Persistent=true
AccuracySec=1m

[Install]
WantedBy=timers.target
EOF
    
    print_status "Timer diário criado (restart às 04:00)"
}

# Configurar systemd para o usuário
configure_systemd() {
    print_status "Configurando systemd..."
    
    # Recarregar configurações
    systemctl --user daemon-reload
    
    # Habilitar lingering para que serviços do usuário iniciem no boot
    sudo loginctl enable-linger $USER
    
    print_status "Configurações systemd aplicadas"
}

# Função para habilitar serviços
enable_services() {
    echo -e "${BLUE}Escolha os serviços para habilitar:${NC}"
    echo "1) Apenas sistema de trading (auto-start no boot)"
    echo "2) Sistema de trading + restart diário às 04:00"
    echo "3) Não habilitar agora (configurar manualmente depois)"
    read -p "Escolha (1/2/3): " choice
    
    case $choice in
        1)
            print_status "Habilitando sistema de trading..."
            systemctl --user enable trading-system.service
            print_status "✅ Sistema será iniciado automaticamente no boot"
            ;;
        2)
            print_status "Habilitando sistema de trading + timer diário..."
            systemctl --user enable trading-system.service
            systemctl --user enable trading-system-restart.timer
            systemctl --user start trading-system-restart.timer
            print_status "✅ Sistema será iniciado automaticamente no boot"
            print_status "✅ Restart diário configurado para 04:00"
            ;;
        3)
            print_warning "Serviços criados mas não habilitados"
            print_warning "Para habilitar manualmente:"
            print_warning "  systemctl --user enable trading-system.service"
            print_warning "  systemctl --user enable trading-system-restart.timer"
            ;;
        *)
            print_error "Opção inválida"
            exit 1
            ;;
    esac
}

# Criar script de controle do sistema
create_control_script() {
    print_status "Criando script de controle do sistema..."
    
    cat > "$PROJECT_DIR/trading_control.sh" << 'EOF'
#!/bin/bash

# Script de controle do sistema de trading

ACTION=$1

case $ACTION in
    start)
        echo "🚀 Iniciando sistema de trading..."
        systemctl --user start trading-system.service
        ;;
    stop)
        echo "🛑 Parando sistema de trading..."
        systemctl --user stop trading-system.service
        ;;
    restart)
        echo "🔄 Reiniciando sistema de trading..."
        systemctl --user restart trading-system.service
        ;;
    status)
        echo "📊 Status do sistema de trading:"
        systemctl --user status trading-system.service
        echo ""
        echo "📋 Sessões tmux ativas:"
        tmux list-sessions 2>/dev/null || echo "Nenhuma sessão tmux ativa"
        ;;
    logs)
        echo "📜 Logs do sistema de trading:"
        journalctl --user -u trading-system.service -f
        ;;
    enable)
        echo "✅ Habilitando auto-start..."
        systemctl --user enable trading-system.service
        ;;
    disable)
        echo "❌ Desabilitando auto-start..."
        systemctl --user disable trading-system.service
        ;;
    *)
        echo "Uso: $0 {start|stop|restart|status|logs|enable|disable}"
        echo ""
        echo "Comandos:"
        echo "  start    - Iniciar sistema"
        echo "  stop     - Parar sistema"
        echo "  restart  - Reiniciar sistema"
        echo "  status   - Ver status"
        echo "  logs     - Ver logs em tempo real"
        echo "  enable   - Habilitar auto-start no boot"
        echo "  disable  - Desabilitar auto-start"
        exit 1
        ;;
esac
EOF
    
    chmod +x "$PROJECT_DIR/trading_control.sh"
    
    print_status "✅ Script de controle criado: trading_control.sh"
}

# Função principal
main() {
    echo -e "${BLUE}Iniciando configuração...${NC}"
    echo ""
    
    check_systemd
    create_user_systemd_dir
    create_trading_service
    create_timer_service
    configure_systemd
    create_control_script
    
    echo ""
    echo -e "${GREEN}✅ Configuração concluída!${NC}"
    echo ""
    
    enable_services
    
    echo ""
    echo -e "${CYAN}📋 Comandos úteis após instalação:${NC}"
    echo -e "  ${YELLOW}Controle geral:${NC} ./trading_control.sh {start|stop|restart|status|logs}"
    echo -e "  ${YELLOW}Manual direto:${NC} ./start_persistent_bot.sh"
    echo -e "  ${YELLOW}Ver status:${NC} systemctl --user status trading-system.service"
    echo -e "  ${YELLOW}Ver logs:${NC} journalctl --user -u trading-system.service -f"
    echo -e "  ${YELLOW}Habilitar/desabilitar:${NC} ./trading_control.sh {enable|disable}"
    echo ""
    echo -e "${GREEN}🎯 Sistema configurado para inicialização automática!${NC}"
}

# Verificar se está sendo executado como script principal
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi