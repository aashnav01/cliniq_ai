#!/bin/bash
# ClinIQ Quick Start Script

set -e

echo "🚀 ClinIQ Startup Script"
echo "======================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📋 Creating .env from template..."
    cp .env.example .env
    echo "✓ .env created"
else
    echo "✓ .env already exists"
fi

# Start Docker services
echo ""
echo "🐳 Starting Docker services (PostgreSQL & Redis)..."
docker-compose up -d
sleep 5

# Check if services are running
if docker ps | grep -q cliniq_postgres; then
    echo "✓ PostgreSQL is running"
else
    echo "✗ PostgreSQL failed to start"
    exit 1
fi

if docker ps | grep -q cliniq_redis; then
    echo "✓ Redis is running"
else
    echo "✗ Redis failed to start"
    exit 1
fi

# Backend setup
echo ""
echo "🔧 Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/Scripts/activate 2>/dev/null || source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Initializing database..."
python -c "from database import init_db; init_db()"

echo "✓ Backend ready"

cd ..

# Frontend setup
echo ""
echo "⚛️  Setting up frontend..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    npm install -q
else
    echo "Node dependencies already installed"
fi

echo "✓ Frontend ready"

cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Start backend:  cd backend && source venv/bin/activate && python main.py"
echo "2. Start frontend: cd frontend && npm run dev"
echo ""
echo "📖 Documentation: http://localhost:5173"
echo "📊 API Docs:      http://localhost:8000/docs"
echo ""
