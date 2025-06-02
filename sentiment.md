# Bot de Grid Trading - Análise de Sentimento de Mercado

## 📋 Resumo Geral do Sistema

### Arquitetura do Bot

**Frontend (React + TypeScript)**
- Interface web responsiva em português brasileiro
- Gráficos interativos com Recharts
- Configuração de parâmetros de grid em tempo real
- Preview dinâmico dos níveis de grid
- Gerenciamento de pares de trading customizados

**Backend (Python + Flask)**
- API REST para controle do bot
- Integração com Binance API (Spot + Futures)
- Sistema de Reinforcement Learning (RL) com TensorFlow
- Análise de sentimento de mercado
- Grid trading automatizado

### Tecnologias Principais

**Backend:**
- Python 3.9+
- Flask + Flask-CORS
- Binance API (python-binance)
- TensorFlow 2.11.0 para RL
- Requests para APIs externas

**Frontend:**
- React + TypeScript
- Tailwind CSS
- Recharts para gráficos
- Lucide React para ícones
- Axios para requisições

## 🎯 Sistema de Sentimento Atual

### Estado Atual da Implementação

**Arquivos Principais de Sentimento:**
```
src/utils/
├── sentiment_analyzer.py          # Analisador ONNX (legado)
├── gemma3_sentiment_analyzer.py   # Novo analisador Gemma-3 + Ollama
├── hybrid_sentiment_analyzer.py   # Sistema híbrido inteligente
└── social_listener.py            # Coleta de dados sociais
```

### Sistema Híbrido Implementado

**1. Gemma-3 + Ollama (Principal)**
- Modelo: `gemma3:1b` (1 bilhão de parâmetros)
- Engine: Ollama REST API (leve e otimizado)
- Especializado em análise de sentimento crypto
- Latência: ~200-500ms por análise

**2. ONNX Fallback (Backup)**
- Modelo: `llmware/slim-sentiment-onnx`
- Análise rápida baseada em keywords
- Ativado quando Ollama não está disponível

### Endpoints de Sentimento

**GET /api/sentiment/status**
```json
{
  "models": {
    "gemma3": {"loaded": true, "available": true},
    "onnx": {"loaded": true, "available": true}
  },
  "performance": {
    "total_analyses": 150,
    "gemma3_usage": "85%",
    "onnx_usage": "15%"
  },
  "recommended_model": "gemma3",
  "crypto_optimized": true
}
```

**POST /api/sentiment/analyze**
```json
{
  "text": "Bitcoin to the moon! 🚀 Diamond hands HODL!"
}
```

**Resposta:**
```json
{
  "sentiment": "BULLISH",
  "confidence": 0.92,
  "reasoning": "Positive crypto slang detected: moon, diamond hands, HODL",
  "analyzer_used": "gemma3",
  "crypto_relevant": true
}
```

## 🔧 Configuração Atual de Sentimento

### Palavras-Chave Crypto (Keywords)

**Sinais Bullish:**
```python
"moon", "lambo", "diamond hands", "hodl", "buy the dip",
"to the moon", "bullish", "pump", "breakout", "rally",
"bullrun", "accumulate", "strong hands", "wagmi", "lfg",
"number go up", "probably nothing", "few understand"
```

**Sinais Bearish:**
```python
"dump", "crash", "bear market", "paper hands", "sell off",
"correction", "bearish", "fud", "panic sell", "liquidation",
"rug pull", "scam", "dead cat bounce", "ngmi", "rekt",
"exit liquidity", "bags", "bag holder"
```

**Indicadores de Sarcasmo:**
```python
"great", "wonderful", "amazing", "perfect", "fantastic",
"totally", "definitely", "sure", "of course"
```

### Prompt Engineering para Gemma-3

```python
prompt = f"""You are an expert cryptocurrency market sentiment analyst. Analyze the following text for trading sentiment.

CONTEXT: Cryptocurrency markets are highly emotional and driven by social media sentiment. Consider:
- Crypto slang and terminology (HODL, moon, diamond hands, paper hands, etc.)
- Sarcasm and irony common in crypto communities
- Market psychology and trader emotions
- Social media tone and emojis

TEXT TO ANALYZE: "{text}"

INSTRUCTIONS:
1. Determine if sentiment is BULLISH (positive for price), BEARISH (negative for price), or NEUTRAL
2. Assign confidence level 0.0-1.0
3. Provide brief reasoning

RESPOND WITH ONLY THIS JSON FORMAT:
{{"sentiment": "BULLISH|BEARISH|NEUTRAL", "confidence": 0.85, "reasoning": "brief explanation"}}
"""
```

## 🎮 Integração com Trading

### Como o Sentimento Afeta o Trading

**1. Seleção de Pares (`pair_selector.py`)**
- Filtra pares com base no sentimento positivo
- Evita pares com sentimento muito negativo
- Prioriza pares com buzz social alto

**2. Gestão de Risco (`risk_management.py`)**
- Reduz alavancagem em sentimento bearish
- Aumenta espaçamento do grid em alta volatilidade
- Ajusta stop-loss baseado no sentimento

**3. Algoritmo RL (`rl_agent.py`)**
- Usa sentimento como feature de entrada
- Treina para reconhecer padrões de sentimento
- Adapta estratégia baseada no humor do mercado

## 📊 Fontes de Dados de Sentimento

### Implementadas
- **Reddit**: r/cryptocurrency, r/bitcoin, r/ethereum
- **Análise de texto**: Posts, comentários, títulos
- **Keywords**: Detecção automática de termos crypto

### Potenciais (Para Implementar)
- **Twitter/X**: Tweets com hashtags crypto
- **Discord**: Servidores de trading
- **Telegram**: Canais de sinais
- **Fear & Greed Index**: API externa
- **Google Trends**: Interesse de busca

## 🛠️ Setup para Implementação

### Instalação do Ollama

```bash
# Instalar Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Baixar modelo Gemma-3
ollama pull gemma3:1b

# Verificar modelos instalados
ollama list

# Testar API
curl http://localhost:11434/api/generate -d '{
  "model": "gemma3:1b",
  "prompt": "Bitcoin is going to the moon!",
  "stream": false
}'
```

### Configuração do Backend

```python
# requirements.txt (já implementado)
requests  # Para Ollama API

# Inicializar analisador
from src.utils.gemma3_sentiment_analyzer import Gemma3SentimentAnalyzer

analyzer = Gemma3SentimentAnalyzer(model_name="gemma3:1b")
result = analyzer.analyze("Bitcoin to the moon! 🚀")
```

### Frontend - Monitoramento

**Componente já implementado:**
- `SentimentModelStatus.tsx`: Monitor em tempo real
- Interface de teste de sentimento
- Estatísticas de performance
- Status dos modelos

## 🎯 Próximos Passos Sugeridos

### 1. Fontes de Dados Adicionais
- Implementar coleta do Twitter/X
- Adicionar Fear & Greed Index
- Integrar Google Trends
- Monitorar canais Telegram

### 2. Melhorias no Modelo
- Fine-tuning do Gemma-3 para crypto
- Treinamento com dados históricos
- Calibração de confiança
- Detecção de manipulation/pump & dump

### 3. Integração Avançada
- Peso dinâmico do sentimento no RL
- Alertas baseados em mudanças de sentimento
- Dashboard de sentimento por ativo
- Correlação sentimento vs. preço

### 4. Otimizações
- Cache inteligente de análises
- Batch processing para múltiplos textos
- Rate limiting para APIs
- Fallback automático entre modelos

## 📝 Arquivos de Configuração

**Backend:**
- `src/utils/gemma3_sentiment_analyzer.py`: Analisador principal
- `src/main.py`: Endpoints de API (linhas 150-200)
- `requirements.txt`: Dependências mínimas

**Frontend:**
- `src/components/SentimentModelStatus.tsx`: Interface
- `src/pages/Index.tsx`: Integração no dashboard

**Dados:**
- `data/`: Logs de análises de sentimento
- `.env`: Chaves de API (Twitter, Reddit, etc.)

## 🔍 Como Testar

```bash
# 1. Backend (com Ollama rodando)
cd backend_consolidated
source .venv/bin/activate
python src/main.py

# 2. Testar endpoint
curl -X POST http://localhost:8080/api/sentiment/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Bitcoin pump incoming! 🚀🌙"}'

# 3. Frontend
cd frontend/algo-grid-pilot
npm start
```

## 💡 Dicas para IA Colaboradora

1. **Foco na coleta de dados**: Twitter, Telegram, Discord
2. **Modelos especializados**: Fine-tuning para crypto
3. **Processamento em tempo real**: Stream processing
4. **Validação histórica**: Backtest correlação sentimento-preço
5. **Interface rica**: Gráficos de sentimento, heatmaps

Este sistema já tem uma base sólida implementada. O próximo passo é expandir as fontes de dados e refinar a análise para maximizar a correlação com movimentos de preço.