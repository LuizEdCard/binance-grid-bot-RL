#!/bin/bash

# Script para iniciar o Grid Trading Bot com RL

echo "Iniciando Grid Trading Bot com Reinforcement Learning..."

# Verificar dependências
echo "Verificando dependências..."
pip install -r requirements.txt

# Verificar se o diretório de logs existe
mkdir -p logs

# Verificar se o diretório de modelos existe
mkdir -p models

# Iniciar o bot
echo "Iniciando o bot..."
python src/bot_logic.py

echo "Bot iniciado!"