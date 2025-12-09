"""
RAG (Retrieval-Augmented Generation) service for Quiz Bot.
Handles text chunking, embedding generation, and semantic retrieval.
"""
import os
import uuid
from typing import List, Dict, Optional, Tuple
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
import chromadb
from chromadb.config import Settings
from sqlalchemy.orm import Session
from backend.models import DocumentChunk, Card


# Initialize ChromaDB client (persistent storage)
CHROMA_DB_DIR = "./chroma_db"
os.makedirs(CHROMA_DB_DIR, exist_ok=True)

chroma_client = chromadb.PersistentClient(
    path=CHROMA_DB_DIR,
    settings=Settings(anonymized_telemetry=False)
)

# Initialize embeddings model
embeddings_model = OpenAIEmbeddings(
    model="text-embedding-ada-002",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)


def get_or_create_collection(document_id: str):
    """Get or create a ChromaDB collection for a document."""
    collection_name = f"doc_{document_id.replace('-', '_')}"
    try:
        collection = chroma_client.get_collection(name=collection_name)
    except Exception:
        collection = chroma_client.create_collection(
            name=collection_name,
            metadata={"document_id": document_id}
        )
    return collection


def chunk_text(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[str]:
    """
    Split text into chunks for embedding.
    
    Args:
        text: Full document text
        chunk_size: Target size in tokens
        chunk_overlap: Overlap between chunks in tokens
        
    Returns:
        List of text chunks
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = text_splitter.split_text(text)
    return chunks


async def create_and_store_chunks(
    document_id: str, 
    text: str, 
    db: Session
) -> int:
    """
    Chunk document text, generate embeddings, and store in database + ChromaDB.
    
    Args:
        document_id: Document ID
        text: Full document text
        db: Database session
        
    Returns:
        Number of chunks created
    """
    # Delete existing chunks for this document
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
    
    # Delete existing ChromaDB collection
    try:
        collection_name = f"doc_{document_id.replace('-', '_')}"
        chroma_client.delete_collection(name=collection_name)
    except Exception:
        pass
    
    # Create new chunks
    chunks = chunk_text(text)
    
    if not chunks:
        return 0
    
    # Get ChromaDB collection
    collection = get_or_create_collection(document_id)
    
    # Generate embeddings and store chunks
    chunk_records = []
    chunk_ids = []
    chunk_texts = []
    chunk_metadatas = []
    
    for idx, chunk_text in enumerate(chunks):
        chunk_id = str(uuid.uuid4())
        
        # Create database record
        chunk_record = DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            chunk_text=chunk_text,
            chunk_index=idx,
            embedding_id=chunk_id
        )
        chunk_records.append(chunk_record)
        
        # Prepare for ChromaDB
        chunk_ids.append(chunk_id)
        chunk_texts.append(chunk_text)
        chunk_metadatas.append({
            "document_id": document_id,
            "chunk_index": idx
        })
    
    # Generate embeddings in batch
    embeddings = embeddings_model.embed_documents(chunk_texts)
    
    # Store in ChromaDB
    collection.add(
        ids=chunk_ids,
        documents=chunk_texts,
        embeddings=embeddings,
        metadatas=chunk_metadatas
    )
    
    # Store in database
    db.bulk_save_objects(chunk_records)
    db.commit()
    
    return len(chunks)


def retrieve_context(
    query: str, 
    document_id: str, 
    top_k: int = 3
) -> List[Dict[str, any]]:
    """
    Retrieve relevant text chunks for a query using semantic search.
    
    Args:
        query: Search query
        document_id: Document to search in
        top_k: Number of results to return
        
    Returns:
        List of dicts with keys: id, text, score, metadata
    """
    try:
        collection = get_or_create_collection(document_id)
        
        # Generate query embedding
        query_embedding = embeddings_model.embed_query(query)
        
        # Search ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results
        context_chunks = []
        if results and results['ids'] and len(results['ids']) > 0:
            for i in range(len(results['ids'][0])):
                context_chunks.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i],
                    "score": 1.0 - results['distances'][0][i],  # Convert distance to similarity
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {}
                })
        
        return context_chunks
    
    except Exception as e:
        print(f"Error retrieving context: {e}")
        return []


def get_related_cards(
    context_chunks: List[Dict[str, any]], 
    document_id: str, 
    db: Session,
    limit: int = 5
) -> List[Card]:
    """
    Find flashcards related to retrieved context chunks.
    
    Args:
        context_chunks: Retrieved context from RAG
        document_id: Document ID
        db: Database session
        limit: Max number of cards to return
        
    Returns:
        List of related Card objects
    """
    # Get all cards for document
    cards = db.query(Card).filter(Card.document_id == document_id).all()
    
    if not cards or not context_chunks:
        return cards[:limit] if cards else []
    
    # Extract context text
    context_text = " ".join([chunk["text"] for chunk in context_chunks])
    
    # Simple relevance scoring based on keyword overlap
    card_scores = []
    for card in cards:
        card_text = f"{card.front} {card.back}".lower()
        context_lower = context_text.lower()
        
        # Count word overlap
        card_words = set(card_text.split())
        context_words = set(context_lower.split())
        overlap = len(card_words.intersection(context_words))
        
        card_scores.append((card, overlap))
    
    # Sort by score and return top cards
    card_scores.sort(key=lambda x: x[1], reverse=True)
    return [card for card, score in card_scores[:limit]]


def assemble_quiz_context(
    document_id: str,
    card: Card,
    db: Session
) -> Tuple[str, List[Dict[str, any]]]:
    """
    Assemble context for a quiz question from a flashcard.
    
    Args:
        document_id: Document ID
        card: Flashcard to create question from
        db: Database session
        
    Returns:
        Tuple of (enriched_question, context_chunks)
    """
    # Retrieve relevant context for the card's question
    context_chunks = retrieve_context(card.front, document_id, top_k=2)
    
    # Build enriched question with context hint
    if context_chunks:
        context_preview = context_chunks[0]["text"][:200] + "..."
        enriched_question = f"{card.front}\n\n💡 Context hint: {context_preview}"
    else:
        enriched_question = card.front
    
    return enriched_question, context_chunks
