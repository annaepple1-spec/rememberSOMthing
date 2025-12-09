# Quick Start Guide

## Prerequisites
- Python 3.8 or higher
- OpenAI API key (for GPT-4o chatbot)

## Setup & Run (Fastest Way)

### Option 1: Using Startup Script (Recommended)
```bash
./start.sh
```

This script will:
1. Create .env file if needed
2. Set up Python virtual environment
3. Install all dependencies
4. Start the server automatically

### Option 2: Manual Setup
```bash
# 1. Create .env file
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
python3 -m uvicorn backend.main:app --reload --port 8000
```

## Access the Application

Once the server is running:
- **Frontend**: http://localhost:8000
- **Backend API**: http://localhost:8000/docs (Swagger UI)
- **Health Check**: http://localhost:8000/health

## Using the Study Assistant Chatbot

### Basic Usage
1. **Upload PDFs**
   - Click "Upload" tab
   - Choose a PDF file
   - Wait for processing (flashcards generated automatically)

2. **Start Chat**
   - Go to "💬 Study Chat" tab
   - Check one or more documents
   - Click "Start Chat"

3. **Ask Questions**
   - Type your question OR
   - Click 🎤 to use voice input
   - Get answers with citations!

### Multi-Document Chat
1. Upload 2+ PDFs
2. Check multiple documents in the list
3. Click "Start Chat (X documents)"
4. Ask questions that span all documents
5. See citations from multiple sources

### Voice Input
1. Click the 🎤 microphone button
2. Speak your question clearly
3. Text appears automatically
4. Review and send

**Browser Requirements:**
- Best: Chrome or Edge
- Good: Safari (iOS 14.5+)
- Limited: Firefox

## Features

### 1. Flashcard Study (Original)
- Spaced repetition algorithm
- Adaptive difficulty
- Progress tracking
- Multiple card types (Definition, Application, Connection, Cloze, MCQ)

### 2. Study Assistant Chatbot (NEW)
- GPT-4o powered responses
- RAG (Retrieval-Augmented Generation)
- Page-level citations
- Follow-up question suggestions
- Multi-document support
- Voice input

## Troubleshooting

### "No module named 'backend'"
```bash
# Make sure you're in the project directory
cd /Users/kmr/rememberSOMthing
# Run from project root
python3 -m uvicorn backend.main:app --reload
```

### "OpenAI API key not found"
1. Check .env file exists in project root
2. Make sure it contains: `OPENAI_API_KEY=sk-...`
3. Restart the server

### Voice input not working
- Grant microphone permissions in browser
- Use Chrome or Edge for best support
- Check HTTPS (may be required)

### No documents showing in chat
- Upload PDFs first in Upload tab
- Wait for processing to complete
- Refresh the Study Chat tab

## Stopping the Server

Press `Ctrl+C` in the terminal

## Project Structure
```
rememberSOMthing/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── routers/
│   │   ├── quiz.py          # Chat endpoints
│   │   ├── upload.py        # PDF upload
│   │   ├── session.py       # Study sessions
│   │   └── progress.py      # Progress tracking
│   ├── services/
│   │   ├── conversational.py  # GPT-4o chat
│   │   ├── rag.py            # RAG retrieval
│   │   ├── ingest.py         # PDF processing
│   │   └── llm.py            # LLM utilities
│   └── models.py            # Database models
├── frontend/
│   ├── index.html           # Main UI
│   ├── app.js               # JavaScript logic
│   └── style.css            # Styling
├── start.sh                 # Startup script
└── requirements.txt         # Dependencies
```

## API Documentation

Once running, visit http://localhost:8000/docs for:
- Interactive API documentation
- Request/response schemas
- Try endpoints directly

## Need Help?

See detailed documentation:
- [CHATBOT_IMPLEMENTATION.md](CHATBOT_IMPLEMENTATION.md) - Technical details
- [MULTI_DOC_VOICE_GUIDE.md](MULTI_DOC_VOICE_GUIDE.md) - Feature guide

---

**Happy studying! 🎓**
