@echo off

REM Bongao Bakery Ordering System Backend Startup Script for Windows

echo 🚀 Starting Bongao Bakery Ordering System Backend...

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📚 Installing dependencies...
pip install --no-cache-dir -r requirements.txt

REM Create database tables
echo 🗄️ Setting up database...
python -c "from app.config.database import init_db, seed_data; init_db(); seed_data()"
echo ✅ Database tables created successfully!

REM Start the application
echo 🌟 Starting the FastAPI application...
echo 📖 API Documentation will be available at: http://localhost:8000/docs
echo 🔗 Application will be running at: http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --env-file .env

pause
