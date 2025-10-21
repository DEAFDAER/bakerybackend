#!/bin/bash

# Bongao Bakery Ordering System Backend Startup Script

echo "🚀 Starting Bongao Bakery Ordering System Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Set environment variables if .env exists
if [ -f ".env" ]; then
    echo "⚙️ Loading environment variables..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Create database tables
echo "🗄️ Setting up database..."
python -c "from app.config.database import create_tables; create_tables()"
echo "✅ Database tables created successfully!"

# Start the application
echo "🌟 Starting the FastAPI application..."
echo "📖 API Documentation will be available at: http://localhost:8000/docs"
echo "🔗 Application will be running at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
