#!/bin/bash

# Script para instalar dependências pesadas gradualmente
# Executa em etapas para evitar problemas de espaço/timeout

echo "🚀 Instalando dependências pesadas do sistema multi-agente..."

# Ativar ambiente virtual
source venv/bin/activate

echo "📦 Instalando ONNX Runtime..."
pip install --no-cache-dir onnxruntime
if [ $? -eq 0 ]; then
    echo "✅ ONNX Runtime instalado com sucesso"
else
    echo "❌ Erro ao instalar ONNX Runtime"
fi

echo "📦 Instalando Tweepy (Twitter API)..."
pip install --no-cache-dir tweepy
if [ $? -eq 0 ]; then
    echo "✅ Tweepy instalado com sucesso"
else
    echo "❌ Erro ao instalar Tweepy"
fi

echo "📦 Instalando PyTorch (pode demorar)..."
pip install --no-cache-dir torch --timeout 1200
if [ $? -eq 0 ]; then
    echo "✅ PyTorch instalado com sucesso"
else
    echo "❌ Erro ao instalar PyTorch - você pode tentar instalar manualmente depois"
fi

echo "📦 Instalando Stable Baselines3 (RL)..."
pip install --no-cache-dir stable-baselines3
if [ $? -eq 0 ]; then
    echo "✅ Stable Baselines3 instalado com sucesso"
else
    echo "❌ Erro ao instalar Stable Baselines3"
fi

echo "📦 Instalando TensorFlow (pode demorar muito)..."
pip install --no-cache-dir tensorflow-cpu==2.19.0 --timeout 1200
if [ $? -eq 0 ]; then
    echo "✅ TensorFlow instalado com sucesso"
else
    echo "❌ Erro ao instalar TensorFlow - você pode tentar instalar manualmente depois"
fi

echo "📦 Instalando dependências opcionais..."
pip install --no-cache-dir matplotlib plotly rich click

echo ""
echo "🎉 Instalação concluída!"
echo ""
echo "📋 Status das dependências:"
python -c "
try:
    import onnxruntime; print('✅ ONNX Runtime')
except: print('❌ ONNX Runtime')

try:
    import tweepy; print('✅ Tweepy')
except: print('❌ Tweepy')

try:
    import torch; print('✅ PyTorch')
except: print('❌ PyTorch')

try:
    import stable_baselines3; print('✅ Stable Baselines3')
except: print('❌ Stable Baselines3')

try:
    import tensorflow; print('✅ TensorFlow')
except: print('❌ TensorFlow')
"

echo ""
echo "💡 Se alguma dependência falhou, você pode tentar instalar individualmente:"
echo "   source venv/bin/activate"
echo "   pip install --no-cache-dir <nome_da_dependencia>"