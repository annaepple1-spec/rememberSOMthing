from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.routers import session, upload, progress

# Create FastAPI app
app = FastAPI(title="AI Flashcard Trainer")

# Add CORS middleware to allow all origins (for frontend development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(session.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(progress.router, prefix="/api")


@app.on_event("startup")
def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
