#!/bin/bash

# Startup script for rememberSOMthing application

echo "🚀 Starting rememberSOMthing Study Assistant..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "📝 IMPORTANT: Please edit .env and add your OPENAI_API_KEY"
    echo "   Open .env in a text editor and replace 'your_openai_api_key_here' with your actual API key"
    echo ""
    echo "Press Enter when ready to continue..."
    read
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "✨ Setup complete!"
echo ""
echo "🌐 Starting backend server..."
echo "   Backend will run on: http://localhost:8000"
echo "   Frontend will be available at: http://localhost:8000"
echo ""
echo "📖 To use the chatbot:"
echo "   1. Upload a PDF in the Upload tab"
echo "   2. Go to 'Study Chat' tab"
echo "   3. Select one or more documents"
echo "   4. Click 'Start Chat'"
echo "   5. Ask questions (type or use 🎤 voice input)"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start the server
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
