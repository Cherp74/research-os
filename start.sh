#!/bin/bash
# Research OS - Quick Start Script

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Research OS v1.0                        ║"
echo "║          Multi-Agent Research System                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Ollama is running
echo -e "${BLUE}Checking Ollama...${NC}"
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${YELLOW}⚠ Ollama is not running. Starting Ollama...${NC}"
    ollama serve &
    sleep 3
fi

# Check for required models
echo -e "${BLUE}Checking required models...${NC}"
if ! ollama list | grep -q "qwen2.5"; then
    echo -e "${YELLOW}⚠ qwen2.5:7b not found. Pulling...${NC}"
    ollama pull qwen2.5:7b
fi

if ! ollama list | grep -q "nomic-embed-text"; then
    echo -e "${YELLOW}⚠ nomic-embed-text not found. Pulling...${NC}"
    ollama pull nomic-embed-text
fi

echo -e "${GREEN}✓ Ollama ready${NC}"
echo ""

# Setup backend
echo -e "${BLUE}Setting up backend...${NC}"
cd backend

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if [ ! -f ".venv/.installed" ]; then
    echo "Installing dependencies..."
    pip install -q -r requirements.txt
    touch .venv/.installed
fi

echo -e "${GREEN}✓ Backend ready${NC}"
echo ""

# Setup frontend
echo -e "${BLUE}Setting up frontend...${NC}"
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

echo -e "${GREEN}✓ Frontend ready${NC}"
echo ""

# Start services
echo -e "${GREEN}Starting Research OS...${NC}"
echo ""

cd ../backend
source .venv/bin/activate

echo -e "${BLUE}Starting backend on http://localhost:8000${NC}"
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

cd ../frontend
echo -e "${BLUE}Starting frontend on http://localhost:5173${NC}"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Research OS is running!                                   ║"
echo "║                                                            ║"
echo "║  Frontend: http://localhost:5173                          ║"
echo "║  Backend:  http://localhost:8000                          ║"
echo "║  API Docs: http://localhost:8000/docs                     ║"
echo "║                                                            ║"
echo "║  Press Ctrl+C to stop                                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Wait for interrupt
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
