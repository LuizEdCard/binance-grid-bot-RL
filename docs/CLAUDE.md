# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Development Commands:**
- `python src/main.py` - Start Flask API server (port 5000) - lightweight API interface
- `python src/bot_logic.py` - Start original grid trading bot with RL and sentiment analysis
- `python src/multi_agent_bot.py` - **Primary**: Start advanced multi-agent trading system (recommended)
- `./start_bot.sh` - Start original bot with environment setup
- `./start_multi_agent_bot.sh` - **Primary**: Start multi-agent system with comprehensive checks
- `./start_api.sh` - Start Flask API server with environment setup

**Dependencies:**
- `pip install -r requirements.txt` - Install basic dependencies 
- `pip install -r requirements_multi_agent.txt` - **Recommended**: Enhanced dependencies for multi-agent system
- **Critical**: TA-Lib C library must be installed manually first (see `docs/talib_installation_guide.md`)

**Testing:**
- `python tests/test_shadow_simulation.py` - Test shadow mode without API keys
- `python tests/quick_shadow_test.py` - Quick shadow mode validation
- Various test files in `tests/` directory - no formal test framework, run directly with python
- **No pytest or unittest framework configured**

**Code Quality:**
- `flake8` for linting (when available)
- **No automated code quality checks configured - add manually when needed**

## Architecture

This is a **cryptocurrency grid trading bot** with reinforcement learning and sentiment analysis. Two main architectures:

### 1. Multi-Agent System (Recommended - `src/multi_agent_bot.py`)
**Specialized agents for distributed processing:**
- **CoordinatorAgent** (`src/agents/coordinator_agent.py`) - Orchestrates system, health monitoring, auto-recovery
- **DataAgent** (`src/agents/data_agent.py`) - Centralized data collection with intelligent caching (70-90% API reduction)
- **SentimentAgent** (`src/agents/sentiment_agent.py`) - Distributed sentiment analysis from Reddit/social media
- **RiskAgent** (`src/agents/risk_agent.py`) - Proactive risk monitoring and portfolio management
- **AIAgent** (`src/agents/ai_agent.py`) - LLM integration for trading decisions and analysis

**Performance improvements over original:**
- 70-80% reduction in API calls via intelligent caching
- 50% reduction in CPU/memory usage
- 70% reduction in operation latency
- Auto-recovery and health monitoring

### 2. Original Monolithic System (`src/bot_logic.py`)
**Single-process implementation with:**
- **Grid Trading** (`src/core/grid_logic.py`) - Main trading strategy with dynamic spacing
- **Reinforcement Learning** (`src/rl/`) - PPO/SAC agents for strategy optimization
- **Sentiment Analysis** (`src/utils/sentiment_analyzer.py`) - ONNX-based sentiment from social media
- **Risk Management** (`src/core/risk_management.py`) - Dynamic risk adjustment

### Core Components (Shared)
- **Pair Selection** (`src/core/pair_selector.py`) - Volume/volatility/sentiment-based filtering
- **API Clients** (`src/utils/api_client.py`, `src/utils/async_client.py`) - Binance integration
- **Intelligent Cache** (`src/utils/intelligent_cache.py`) - Predictive caching with compression
- **Configuration** (`src/config/config.yaml`) - Unified YAML configuration

### Configuration Architecture
**Main config**: `src/config/config.yaml`
- Supports both Spot and Futures markets
- Grid parameters (levels, spacing, leverage)
- RL agent settings (PPO/SAC, features, training frequency)
- Sentiment analysis configuration (Reddit, smoothing, risk adjustment)
- Risk management (stop loss, drawdown limits, position sizing)
- AI agent integration settings

**Environment**: `.env` file (create manually)
- `BINANCE_API_KEY` / `BINANCE_API_SECRET` - Trading API access
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` - Alert notifications
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` - Sentiment data source

### Data Flow
1. **Market Data**: DataAgent fetches/caches ticker data, order books, historical data
2. **Sentiment**: SentimentAgent analyzes Reddit posts → sentiment score (-1 to 1)
3. **Pair Selection**: Filters trading pairs by volume, volatility, sentiment thresholds
4. **Grid Trading**: Places buy/sell orders with RL-optimized spacing and levels
5. **Risk Management**: Monitors positions, adjusts leverage based on sentiment/drawdown
6. **AI Integration**: LLM provides market analysis and trading recommendations

### Key Dependencies
- **TA-Lib** (C library) - Technical indicators (ATR, ADX, candlestick patterns)
- **TensorFlow 2.11.0** - Reinforcement learning models
- **ONNX Runtime** - Local sentiment analysis (`llmware/slim-sentiment-onnx`)
- **python-binance** - Exchange API integration
- **PRAW** - Reddit data collection
- **aiohttp** - Asynchronous API client (multi-agent system)

### Operation Modes
- **Production**: Real trading with API keys
- **Shadow**: Real-time simulation without actual trades
- **Test**: Local simulation with mock data