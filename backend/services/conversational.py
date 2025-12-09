"""
Conversational AI service for Quiz Bot with RAG and citation support.
Uses GPT-4 to provide intelligent responses based on uploaded course materials.
"""
import os
from typing import List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from backend.models import Document
from backend.services.rag import retrieve_context, retrieve_context_multi_doc

# Ensure .env is loaded
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Initialize GPT-4 LLM
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("[CONVERSATIONAL WARNING] No OPENAI_API_KEY found in environment")
    llm = None
else:
    print(f"[CONVERSATIONAL] OpenAI API key loaded successfully")
    # Use GPT-4o for best results (falls back to gpt-4 if not available)
    llm = ChatOpenAI(
        model="gpt-4o",  # Latest GPT-4 model with optimized performance
        temperature=0.3,  # Lower temperature for more factual responses
        api_key=api_key
    )


def format_citations(context_chunks: List[Dict], document_title: str = None) -> str:
    """
    Format retrieved context chunks into citations.
    
    Args:
        context_chunks: List of context chunks with text, page_number, document_title, etc.
        document_title: Optional single document title (for backward compatibility)
        
    Returns:
        Formatted citation string
    """
    if not context_chunks:
        return ""
    
    citations = []
    for i, chunk in enumerate(context_chunks, 1):
        page_num = chunk.get('page_number')
        # Use chunk's document_title if available (multi-doc), otherwise use provided title
        doc_title = chunk.get('document_title', document_title or 'Document')
        
        if page_num:
            citations.append(f"[{i}] {doc_title}, Page {page_num}")
        else:
            citations.append(f"[{i}] {doc_title}")
    
    return "\n".join(citations)


def generate_chat_response(
    user_question: str,
    document_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
    document_title: Optional[str] = None,
    db: Session = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, any]:
    """
    Generate a conversational response using RAG and GPT-4.
    
    Args:
        user_question: The user's question
        document_id: Single document ID (for backward compatibility)
        document_ids: List of document IDs to search (for multi-doc mode)
        document_title: Title for single document mode
        db: Database session
        conversation_history: Optional list of previous messages [{"role": "user"/"assistant", "content": "..."}]
        
    Returns:
        Dict with keys: response (str), citations (str), context_chunks (list), sources (list)
    """
    if not llm:
        return {
            "response": "I'm sorry, but the AI service is not configured. Please check the OpenAI API key.",
            "citations": "",
            "context_chunks": [],
            "sources": []
        }
    
    # Determine if we're in single-doc or multi-doc mode
    if document_ids and len(document_ids) > 0:
        # Multi-document mode
        context_chunks = retrieve_context_multi_doc(
            query=user_question,
            document_ids=document_ids,
            db=db,
            top_k_per_doc=2  # Get top 2 from each document
        )
        doc_titles = list(set([chunk.get('document_title', 'Document') for chunk in context_chunks]))
        context_description = f"{len(document_ids)} documents ({', '.join(doc_titles[:3])}{'...' if len(doc_titles) > 3 else ''})"
    else:
        # Single document mode (backward compatibility)
        if not document_id:
            return {
                "response": "No document specified for the query.",
                "citations": "",
                "context_chunks": [],
                "sources": []
            }
        context_chunks = retrieve_context(
            query=user_question,
            document_id=document_id,
            top_k=5
        )
        # Add document info to chunks for consistency
        for chunk in context_chunks:
            chunk['document_id'] = document_id
            chunk['document_title'] = document_title or 'Document'
        context_description = f'"{document_title}"' if document_title else "the document"
    
    if not context_chunks:
        return {
            "response": "I couldn't find relevant information in the uploaded documents to answer your question. Please try rephrasing or ask about topics covered in the material.",
            "citations": "",
            "context_chunks": [],
            "sources": []
        }
    
    # Build context string with page references
    context_str = ""
    sources = []
    for i, chunk in enumerate(context_chunks, 1):
        page_num = chunk.get('page_number')
        doc_title = chunk.get('document_title', 'Document')
        page_ref = f" ({doc_title}, Page {page_num})" if page_num else f" ({doc_title})"
        context_str += f"\n[Source {i}]{page_ref}:\n{chunk['text']}\n"
        
        sources.append({
            "source_num": i,
            "page": page_num,
            "document_title": doc_title,
            "text": chunk['text'][:200]
        })
    
    # Build system message with instructions
    system_message = f"""You are an intelligent study assistant helping students understand course material from {context_description}. 

Your role:
1. Answer questions clearly and accurately based ONLY on the provided course material
2. Cite your sources by referencing [Source X] numbers when you use information
3. When citing information from different documents, mention which document it's from
4. If the question cannot be answered from the given material, politely say so
5. Be conversational, helpful, and educational
6. Break down complex concepts into understandable explanations
7. When citing, use the format: "According to [Source 1]..." or "As mentioned in [Source 2]..."

Context from the course material:
{context_str}

Remember to cite sources whenever you reference specific information!"""

    # Build message history
    messages = [SystemMessage(content=system_message)]
    
    # Add conversation history if provided
    if conversation_history:
        for msg in conversation_history[-6:]:  # Keep last 6 messages for context
            if msg.get('role') == 'user':
                messages.append(HumanMessage(content=msg.get('content', '')))
            elif msg.get('role') == 'assistant':
                messages.append(SystemMessage(content=f"Assistant: {msg.get('content', '')}"))
    
    # Add current question
    messages.append(HumanMessage(content=user_question))
    
    # Generate response
    try:
        response = llm.invoke(messages)
        answer = response.content
        
        # Format citations (now handles both single and multi-doc)
        citations = format_citations(context_chunks)
        
        return {
            "response": answer,
            "citations": citations,
            "context_chunks": context_chunks,
            "sources": sources
        }
    
    except Exception as e:
        print(f"[CONVERSATIONAL ERROR] Failed to generate response: {e}")
        return {
            "response": f"I encountered an error while processing your question: {str(e)}",
            "citations": "",
            "context_chunks": context_chunks,
            "sources": sources
        }


def generate_follow_up_questions(
    user_question: str,
    response: str,
    document_id: str,
    db: Session
) -> List[str]:
    """
    Generate suggested follow-up questions based on the conversation.
    
    Args:
        user_question: Original question
        response: Assistant's response
        document_id: Document ID
        db: Database session
        
    Returns:
        List of 2-3 suggested follow-up questions
    """
    if not llm:
        return []
    
    prompt = f"""Based on this Q&A exchange, suggest 2-3 relevant follow-up questions a student might ask to deepen their understanding:

Question: {user_question}

Answer: {response}

Generate 2-3 concise, specific follow-up questions (one per line, no numbering):"""

    try:
        result = llm.invoke([HumanMessage(content=prompt)])
        questions = [q.strip() for q in result.content.strip().split('\n') if q.strip()]
        return questions[:3]
    except Exception as e:
        print(f"[CONVERSATIONAL ERROR] Failed to generate follow-up questions: {e}")
        return []
