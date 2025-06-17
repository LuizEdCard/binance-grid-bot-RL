#!/bin/bash

# Complete Trading System Startup Script
# This script starts both the Flask API and Multi-Agent Bot together

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

# PID storage
API_PID=""
BOT_PID=""

echo -e "${CYAN}🚀 Complete Trading System Startup${NC}"
echo "====================================="
echo ""

# Function to print colored messages
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_api() {
    echo -e "${BLUE}[API]${NC} $1"
}

print_bot() {
    echo -e "${PURPLE}[BOT]${NC} $1"
}

# Check if Python is available
check_python() {
    print_status "Checking Python installation..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python not found. Please install Python 3.9 or higher."
        exit 1
    fi
    
    # Check Python version
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
        print_error "Python 3.9+ required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    print_status "Python $PYTHON_VERSION found"
}

# Check if virtual environment exists
check_venv() {
    print_status "Checking virtual environment..."
    
    if [ ! -d "venv" ]; then
        print_warning "Virtual environment not found. Creating one..."
        $PYTHON_CMD -m venv venv
        print_status "Virtual environment created"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    print_status "Virtual environment activated"
}

# Install/update dependencies
install_dependencies() {
    print_status "Installing/updating dependencies..."
    
    # Prioritize the cleaned multi-agent requirements
    if [ -f "requirements_multi_agent.txt" ]; then
        pip install -r requirements_multi_agent.txt
        print_status "Dependencies installed from requirements_multi_agent.txt (optimized)"
    elif [ -f "requirements.txt" ]; then
        print_warning "Using fallback requirements.txt (may include unnecessary dependencies)"
        pip install -r requirements.txt
        print_status "Dependencies installed from requirements.txt"
    else
        print_warning "No requirements file found. Installing basic dependencies..."
        pip install numpy pandas pyyaml python-dotenv aiohttp flask
    fi
}

# Check configuration
check_config() {
    print_status "Checking configuration..."
    
    CONFIG_FILE="$SRC_DIR/config/config.yaml"
    ENV_FILE="$SCRIPT_DIR/secrets/.env"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    if [ ! -f "$ENV_FILE" ]; then
        print_warning "Environment file not found: $ENV_FILE"
        mkdir -p "$SCRIPT_DIR/secrets"
        cat > "$ENV_FILE" << EOF
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
        print_warning "Template secrets/.env created. Configure your API keys before production use."
    fi
    
    print_status "Configuration check completed"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p data
    mkdir -p models
    mkdir -p data/grid_states
    
    print_status "Directories created"
}

# Check if ports are available
check_ports() {
    print_status "Checking port availability..."
    
    # Check Flask API port (5000)
    if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port 5000 is already in use. Flask API may already be running."
        print_warning "Use 'pkill -f src/main.py' to stop existing API if needed."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    print_status "Port check completed"
}

# Function to handle cleanup on exit
cleanup() {
    echo ""
    print_status "Shutting down complete system..."
    
    # Stop Flask API
    if [ ! -z "$API_PID" ] && kill -0 $API_PID 2>/dev/null; then
        print_api "Stopping Flask API (PID: $API_PID)..."
        kill -TERM $API_PID
        wait $API_PID 2>/dev/null || true
        print_api "Flask API stopped"
    fi
    
    # Stop Multi-Agent Bot
    if [ ! -z "$BOT_PID" ] && kill -0 $BOT_PID 2>/dev/null; then
        print_bot "Stopping Multi-Agent Bot (PID: $BOT_PID)..."
        kill -TERM $BOT_PID
        wait $BOT_PID 2>/dev/null || true
        print_bot "Multi-Agent Bot stopped"
    fi
    
    print_status "System shutdown completed"
}

# Set up signal handlers
trap cleanup EXIT INT TERM

# Start Flask API
start_flask_api() {
    print_api "Starting Flask API..."
    
    cd "$SCRIPT_DIR"
    export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
    
    # Start Flask API in background
    $PYTHON_CMD src/main.py > logs/flask_api.log 2>&1 &
    API_PID=$!
    
    # Wait a moment for startup
    sleep 3
    
    # Check if API started successfully
    if kill -0 $API_PID 2>/dev/null; then
        print_api "Flask API started successfully (PID: $API_PID)"
        print_api "API available at: http://localhost:5000"
        print_api "Frontend interface: http://localhost:5000"
    else
        print_error "Failed to start Flask API"
        print_error "Check logs/flask_api.log for details"
        exit 1
    fi
}

# Start Multi-Agent Bot
start_multi_agent_bot() {
    print_bot "Starting Multi-Agent Bot..."
    
    cd "$SRC_DIR"
    
    # Start Multi-Agent Bot in background
    $PYTHON_CMD multi_agent_bot.py > ../logs/multi_agent_bot.log 2>&1 &
    BOT_PID=$!
    
    # Wait a moment for startup
    sleep 3
    
    # Check if bot started successfully
    if kill -0 $BOT_PID 2>/dev/null; then
        print_bot "Multi-Agent Bot started successfully (PID: $BOT_PID)"
        print_bot "Bot running in background with AI integration"
    else
        print_error "Failed to start Multi-Agent Bot"
        print_error "Check logs/multi_agent_bot.log for details"
        exit 1
    fi
}

# Monitor system status
monitor_system() {
    print_status "System monitoring started..."
    print_status "Press Ctrl+C to stop the complete system"
    echo ""
    echo -e "${CYAN}System Status:${NC}"
    echo -e "  ${BLUE}Flask API:${NC} http://localhost:5000 (PID: $API_PID)"
    echo -e "  ${PURPLE}Multi-Agent Bot:${NC} Running in background (PID: $BOT_PID)"
    echo ""
    echo -e "${YELLOW}Logs:${NC}"
    echo -e "  Flask API: tail -f logs/flask_api.log"
    echo -e "  Multi-Agent Bot: tail -f logs/multi_agent_bot.log"
    echo -e "  Combined: tail -f logs/*.log"
    echo ""
    
    # Monitor both processes
    while true; do
        # Check API health
        if ! kill -0 $API_PID 2>/dev/null; then
            print_error "Flask API process died unexpectedly"
            break
        fi
        
        # Check Bot health
        if ! kill -0 $BOT_PID 2>/dev/null; then
            print_error "Multi-Agent Bot process died unexpectedly"
            break
        fi
        
        sleep 5
    done
}

# Main execution
main() {
    echo -e "${BLUE}Starting system checks...${NC}"
    echo ""
    
    check_python
    check_venv
    install_dependencies
    check_config
    create_directories
    check_ports
    
    echo ""
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo ""
    
    # Parse command line arguments
    SKIP_API=false
    SKIP_BOT=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --api-only)
                SKIP_BOT=true
                shift
                ;;
            --bot-only)
                SKIP_API=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --api-only    Start only Flask API"
                echo "  --bot-only    Start only Multi-Agent Bot"
                echo "  --help        Show this help message"
                echo ""
                echo "Default: Start both Flask API and Multi-Agent Bot"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    echo -e "${CYAN}🚀 Starting Complete Trading System...${NC}"
    echo ""
    
    # Start components
    if [ "$SKIP_API" = false ]; then
        start_flask_api
    fi
    
    if [ "$SKIP_BOT" = false ]; then
        start_multi_agent_bot
    fi
    
    echo ""
    echo -e "${GREEN}🎉 Complete system started successfully!${NC}"
    echo ""
    
    # Monitor system
    monitor_system
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi