#!/bin/bash

echo "=== DIAGNÓSTICO DO AMBIENTE VIRTUAL ==="
echo "Diretório atual: $(pwd)"
echo "Shell atual: $SHELL"
echo "Versão do bash: $BASH_VERSION"
echo ""

echo "=== VERIFICANDO ESTRUTURA DO VENV ==="
if [ -d "venv" ]; then
    echo "✓ Diretório venv existe"
    if [ -f "venv/bin/activate" ]; then
        echo "✓ Script activate existe"
        echo "Permissões do activate: $(ls -la venv/bin/activate)"
    else
        echo "✗ Script activate NÃO encontrado"
    fi
else
    echo "✗ Diretório venv NÃO existe"
fi

echo ""
echo "=== TESTANDO ATIVAÇÃO ==="
echo "Tentando ativar o ambiente virtual..."

# Tenta ativar o venv
if source venv/bin/activate 2>/dev/null; then
    echo "✓ Ativação bem-sucedida!"
    echo "Python ativo: $(which python)"
    echo "Versão do Python: $(python --version)"
    echo "Prompt do shell: $PS1"
    deactivate 2>/dev/null
else
    echo "✗ Falha na ativação"
    echo "Tentando diagnosticar o erro..."
    
    # Tenta ativar e captura o erro
    source venv/bin/activate 2>&1 || echo "Erro capturado acima"
fi

echo ""
echo "=== VERIFICAÇÕES ADICIONAIS ==="
echo "PATH atual: $PATH"
echo "Python do sistema: $(which python3)"
echo "Versão Python sistema: $(python3 --version)"

echo ""
echo "=== INSTRUÇÕES ==="
echo "Para ativar manualmente, execute:"
echo "source venv/bin/activate"
echo "ou"
echo ". venv/bin/activate"

