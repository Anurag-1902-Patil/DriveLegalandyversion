"""
DriveLegal – FastAPI Application Entry Point
Starts the server, registers routes, configures CORS, database engine, and logging.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# ── Import Routers ─────────────────────────────────────────────────────────
from app.routes.chat import router as chat_router
from app.routes.location import router as location_router
from app.auth import router as auth_router            # ◄ Cleaned up and imported from auth.py
from app.routes.profile import router as profile_router  # ◄ Imported our profile router

from rag.retriever import load_index
from app.database import engine, Base
import app.models as models

# ── Logging ────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("drivelegal")


# ── Lifespan: load Qdrant index and DB tables at startup ──────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)  # Automatically maps tables on startup
    
    logger.info("Loading Qdrant index…")
    load_index()  # Initializes Qdrant client and embedder
    logger.info("Qdrant index ready.")
    yield
    logger.info("Shutting down DriveLegal.")


# ── App Initialization ─────────────────────────────────────────────────────
app = FastAPI(
    title="DriveLegal API",
    description="AI-powered road safety chatbot – location-aware traffic law Q&A.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routers ───────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(location_router)
app.include_router(auth_router)       # ◄ Registers /api/auth/send-otp and /api/auth/verify-otp
app.include_router(profile_router)    # ◄ Registers /api/profile/verify-dl and /dashboard-data/{user_id}


# ── Serve the HTML frontend at /ui ─────────────────────────────────────────
@app.get("/ui", tags=["Frontend"], include_in_schema=False)
def serve_ui():
    """Serve the main dashboard HTML file."""
    return FileResponse("frontend/ui.html")


@app.get("/health", tags=["System"])
def health():
    """Simple liveness check."""
    return {"status": "ok", "service": "DriveLegal"}