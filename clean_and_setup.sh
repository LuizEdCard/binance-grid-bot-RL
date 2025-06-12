#!/bin/bash

echo "🧹 LIMPEZA COMPLETA E CONFIGURAÇÃO FINAL"
echo "========================================"

# 1. VERIFICAR SE ESTÁ NO AMBIENTE VIRTUAL
echo "🔄 Verificando ambiente..."
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "❌ Ambiente virtual não está ativo!"
    echo "Execute: source venv/bin/activate"
    exit 1
fi

# 3. VERIFICAR ESPAÇO LIVRE ANTES
echo "💾 Espaço em disco antes da limpeza:"
df -h "$HOME" | tail -1

# 4. LIMPAR CACHES E ARQUIVOS TEMPORÁRIOS
echo "🧹 Limpando caches..."

# Cache do pip
pip cache purge

# Cache do pip (se existir)
pip cache purge 2>/dev/null || true

# Cache do Python
find "$HOME" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$HOME" -name "*.pyc" -delete 2>/dev/null || true

# 5. VERIFICAR ESPAÇO LIVRE DEPOIS
echo "💾 Espaço em disco após limpeza:"
df -h "$HOME" | tail -1

# 6. VERIFICAR AMBIENTE VIRTUAL
echo "🎯 Verificando ambiente virtual..."
echo "✅ Ambiente virtual ativo: $(basename $VIRTUAL_ENV)"
echo "Python: $(python --version)"
echo "Localização: $(which python)"

# 7. VERIFICAR DEPENDÊNCIAS NO AMBIENTE CORRETO
echo ""
echo "🔍 VERIFICANDO DEPENDÊNCIAS NO AMBIENTE CORRETO"
echo "==============================================="

python -c "
import sys
print(f'Python ativo: {sys.executable}')
print(f'Ambiente: {os.path.basename(os.environ.get("VIRTUAL_ENV", "Nenhum ambiente ativo"))}')

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
            print('   pip install TA-Lib --no-cache-dir')
        elif module == 'tensorflow':
            print('   pip install tensorflow-cpu==2.19.0')
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
echo "   source venv/bin/activate      # Sempre ativar este ambiente"
echo "   pip list                      # Ver pacotes instalados"
echo "   deactivate                    # Sair do ambiente virtual"