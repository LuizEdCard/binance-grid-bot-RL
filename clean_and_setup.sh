#!/bin/bash

echo "🧹 LIMPEZA COMPLETA E CONFIGURAÇÃO FINAL"
echo "========================================"

# 1. LIMPAR VARIÁVEIS DE AMBIENTE ANTIGAS
echo "🔄 Limpando ambiente antigo..."
unset CONDA_DEFAULT_ENV
unset CONDA_PREFIX
unset CONDA_PROMPT_MODIFIER

# 2. FORÇAR SAÍDA DE QUALQUER AMBIENTE
echo "🚪 Saindo de ambientes ativos..."
conda deactivate 2>/dev/null || true
conda deactivate 2>/dev/null || true

# 3. VERIFICAR ESPAÇO LIVRE ANTES
echo "💾 Espaço em disco antes da limpeza:"
df -h "$HOME" | tail -1

# 4. LIMPAR CACHES E ARQUIVOS TEMPORÁRIOS
echo "🧹 Limpando caches..."

# Cache do conda
conda clean --all -y

# Cache do pip (se existir)
pip cache purge 2>/dev/null || true

# Cache do Python
find "$HOME" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$HOME" -name "*.pyc" -delete 2>/dev/null || true

# 5. VERIFICAR ESPAÇO LIVRE DEPOIS
echo "💾 Espaço em disco após limpeza:"
df -h "$HOME" | tail -1

# 6. ATIVAR AMBIENTE CORRETO
echo "🎯 Ativando ambiente trading-bot..."
conda activate trading-bot

# Verificar se ativação funcionou
if [[ "$CONDA_DEFAULT_ENV" == "trading-bot" ]]; then
    echo "✅ Ambiente trading-bot ativado com sucesso"
    echo "Python: $(python --version)"
    echo "Localização: $(which python)"
else
    echo "❌ Falha ao ativar ambiente. Tentando método alternativo..."
    source activate trading-bot
fi

# 7. VERIFICAR DEPENDÊNCIAS NO AMBIENTE CORRETO
echo ""
echo "🔍 VERIFICANDO DEPENDÊNCIAS NO AMBIENTE CORRETO"
echo "==============================================="

python -c "
import sys
print(f'Python ativo: {sys.executable}')
print(f'Ambiente: $CONDA_DEFAULT_ENV' if '$CONDA_DEFAULT_ENV' else 'Nenhum ambiente ativo')

# Lista de módulos necessários
required_modules = [
    'flask', 'pandas', 'numpy', 'tensorflow', 
    'binance', 'talib', 'sklearn', 'transformers'
]

installed = []
missing = []

for module in required_modules:
    try:
        __import__(module)
        installed.append(module)
    except ImportError:
        missing.append(module)

print(f'\\n📊 Status: {len(installed)}/{len(required_modules)} dependências instaladas')
print(f'✅ Instaladas: {installed}')
print(f'❌ Faltando: {missing}')

if missing:
    print(f'\\n🔧 Comandos para instalar faltantes:')
    for module in missing:
        if module == 'talib':
            print('   conda install -c conda-forge ta-lib -y')
        elif module == 'tensorflow':
            print('   pip install tensorflow==2.11.0')
        elif module == 'sklearn':
            print('   pip install scikit-learn')
        else:
            print(f'   pip install {module}')
"

echo ""
echo "🎯 PRÓXIMOS PASSOS:"
echo "   1. Se há dependências faltando, execute:"
echo "      ./setup_complete.sh"
echo "   2. Para instalar apenas TA-Lib:"
echo "      conda install -c conda-forge ta-lib -y"
echo "   3. Para testar funcionamento:"
echo "      python quick_test.py"

echo ""
echo "💡 COMANDOS ÚTEIS:"
echo "   conda activate trading-bot    # Sempre ativar este ambiente"
echo "   conda list                    # Ver pacotes instalados"
echo "   pip list                      # Ver pacotes pip"
echo "   conda info --envs             # Ver todos os ambientes"