"""
DriveLegal – Pydantic Models & Database Schemas
Strict input/output schemas for endpoints and SQLAlchemy model tracking definitions.
"""

from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float, Text, DateTime
from app.database import Base   

# ── GPS / Location ─────────────────────────────────────────────────────────

class GPSPayload(BaseModel):
    """Raw GPS coordinates from the browser Geolocation API."""
    lat: float = Field(..., ge=-90.0, le=90.0,  example=18.5204,  description="Latitude")
    lon: float = Field(..., ge=-180.0, le=180.0, example=73.8567,  description="Longitude")
    accuracy: Optional[float] = Field(None, ge=0, example=15.0, description="Accuracy in metres")
    client_timestamp: Optional[str] = Field(None, description="ISO-8601 client timestamp")


class GPSUpdateResponse(BaseModel):
    """Response after accepting a GPS fix."""
    status: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    lat: float
    lon: float
    accuracy_m: Optional[float] = None


class CurrentLocationResponse(BaseModel):
    """Latest GPS fix from memory."""
    fix_available: bool
    age_seconds: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    accuracy_m: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    context_string: Optional[str] = None


class Location(BaseModel):
    city: str = Field(..., example="Pune")
    state: str = Field(..., example="Maharashtra")
    country: str = Field(default="India", example="India")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=3, max_length=500, example="Fine for jumping a red light?")
    location: Location


class Source(BaseModel):
    law_section: Optional[str] = None
    category: Optional[str] = None
    region: Optional[str] = None
    text_snippet: Optional[str] = None


# ── Confidence Scoring ─────────────────────────────────────────────────────

class ConfidenceLevel(str, Enum):
    """Three-tier confidence signal for every chat response."""
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class ConfidenceDetail(BaseModel):
    """Composite confidence score derived from three independent signals."""
    level: ConfidenceLevel
    retrieval_score: Optional[float] = None      # top-1 Qdrant cosine similarity (0–1)
    fine_from_structured_data: bool = False      # did fines.json return a match?
    is_offline_fallback: bool = False            # Ollama/Mistral was unavailable


class ChatResponse(BaseModel):
    answer: str
    fine_amount: Optional[str] = None            # e.g. "₹1,000 – ₹2,000"
    sources: List[Source] = []
    disclaimer: str = (
        "This information is indicative and for awareness only. "
        "Fine amounts may vary. Please verify with the official RTO or traffic authority."
    )
    offline_fallback: bool = False               # True when Ollama/Mistral was unavailable
    confidence: Optional[ConfidenceDetail] = None  # Composite confidence signal


# ── DATABASE SCHEMAS (SQLAlchemy Models) ──────────────────────────────────

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True) # Optional if using strictly OTP
    
    # DL Verification Flag & Profile Data
    is_verified = Column(Boolean, default=False)
    dl_number = Column(String, unique=True, index=True, nullable=True)
    official_name = Column(String, nullable=True)
    dob = Column(String, nullable=True)
    validity_expiry = Column(String, nullable=True)


class ViolationDB(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Violation details
    offence = Column(String, nullable=False)
    fine_amount = Column(Integer, default=0)
    status = Column(String, default="Unpaid") # Unpaid, Paid
    location = Column(String, nullable=True)
    timestamp = Column(String, nullable=True)


class ChatMessageDB(Base):
    """Stores user queries and chatbot answers mapped uniquely back to user profiles."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String, nullable=False)          # 'user' or 'bot'
    message = Column(Text, nullable=False)
    fine_amount = Column(String, nullable=True)      # Stores extracted fine context if relevant
    location_tag = Column(String, nullable=True)     # e.g. "Pune, Maharashtra"
    timestamp = Column(DateTime, default=datetime.utcnow)