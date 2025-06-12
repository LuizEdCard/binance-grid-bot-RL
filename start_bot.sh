#!/bin/bash

# Script para iniciar o servidor backend do Grid Trading Bot

echo "Iniciando servidor backend do Trading Bot..."

# Verificar dependências
echo "Verificando dependências..."
./.venv/bin/pip install -r requirements.txt

# Verificar se os diretórios necessários existem
mkdir -p logs
mkdir -p models
mkdir -p data/grid_states

# Verificar se o arquivo .env existe na pasta secrets
if [ ! -f "secrets/.env" ]; then
    echo "AVISO: Arquivo secrets/.env não encontrado. Certifique-se de configurar as credenciais da API."
fi

# Iniciar o servidor backend (usando main.py ao invés de bot_logic.py)
echo "Iniciando o servidor backend..."
./.venv/bin/python src/main.py

echo "Servidor backend iniciado!"
echo "Você pode iniciar os grids de trading através do frontend ou pelo agente RL."
