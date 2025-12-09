# rememberSOMthing 🧠

<div align="center">

**An AI-powered study platform combining intelligent flashcards with conversational learning**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 📖 Overview

rememberSOMthing is an intelligent study assistant that transforms your course materials into an interactive learning experience. Upload PDFs and get:

- **🤖 AI Study Chat**: Ask questions about your materials and receive cited, accurate answers
- **📇 Smart Flashcards**: Automatically generated cards with spaced repetition
- **📊 Progress Tracking**: Monitor your learning with detailed analytics
- **🎯 Adaptive Learning**: Difficulty adjusts based on your performance

Built with FastAPI, GPT-4o, and modern RAG (Retrieval-Augmented Generation) techniques.

## ✨ Features

### 🤖 AI Study Assistant Chatbot
- **Intelligent Q&A**: Ask questions in natural language about your uploaded materials
- **Source Citations**: Every answer includes page-level citations from your PDFs
- **Multi-Document Support**: Query across multiple documents simultaneously
- **Voice Input**: Hands-free question asking using speech-to-text
- **Cross-Document Synthesis**: Get answers that combine information from multiple sources
- **Follow-up Suggestions**: AI suggests relevant questions to deepen understanding
- **Context Awareness**: Maintains conversation history for natural dialogue

### 📇 Intelligent Flashcard System
- **Automatic Generation**: AI creates diverse question types from your PDFs
- **Spaced Repetition**: Optimized review schedule using SM-2 algorithm
- **Adaptive Difficulty**: Questions adjust based on your performance
- **Multiple Card Types**: 
  - Definition cards
  - Application scenarios
  - Connection questions
  - Cloze deletions
  - Multiple choice questions
- **Real-time Evaluation**: GPT-4o grades your answers with detailed feedback

### 📊 Learning Analytics
- **Topic Mastery Tracking**: Monitor understanding across different topics
- **Performance Metrics**: Accuracy rates, streak tracking, and review statistics
- **Progress Visualization**: Visual dashboards showing your learning journey
- **Review Scheduling**: Smart reminders based on spaced repetition intervals

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

### Installation

#### Option 1: Automated Setup (Recommended)
```bash
# Clone the repository
git clone https://github.com/annaepple1-spec/rememberSOMthing.git
cd rememberSOMthing

# Run the startup script
./start.sh
```

The script will automatically:
1. Create a `.env` file with your OpenAI API key
2. Set up a Python virtual environment
3. Install all dependencies
4. Start the development server

#### Option 2: Manual Setup
```bash
# Clone the repository
git clone https://github.com/annaepple1-spec/rememberSOMthing.git
cd rememberSOMthing

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=your_api_key_here" > .env

# Start the server
python3 -m uvicorn backend.main:app --reload --port 8000
```

### Access the Application
- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📚 Usage

### 1. Upload Study Materials
1. Navigate to the **Upload** tab
2. Select a PDF file (lecture notes, textbook chapter, etc.)
3. Wait for processing - flashcards are generated automatically
4. Your document is now ready for both flashcard study and chat

### 2. Chat with Your Materials
1. Go to the **💬 Study Chat** tab
2. Select one or more documents from your library
3. Click "Start Chat"
4. Ask questions using text or voice input
5. Receive answers with page-level citations
6. Follow suggested questions to explore deeper

### 3. Study with Flashcards
1. Navigate to the **Review** tab
2. Answer flashcard questions
3. Receive AI-powered feedback
4. Track your progress and mastery levels
5. Return for spaced repetition reviews

## 🏗️ Architecture

### Tech Stack
- **Backend**: FastAPI, SQLAlchemy, Python 3.8+
- **AI/ML**: OpenAI GPT-4o, LangChain, ChromaDB (vector store)
- **Document Processing**: PyMuPDF, CrewAI
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Database**: SQLite

### Project Structure
```
rememberSOMthing/
├── backend/
│   ├── main.py              # FastAPI application entry
│   ├── database.py          # Database configuration
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── agents/              # AI agents (CrewAI)
│   ├── routers/             # API endpoints
│   └── services/            # Business logic
│       ├── conversational.py    # Chatbot service
│       ├── rag.py              # RAG implementation
│       ├── flashcard_crew.py   # Flashcard generation
│       ├── adaptive_selection.py
│       └── scheduler.py        # Spaced repetition
├── frontend/
│   ├── index.html           # Main UI
│   ├── app.js              # Frontend logic
│   └── style.css           # Styling
├── chroma_db/              # Vector embeddings
├── requirements.txt        # Python dependencies
└── .env                    # Configuration (create this)
```

## 📋 Documentation

- **[Quick Start Guide](QUICKSTART.md)**: Detailed setup instructions
- **[Chatbot Implementation](CHATBOT_IMPLEMENTATION.md)**: Technical details on AI chat
- **[Chatbot Improvements](CHATBOT_IMPROVEMENTS.md)**: Recent enhancements and features
- **[Multi-Document Voice Guide](MULTI_DOC_VOICE_GUIDE.md)**: Voice and multi-doc features
- **[Security Guide](SECURITY.md)**: Security best practices
- **[Handsome Dan Setup](SETUP_HANDSOME_DAN.md)**: Loading animation configuration

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Getting Started
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Make your changes
4. Run tests if available
5. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
6. Push to the branch (`git push origin feature/AmazingFeature`)
7. Open a Pull Request

### Areas for Contribution
- 🐛 **Bug Fixes**: Report or fix bugs
- ✨ **New Features**: Suggest or implement new capabilities
- 📖 **Documentation**: Improve docs, add examples, fix typos
- 🧪 **Testing**: Add unit tests, integration tests
- 🎨 **UI/UX**: Enhance the frontend experience
- ⚡ **Performance**: Optimize algorithms, reduce latency
- 🌐 **Internationalization**: Add support for other languages

### Code Guidelines
- Follow PEP 8 for Python code
- Add docstrings to functions and classes
- Keep functions focused and modular
- Add comments for complex logic
- Update documentation for new features

## 🐛 Troubleshooting

### Common Issues

**"No module named 'backend'"**
```bash
# Ensure you're in the project root directory
cd /path/to/rememberSOMthing
python3 -m uvicorn backend.main:app --reload
```

**OpenAI API Errors**
- Verify your API key is correct in `.env`
- Check your OpenAI account has credits
- Ensure `OPENAI_API_KEY` is set as an environment variable

**Voice Input Not Working**
- Use Chrome, Edge, or Safari (iOS 14.5+)
- Grant microphone permissions to your browser
- Ensure HTTPS or localhost (required for Web Speech API)

**Database Issues**
```bash
# Reset the database
rm flashcards.db
rm -rf chroma_db/
# Restart the server to recreate
```

##  Acknowledgments

- **OpenAI** for GPT-4o and embeddings API
- **FastAPI** for the excellent web framework
- **LangChain** for RAG tooling
- **CrewAI** for multi-agent orchestration
- **Yale University** for Handsome Dan (our loading animation mascot 🐶)

## 📧 Contact

**Project Maintainers**: 
- [@annaepple1-spec](https://github.com/annaepple1-spec)
- [@Kenza-R](https://github.com/Kenza-R)
- [@maxjobraun](https://github.com/maxjobraun)

**Repository**: [github.com/annaepple1-spec/rememberSOMthing](https://github.com/annaepple1-spec/rememberSOMthing)

---

<div align="center">

**⭐ Star this repository if you find it helpful!**

Made with ❤️ and ☕

</div>
