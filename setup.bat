@echo off
REM ClinIQ Quick Start Script for Windows

setlocal enabledelayedexpansion

echo.
echo 🚀 ClinIQ Startup Script
echo =======================
echo.

REM Check if .env exists
if not exist .env (
    echo 📋 Creating .env from template...
    copy .env.example .env
    echo ✓ .env created
) else (
    echo ✓ .env already exists
)

REM Start Docker services
echo.
echo 🐳 Starting Docker services (PostgreSQL ^& Redis)...
docker-compose up -d
timeout /t 5 /nobreak

REM Check if services are running
docker ps | findstr "cliniq_postgres" >nul
if errorlevel 1 (
    echo ✗ PostgreSQL failed to start
    exit /b 1
) else (
    echo ✓ PostgreSQL is running
)

docker ps | findstr "cliniq_redis" >nul
if errorlevel 1 (
    echo ✗ Redis failed to start
    exit /b 1
) else (
    echo ✓ Redis is running
)

REM Backend setup
echo.
echo 🔧 Setting up backend...
cd backend

if not exist venv (
    echo Creating Python virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -q -r requirements.txt

echo Initializing database...
python -c "from database import init_db; init_db()"

echo ✓ Backend ready

cd ..

REM Frontend setup
echo.
echo ⚛️  Setting up frontend...
cd frontend

if not exist node_modules (
    echo Installing Node dependencies...
    call npm install -q
) else (
    echo Node dependencies already installed
)

echo ✓ Frontend ready

cd ..

echo.
echo ✅ Setup complete!
echo.
echo 🎯 Next steps:
echo 1. Start backend:  cd backend ^& venv\Scripts\activate.bat ^& python main.py
echo 2. Start frontend: cd frontend ^& npm run dev
echo.
echo 📖 Documentation: http://localhost:5173
echo 📊 API Docs:      http://localhost:8000/docs
echo.

pause
