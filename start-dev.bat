@echo off
REM ClinIQ Development Server Startup for Windows

echo.
echo 🚀 Starting ClinIQ Services...
echo.

REM Start Backend in new window
echo Starting Backend...
cd backend
start "ClinIQ Backend" cmd /k "venv\Scripts\activate.bat && python main.py"
cd ..

timeout /t 2 /nobreak

REM Start Frontend in new window
echo Starting Frontend...
cd frontend
start "ClinIQ Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ✅ Services are starting in new windows!
echo.
echo 📖 Frontend:  http://localhost:5173
echo 📊 API Docs:  http://localhost:8000/docs
echo 📡 API Base:  http://localhost:8000
echo.
echo Close the windows to stop the services
echo.

pause
