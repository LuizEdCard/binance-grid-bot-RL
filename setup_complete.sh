#!/bin/bash

# Script Único e Completo para Configuração do Trading Bot
# Une instalação + correções + verificação

echo "🎯 CONFIGURAÇÃO COMPLETA DO TRADING BOT"
echo "========================================"

# 1. VERIFICAR AMBIENTE
echo "🔍 Verificando ambiente..."
if [[ "$CONDA_DEFAULT_ENV" != "trading-bot" ]]; then
    echo "❌ ERRO: Ambiente 'trading-bot' não está ativo!"
    echo "Execute primeiro: conda activate trading-bot"
    exit 1
fi

echo "✅ Ambiente trading-bot ativo"
echo "Python: $(python --version)"
echo "Localização: $(which python)"
echo ""

# 2. LIMPEZA INICIAL
echo "🧹 Limpeza inicial..."
pip cache purge
pip uninstall tensorflow ta-lib -y 2>/dev/null

# 3. ATUALIZAR FERRAMENTAS BASE
echo "🔧 Atualizando ferramentas base..."
pip install --upgrade pip setuptools wheel

# 4. INSTALAR NUMPY COMPATÍVEL PRIMEIRO
echo "🔢 Instalando NumPy compatível..."
pip install numpy==1.23.5 --force-reinstall

# 5. INSTALAR TA-LIB CORRETAMENTE
echo "📈 Instalando TA-Lib..."
echo "  → Instalando bibliotecas C via conda..."
conda install -c conda-forge libta-lib -y

echo "  → Instalando TA-Lib Python..."
pip install TA-Lib --no-cache-dir

# Verificar TA-Lib imediatamente
echo "  → Testando TA-Lib..."
if python -c "import talib; print('✅ TA-Lib OK')" 2>/dev/null; then
    echo "✅ TA-Lib instalado com sucesso"
else
    echo "❌ TA-Lib falhou. Tentando método alternativo..."
    pip uninstall ta-lib -y
    conda install -c conda-forge ta-lib -y
fi

# 6. INSTALAR TENSORFLOW
echo "🤖 Instalando TensorFlow..."
pip install tensorflow==2.11.0 --no-cache-dir

# 7. INSTALAR OUTRAS DEPENDÊNCIAS EM GRUPOS
echo "📦 Instalando dependências por grupos..."

echo "  → Grupo 1: Web Framework"
pip install flask==3.0.0 flask-cors pyyaml

echo "  → Grupo 2: Análise de Dados"
pip install pandas scikit-learn xgboost

echo "  → Grupo 3: APIs de Trading"
pip install python-binance ccxt

echo "  → Grupo 4: Machine Learning"
pip install gymnasium

echo "  → Grupo 5: Análise de Sentimento"
pip install requests huggingface_hub onnxruntime transformers

echo "  → Grupo 6: Utilitários"
pip install praw python-dotenv

# 8. VERIFICAÇÃO COMPLETA
echo ""
echo "🔍 VERIFICAÇÃO FINAL"
echo "==================="

# Função para testar módulos
test_module() {
    local module=$1
    local description=$2
    if python -c "import $module" 2>/dev/null; then
        echo "✅ $module - $description"
        return 0
    else
        echo "❌ $module - $description"
        return 1
    fi
}

# Testar módulos críticos
modules_critical=(
    "talib:Análise Técnica"
    "tensorflow:Machine Learning"
    "pandas:Análise de Dados"
    "numpy:Computação Numérica"
    "binance:API Binance"
    "flask:Servidor Web"
)

success_count=0
total_count=${#modules_critical[@]}

for item in "${modules_critical[@]}"; do
    module="${item%:*}"
    description="${item#*:}"
    if test_module "$module" "$description"; then
        ((success_count++))
    fi
done

echo ""
echo "📊 RESULTADO: $success_count/$total_count módulos funcionando"

# 9. TESTES FUNCIONAIS
if [ $success_count -eq $total_count ]; then
    echo ""
    echo "🧪 TESTES FUNCIONAIS"
    echo "==================="
    
    echo "Testando TA-Lib SMA..."
    python -c "
import talib
import numpy as np
data = np.random.random(50)
sma = talib.SMA(data, timeperiod=14)
print('✅ TA-Lib SMA funcional')
" 2>/dev/null && echo "✅ TA-Lib SMA OK" || echo "❌ TA-Lib SMA falhou"
    
    echo "Testando TensorFlow..."
    python -c "
import tensorflow as tf
print(f'✅ TensorFlow {tf.__version__} funcional')
" 2>/dev/null || echo "❌ TensorFlow falhou"
    
    echo "Testando API Binance..."
    python -c "
from binance.client import Client
print('✅ Binance Client funcional')
" 2>/dev/null || echo "❌ Binance Client falhou"
fi

# 10. RELATÓRIO FINAL
echo ""
echo "🎯 RELATÓRIO FINAL"
echo "================="

if [ $success_count -eq $total_count ]; then
    echo "🎉 CONFIGURAÇÃO COMPLETA E FUNCIONAL!"
    echo ""
    echo "✅ Todos os módulos críticos estão funcionando"
    echo "✅ Ambiente está pronto para uso"
    echo ""
    echo "🚀 PRÓXIMOS PASSOS:"
    echo "   1. Testar bot:        python quick_test.py"
    echo "   2. Iniciar API:       ./start_api.sh"
    echo "   3. Testar Fibonacci:  python test_fibonacci.py"
    echo ""
    echo "📝 COMANDOS ÚTEIS:"
    echo "   conda activate trading-bot    # Ativar ambiente"
    echo "   conda deactivate              # Desativar ambiente"
    echo "   pip list                      # Ver pacotes instalados"
else
    echo "⚠️  CONFIGURAÇÃO INCOMPLETA"
    echo ""
    echo "❌ $((total_count - success_count)) módulos falharam"
    echo ""
    echo "🔧 SOLUÇÕES:"
    echo "   1. Execute novamente: ./setup_complete.sh"
    echo "   2. Verifique logs de erro acima"
    echo "   3. Entre em contato com suporte"
fi

echo ""
echo "📋 INFORMAÇÕES DO AMBIENTE:"
echo "   Ambiente: $CONDA_DEFAULT_ENV"
echo "   Python: $(python --version)"
echo "   Pip: $(pip --version)"
echo "   Localização: $(which python)"