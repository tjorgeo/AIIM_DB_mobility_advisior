#!/usr/bin/env bash

# ==============================================================================
# DB MoveOptimizer E2E Sandbox Runner
# Automates VirtualEnv setup, dependency installations, and concurrent startups.
# ==============================================================================

# Exit immediately if a command exits with a non-zero status.
set -e

# Define paths relative to the script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "======================================================================"
echo "🚉 DB MoveOptimizer — Starting Backbone Environment Setup & Launch"
echo "======================================================================"

# 1. Environment Checks
echo "🔍 Checking runtime environments..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed. Please install Python 3.10+ and retry."
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Error: node is not installed. Please install Node.js (v18+) and retry."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed. Please install npm and retry."
    exit 1
fi

echo "✅ Environment checks passed: Python, Node, and npm are available."

# 2. Python Virtual Environment Setup & Backend Installation
echo "🐍 Setting up Python Virtual Environment..."
cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment 'venv'..."
    python3 -m venv venv
fi

echo "Activating virtual environment & installing Python dependencies..."
source venv/bin/activate
pip3 install -q --upgrade pip
pip3 install -q -r requirements.txt
echo "✅ Backend dependencies successfully loaded."

# 3. Node Package Installation for Frontend
echo "📦 Installing Node dependencies for Vite/React frontend..."
cd "$FRONTEND_DIR"
npm install --no-audit --no-fund --loglevel=error
echo "✅ Frontend dependencies successfully loaded."

# 4. Starting Services concurrently with signal trapping
echo "🚀 Booting services..."

# Define background process management
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "🔌 Shutting down services cleanly..."
    if [ -n "$BACKEND_PID" ]; then
        echo "Terminating Backend (PID: $BACKEND_PID)..."
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        echo "Terminating Frontend (PID: $FRONTEND_PID)..."
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo "✅ Services terminated. Have a safe journey!"
}

# Trap Ctrl+C (SIGINT) and exit signals to trigger cleanup
trap cleanup EXIT SIGINT SIGTERM

# Start Backend
echo "📡 Starting FastAPI Backend on http://localhost:8000..."
cd "$BACKEND_DIR"
source venv/bin/activate
python3 main.py > backend.log 2>&1 &
BACKEND_PID=$!

# Start Frontend
echo "🎨 Starting React/Vite Frontend on http://localhost:3000..."
cd "$FRONTEND_DIR"
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait a couple of seconds to ensure servers did not crash immediately on boot
sleep 3

# Check if processes are still running
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "❌ Error: FastAPI Backend failed to start. Check backend/backend.log for errors."
    exit 1
fi

if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "❌ Error: React Frontend failed to start. Check frontend/frontend.log for errors."
    exit 1
fi

echo "======================================================================"
echo "🚀 DB MoveOptimizer Backbone Running!"
echo "📡 Backend API Gateway: http://localhost:8000"
echo "🎨 Visual UI Dashboard: http://localhost:3000"
echo "👉 Logs are streamed to backend/backend.log and frontend/frontend.log"
echo "ℹ️  Press Ctrl+C to terminate both servers and stop the pilot."
echo "======================================================================"

# Keep script running to maintain the background trap
wait
