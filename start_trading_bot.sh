#!/bin/bash

# Script para iniciar o Bot de Trading com configuração correta do PYTHONPATH
echo "🤖 Iniciando Trading Bot..."

# Definir diretório do projeto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Diretório do projeto: $PROJECT_DIR"

# Configurar PYTHONPATH
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"
echo "🔧 PYTHONPATH configurado: $PYTHONPATH"

# Verificar se arquivo .env existe
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "❌ Arquivo .env não encontrado. Execute ./start_api.sh primeiro para criar o template."
    exit 1
fi

# Verificar dependências Python
echo "🔍 Verificando dependências..."
python3 -c "import sys; sys.path.insert(0, 'src'); import bot_logic" 2>/dev/null || {
    echo "❌ Erro ao importar módulos. Verifique as dependências:"
    echo "   pip install -r requirements.txt"
    exit 1
}

echo "✅ Dependências verificadas!"

# Iniciar bot
echo "🚀 Iniciando Trading Bot..."
cd "$PROJECT_DIR"
python3 src/bot_logic.py

echo "🔄 Bot finalizado."