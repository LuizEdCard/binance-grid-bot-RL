# 📚 **API Documentation - Trading Bot System**

**Base URL**: `http://localhost:5000`  
**Content-Type**: `application/json`  
**CORS**: Enabled for all routes

---

## 📊 **1. SYSTEM STATUS ENDPOINTS**

### `GET /api/status`
**Descrição**: Status geral do sistema e bots ativos  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "active_bots": {
    "ADAUSDT": {
      "status": "running",
      "market_type": "futures",
      "uptime": 3600,
      "last_trade": "2025-06-14T15:30:00Z"
    }
  },
  "api_status": "online",
  "timestamp": 1749926400
}
```

### `GET /api/operation_mode`
**Descrição**: Modo de operação atual (Production/Shadow)  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "mode": "Production",
  "description": "Live trading with real money",
  "shadow_mode": false
}
```

### `GET /api/metrics`
**Descrição**: Métricas do sistema multi-agent  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "system": {
    "uptime": 7200,
    "memory_usage": "45.2 MB",
    "cpu_usage": "12.5%",
    "active_pairs": 3
  },
  "trading": {
    "total_trades": 156,
    "successful_trades": 142,
    "success_rate": 91.03,
    "total_pnl": 45.67
  },
  "cache": {
    "hit_rate": 89.5,
    "size": "12.3 MB",
    "entries": 1250
  }
}
```

---

## 💰 **2. BALANCE & ACCOUNT ENDPOINTS**

### `GET /api/balance`
**Descrição**: Saldos detalhados de todas as contas  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "spot": {
    "balances": [
      {
        "asset": "USDT",
        "free": "250.50",
        "locked": "0.00",
        "usdt_value": 250.50
      },
      {
        "asset": "BTC",
        "free": "0.00150000",
        "locked": "0.00000000",
        "usdt_value": 150.75
      }
    ],
    "total_usdt_value": 401.25
  },
  "futures": {
    "available_balance": 100.64,
    "balances": [
      {
        "asset": "USDT",
        "wallet_balance": "99.68585833",
        "margin_balance": "99.68585833",
        "available_balance": "100.64287942",
        "usdt_value": 100.64287942
      }
    ],
    "total_usdt_value": 100.64
  },
  "total_portfolio_value": 501.89
}
```

### `GET /api/balance/summary`
**Descrição**: Resumo simplificado dos saldos  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "total_usdt": 501.89,
  "spot_usdt": 401.25,
  "futures_usdt": 100.64,
  "available_for_trading": 350.89,
  "in_positions": 151.00
}
```

---

## 📈 **3. MARKET DATA ENDPOINTS**

### `GET /api/market_data`
**Descrição**: Dados de mercado para todos os pares  
**Parâmetros**: 
- `limit` (opcional): Limitar número de pares retornados  
**Resposta**:
```json
{
  "tickers": [
    {
      "symbol": "BTCUSDT",
      "price": "67250.50",
      "change_24h": "+2.45%",
      "volume_24h": "1250000000.00",
      "high_24h": "68000.00",
      "low_24h": "66500.00"
    },
    {
      "symbol": "ETHUSDT", 
      "price": "3245.75",
      "change_24h": "-1.20%",
      "volume_24h": "850000000.00",
      "high_24h": "3290.00",
      "low_24h": "3200.00"
    }
  ],
  "total_symbols": 3143,
  "last_update": 1749926400
}
```

### `GET /api/klines/<symbol>`
**Descrição**: Dados de candlestick para um símbolo específico  
**Parâmetros**:
- `interval` (opcional): 1m, 5m, 15m, 1h, 4h, 1d (padrão: 1h)
- `limit` (opcional): Número de candles (padrão: 100)
**Exemplo**: `/api/klines/BTCUSDT?interval=1h&limit=50`  
**Resposta**:
```json
{
  "symbol": "BTCUSDT",
  "interval": "1h",
  "klines": [
    {
      "open_time": 1749926400,
      "open": "67200.00",
      "high": "67350.00", 
      "low": "67150.00",
      "close": "67250.50",
      "volume": "125.50",
      "close_time": 1749930000
    }
  ],
  "count": 50
}
```

### `GET /api/indicators/<symbol>`
**Descrição**: Indicadores técnicos para um símbolo  
**Parâmetros**:
- `indicators` (opcional): rsi,macd,sma,ema (padrão: todos)
- `period` (opcional): Período para cálculo (padrão: 14)
**Exemplo**: `/api/indicators/BTCUSDT?indicators=rsi,macd&period=14`  
**Resposta**:
```json
{
  "symbol": "BTCUSDT",
  "indicators": {
    "rsi": {
      "value": 65.2,
      "signal": "neutral",
      "period": 14
    },
    "macd": {
      "macd": 125.5,
      "signal": 120.3,
      "histogram": 5.2,
      "trend": "bullish"
    },
    "sma_20": 66890.45,
    "ema_20": 67120.30
  },
  "timestamp": 1749926400
}
```

---

## 🤖 **4. TRADING ENDPOINTS**

### `GET /api/trading/pairs`
**Descrição**: Pares atualmente sendo negociados  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "active_pairs": [
    {
      "symbol": "ADAUSDT",
      "market_type": "futures",
      "status": "trading",
      "grid_levels": 8,
      "unrealized_pnl": 12.45,
      "open_orders": 6
    },
    {
      "symbol": "ETHUSDT",
      "market_type": "spot", 
      "status": "monitoring",
      "grid_levels": 5,
      "unrealized_pnl": -2.10,
      "open_orders": 3
    }
  ],
  "total_pairs": 2
}
```

### `GET /api/trading/executions`
**Descrição**: Execuções de trading em tempo real  
**Parâmetros**:
- `limit` (opcional): Número de execuções (padrão: 50)
- `symbol` (opcional): Filtrar por símbolo específico
**Resposta**:
```json
{
  "executions": [
    {
      "symbol": "ADAUSDT",
      "side": "BUY",
      "quantity": "8.0",
      "price": "0.6290",
      "notional": "5.032",
      "timestamp": 1749926400,
      "order_id": "54880337983",
      "market_type": "futures"
    }
  ],
  "total_executions": 156,
  "returned": 50
}
```

### `POST /api/grid/start`
**Descrição**: Iniciar grid trading para um símbolo  
**Parâmetros** (JSON Body):
```json
{
  "symbol": "ADAUSDT",
  "market_type": "futures",
  "initial_levels": 8,
  "spacing_perc": 0.001,
  "capital_usdt": 50.0
}
```
**Resposta**:
```json
{
  "success": true,
  "message": "Grid trading started for ADAUSDT",
  "symbol": "ADAUSDT",
  "grid_id": "grid_ADAUSDT_1749926400",
  "initial_orders": 8,
  "capital_allocated": 50.0
}
```

### `POST /api/grid/stop`
**Descrição**: Parar grid trading para um símbolo  
**Parâmetros** (JSON Body):
```json
{
  "symbol": "ADAUSDT"
}
```
**Resposta**:
```json
{
  "success": true,
  "message": "Grid trading stopped for ADAUSDT",
  "symbol": "ADAUSDT",
  "final_pnl": 12.45,
  "orders_cancelled": 6
}
```

### `GET /api/grid/status/<symbol>`
**Descrição**: Status detalhado do grid para um símbolo  
**Exemplo**: `/api/grid/status/ADAUSDT`  
**Resposta**:
```json
{
  "symbol": "ADAUSDT",
  "status": "active",
  "market_type": "futures",
  "grid_levels": 8,
  "current_spacing": 0.001,
  "total_orders": 6,
  "active_orders": [
    {
      "price": "0.6290",
      "type": "buy",
      "quantity": "8.0",
      "order_id": "54880337983"
    }
  ],
  "unrealized_pnl": 12.45,
  "realized_pnl": 8.90,
  "total_trades": 24,
  "uptime": 3600
}
```

### `GET /api/recommended_pairs`
**Descrição**: Pares recomendados pelo sistema de IA  
**Parâmetros**:
- `limit` (opcional): Número de recomendações (padrão: 10)
- `market_type` (opcional): spot, futures, ou all (padrão: all)
**Resposta**:
```json
{
  "recommended_pairs": [
    {
      "symbol": "ADAUSDT",
      "score": 85.5,
      "market_type": "futures",
      "reasons": ["High volatility", "Strong volume", "AI bullish signal"],
      "risk_level": "medium",
      "expected_return": "2.5%"
    },
    {
      "symbol": "ETHUSDT",
      "score": 78.2,
      "market_type": "spot",
      "reasons": ["Technical breakout", "Positive sentiment"],
      "risk_level": "low", 
      "expected_return": "1.8%"
    }
  ],
  "total_recommendations": 2,
  "last_analysis": 1749926400
}
```

---

## 🔴 **5. LIVE DATA ENDPOINTS (Novos)**

### `GET /api/live/trading/all`
**Descrição**: Dados de trading ao vivo para todos os símbolos  
**Parâmetros**:
- `limit` (opcional): Limitar símbolos retornados (padrão: 50)
**Resposta**:
```json
{
  "success": true,
  "symbols": ["ADAUSDT", "ETHUSDT"],
  "data": {
    "ADAUSDT": {
      "symbol": "ADAUSDT",
      "position": {
        "side": "LONG",
        "size": "24.0",
        "entry_price": "0.6250",
        "mark_price": "0.6290",
        "unrealized_pnl": "9.60"
      },
      "unrealized_pnl": 12.45,
      "realized_pnl": 8.90,
      "recent_trades": [
        {
          "price": "0.6290",
          "quantity": "8.0",
          "side": "BUY",
          "timestamp": 1749926400
        }
      ],
      "timestamp": 1749926400
    }
  },
  "total_symbols": 2,
  "last_update": 1749926400
}
```

### `GET /api/live/trading/<symbol>`
**Descrição**: Dados específicos de um par de trading  
**Exemplo**: `/api/live/trading/ADAUSDT`  
**Resposta**:
```json
{
  "success": true,
  "symbol": "ADAUSDT",
  "data": {
    "position": {
      "side": "LONG",
      "size": "24.0",
      "entry_price": "0.6250",
      "mark_price": "0.6290",
      "unrealized_pnl": "9.60"
    },
    "recent_trades": [
      {
        "price": "0.6290",
        "quantity": "8.0", 
        "side": "BUY",
        "timestamp": 1749926400
      }
    ],
    "unrealized_pnl": 12.45,
    "timestamp": 1749926400
  },
  "data_age_seconds": 30
}
```

### `GET /api/live/agents/all/decisions`
**Descrição**: Decisões recentes de todos os agentes  
**Parâmetros**:
- `limit_per_agent` (opcional): Decisões por agente (padrão: 5)
**Resposta**:
```json
{
  "success": true,
  "agents": ["ai", "sentiment", "risk", "data"],
  "decisions": {
    "ai": [
      {
        "action": "buy_signal",
        "confidence": 0.85,
        "reasoning": "Strong bullish indicators detected",
        "symbol": "ADAUSDT",
        "timestamp": 1749926400,
        "agent": "ai"
      }
    ],
    "sentiment": [
      {
        "action": "positive_sentiment",
        "score": 0.72,
        "sources": ["reddit", "twitter"],
        "symbol": "ETHUSDT",
        "timestamp": 1749926380,
        "agent": "sentiment"
      }
    ],
    "risk": [
      {
        "action": "risk_assessment",
        "level": "medium",
        "portfolio_exposure": 0.45,
        "recommendation": "reduce_position_size",
        "timestamp": 1749926360,
        "agent": "risk"
      }
    ]
  },
  "total_agents": 4,
  "last_update": 1749926400
}
```

### `GET /api/live/agents/<agent_name>/decisions`
**Descrição**: Stream de decisões de um agente específico  
**Parâmetros**:
- `limit` (opcional): Número de decisões (padrão: 20)
- `since` (opcional): Timestamp para filtrar decisões recentes
**Exemplo**: `/api/live/agents/ai/decisions?limit=10&since=1749926000`  
**Resposta**:
```json
{
  "success": true,
  "agent": "ai",
  "decisions": [
    {
      "action": "market_analysis",
      "result": "bullish_trend",
      "confidence": 0.78,
      "symbol": "BTCUSDT",
      "reasoning": "Technical indicators show strong upward momentum",
      "timestamp": 1749926400,
      "agent": "ai"
    }
  ],
  "total_decisions": 10,
  "latest_timestamp": 1749926400,
  "has_more": false
}
```

### `GET /api/live/system/status`
**Descrição**: Status abrangente do sistema em tempo real  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "success": true,
  "status": {
    "timestamp": 1749926400,
    "components": {
      "trading": {
        "status": "active",
        "uptime": 3600,
        "pairs_active": 3,
        "orders_open": 15
      },
      "websocket": {
        "status": "connected",
        "latency": 45,
        "reconnections": 0
      },
      "ai_agents": {
        "status": "operational",
        "active_agents": 4,
        "decisions_per_minute": 12.5
      }
    },
    "overview": {
      "total_components": 8,
      "active_trading_pairs": 3,
      "total_agent_decisions": 1247,
      "system_uptime": 7200
    },
    "health": {
      "trading_active": true,
      "agents_responsive": true,
      "data_fresh": true,
      "overall_health": "healthy"
    }
  }
}
```

### `GET /api/live/profits/summary`
**Descrição**: Resumo de lucros/perdas em tempo real  
**Parâmetros**:
- `timeframe` (opcional): 1h, 24h, 7d, 30d (padrão: 24h)
**Resposta**:
```json
{
  "success": true,
  "summary": {
    "timeframe": "24h",
    "total_realized_pnl": 45.67,
    "total_unrealized_pnl": 12.34,
    "profitable_trades": 15,
    "losing_trades": 3,
    "total_trades": 18,
    "success_rate": 0.833,
    "best_performer": {
      "symbol": "ADAUSDT",
      "pnl": 18.90
    },
    "worst_performer": {
      "symbol": "ETHUSDT", 
      "pnl": -2.10
    },
    "by_symbol": {
      "ADAUSDT": {
        "unrealized_pnl": 12.45,
        "realized_pnl": 8.90,
        "total_pnl": 21.35
      },
      "ETHUSDT": {
        "unrealized_pnl": -0.10,
        "realized_pnl": -2.00,
        "total_pnl": -2.10
      }
    }
  },
  "timestamp": 1749926400
}
```

### `GET /api/live/alerts`
**Descrição**: Alertas e notificações do sistema  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "success": true,
  "alerts": [
    {
      "type": "warning",
      "severity": "medium",
      "message": "Trading data for BTCUSDT is stale (320s old)",
      "symbol": "BTCUSDT",
      "timestamp": 1749926400
    },
    {
      "type": "info",
      "severity": "low",
      "message": "New profitable trade executed on ADAUSDT",
      "symbol": "ADAUSDT",
      "timestamp": 1749926380
    }
  ],
  "total_alerts": 2,
  "alert_levels": {
    "critical": 0,
    "high": 0,
    "medium": 1,
    "low": 1
  }
}
```

---

## 🤖 **6. MULTI-AGENT ENDPOINTS**

### `GET /api/model/api/system/status`
**Descrição**: Status detalhado do sistema multi-agent  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "system": {
    "status": "operational",
    "agents_count": 4,
    "uptime": 7200,
    "last_health_check": 1749926400
  },
  "agents": {
    "ai": {
      "status": "active",
      "last_decision": 1749926395,
      "decisions_count": 234,
      "confidence_avg": 0.76
    },
    "sentiment": {
      "status": "active", 
      "last_analysis": 1749926390,
      "sentiment_score": 0.62,
      "sources_monitored": 3
    },
    "risk": {
      "status": "active",
      "last_assessment": 1749926385,
      "current_risk_level": "medium",
      "alerts_triggered": 2
    },
    "data": {
      "status": "active",
      "cache_hit_rate": 89.5,
      "websocket_connected": true,
      "last_data_update": 1749926400
    }
  }
}
```

### `GET /api/model/api/agents/<agent_name>/metrics`
**Descrição**: Métricas detalhadas de um agente específico  
**Exemplo**: `/api/model/api/agents/ai/metrics`  
**Resposta**:
```json
{
  "success": true,
  "agent": "ai",
  "metrics": {
    "decisions_made": 234,
    "accuracy_rate": 0.78,
    "current_analysis": {
      "market_trend": "bullish",
      "confidence": 0.82,
      "last_update": 1749926400
    },
    "agent_name": "ai",
    "status": "active",
    "last_update": 1749926400,
    "uptime": 7200
  },
  "timestamp": 1749926400
}
```

---

## 🔧 **7. CONFIGURATION ENDPOINTS**

### `GET /api/grid/config`
**Descrição**: Configuração atual do grid trading  
**Parâmetros**: Nenhum  
**Resposta**:
```json
{
  "grid": {
    "initial_levels": 8,
    "initial_spacing_perc": 0.001,
    "futures": {
      "leverage": 10,
      "max_leverage": 15
    },
    "spot": {
      "max_base_asset_allocation": 0.5,
      "min_order_size_usd": 5
    }
  },
  "trading": {
    "capital_per_pair_usd": 50,
    "cycle_interval_seconds": 15,
    "allow_market_switching": true
  }
}
```

### `POST /api/grid/config`
**Descrição**: Atualizar configuração do grid trading  
**Parâmetros** (JSON Body):
```json
{
  "initial_levels": 10,
  "initial_spacing_perc": 0.0015,
  "leverage": 15
}
```
**Resposta**:
```json
{
  "success": true,
  "message": "Grid configuration updated successfully",
  "updated_config": {
    "initial_levels": 10,
    "initial_spacing_perc": 0.0015,
    "leverage": 15
  }
}
```

---

## ⚠️ **8. ERROR RESPONSES**

Todos os endpoints podem retornar os seguintes erros:

### `400 Bad Request`
```json
{
  "error": "Invalid parameters",
  "message": "Symbol INVALID not found",
  "code": 400
}
```

### `404 Not Found`
```json
{
  "error": "Endpoint not found",
  "message": "The requested endpoint does not exist",
  "code": 404
}
```

### `500 Internal Server Error`
```json
{
  "error": "Internal server error",
  "message": "Database connection failed",
  "code": 500
}
```

### `503 Service Unavailable`
```json
{
  "error": "Service unavailable",
  "message": "Binance API rate limit exceeded",
  "code": 503,
  "retry_after": 300
}
```

---

## 🔥 **9. WEBSOCKET ENDPOINTS** (Planned)

### `WS /ws/trading/updates`
**Descrição**: Stream em tempo real de atualizações de trading  
**Mensagens**:
```json
{
  "type": "trade_execution",
  "data": {
    "symbol": "ADAUSDT",
    "side": "BUY",
    "quantity": "8.0",
    "price": "0.6290",
    "timestamp": 1749926400
  }
}
```

### `WS /ws/agents/decisions`
**Descrição**: Stream de decisões dos agentes em tempo real  
**Mensagens**:
```json
{
  "type": "agent_decision",
  "data": {
    "agent": "ai",
    "action": "buy_signal",
    "confidence": 0.85,
    "symbol": "ADAUSDT",
    "timestamp": 1749926400
  }
}
```

---

## 📋 **10. QUICK REFERENCE**

### **Trading Operations**
- `GET /api/status` - System status
- `GET /api/trading/pairs` - Active trading pairs
- `POST /api/grid/start` - Start grid trading
- `POST /api/grid/stop` - Stop grid trading

### **Live Data**
- `GET /api/live/trading/all` - Live trading data
- `GET /api/live/system/status` - Live system status
- `GET /api/live/profits/summary` - Live profit summary

### **Market Data**
- `GET /api/market_data` - All market tickers
- `GET /api/balance/summary` - Account balance
- `GET /api/indicators/<symbol>` - Technical indicators

### **Multi-Agent**
- `GET /api/live/agents/all/decisions` - All agent decisions
- `GET /api/model/api/system/status` - Agent system status

---

**📝 Note**: Todos os timestamps são em formato Unix (segundos desde 1970).  
**🔒 Security**: A API atualmente não requer autenticação para desenvolvimento.  
**📊 Rate Limits**: Respeite os limites da Binance API para evitar bans temporários.