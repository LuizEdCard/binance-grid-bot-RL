#!/bin/bash

# Script para iniciar a API Flask com configuração correta do PYTHONPATH
echo "🚀 Iniciando API Flask do Trading Bot..."

# Definir diretório do projeto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Diretório do projeto: $PROJECT_DIR"

# Configurar PYTHONPATH
export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"
echo "🔧 PYTHONPATH configurado: $PYTHONPATH"

# Verificar se arquivo .env existe na pasta secrets
if [ ! -f "$PROJECT_DIR/secrets/.env" ]; then
    echo "⚠️  Arquivo secrets/.env não encontrado. Criando estrutura..."
    mkdir -p "$PROJECT_DIR/secrets"
    cat > "$PROJECT_DIR/secrets/.env" << EOF
# API Keys
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Reddit (opcional)
REDDIT_CLIENT_ID=your_reddit_client_id_here
REDDIT_CLIENT_SECRET=your_reddit_client_secret_here
REDDIT_USER_AGENT=your_reddit_user_agent_here
EOF
    echo "📝 Template secrets/.env criado. Configure suas chaves de API antes de usar em produção."
fi

# Verificar dependências Python
echo "🔍 Verificando dependências..."
python3 -c "import sys; sys.path.insert(0, 'src'); import main" 2>/dev/null || {
    echo "❌ Erro ao importar módulos. Verifique as dependências:"
    echo "   pip install -r requirements.txt"
    exit 1
}

echo "✅ Dependências verificadas!"

# Iniciar servidor
echo "🌟 Iniciando servidor Flask..."
cd "$PROJECT_DIR"
python3 src/main.py

echo "🔄 Servidor finalizado."