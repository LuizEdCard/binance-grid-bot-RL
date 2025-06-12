#!/bin/bash

# DEPRECATED: Este script era para correção de problemas do Conda
# Agora usando venv

echo "⚠️  SCRIPT DESCONTINUADO - PROBLEMAS CONDA RESOLVIDOS COM VENV"
echo "=============================================================="
echo ""
echo "Este script foi criado para resolver conflitos do Conda."
echo "O projeto agora usa venv, eliminando esses problemas."
echo ""
echo "🔧 SE ENCONTRAR PROBLEMAS COM VENV:"
echo "   1. deactivate"
echo "   2. source venv/bin/activate"
echo "   3. pip list  # verificar dependências"
echo ""
exit 1

# 1. LIMPAR COMPLETAMENTE O SHELL
echo "🧹 Limpando configurações do shell..."

# Remover todas as variáveis conda do ambiente atual
unset CONDA_DEFAULT_ENV
unset CONDA_PREFIX
unset CONDA_PROMPT_MODIFIER
unset CONDA_SHLVL
unset CONDA_EXE
unset CONDA_PYTHON_EXE

# 2. REINICIALIZAR CONDA
echo "🔄 Reinicializando conda..."
eval "$(/home/luiz/miniconda3/bin/conda shell.bash hook)"

# 3. VERIFICAR ESTADO LIMPO
echo "🔍 Verificando estado atual..."
echo "Ambientes disponíveis:"
conda info --envs

echo ""
echo "Estado do shell:"
echo "CONDA_DEFAULT_ENV: ${CONDA_DEFAULT_ENV:-'(não definido)'}"
echo "Python ativo: $(which python)"

# 4. ATIVAR APENAS O AMBIENTE CORRETO
echo ""
echo "🎯 Ativando APENAS o ambiente trading-bot..."
conda activate trading-bot

# 5. VERIFICAR CORREÇÃO
echo ""
echo "✅ VERIFICAÇÃO FINAL:"
echo "CONDA_DEFAULT_ENV: $CONDA_DEFAULT_ENV"
echo "Python: $(which python)"
echo "Versão: $(python --version)"

# Teste de importação simples
echo ""
echo "🧪 Teste básico de funcionamento:"
python -c "
import sys
print(f'Executável Python: {sys.executable}')
print(f'Versão: {sys.version.split()[0]}')

# Testar alguns módulos básicos
basic_modules = ['os', 'sys', 'json']
for module in basic_modules:
    try:
        __import__(module)
        print(f'✅ {module}')
    except:
        print(f'❌ {module}')
"

echo ""
echo "🎯 INSTRUÇÕES:"
echo "1. Se ainda mostrar (trading-bot) (base), feche o terminal e abra um novo"
echo "2. No novo terminal, execute: conda activate trading-bot"
echo "3. Deve mostrar apenas: (trading-bot) no prompt"
echo ""
echo "💡 Para sempre ativar automaticamente, adicione ao ~/.bashrc:"
echo "   echo 'conda activate trading-bot' >> ~/.bashrc"