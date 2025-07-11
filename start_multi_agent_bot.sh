#!/bin/bash

# Multi-Agent Trading Bot Startup Script
# This script starts the advanced multi-agent trading system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

echo -e "${BLUE}🤖 Multi-Agent Trading Bot Startup${NC}"
echo "======================================"
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
        pip install numpy pandas pyyaml python-dotenv aiohttp
    fi
}

# Check TA-Lib installation
check_talib() {
    print_status "Checking TA-Lib installation..."
    
    if $PYTHON_CMD -c "import talib" 2>/dev/null; then
        print_status "TA-Lib is installed"
    else
        print_warning "TA-Lib not found. Some features may be limited."
        print_warning "See talib_installation_guide.md for installation instructions"
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
        print_warning "Please create secrets/.env file with your API credentials"
        echo ""
        echo "Required environment variables:"
        echo "  BINANCE_API_KEY=your_api_key"
        echo "  BINANCE_API_SECRET=your_api_secret"
        echo "  TELEGRAM_BOT_TOKEN=your_telegram_token (optional)"
        echo "  TELEGRAM_CHAT_ID=your_chat_id (optional)"
        echo "  REDDIT_CLIENT_ID=your_reddit_client_id (optional)"
        echo "  REDDIT_CLIENT_SECRET=your_reddit_client_secret (optional)"
        echo "  REDDIT_USER_AGENT=your_user_agent (optional)"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    print_status "Configuration check completed"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p data
    mkdir -p models
    
    print_status "Directories created"
}

# Check system resources
check_resources() {
    print_status "Checking system resources..."
    
    # Check available memory
    if command -v free &> /dev/null; then
        AVAILABLE_MEM=$(free -m | awk 'NR==2{printf "%.0f", $7}')
        if [ "$AVAILABLE_MEM" -lt 1024 ]; then
            print_warning "Low available memory: ${AVAILABLE_MEM}MB. Recommended: 1GB+"
        fi
    fi
    
    # Check disk space
    if command -v df &> /dev/null; then
        AVAILABLE_DISK=$(df . | awk 'NR==2{printf "%.0f", $4/1024}')
        if [ "$AVAILABLE_DISK" -lt 1024 ]; then
            print_warning "Low disk space: ${AVAILABLE_DISK}MB. Recommended: 1GB+"
        fi
    fi
    
    print_status "Resource check completed"
}

# Function to handle cleanup on exit
cleanup() {
    echo ""
    print_status "Cleaning up..."
    
    # Kill any background processes
    if [ ! -z "$BOT_PID" ]; then
        if kill -0 $BOT_PID 2>/dev/null; then
            print_status "Stopping bot process..."
            kill -TERM $BOT_PID
            wait $BOT_PID 2>/dev/null || true
        fi
    fi
    
    print_status "Cleanup completed"
}

# Set up signal handlers
trap cleanup EXIT INT TERM

# Main execution
main() {
    echo -e "${BLUE}Starting system checks...${NC}"
    echo ""
    
    check_python
    check_venv
    install_dependencies
    check_talib
    check_config
    create_directories
    check_resources
    
    echo ""
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo ""
    
    # Parse command line arguments
    MODE="normal"
    EXTRA_ARGS=""
    START_API=true
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --test)
                MODE="test"
                shift
                ;;
            --shadow)
                MODE="shadow"
                shift
                ;;
            --production)
                MODE="production"
                shift
                ;;
            --debug)
                EXTRA_ARGS="$EXTRA_ARGS --debug"
                shift
                ;;
            --no-api)
                START_API=false
                shift
                ;;
            --bot-only)
                START_API=false
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --test        Run in test mode"
                echo "  --shadow      Run in shadow mode (default)"
                echo "  --production  Run in production mode"
                echo "  --debug       Enable debug logging"
                echo "  --no-api      Don't start Flask API (bot only)"
                echo "  --bot-only    Same as --no-api"
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
    
    if [ "$START_API" = true ]; then
        print_status "Starting Complete Trading System (Flask API + Multi-Agent Bot) in $MODE mode..."
    else
        print_status "Starting Multi-Agent Bot only in $MODE mode..."
    fi
    echo ""
    
    # Variables for process management
    API_PID=""
    BOT_PID=""
    
    # Function to handle cleanup
    cleanup_processes() {
        echo ""
        print_status "Shutting down system..."
        
        if [ ! -z "$API_PID" ] && kill -0 $API_PID 2>/dev/null; then
            print_status "Stopping Flask API..."
            kill -TERM $API_PID
            wait $API_PID 2>/dev/null || true
        fi
        
        if [ ! -z "$BOT_PID" ] && kill -0 $BOT_PID 2>/dev/null; then
            print_status "Stopping Multi-Agent Bot..."
            kill -TERM $BOT_PID
            wait $BOT_PID 2>/dev/null || true
        fi
        
        print_status "System shutdown completed"
    }
    
    # Set up signal handlers
    trap cleanup_processes EXIT INT TERM
    
    # Start Flask API if requested
    if [ "$START_API" = true ] && [ "$MODE" != "test" ]; then
        print_status "Starting Flask API..."
        cd "$SCRIPT_DIR"
        export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
        
        # Start Flask API in background
        source venv/bin/activate 2>/dev/null || true
        $PYTHON_CMD src/main.py > logs/flask_api.log 2>&1 &
        API_PID=$!
        
        # Wait for API to start
        sleep 3
        
        # Check if API started successfully
        if kill -0 $API_PID 2>/dev/null; then
            print_status "Flask API started successfully (PID: $API_PID)"
            print_status "API available at: http://localhost:5000"
        else
            print_error "Failed to start Flask API"
            print_error "Check logs/flask_api.log for details"
            exit 1
        fi
    fi
    
    # Start the bot
    cd "$SRC_DIR"
    
    if [ "$MODE" = "test" ]; then
        print_status "Running test suite..."
        $PYTHON_CMD -m pytest tests/ -v
    else
        print_status "Starting multi-agent bot..."
        
        if [ "$START_API" = true ]; then
            print_status "System running: Flask API (http://localhost:5000) + Multi-Agent Bot"
        fi
        
        print_status "Press Ctrl+C to stop"
        echo ""
        
        # Start the bot and capture PID
        source venv/bin/activate 2>/dev/null || true
        $PYTHON_CMD multi_agent_bot.py $EXTRA_ARGS &
        BOT_PID=$!
        
        # Monitor both processes if API is running
        if [ "$START_API" = true ]; then
            while true; do
                # Check if both processes are still running
                if ! kill -0 $API_PID 2>/dev/null; then
                    print_error "Flask API process died unexpectedly"
                    break
                fi
                
                if ! kill -0 $BOT_PID 2>/dev/null; then
                    print_error "Multi-Agent Bot process died unexpectedly"
                    break
                fi
                
                sleep 5
            done
        else
            # Just wait for the bot if no API
            wait $BOT_PID
        fi
    fi
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi