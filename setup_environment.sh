#!/bin/bash

# Script para configurar o ambiente Conda correto para o projeto

echo "🔧 Configurando ambiente Conda para o projeto..."

# 1. Desativar ambiente atual se ativo
conda deactivate 2>/dev/null

# 2. Verificar se ambiente nomeado já existe
if conda env list | grep -q "trading-bot"; then
    echo "✅ Ambiente 'trading-bot' já existe"
    conda activate trading-bot
else
    echo "📦 Criando novo ambiente 'trading-bot'..."
    
    # 3. Criar ambiente nomeado baseado no ambiente atual
    conda create -n trading-bot --clone ./.conda -y
    
    # 4. Ativar o novo ambiente
    conda activate trading-bot
    
    echo "✅ Ambiente 'trading-bot' criado e ativado"
fi

# 5. Verificar instalação
echo "🔍 Verificando ambiente:"
echo "Python: $(which python)"
echo "Conda env: $CONDA_DEFAULT_ENV"

# 6. Verificar dependências críticas
echo "📋 Verificando dependências:"
python -c "import talib; print('✅ TA-Lib instalado')" 2>/dev/null || echo "❌ TA-Lib não encontrado"
python -c "import tensorflow; print('✅ TensorFlow instalado')" 2>/dev/null || echo "❌ TensorFlow não encontrado"
python -c "import binance; print('✅ Python-Binance instalado')" 2>/dev/null || echo "❌ Python-Binance não encontrado"

echo ""
echo "🎉 Ambiente configurado! Use sempre:"
echo "   conda activate trading-bot"
echo ""
echo "💡 Para ativar automaticamente, adicione ao ~/.bashrc:"
echo "   echo 'conda activate trading-bot' >> ~/.bashrc"