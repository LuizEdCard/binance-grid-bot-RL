# 🔐 Configuração de Credenciais

## Como Configurar suas Credenciais de Forma Segura

### 1. Criar a Pasta de Segredos
```bash
mkdir -p secrets
```

### 2. Copiar o Template
```bash
cp .env.example secrets/.env
```

### 3. Editar suas Credenciais
Abra o arquivo `secrets/.env` e preencha com suas credenciais reais:

```bash
nano secrets/.env
```

ou

```bash
vim secrets/.env
```

### 4. Configurações Necessárias

#### Binance API (Obrigatório)
```env
BINANCE_API_KEY="sua_chave_api_binance_aqui"
BINANCE_API_SECRET="seu_secret_api_binance_aqui"
```

#### Telegram (Opcional - para alertas)
```env
TELEGRAM_BOT_TOKEN="seu_token_bot_telegram_aqui"
TELEGRAM_CHAT_ID="seu_chat_id_telegram_aqui"
```

#### Reddit (Opcional - para análise de sentimento)
```env
REDDIT_CLIENT_ID="seu_client_id_reddit_aqui"
REDDIT_CLIENT_SECRET="seu_client_secret_reddit_aqui"
REDDIT_USER_AGENT="seu_user_agent_reddit_aqui"
```

## 🛡️ Segurança

### ✅ O que Fazemos
- ✅ Pasta `secrets/` está no `.gitignore`
- ✅ Arquivos `.env` não são enviados para o repositório
- ✅ Template `.env.example` disponível como referência
- ✅ Credenciais ficam apenas na sua máquina local

### ❌ Nunca Faça
- ❌ Não commite arquivos `.env` com credenciais reais
- ❌ Não compartilhe suas chaves de API
- ❌ Não deixe credenciais em código fonte
- ❌ Não use credenciais de produção em testes

## 🚀 Como Obter suas Credenciais

### Binance API
1. Acesse [Binance API Management](https://www.binance.com/en/my/settings/api-management)
2. Crie uma nova API Key
3. Configure as permissões necessárias:
   - ✅ Spot & Margin Trading
   - ✅ Futures Trading (se usar futuros)
   - ❌ Withdraw (nunca ative para trading bots)

### Telegram Bot (Opcional)
1. Fale com [@BotFather](https://t.me/botfather) no Telegram
2. Use `/newbot` para criar um novo bot
3. Copie o token fornecido
4. Para obter chat ID: fale com [@userinfobot](https://t.me/userinfobot)

### Reddit API (Opcional)
1. Acesse [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. Crie uma nova aplicação do tipo "script"
3. Copie o client ID e secret

## 🔧 Verificação

Para verificar se suas credenciais estão funcionando:

```bash
# Testar carregamento das variáveis
python -c "
import os
import sys
sys.path.insert(0, 'src')
from utils.api_client import *
print('✅ Arquivo encontrado:', os.path.exists(ENV_PATH))
print('🔑 BINANCE_API_KEY configurada:', bool(os.environ.get('BINANCE_API_KEY')))
"
```

## 📁 Estrutura Final
```
projeto/
├── secrets/           # ← Não vai para o git
│   └── .env          # ← Suas credenciais reais
├── .env.example      # ← Template público
├── .gitignore        # ← Inclui secrets/
└── src/
    └── ...
```

## 🆘 Problemas Comuns

### "Arquivo .env não encontrado"
- Verifique se criou a pasta `secrets/`
- Verifique se copiou `.env.example` para `secrets/.env`

### "API Key inválida"
- Verifique se copiou a chave corretamente (sem espaços)
- Verifique se a API Key está ativa na Binance
- Verifique as permissões da API Key

### "Credenciais foram expostas no git"
- Execute: `git rm --cached .env` (se ainda estiver rastreado)
- Regenere suas API Keys na Binance
- Configure novamente com as novas chaves