#!/bin/bash

# Test Flask API startup only
echo "🧪 Testing Flask API startup..."

# Kill any existing API processes
pkill -f "python.*src/main.py" 2>/dev/null || true
sleep 2

# Start Flask API
echo "🚀 Starting Flask API..."
source venv/bin/activate
export PYTHONPATH="src:$PYTHONPATH"

python3 src/main.py > logs/flask_test.log 2>&1 &
API_PID=$!

# Wait for startup
echo "⏳ Waiting for Flask API to start..."
sleep 8

# Test if running
if kill -0 $API_PID 2>/dev/null; then
    echo "✅ Flask API started successfully (PID: $API_PID)"
    echo "🌐 Testing endpoints..."
    
    # Test basic endpoints
    echo "📊 Testing /api/status..."
    curl -s http://localhost:5000/api/status | head -c 200
    echo ""
    
    echo "💰 Testing /api/balance..."
    curl -s http://localhost:5000/api/balance | head -c 200
    echo ""
    
    echo "📈 Testing new live data endpoint..."
    curl -s http://localhost:5000/api/live/system/status | head -c 200
    echo ""
    
    # Stop API
    echo "🛑 Stopping Flask API..."
    kill $API_PID
    
    echo "✅ Test completed successfully!"
else
    echo "❌ Flask API failed to start"
    echo "📜 Log output:"
    cat logs/flask_test.log
fi