"""
DriveLegal – Pydantic Models
Strict input/output schemas for the /chat endpoint.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


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


class ChatResponse(BaseModel):
    answer: str
    fine_amount: Optional[str] = None      # e.g. "₹1,000 – ₹2,000"
    sources: List[Source] = []
    disclaimer: str = (
        "This information is indicative and for awareness only. "
        "Fine amounts may vary. Please verify with the official RTO or traffic authority."
    )
    offline_fallback: bool = False         # True when Ollama/Mistral was unavailable
