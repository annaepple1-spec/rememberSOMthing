# Multi-Document Chat & Voice Input - Quick Guide

## 🎯 New Features Overview

### 1. Multi-Document Chat
Chat with multiple PDFs simultaneously to get comprehensive answers from all your course materials.

**How to Use:**
1. Upload multiple PDFs (Upload tab)
2. Go to "Study Chat" tab
3. **Check multiple documents** in the list (not just one!)
4. Click "Start Chat (X documents)"
5. Ask questions that span multiple documents

**Example Questions:**
- "Compare the inventory methods discussed in both documents"
- "What do my notes say about production planning across all chapters?"
- "Find all mentions of supply chain optimization"

**Benefits:**
- See connections between different materials
- Get more comprehensive answers
- Compare and contrast concepts
- Study from entire course materials at once

### 2. Voice Input
Speak your questions instead of typing them.

**How to Use:**
1. Start a chat session
2. Click the **🎤 microphone button** 
3. Speak your question clearly
4. Text appears automatically
5. Click "Send" or edit first

**Tips:**
- Speak clearly and at normal pace
- Works best in quiet environments
- Review transcription before sending
- Grant microphone permission when prompted

**Browser Support:**
- ✅ Chrome (best support)
- ✅ Edge
- ✅ Safari (iOS 14.5+)
- ⚠️ Firefox (limited)

## 🔧 Technical Details

### Multi-Document RAG Architecture
```
User Question
    ↓
[retrieve_context_multi_doc]
    ↓
Search Document 1 (top 2 chunks)
Search Document 2 (top 2 chunks)
Search Document 3 (top 2 chunks)
    ↓
Aggregate & Sort by Relevance
    ↓
GPT-4o Synthesis
    ↓
Response with Multi-Source Citations
```

### Voice Input Flow
```
User clicks 🎤
    ↓
Web Speech API starts
    ↓
Browser captures audio
    ↓
Real-time transcription
    ↓
Text appears in input
    ↓
User sends or edits
```

## 📊 API Changes

### Start Chat (Updated)
```json
// Multi-document mode
POST /api/quiz/start
{
  "document_ids": ["doc1", "doc2", "doc3"]
}

// Single document mode (still works)
POST /api/quiz/start
{
  "document_id": "doc1"
}
```

### Chat Endpoint (Updated)
```json
POST /api/quiz/chat
{
  "session_id": "uuid",
  "message": "user question",
  "document_ids": ["doc1", "doc2"],  // Optional, for multi-doc
  "conversation_history": [...]
}
```

### Citation Format (Updated)
```
Old (single doc):
[1] Operations Management.pdf, Page 12

New (multi-doc):
[1] Operations Management.pdf, Page 12
[2] Supply Chain Basics.pdf, Page 8
[3] Inventory Control.pdf, Page 15
```

## 🎨 UI Changes

### Document Selection
**Before:** Single dropdown
**Now:** Multi-select checkboxes

### Chat Input
**Before:** Text only
**Now:** Text + 🎤 Voice button

### Stats Display
**Before:** Questions | Correct | Score
**Now:** Messages | Documents | Sources Used

## 💡 Use Cases

### Multi-Document Chat
1. **Exam Prep**: "Summarize key concepts from all my study materials"
2. **Research**: "Find all references to sustainability across documents"
3. **Comparison**: "How do these two textbooks explain the same topic?"
4. **Comprehensive Review**: "What are the main themes in this course?"

### Voice Input
1. **Accessibility**: Students with typing difficulties
2. **Mobile Study**: Easier input on phones
3. **Multitasking**: Ask questions while walking/commuting
4. **Speed**: Faster than typing long questions
5. **Natural**: More conversational interaction

## 🚀 Quick Start

### Test Multi-Document Chat
```
1. Upload: lecture1.pdf, lecture2.pdf, textbook_ch3.pdf
2. Check all three boxes
3. Start chat
4. Ask: "What are the main production systems discussed?"
5. See answer with citations from all 3 sources
```

### Test Voice Input
```
1. Start any chat session
2. Click 🎤 button (red pulse indicates recording)
3. Say: "Explain MRP systems"
4. Text appears
5. Click Send
```

## 🔍 Debugging

### Voice Input Not Working?
- Check microphone permissions in browser settings
- Try Chrome/Edge (best support)
- Check if HTTPS (required for Web Speech API)
- Look for 🎤 button (hidden if unsupported)

### Multi-Document Citations Not Showing?
- Verify all documents have flashcards generated
- Check that document_ids are passed in request
- Look in browser console for API errors

## 📈 Performance

### Multi-Document Mode
- **Retrieval time**: ~200-500ms per document
- **Total time**: 1-2 seconds for 3 documents
- **Recommended**: 1-5 documents per session
- **Maximum**: No hard limit, but 10+ may be slow

### Voice Input
- **Latency**: Instant transcription
- **Accuracy**: 85-95% (depends on audio quality)
- **Offline**: Not supported (requires browser API)

---

**Enjoy your enhanced study assistant! 🎓**
