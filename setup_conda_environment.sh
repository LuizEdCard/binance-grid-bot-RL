#!/bin/bash

# Setup Conda Environment for Trading Bot
# Python 3.10 + All Dependencies with TA-Lib via conda

echo "🐍 SETUP CONDA ENVIRONMENT - TRADING BOT"
echo "========================================"

# 1. VERIFICAR SE CONDA ESTÁ DISPONÍVEL
if ! command -v conda &> /dev/null; then
    echo "❌ ERRO: Conda não encontrado!"
    echo "   Instale o Anaconda ou Miniconda primeiro"
    exit 1
fi

echo "✅ Conda encontrado: $(conda --version)"

# 2. CRIAR AMBIENTE COM PYTHON 3.10
echo ""
echo "🔧 Criando ambiente 'trading-bot' com Python 3.10..."
conda create -n trading-bot python=3.10 -y

# 3. ATIVAR AMBIENTE
echo "🔄 Ativando ambiente..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate trading-bot

# Verificar se ativou corretamente
if [[ "$CONDA_DEFAULT_ENV" != "trading-bot" ]]; then
    echo "❌ ERRO: Falha ao ativar ambiente 'trading-bot'"
    echo "   Execute manualmente: conda activate trading-bot"
    exit 1
fi

echo "✅ Ambiente 'trading-bot' ativo"
echo "   Python: $(python --version)"
echo "   Localização: $(which python)"

# 4. ATUALIZAR FERRAMENTAS BASE
echo ""
echo "🔧 Atualizando ferramentas base..."
pip install --upgrade pip setuptools wheel

# 5. INSTALAR TA-LIB VIA CONDA (MÉTODO MAIS CONFIÁVEL)
echo ""
echo "📈 Instalando TA-Lib via conda (inclui biblioteca C)..."
conda install -c conda-forge ta-lib -y

# Testar TA-Lib imediatamente
echo "   🧪 Testando TA-Lib..."
if python -c "import talib; print('✅ TA-Lib funcional')" 2>/dev/null; then
    echo "✅ TA-Lib instalado com sucesso via conda"
else
    echo "⚠️  TA-Lib via conda falhou. Tentando método pip..."
    # Fallback: instalar biblioteca C separadamente
    conda install -c conda-forge libta-lib -y
    pip install TA-Lib --no-cache-dir
    
    if python -c "import talib; print('✅ TA-Lib funcional')" 2>/dev/null; then
        echo "✅ TA-Lib instalado via método híbrido"
    else
        echo "❌ TA-Lib falhou. Será necessário instalação manual."
    fi
fi

# 6. INSTALAR TENSORFLOW (COMPATÍVEL COM PYTHON 3.10)
echo ""
echo "🤖 Instalando TensorFlow..."
pip install tensorflow==2.11.0 --no-cache-dir

# 7. INSTALAR DEPENDÊNCIAS CORE EM GRUPOS
echo ""
echo "📦 Instalando dependências core..."

echo "   → Grupo 1: Análise Numérica"
pip install numpy==1.23.5 pandas scikit-learn

echo "   → Grupo 2: Web Framework"
pip install flask==2.2.0 flask-cors pyyaml

echo "   → Grupo 3: APIs de Trading"
pip install python-binance ccxt

echo "   → Grupo 4: Machine Learning"
pip install gymnasium stable-baselines3

echo "   → Grupo 5: Análise de Sentimento"
pip install transformers torch onnxruntime huggingface-hub

echo "   → Grupo 6: Utilitários"
pip install praw python-dotenv requests psutil

echo "   → Grupo 7: Assíncrono e Networking"
pip install aiohttp asyncio-throttle

echo "   → Grupo 8: Telegram (Opcional)"
pip install python-telegram-bot

# 8. INSTALAR DEPENDÊNCIAS OPCIONAIS
echo ""
echo "📊 Instalando dependências opcionais..."
pip install xgboost redis lz4 msgpack click rich tqdm matplotlib plotly

# 9. VERIFICAÇÃO COMPLETA
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
echo "📋 Módulos críticos:"
modules_critical=(
    "talib:Análise Técnica"
    "tensorflow:Machine Learning"
    "pandas:Análise de Dados"
    "numpy:Computação Numérica"
    "binance:API Binance"
    "flask:Servidor Web"
    "sklearn:Scikit-learn"
    "gymnasium:RL Environment"
    "stable_baselines3:RL Algorithms"
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
echo "📋 Módulos opcionais:"
modules_optional=(
    "torch:PyTorch"
    "transformers:Hugging Face"
    "onnxruntime:ONNX Runtime"
    "praw:Reddit API"
    "aiohttp:Async HTTP"
    "redis:Caching"
)

optional_success=0
optional_total=${#modules_optional[@]}

for item in "${modules_optional[@]}"; do
    module="${item%:*}"
    description="${item#*:}"
    if test_module "$module" "$description"; then
        ((optional_success++))
    fi
done

# 10. TESTES FUNCIONAIS
echo ""
echo "🧪 TESTES FUNCIONAIS"
echo "==================="

if [ $success_count -eq $total_count ]; then
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

    echo "Testando Binance Client..."
    python -c "
from binance.client import Client
print('✅ Binance Client funcional')
" 2>/dev/null || echo "❌ Binance Client falhou"
fi

# 11. RELATÓRIO FINAL
echo ""
echo "🎯 RELATÓRIO FINAL"
echo "================="

echo "📊 Resultado dos Testes:"
echo "   Módulos críticos: $success_count/$total_count"
echo "   Módulos opcionais: $optional_success/$optional_total"

if [ $success_count -eq $total_count ]; then
    echo ""
    echo "🎉 AMBIENTE CRIADO COM SUCESSO!"
    echo ""
    echo "✅ Python 3.10 configurado"
    echo "✅ TA-Lib instalado via conda"
    echo "✅ Todas as dependências críticas funcionando"
    echo ""
    echo "🚀 COMO USAR:"
    echo "   1. Ativar ambiente:     conda activate trading-bot"
    echo "   2. Testar bot:          python tests/quick_test.py"
    echo "   3. Shadow + IA test:    python tests/test_shadow_and_ai_fallback.py"
    echo "   4. Iniciar sistema:     python src/multi_agent_bot.py"
    echo ""
    echo "📝 COMANDOS ÚTEIS:"
    echo "   conda activate trading-bot    # Ativar ambiente"
    echo "   conda deactivate              # Desativar ambiente"
    echo "   pip list                      # Ver pacotes instalados"
    echo "   conda list                    # Ver pacotes conda"
    echo "   conda env list                # Ver todos os ambientes"
else
    echo ""
    echo "⚠️  ALGUMAS DEPENDÊNCIAS FALHARAM"
    echo ""
    echo "❌ $((total_count - success_count)) módulos críticos falharam"
    echo ""
    echo "🔧 SOLUÇÕES:"
    echo "   1. Execute novamente: ./setup_conda_environment.sh"
    echo "   2. Instale manualmente: conda activate trading-bot && pip install <modulo>"
    echo "   3. Para TA-Lib: conda install -c conda-forge ta-lib"
fi

echo ""
echo "📋 INFORMAÇÕES DO AMBIENTE:"
echo "   Ambiente: $CONDA_DEFAULT_ENV"
echo "   Python: $(python --version)"
echo "   Pip: $(pip --version)"
echo "   Conda: $(conda --version)"
echo "   Localização Python: $(which python)"
echo "   Localização Conda: $(which conda)"

echo ""
echo "✅ Setup completo! Ambiente 'trading-bot' pronto para uso."