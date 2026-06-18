#!/usr/bin/env bash

# ==============================================================================
# DB MoveOptimizer Docker Runner
# Starts frontend, backend, and database via Docker Compose.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "🚉 DB MoveOptimizer — Starting Docker Environment"
echo "======================================================================"

echo "🔍 Checking Docker..."

if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed or not available in PATH."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose is not available."
    exit 1
fi

echo "✅ Docker and Docker Compose are available."

if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found."
    echo "ℹ️  Create one from .env.example if your services need environment variables."
fi

cleanup() {
    echo ""
    echo "🔌 Stopping Docker services..."
    docker compose down --remove-orphans
    echo "✅ Docker services stopped."
}

trap cleanup EXIT SIGINT SIGTERM

echo "🚀 Building and starting services..."
echo "📡 Backend:  http://localhost:8000"
echo "🎨 Frontend: http://localhost:5173"
echo "🗄️  Postgres: localhost:5432"
echo "======================================================================"
echo "ℹ️  Press Ctrl+C to stop all services."
echo "======================================================================"

docker compose up --build