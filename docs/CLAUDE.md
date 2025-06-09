# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Development Commands:**
- `python src/main.py` - Start Flask API backend server (port 5000)
- `python src/bot_logic.py` - Start the original grid trading bot with RL and sentiment analysis
- `python src/multi_agent_bot.py` - **NEW: Start the advanced multi-agent trading system**
- `bash start_bot.sh` - Automated bot startup script (original system)
- `bash start_multi_agent_bot.sh` - **NEW: Start multi-agent system with checks and monitoring**
- `pip install -r requirements.txt` - Install Python dependencies (original)
- `pip install -r requirements_multi_agent.txt` - **NEW: Install enhanced dependencies for multi-agent system**

**TA-Lib Requirement:**
- TA-Lib C library must be installed manually before Python dependencies (see `docs/talib_installation_guide.md`)
- Required for technical indicators (ATR, ADX) and candlestick pattern recognition

**Testing and Quality:**
- Use `flake8` for code quality checks (multiple reports available: flake8_report.txt, etc.)
- Code includes test-like patterns but no formal test framework configured
- When making changes, run flake8 to check code quality

## Architecture

**Core Trading System:**
- **Grid Trading Bot** (`src/core/grid_logic.py`) - Main trading strategy implementation
- **Reinforcement Learning** (`src/rl/`) - PPO/SAC agents for dynamic strategy optimization
- **Sentiment Analysis** (`src/utils/sentiment_analyzer.py`, `src/utils/social_listener.py`) - Reddit sentiment integration using ONNX models
- **Risk Management** (`src/core/risk_management.py`) - Dynamic risk adjustment based on sentiment and market conditions

**API Structure:**
- **Flask Backend** (`src/main.py`) - REST API for bot control and market data
- **Model Routes** (`src/routes/model_api.py`) - ML model endpoints
- **User Routes** (`src/routes/user.py`) - User management

**Configuration:**
- `src/config/config.yaml` - Main bot configuration (grid parameters, RL settings, sentiment analysis, supports both spot and futures markets)
- `.env` file expected for API keys (Binance, Telegram, Reddit) - must be created manually
- Environment setup: Python 3.9+, TA-Lib C library prerequisite

**Key Components:**
- **Pair Selection** (`src/core/pair_selector.py`) - Intelligent pair filtering using volume, volatility, sentiment
- **Alerting** (`src/utils/alerter.py`) - Telegram notifications
- **Multi-pair Execution** - Concurrent trading across multiple cryptocurrency pairs
- **Operation Mode** - Production (real trading)

**Data Flow:**
1. Sentiment analysis fetches Reddit data → ONNX model analysis → sentiment score
2. Pair selector uses sentiment + technical indicators to choose trading pairs  
3. Grid logic creates buy/sell orders with RL-optimized spacing
4. Risk management monitors positions and adjusts leverage based on sentiment
5. Flask API provides external control interface

**Dependencies:**
- Binance API for trading operations (spot and futures)
- TensorFlow 2.11.0 for RL models
- ONNX runtime for sentiment analysis (`llmware/slim-sentiment-onnx`)
- PRAW for Reddit data collection
- TA-Lib for technical indicators (manual C library installation required)
- Flask/Flask-CORS for API server
- Stable-baselines3 for RL algorithms (PPO/SAC)

**Development Notes:**
- Code is primarily in Portuguese with English comments
- **Three main entry points**: 
  - `bot_logic.py` - Original trading bot
  - `multi_agent_bot.py` - **NEW: Advanced multi-agent system**
  - `main.py` - API server
- Supports concurrent multi-pair trading via threading (original) and multiprocessing (multi-agent)
- Mock mode available for testing without API credentials
- **NEW: Multi-agent architecture** with specialized agents for data, sentiment, risk, and coordination
- **NEW: Intelligent caching** with predictive prefetching reduces API calls by 70-90%
- **NEW: Asynchronous processing** for improved performance and lower latency