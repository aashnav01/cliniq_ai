#!/bin/bash
# ClinIQ Development Server Startup

echo "🚀 Starting ClinIQ Services..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to run command in background
run_service() {
    local name=$1
    local cmd=$2
    local dir=$3
    
    echo -e "${YELLOW}Starting $name...${NC}"
    (cd "$dir" && eval "$cmd") &
    echo -e "${GREEN}✓ $name started (PID: $!)${NC}"
}

# Start Backend
run_service "Backend" "source venv/bin/activate && python main.py" "backend"

sleep 2

# Start Frontend
run_service "Frontend" "npm run dev" "frontend"

echo ""
echo -e "${GREEN}✅ All services started!${NC}"
echo ""
echo "📖 Frontend:  http://localhost:5173"
echo "📊 API Docs:  http://localhost:8000/docs"
echo "📡 API Base:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for interrupt
wait
