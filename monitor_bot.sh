#!/bin/bash

# Script para monitorar o status do bot remotamente

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SESSION_NAME="trading-bot"

echo -e "${BLUE}🔍 Monitor do Multi-Agent Trading Bot${NC}"
echo "======================================"

# Verificar se tmux está instalado
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}❌ tmux não está instalado${NC}"
    exit 1
fi

# Verificar se a sessão existe
if ! tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${RED}❌ Sessão '$SESSION_NAME' não encontrada${NC}"
    echo -e "${YELLOW}💡 Use: ./start_persistent_bot.sh para iniciar${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Sessão '$SESSION_NAME' está ativa${NC}"

# Menu de opções
while true; do
    echo ""
    echo -e "${BLUE}Opções de Monitoramento:${NC}"
    echo "1) 📊 Ver logs em tempo real"
    echo "2) 🔗 Conectar à sessão do bot"  
    echo "3) 📈 Status rápido das posições"
    echo "4) 💰 Verificar saldo"
    echo "5) 🛑 Parar o bot"
    echo "6) ❌ Sair"
    
    read -p "Escolha uma opção (1-6): " choice
    
    case $choice in
        1)
            echo -e "${GREEN}📊 Logs em tempo real (Ctrl+C para sair):${NC}"
            tail -f logs/bot.log src/logs/bot.log 2>/dev/null | head -50
            ;;
        2)
            echo -e "${GREEN}🔗 Conectando à sessão...${NC}"
            echo -e "${YELLOW}💡 Para sair sem parar o bot: Ctrl+B, depois D${NC}"
            sleep 2
            tmux attach-session -t $SESSION_NAME
            ;;
        3)
            echo -e "${GREEN}📈 Status das posições:${NC}"
            echo "Últimas linhas dos logs de pares:"
            for log_file in src/logs/pairs/*.log; do
                if [ -f "$log_file" ]; then
                    pair=$(basename "$log_file" .log)
                    echo -e "${YELLOW}--- $pair ---${NC}"
                    tail -5 "$log_file" 2>/dev/null | grep -E "(PREÇO:|POSIÇÃO:|PNL:)" | tail -1
                fi
            done
            ;;
        4)
            echo -e "${GREEN}💰 Verificando saldo...${NC}"
            tail -20 logs/bot.log src/logs/bot.log 2>/dev/null | grep -E "(Available balances|Total Balance)" | tail -2
            ;;
        5)
            echo -e "${YELLOW}⚠️  Tem certeza que deseja parar o bot? (y/N)${NC}"
            read -p "Confirmar: " confirm
            if [[ $confirm == [yY] ]]; then
                echo -e "${RED}🛑 Parando o bot...${NC}"
                tmux kill-session -t $SESSION_NAME
                echo -e "${GREEN}✅ Bot parado${NC}"
                exit 0
            else
                echo -e "${BLUE}❌ Operação cancelada${NC}"
            fi
            ;;
        6)
            echo -e "${BLUE}👋 Saindo do monitor...${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Opção inválida${NC}"
            ;;
    esac
    
    echo ""
    read -p "Pressione Enter para continuar..."
done