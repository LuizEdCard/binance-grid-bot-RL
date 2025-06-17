#!/bin/bash

# Script para iniciar o sistema completo de trading de forma persistente
# Inicia Flask API + Multi-Agent Bot usando tmux para sessões em background

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🚀 Sistema Completo de Trading - MODO PERSISTENTE${NC}"
echo -e "${YELLOW}📋 Flask API + Multi-Agent Bot continuarão rodando após bloqueio de tela${NC}"

# Verificar se tmux está instalado
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}❌ tmux não encontrado. Instalando...${NC}"
    sudo apt update && sudo apt install -y tmux
fi

# Nomes das sessões tmux
API_SESSION="trading-api"
BOT_SESSION="trading-bot"

# Função para verificar e gerenciar sessões existentes
manage_existing_sessions() {
    local has_api_session=false
    local has_bot_session=false
    
    if tmux has-session -t $API_SESSION 2>/dev/null; then
        has_api_session=true
    fi
    
    if tmux has-session -t $BOT_SESSION 2>/dev/null; then
        has_bot_session=true
    fi
    
    if [ "$has_api_session" = true ] || [ "$has_bot_session" = true ]; then
        echo -e "${YELLOW}⚠️  Sessões existentes detectadas:${NC}"
        [ "$has_api_session" = true ] && echo -e "   ${BLUE}Flask API:${NC} $API_SESSION"
        [ "$has_bot_session" = true ] && echo -e "   ${PURPLE}Multi-Agent Bot:${NC} $BOT_SESSION"
        echo ""
        echo -e "${BLUE}Opções:${NC}"
        echo "1) Conectar às sessões existentes"
        echo "2) Parar todas e criar novas"
        echo "3) Cancelar"
        read -p "Escolha (1/2/3): " choice
        
        case $choice in
            1)
                echo -e "${GREEN}🔗 Conectando às sessões existentes...${NC}"
                if [ "$has_api_session" = true ] && [ "$has_bot_session" = true ]; then
                    # Criar uma nova sessão temporária para mostrar as duas
                    tmux new-session -d -s "trading-monitor"
                    tmux split-window -h -t "trading-monitor"
                    tmux send-keys -t "trading-monitor:0.0" "tmux attach -t $API_SESSION" C-m
                    tmux send-keys -t "trading-monitor:0.1" "tmux attach -t $BOT_SESSION" C-m
                    tmux attach-session -t "trading-monitor"
                elif [ "$has_api_session" = true ]; then
                    tmux attach-session -t $API_SESSION
                else
                    tmux attach-session -t $BOT_SESSION
                fi
                exit 0
                ;;
            2)
                echo -e "${YELLOW}🛑 Parando sessões existentes...${NC}"
                [ "$has_api_session" = true ] && tmux kill-session -t $API_SESSION
                [ "$has_bot_session" = true ] && tmux kill-session -t $BOT_SESSION
                ;;
            3)
                echo -e "${BLUE}❌ Cancelado pelo usuário${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ Opção inválida${NC}"
                exit 1
                ;;
        esac
    fi
}

# Verificar sessões existentes
manage_existing_sessions

# Verificar diretório do projeto
PROJECT_DIR="/home/luiz/PycharmProjects/binance-grid-bot-RL"
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ Diretório do projeto não encontrado: $PROJECT_DIR${NC}"
    exit 1
fi

# Verificar arquivo de ambiente
ENV_FILE="$PROJECT_DIR/secrets/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Arquivo .env não encontrado: $ENV_FILE${NC}"
    echo -e "${YELLOW}💡 Configure suas credenciais da Binance primeiro${NC}"
    exit 1
fi

# Função para iniciar Flask API
start_flask_api() {
    echo -e "${BLUE}🌐 Iniciando Flask API em sessão persistente...${NC}"
    
    # Criar sessão para API
    tmux new-session -d -s $API_SESSION -c $PROJECT_DIR
    
    # Configurar API
    tmux send-keys -t $API_SESSION "clear" C-m
    tmux send-keys -t $API_SESSION "echo '🌐 Flask API - Sessão Persistente'" C-m
    tmux send-keys -t $API_SESSION "echo '📋 Sessão: $API_SESSION | $(date)'" C-m
    tmux send-keys -t $API_SESSION "echo '🔗 Interface: http://localhost:5000'" C-m
    tmux send-keys -t $API_SESSION "echo '⚠️  Para sair sem parar: Ctrl+B, depois D'" C-m
    tmux send-keys -t $API_SESSION "echo ''" C-m
    
    # Ativar ambiente virtual
    tmux send-keys -t $API_SESSION "if [ -d 'venv' ]; then source venv/bin/activate; echo '✅ Ambiente virtual ativado'; fi" C-m
    
    # Configurar PYTHONPATH
    tmux send-keys -t $API_SESSION "export PYTHONPATH=\"$PROJECT_DIR/src:\$PYTHONPATH\"" C-m
    
    # Iniciar Flask API
    tmux send-keys -t $API_SESSION "python src/main.py" C-m
    
    echo -e "${BLUE}✅ Flask API iniciada na sessão '$API_SESSION'${NC}"
}

# Função para iniciar Multi-Agent Bot
start_multi_agent_bot() {
    echo -e "${PURPLE}🤖 Iniciando Multi-Agent Bot em sessão persistente...${NC}"
    
    # Criar sessão para Bot
    tmux new-session -d -s $BOT_SESSION -c $PROJECT_DIR
    
    # Configurar Bot
    tmux send-keys -t $BOT_SESSION "clear" C-m
    tmux send-keys -t $BOT_SESSION "echo '🤖 Multi-Agent Trading Bot - Sessão Persistente'" C-m
    tmux send-keys -t $BOT_SESSION "echo '📋 Sessão: $BOT_SESSION | $(date)'" C-m
    tmux send-keys -t $BOT_SESSION "echo '🧠 AI Multi-Agent System Ativo'" C-m
    tmux send-keys -t $BOT_SESSION "echo '⚠️  Para sair sem parar: Ctrl+B, depois D'" C-m
    tmux send-keys -t $BOT_SESSION "echo ''" C-m
    
    # Ativar ambiente virtual
    tmux send-keys -t $BOT_SESSION "if [ -d 'venv' ]; then source venv/bin/activate; echo '✅ Ambiente virtual ativado'; fi" C-m
    
    # Iniciar Bot
    tmux send-keys -t $BOT_SESSION "python src/multi_agent_bot.py" C-m
    
    echo -e "${PURPLE}✅ Multi-Agent Bot iniciado na sessão '$BOT_SESSION'${NC}"
}

echo -e "${GREEN}✅ Iniciando sistema completo em sessões tmux...${NC}"

# Iniciar componentes
start_flask_api
sleep 3  # Aguardar API inicializar
start_multi_agent_bot

echo ""
echo -e "${CYAN}🎉 Sistema completo iniciado com sucesso!${NC}"
echo -e "${BLUE}📋 Sessões ativas:${NC}"
echo -e "   ${BLUE}Flask API:${NC} $API_SESSION (http://localhost:5000)"
echo -e "   ${PURPLE}Multi-Agent Bot:${NC} $BOT_SESSION"
echo ""
echo -e "${YELLOW}📋 Comandos úteis:${NC}"
echo -e "   ${YELLOW}Ver sessões:${NC} tmux list-sessions"
echo -e "   ${YELLOW}Conectar API:${NC} tmux attach -t $API_SESSION"
echo -e "   ${YELLOW}Conectar Bot:${NC} tmux attach -t $BOT_SESSION"
echo -e "   ${YELLOW}Monitor completo:${NC} ./monitor_bot.sh"
echo -e "   ${YELLOW}Parar API:${NC} tmux kill-session -t $API_SESSION"
echo -e "   ${YELLOW}Parar Bot:${NC} tmux kill-session -t $BOT_SESSION"
echo -e "   ${YELLOW}Parar tudo:${NC} tmux kill-server"
echo ""
echo -e "${GREEN}🎯 Criando sessão de monitoramento integrada...${NC}"
sleep 2

# Criar sessão de monitoramento que mostra ambas
tmux new-session -d -s "trading-monitor"
tmux split-window -h -t "trading-monitor"
tmux split-window -v -t "trading-monitor:0.1"

# Painel 0: API logs
tmux send-keys -t "trading-monitor:0.0" "touch logs/flask_api.log && tail -f logs/flask_api.log" C-m

# Painel 1: Bot logs  
tmux send-keys -t "trading-monitor:0.1" "touch logs/bot.log && tail -f logs/bot.log" C-m

# Painel 2: Sistema de monitoramento
tmux send-keys -t "trading-monitor:0.2" "echo '📊 Monitor do Sistema de Trading'" C-m
tmux send-keys -t "trading-monitor:0.2" "echo '========================'" C-m
tmux send-keys -t "trading-monitor:0.2" "echo 'Flask API: http://localhost:5000'" C-m
tmux send-keys -t "trading-monitor:0.2" "echo '🔍 Para verificar posições: python check_positions.py'" C-m
tmux send-keys -t "trading-monitor:0.2" "echo '📊 Comandos úteis:'" C-m
tmux send-keys -t "trading-monitor:0.2" "echo '  tmux attach -t $API_SESSION  # Conectar à API'" C-m
tmux send-keys -t "trading-monitor:0.2" "echo '  tmux attach -t $BOT_SESSION  # Conectar ao Bot'" C-m
tmux send-keys -t "trading-monitor:0.2" "echo ''" C-m
tmux send-keys -t "trading-monitor:0.2" "echo 'Pressione Ctrl+B, depois D para sair'" C-m
tmux send-keys -t "trading-monitor:0.2" "echo ''" C-m
tmux send-keys -t "trading-monitor:0.2" "if [ -d 'venv' ]; then source venv/bin/activate; fi" C-m

# Conectar à sessão de monitoramento
tmux attach-session -t "trading-monitor"