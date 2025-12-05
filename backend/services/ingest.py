"""Service for ingesting PDFs and generating flashcards."""
import uuid
import fitz  # PyMuPDF
from fastapi import UploadFile
from sqlalchemy.orm import Session
from backend.models import Document, Card, CardType


def generate_cards_from_chunk(chunk_text: str, document_id: str) -> list[Card]:
    """
    Generate flashcards from a text chunk.
    
    For demo purposes, creates simple cards from each chunk:
    - 1 definition card with a summary
    - 1 application card if chunk is long enough
    
    Args:
        chunk_text: Text chunk to generate cards from
        document_id: ID of the parent document
        
    Returns:
        List of Card objects
    """
    cards = []
    
    # Create a definition card with a truncated version
    truncated = chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text
    
    cards.append(Card(
        id=str(uuid.uuid4()),
        document_id=document_id,
        topic="Document Summary",
        type=CardType.definition,
        front="Summarize this section in one sentence",
        back=truncated
    ))
    
    # If chunk is long enough, create an application card
    if len(chunk_text) > 500:
        cards.append(Card(
            id=str(uuid.uuid4()),
            document_id=document_id,
            topic="Document Content",
            type=CardType.application,
            front="What are the key concepts in this section?",
            back=chunk_text[:300] + "..." if len(chunk_text) > 300 else chunk_text
        ))
    
    return cards


def process_pdf(file: UploadFile, db: Session) -> Document:
    """
    Process a PDF file and generate flashcards from its content.
    
    Steps:
    1. Create a Document row with the filename as title
    2. Extract all text from the PDF using PyMuPDF
    3. Chunk the text into ~1000 character segments
    4. Generate 1-3 flashcards per chunk
    5. Save all cards to the database
    
    Args:
        file: Uploaded PDF file
        db: Database session
        
    Returns:
        The created Document object with cards
    """
    # Create a document
    doc_id = str(uuid.uuid4())
    filename = file.filename or "Untitled Document"
    
    document = Document(
        id=doc_id,
        title=filename
    )
    db.add(document)
    
    # Read PDF content
    pdf_bytes = file.file.read()
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Extract all text from PDF
    full_text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        full_text += page.get_text()
    
    pdf_document.close()
    
    # Chunk the text (roughly 1000 characters per chunk)
    chunk_size = 1000
    chunks = []
    for i in range(0, len(full_text), chunk_size):
        chunk = full_text[i:i + chunk_size].strip()
        if chunk:  # Only add non-empty chunks
            chunks.append(chunk)
    
    # Generate cards from each chunk
    all_cards = []
    for chunk in chunks:
        chunk_cards = generate_cards_from_chunk(chunk, doc_id)
        all_cards.extend(chunk_cards)
    
    # Add all cards to the database
    for card in all_cards:
        db.add(card)
    
    # Commit everything
    db.commit()
    db.refresh(document)
    
    return document, len(all_cards)
