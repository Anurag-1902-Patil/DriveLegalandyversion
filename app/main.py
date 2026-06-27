"""
DriveLegal – FastAPI Application Entry Point
Starts the server, registers routes, configures CORS and logging.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.chat import router as chat_router
from app.routes.location import router as location_router
from app.auth import request_otp, verify_otp  # ◄ Imported our new auth functions
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


# ── Lifespan: load Qdrant index once at startup ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading Qdrant index…")
    load_index()          # initializes Qdrant client and embedder
    logger.info("Qdrant index ready.")
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
app.include_router(location_router)


# ── Authentication Endpoints ───────────────────────────────────────────────
@app.post("/api/auth/send-otp", tags=["Authentication"])
async def api_send_otp(background_tasks: BackgroundTasks, payload: dict = Body(...)):
    """Accepts an email address and fires an OTP to the user in the background."""
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email address is required.")
    
    # We use background_tasks so the user doesn't wait for the email server to respond
    background_tasks.add_task(request_otp, email)
    return {"status": "success", "message": "Verification code dispatched successfully."}


@app.post("/api/auth/verify-otp", tags=["Authentication"])
async def api_verify_otp(payload: dict = Body(...)):
    """Verifies the 6-digit OTP code and exchanges it for a secure session token."""
    email = payload.get("email")
    code = payload.get("code")
    
    if not email or not code:
        raise HTTPException(status_code=400, detail="Both email and validation code are required.")
    
    result = verify_otp(email, code)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
        
    return result


# ── Serve the HTML frontend at /ui ─────────────────────────────────────────
@app.get("/ui", tags=["Frontend"], include_in_schema=False)
def serve_ui():
    """Serve the main dashboard HTML file."""
    return FileResponse("frontend/ui.html")


@app.get("/health", tags=["System"])
def health():
    """Simple liveness check."""
    return {"status": "ok", "service": "DriveLegal"}