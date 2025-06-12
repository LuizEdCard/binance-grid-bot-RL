# 📰 Integração de Notícias da Binance com Análise de Sentimentos

## 🎯 Visão Geral

O sistema agora integra automaticamente as notícias, anúncios e feeds da Binance na análise de sentimentos do bot de trading. Isso permite decisões mais informadas baseadas em:

- **Anúncios oficiais da Binance** 📢
- **Notícias gerais do mercado crypto** 📈
- **Conteúdo em destaque/trending** 🔥
- **Análise de sentimento em tempo real** 🧠

## 🚀 Recursos Implementados

### 1. **BinanceNewsListener**
Coleta notícias diretamente da API pública da Binance:

```python
from utils.binance_news_listener import BinanceNewsListener

async with BinanceNewsListener() as listener:
    # Buscar notícias das últimas 24 horas
    news = await listener.fetch_all_recent_news(hours_back=24)
    
    # Buscar notícias específicas de símbolos
    btc_news = await listener.get_crypto_specific_news(['BTC', 'ETH'])
```

### 2. **Análise de Sentimento Integrada**
Analisa automaticamente o sentimento das notícias:

```python
from utils.sentiment_analyzer import SentimentAnalyzer

analyzer = SentimentAnalyzer()

# Análise geral de notícias
sentiment = await analyzer.analyze_binance_news(hours_back=24)

# Análise específica de símbolos
btc_sentiment = await analyzer.get_symbol_sentiment_from_news('BTC')
```

### 3. **Integração com Agente de Sentimentos**
As notícias da Binance são automaticamente incluídas na análise de sentimentos do bot:

```python
# Configurado automaticamente no sentiment_agent.py
sources = {
    "reddit": RedditSentimentSource(),
    "binance_news": BinanceNewsSentimentSource(),  # ✅ Nova fonte
    "twitter": TwitterSentimentSource()
}
```

## ⚙️ Configuração

### 1. **Arquivo config.yaml**
Adicione ou ajuste as configurações de notícias da Binance:

```yaml
sentiment_analysis:
  enabled: true
  fetch_interval_minutes: 60
  
  # Nova seção para notícias da Binance
  binance_news:
    enabled: true                    # Ativar/desativar fonte
    fetch_interval_minutes: 30       # Intervalo de busca
    hours_back: 24                   # Buscar últimas X horas
    min_relevance_score: 0.2         # Score mínimo de relevância
    max_news_per_fetch: 20           # Máximo de notícias por busca
    include_announcements: true      # Incluir anúncios
    include_general_news: true       # Incluir notícias gerais
    include_trending: true           # Incluir conteúdo em destaque
    
  reddit:
    enabled: true
    # ... outras configurações
```

### 2. **Ativação Automática**
A integração é ativada automaticamente quando:
- ✅ `sentiment_analysis.enabled: true`
- ✅ `sentiment_analysis.binance_news.enabled: true`

## 📊 Tipos de Dados Coletados

### **Anúncios Oficiais**
- Novos listings de criptomoedas
- Mudanças em produtos e serviços
- Atualizações de políticas
- Manutenções programadas

### **Notícias do Mercado**
- Análises de mercado
- Relatórios de trading
- Insights de produtos
- Educação sobre crypto

### **Conteúdo em Destaque**
- Artigos populares
- Conteúdo promocional
- Eventos especiais
- Parcerias importantes

## 🎯 Score de Relevância

O sistema atribui scores de relevância baseados em palavras-chave crypto:

**Palavras-chave monitored:**
```python
crypto_keywords = [
    "bitcoin", "btc", "ethereum", "eth", "binance", "crypto", 
    "trading", "market", "price", "bull", "bear", "pump", "dump",
    "ada", "cardano", "bnb", "usdt", "defi", "nft", "altcoin",
    "spot", "futures", "margin", "leverage", "liquidation"
]
```

**Cálculo de relevância:**
- Score 0.0-1.0 baseado em matches de palavras-chave
- Notícias com score >= `min_relevance_score` são incluídas
- Score mais alto = maior peso na análise de sentimento

## 📈 Exemplo de Uso Prático

### **1. Análise Manual**
```python
# Testar a integração
python test_sentiment_integration_final.py
```

### **2. Busca de Sentimento Específico**
```python
from utils.sentiment_analyzer import SentimentAnalyzer

analyzer = SentimentAnalyzer()

# Analisar sentimento do BTC nas últimas 12 horas
btc_sentiment = await analyzer.get_symbol_sentiment_from_news('BTC', hours_back=12)

print(f"BTC Sentiment: {btc_sentiment['symbol_sentiment']}")
print(f"Score: {btc_sentiment['symbol_score']}")
print(f"Menções: {btc_sentiment['mentions_count']}")
```

### **3. Análise de Múltiplos Símbolos**
```python
symbols = ['BTC', 'ETH', 'ADA', 'BNB']
sentiments = analyzer.analyze_multiple_symbols(symbols, hours_back=24)

for symbol, data in sentiments.items():
    print(f"{symbol}: {data['symbol_sentiment']} ({data['symbol_score']:.3f})")
```

## 🔧 Estrutura de Dados

### **BinanceNewsItem**
```python
@dataclass
class BinanceNewsItem:
    id: str                    # ID único da notícia
    title: str                 # Título da notícia
    body: str                  # Corpo da notícia
    type: str                  # Tipo (announcement, news, trending)
    published_time: datetime   # Data de publicação
    tags: List[str]           # Tags/categorias
    url: str                  # URL da notícia
    relevance_score: float    # Score de relevância (0.0-1.0)
    sentiment_score: float    # Score de sentimento (-1.0 a 1.0)
```

### **Resultado de Análise**
```python
{
    "overall_sentiment": "positive|negative|neutral",
    "average_score": 0.123,           # Score médio (-1.0 a 1.0)
    "weighted_score": 0.456,          # Score ponderado por relevância
    "news_count": 15,                 # Número de notícias analisadas
    "time_range_hours": 24,           # Período analisado
    "analyzed_at": "2025-06-11T20:40:00",
    "symbols_filter": ["BTC"] | "all",
    "news_items": [...],              # Lista de notícias analisadas
    "stats": {
        "positive_count": 5,
        "negative_count": 2,
        "neutral_count": 8,
        "avg_relevance": 0.67
    }
}
```

## 🎛️ Monitoramento e Logs

### **Logs Informativos**
```
INFO - Fetching all Binance news from last 24 hours...
INFO - Fetched 10 trending articles from Binance
INFO - Parsed 10 new trending articles
INFO - Successfully fetched 10 unique Binance news items
INFO - Analyzed 10 Binance news items. Overall sentiment: neutral (0.068)
```

### **Estatísticas do Sistema**
```python
# Obter estatísticas do listener
stats = listener.get_statistics()
print(f"Total fetched: {stats['total_fetched']}")
print(f"Fetch errors: {stats['fetch_errors']}")
print(f"Keywords count: {stats['keywords_count']}")
```

## ⚡ Performance e Limites

### **Configuração Recomendada**
- ✅ **fetch_interval_minutes**: 30 (evita spam de requests)
- ✅ **hours_back**: 24 (últimas 24 horas)
- ✅ **max_news_per_fetch**: 20 (limite conservador)
- ✅ **min_relevance_score**: 0.2 (filtra ruído)

### **Rate Limiting**
- Requests limitados por configuração
- Cache interno evita duplicatas
- Retry automático em caso de erro

### **Fallback System**
1. **ONNX Model** → análise local
2. **AI Local (Ollama)** → fallback inteligente  
3. **Rule-based** → fallback básico

## 🐛 Troubleshooting

### **Problema: "Failed to connect to Binance news API"**
✅ **Solução:** Verificar conexão internet e firewall

### **Problema: "No relevant Binance news found"**
✅ **Solução:** Diminuir `min_relevance_score` ou aumentar `hours_back`

### **Problema: "Cannot run the event loop while another loop is running"**
✅ **Solução:** Usar métodos `async` quando possível

### **Debugging**
```python
# Teste de conexão
python test_binance_simple.py

# Teste completo
python test_sentiment_integration_final.py

# Teste individual
from utils.binance_news_listener import BinanceNewsListener
async with BinanceNewsListener() as listener:
    connected = await listener.test_connection()
    print(f"Connected: {connected}")
```

## 🚀 Próximos Passos

### **Melhorias Planejadas**
1. **Filtragem por categoria** (DeFi, NFT, Trading, etc.)
2. **Análise de impacto temporal** (correlação preço vs. notícia)
3. **Alertas automáticos** para sentimento extremo
4. **Dashboard web** para visualização

### **Integração com Trading**
A análise de sentimento das notícias da Binance será automaticamente:
- ✅ Incluída no score de sentimento geral
- ✅ Usada para filtrar pares de trading
- ✅ Considerada para ajustes de risco
- ✅ Disponível para IA do bot

## 📋 Checklist de Configuração

- [ ] Verificar `sentiment_analysis.enabled: true` em config.yaml
- [ ] Configurar `binance_news.enabled: true`
- [ ] Ajustar `fetch_interval_minutes` conforme necessário
- [ ] Testar conexão com `python test_binance_simple.py`
- [ ] Verificar logs para confirmação de funcionamento
- [ ] Monitorar performance e ajustar limites se necessário

---

🎉 **A integração de notícias da Binance está agora completamente operacional e pronta para melhorar as decisões de trading do seu bot!**