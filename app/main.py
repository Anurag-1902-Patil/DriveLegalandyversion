"""
DriveLegal – FastAPI Application Entry Point
Starts the server, registers routes, configures CORS and logging.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.chat import router as chat_router
from rag.retriever import load_index

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


# ── Lifespan: load FAISS index once at startup ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading FAISS index…")
    load_index()          # warms up the retriever singleton
    logger.info("FAISS index ready.")
    yield
    logger.info("Shutting down DriveLegal.")


# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DriveLegal API",
    description="AI-powered road safety chatbot – location-aware traffic law Q&A.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health", tags=["System"])
def health():
    """Simple liveness check."""
    return {"status": "ok", "service": "DriveLegal"}