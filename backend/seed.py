"""Seed script to populate demo data for the flashcard app."""
import uuid
from backend.database import init_db, SessionLocal
from backend.models import Document, Card, CardType


def seed():
    """Seed the database with demo data."""
    # Initialize database tables
    init_db()
    
    # Create a database session
    db = SessionLocal()
    
    try:
        # Create a demo document
        doc_id = str(uuid.uuid4())
        document = Document(
            id=doc_id,
            title="Demo Document: Intro to Economics"
        )
        db.add(document)
        
        # Create flashcards with different types
        cards = [
            Card(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                topic="Basic Economics",
                type=CardType.definition,
                front="What is inflation?",
                back="Inflation is the rate at which the general level of prices for goods and services rises, eroding purchasing power over time."
            ),
            Card(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                topic="Monetary Policy",
                type=CardType.definition,
                front="Define monetary policy.",
                back="Monetary policy is the process by which a central bank manages the money supply and interest rates to achieve macroeconomic objectives like controlling inflation and stabilizing the economy."
            ),
            Card(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                topic="Interest Rates",
                type=CardType.application,
                front="How would raising interest rates affect consumer spending?",
                back="Raising interest rates typically reduces consumer spending because borrowing becomes more expensive, making loans for cars, homes, and other purchases less attractive. This also encourages saving over spending."
            ),
            Card(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                topic="Supply and Demand",
                type=CardType.connection,
                front="How are inflation and supply chain disruptions connected?",
                back="Supply chain disruptions reduce the availability of goods, shifting the supply curve left. With demand remaining constant or increasing, this scarcity drives prices up, contributing to inflation."
            ),
            Card(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                topic="GDP",
                type=CardType.cloze,
                front="GDP stands for _____ _____ _____.",
                back="Gross Domestic Product"
            ),
        ]
        
        for card in cards:
            db.add(card)
        
        # Commit the transaction
        db.commit()
        
        print(f"✓ Seeded demo data.")
        print(f"  - Created document: '{document.title}' (ID: {doc_id})")
        print(f"  - Added {len(cards)} flashcards")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
