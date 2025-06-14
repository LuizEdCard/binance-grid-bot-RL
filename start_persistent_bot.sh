#!/bin/bash

# Script para iniciar o bot de forma persistente (continua rodando mesmo após bloqueio de tela)
# Usa tmux para criar uma sessão em background

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Iniciando Multi-Agent Trading Bot em modo PERSISTENTE${NC}"
echo -e "${YELLOW}📋 Este bot continuará rodando mesmo após bloqueio de tela${NC}"

# Verificar se tmux está instalado
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}❌ tmux não encontrado. Instalando...${NC}"
    sudo apt update && sudo apt install -y tmux
fi

# Nome da sessão tmux
SESSION_NAME="trading-bot"

# Verificar se já existe uma sessão ativa
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Sessão '$SESSION_NAME' já existe${NC}"
    echo -e "${BLUE}Opções:${NC}"
    echo "1) Conectar à sessão existente"
    echo "2) Parar sessão existente e criar nova"
    echo "3) Cancelar"
    read -p "Escolha (1/2/3): " choice
    
    case $choice in
        1)
            echo -e "${GREEN}🔗 Conectando à sessão existente...${NC}"
            tmux attach-session -t $SESSION_NAME
            exit 0
            ;;
        2)
            echo -e "${YELLOW}🛑 Parando sessão existente...${NC}"
            tmux kill-session -t $SESSION_NAME
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

echo -e "${GREEN}✅ Iniciando nova sessão tmux...${NC}"

# Criar nova sessão tmux em background e executar o bot
tmux new-session -d -s $SESSION_NAME -c $PROJECT_DIR

# Configurar tmux para logging automático
tmux send-keys -t $SESSION_NAME "clear" C-m
tmux send-keys -t $SESSION_NAME "echo '🚀 Multi-Agent Trading Bot - Sessão Persistente'" C-m
tmux send-keys -t $SESSION_NAME "echo '📋 Sessão: $SESSION_NAME | $(date)'" C-m
tmux send-keys -t $SESSION_NAME "echo '⚠️  Para sair sem parar o bot: Ctrl+B, depois D'" C-m
tmux send-keys -t $SESSION_NAME "echo '🔄 Para reconectar: tmux attach -t $SESSION_NAME'" C-m
tmux send-keys -t $SESSION_NAME "echo ''" C-m

# Ativar ambiente virtual se existir
tmux send-keys -t $SESSION_NAME "if [ -d 'venv' ]; then source venv/bin/activate; echo '✅ Ambiente virtual ativado'; fi" C-m

# Iniciar o bot
tmux send-keys -t $SESSION_NAME "python src/multi_agent_bot.py" C-m

echo -e "${GREEN}✅ Bot iniciado na sessão tmux '$SESSION_NAME'${NC}"
echo -e "${BLUE}📋 Comandos úteis:${NC}"
echo -e "   ${YELLOW}Conectar à sessão:${NC} tmux attach -t $SESSION_NAME"
echo -e "   ${YELLOW}Ver sessões ativas:${NC} tmux list-sessions"
echo -e "   ${YELLOW}Sair sem parar bot:${NC} Ctrl+B, depois D"
echo -e "   ${YELLOW}Parar o bot:${NC} tmux kill-session -t $SESSION_NAME"
echo ""
echo -e "${GREEN}🎯 Conectando à sessão automaticamente...${NC}"
sleep 2

# Conectar à sessão
tmux attach-session -t $SESSION_NAME