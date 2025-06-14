# API Endpoints Documentation - Agent History and Metrics

## New API Endpoints for Agent Monitoring and History

### 1. Agent List and Capabilities

**GET `/api/agents`**
- **Description**: List all available agents and their capabilities
- **Response**: 
```json
{
  "agents": {
    "ai": {
      "has_statistics": true,
      "has_history": true,
      "history_methods": ["get_recent_analyses"],
      "available_methods": ["analyze_market", "get_statistics", ...]
    },
    "data": { ... },
    "risk": { ... },
    "sentiment": { ... },
    "coordinator": { ... }
  },
  "total_agents": 5,
  "active_agents": 5
}
```

### 2. Agent Detailed Metrics

**GET `/api/agents/<agent_name>/metrics`**
- **Description**: Get detailed performance metrics for a specific agent
- **Parameters**: 
  - `agent_name`: ai, data, risk, sentiment, coordinator
- **Response**: Agent-specific statistics object

### 3. Agent Action/Decision History

**GET `/api/agents/<agent_name>/history`**
- **Description**: Get action/decision history for a specific agent
- **Parameters**: 
  - `agent_name`: ai, data, risk, sentiment, coordinator
  - `limit` (optional): Number of entries to return (default: 20)
  - `since` (optional): Timestamp to filter entries from
  - `symbol` (optional): Required for data agent history
- **Response**: Array of historical entries with timestamps

**Examples:**
```bash
# Get AI agent analysis history
GET /api/agents/ai/history?limit=10

# Get data history for specific symbol
GET /api/agents/data/history?symbol=BTCUSDT&limit=5

# Get sentiment analysis history since timestamp
GET /api/agents/sentiment/history?since=1640995200&limit=15
```

### 4. Agent Decision Context and Rationale

**GET `/api/agents/<agent_name>/decisions`**
- **Description**: Get detailed decision log with context and rationale
- **Parameters**: 
  - `agent_name`: ai, data, risk, sentiment, coordinator
  - `limit` (optional): Number of decisions to return (default: 10)
  - `include_context` (optional): Include decision context (default: true)
- **Response**: 
```json
{
  "agent": "ai",
  "decisions": [
    {
      "timestamp": 1640995200,
      "decision_type": "market_analysis",
      "context": { ... },
      "decision": { ... },
      "rationale": "Analysis based on technical indicators..."
    }
  ],
  "total_decisions": 5,
  "include_context": true
}
```

### 5. System Status Overview

**GET `/api/system/status`**
- **Description**: Get comprehensive system status including all agents
- **Response**: 
```json
{
  "timestamp": 1640995200,
  "system_health": "healthy",
  "agents": {
    "ai": {
      "status": "active",
      "capabilities": {
        "statistics": true,
        "history": true
      },
      "last_activity": 1640995190,
      "performance": { ... }
    }
  },
  "total_agents": 5,
  "active_agents": 5
}
```

### 6. Testing Endpoints

**GET `/api/testing/available`**
- **Description**: Get list of available tests
- **Response**: 
```json
{
  "available_tests": {
    "agents_availability": {
      "description": "Test if all agents are responding",
      "estimated_duration": "< 5s"
    },
    "ai_connectivity": {
      "description": "Test AI agent connectivity and model availability",
      "estimated_duration": "< 10s"
    },
    "data_freshness": {
      "description": "Test if data agent has fresh market data",
      "estimated_duration": "< 2s"
    }
  },
  "total_tests": 3
}
```

**POST `/api/testing/run/<test_name>`**
- **Description**: Run a specific test and return results
- **Parameters**: 
  - `test_name`: agents_availability, ai_connectivity, data_freshness
- **Response**: 
```json
{
  "test_name": "agents_availability",
  "timestamp": 1640995200,
  "status": "pass",
  "results": {
    "ai": {
      "status": "pass",
      "response_time": "< 1s",
      "has_data": true
    }
  }
}
```

## Existing Endpoints (Enhanced)

### AI Model Management

**GET `/ai/models`** - Get AI model information
**POST `/ai/models/refresh`** - Force refresh model detection
**GET `/ai/status`** - Get comprehensive AI agent status
**POST `/ai/models/reset-flag`** - Reset model change detection flag

## Agent History Methods Implementation

### Per-Agent History Methods:

1. **AIAgent**: `get_recent_analyses(limit=10)` 
   - Returns recent market analyses with timestamps and reasoning

2. **DataAgent**: `get_data_history(symbol, limit=10)`
   - Returns recent data collection events for a specific symbol

3. **RiskAgent**: `get_risk_history(limit=20)`
   - Returns recent risk assessments and alert events

4. **SentimentAgent**: `get_sentiment_history(limit=20)`
   - Returns recent sentiment analysis results by source

5. **CoordinatorAgent**: `get_coordination_history(limit=20)` *(NEW)*
   - Returns recent coordination events, health checks, and load balancing activities

## Usage Examples

### Frontend Integration
```javascript
// Get all agents status
const agentsStatus = await fetch('/api/system/status').then(r => r.json());

// Get AI decision history with context
const aiDecisions = await fetch('/api/agents/ai/decisions?limit=5&include_context=true')
  .then(r => r.json());

// Run connectivity test
const testResult = await fetch('/api/testing/run/ai_connectivity', {method: 'POST'})
  .then(r => r.json());

// Get fresh data for BTCUSDT
const dataHistory = await fetch('/api/agents/data/history?symbol=BTCUSDT&limit=10')
  .then(r => r.json());
```

### Monitoring Dashboard
These endpoints enable comprehensive monitoring dashboards showing:
- Agent performance metrics
- Decision history with reasoning
- System health status
- Historical trends
- Real-time testing capabilities

## Real-Time Data and WebSocket Endpoints

### WebSocket Status
**GET `/api/websocket/status`**
- **Description**: Get WebSocket connection status and statistics
- **Response**: 
```json
{
  "websocket_enabled": true,
  "connections": {
    "spot_ticker": "connected",
    "futures_ticker": "connected",
    "depth": "connected",
    "klines": "connected",
    "trades": "connected"
  },
  "last_message_time": 1640995200,
  "message_count": 12345,
  "reconnections": 2
}
```

### Real-Time Ticker Data
**GET `/api/realtime/ticker/<symbol>`**
- **Description**: Get real-time ticker data for a specific symbol
- **Parameters**: 
  - `symbol`: Trading pair (e.g., BTCUSDT)
- **Response**: 
```json
{
  "symbol": "BTCUSDT",
  "data": {
    "price": 42500.50,
    "change": 2.5,
    "volume": 15678.90,
    "high": 43000.00,
    "low": 41800.00,
    "timestamp": 1640995200
  },
  "source": "websocket",
  "timestamp": 1640995200
}
```

### Real-Time Order Book
**GET `/api/realtime/orderbook/<symbol>`**
- **Description**: Get real-time order book depth data
- **Parameters**: 
  - `symbol`: Trading pair (e.g., BTCUSDT)
- **Response**: 
```json
{
  "symbol": "BTCUSDT",
  "bids": [[42500.50, 1.5], [42500.00, 2.3]],
  "asks": [[42501.00, 1.2], [42501.50, 0.8]],
  "last_update_id": 123456789,
  "timestamp": 1640995200,
  "source": "websocket"
}
```

## Social Media and News Feed Endpoints

### Social Media Sentiment
**GET `/api/social/sentiment/<symbol>`**
- **Description**: Get aggregated social media sentiment for a symbol
- **Parameters**: 
  - `symbol`: Cryptocurrency symbol (e.g., BTC, ETH)
  - `hours` (optional): Hours to look back (default: 6)
- **Response**: 
```json
{
  "symbol": "BTC",
  "sentiment_score": 0.75,
  "post_count": 156,
  "sources": ["reddit", "twitter", "news_cointelegraph"],
  "time_period_hours": 6,
  "posts": [
    {
      "source": "reddit",
      "content": "Bitcoin looking bullish...",
      "sentiment_score": 0.8,
      "author": "crypto_trader",
      "timestamp": 1640995100
    }
  ]
}
```

### Social Media Feeds
**GET `/api/social/feeds`**
- **Description**: Get recent social media posts and news
- **Parameters**: 
  - `limit` (optional): Number of posts to return (default: 20)
  - `source` (optional): Filter by source (reddit, twitter, etc.)
- **Response**: 
```json
{
  "posts": [
    {
      "title": "Bitcoin breaks new resistance level",
      "content": "...",
      "source": "news_cointelegraph",
      "symbols": ["BTC"],
      "sentiment_score": 0.8,
      "published_time": 1640995000
    }
  ],
  "total_count": 45,
  "sources_available": ["reddit", "twitter", "telegram", "news_cointelegraph"],
  "last_update": 1640995200
}
```

### Influencer Posts
**GET `/api/social/influencers`**
- **Description**: Get posts from known crypto influencers
- **Parameters**: 
  - `hours` (optional): Hours to look back (default: 12)
  - `min_credibility` (optional): Minimum credibility score (default: 0.7)
- **Response**: 
```json
{
  "influencer_posts": [],
  "time_period_hours": 12,
  "min_credibility_score": 0.7,
  "known_influencers": ["elonmusk", "michael_saylor", "cz_binance", "VitalikButerin"]
}
```

## High-Frequency Trading Endpoints

### HFT Status
**GET `/api/hft/status`**
- **Description**: Get high-frequency trading engine status
- **Response**: 
```json
{
  "enabled": true,
  "active_symbols": ["BTCUSDT", "ETHUSDT"],
  "active_positions": 3,
  "trades_today": 47,
  "profit_today": 12.45,
  "win_rate": 68.5,
  "avg_profit_per_trade": 0.26,
  "min_profit_threshold": 0.0001
}
```

### HFT Performance
**GET `/api/hft/performance`**
- **Description**: Get high-frequency trading performance metrics
- **Parameters**: 
  - `days` (optional): Days to look back (default: 7)
- **Response**: 
```json
{
  "period_days": 7,
  "total_trades": 324,
  "completed_trades": 298,
  "profitable_trades": 204,
  "win_rate": 68.46,
  "total_pnl": 156.78,
  "total_fees": 23.45,
  "net_profit": 133.33,
  "avg_profit_per_trade": 0.45,
  "trades_by_symbol": {
    "BTCUSDT": {"trades": 156, "profit": 89.12},
    "ETHUSDT": {"trades": 142, "profit": 44.21}
  }
}
```

### HFT Symbol Management
**POST `/api/hft/symbols`**
- **Description**: Add or remove symbols from high-frequency trading
- **Request Body**: 
```json
{
  "action": "add",
  "symbol": "BTCUSDT"
}
```
- **Response**: 
```json
{
  "status": "success",
  "action": "added",
  "symbol": "BTCUSDT",
  "message": "Symbol BTCUSDT added to high-frequency trading"
}
```

## Data Storage and Cache Endpoints

### Storage Statistics
**GET `/api/storage/stats`**
- **Description**: Get local data storage statistics
- **Response**: 
```json
{
  "storage_statistics": {
    "database_size_mb": 45.6,
    "cache_files": 12,
    "memory_cache_entries": 156,
    "ticker_data_records": 12345,
    "social_sentiment_records": 5678,
    "news_data_records": 890
  },
  "cache_enabled": true,
  "database_path": "/data/cache/market_data.db",
  "cache_directory": "/data/cache/json_cache"
}
```

### Storage Cleanup
**POST `/api/storage/cleanup`**
- **Description**: Clean up old data from storage
- **Request Body**: 
```json
{
  "days_to_keep": 30
}
```
- **Response**: 
```json
{
  "status": "success",
  "message": "Cleanup scheduled for data older than 30 days",
  "days_to_keep": 30
}
```

## Implementation Features

### High-Frequency Trading Engine
- **Micro-profit targeting**: Minimum 0.01% profit threshold
- **Real-time execution**: WebSocket-based order placement
- **Multiple strategies**: Scalping, spread trading, momentum trading
- **Risk management**: Automatic stop-loss and position sizing
- **Performance tracking**: Detailed metrics and trade history

### WebSocket Integration
- **Real-time data**: Ticker, depth, klines, trades
- **Auto-reconnection**: Intelligent reconnection with exponential backoff
- **Rate limiting**: Built-in rate limiting to respect API limits
- **Data caching**: Local storage for offline access
- **Performance optimization**: Concurrent processing and batching

### Social Media Integration
- **Multi-platform**: Reddit, Twitter, Telegram, news sites
- **Influencer tracking**: Known crypto personalities with credibility scores
- **Sentiment analysis**: Real-time sentiment scoring
- **Symbol detection**: Automatic cryptocurrency symbol extraction
- **News aggregation**: RSS feeds from major crypto news sources

### Local Data Storage
- **SQLite database**: Persistent storage for all data types
- **Compressed caching**: Gzip-compressed JSON files for bulk data
- **Memory caching**: Hot data in memory with TTL
- **Automatic cleanup**: Configurable data retention policies
- **Statistics tracking**: Detailed usage and performance metrics

## Usage Examples for New Features

### Real-Time Trading Dashboard
```javascript
// Monitor real-time prices
const ticker = await fetch('/api/realtime/ticker/BTCUSDT').then(r => r.json());

// Check HFT performance
const hftStatus = await fetch('/api/hft/status').then(r => r.json());

// Get social sentiment
const sentiment = await fetch('/api/social/sentiment/BTC?hours=6').then(r => r.json());
```

### High-Frequency Trading Control
```javascript
// Add symbol to HFT
await fetch('/api/hft/symbols', {
  method: 'POST',
  body: JSON.stringify({action: 'add', symbol: 'BTCUSDT'})
});

// Monitor performance
const performance = await fetch('/api/hft/performance?days=7').then(r => r.json());
```

### Social Media Monitoring
```javascript
// Get recent crypto news
const feeds = await fetch('/api/social/feeds?limit=10').then(r => r.json());

// Monitor influencer posts
const influencers = await fetch('/api/social/influencers?min_credibility=0.8')
  .then(r => r.json());
```

## Error Handling

All endpoints return proper HTTP status codes:
- `200 OK`: Successful request
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Agent not found
- `500 Internal Server Error`: Server error
- `501 Not Implemented`: Agent lacks required method
- `503 Service Unavailable`: Agent not available

Error responses include descriptive error messages and available alternatives when applicable.