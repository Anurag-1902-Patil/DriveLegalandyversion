"""
DriveLegal – /chat and /health routes
POST /chat  → runs RAG pipeline + challan lookup → returns answer
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models import ChatRequest, ChatResponse, Source
from rag.chain import get_answer
from rag.challan import lookup_fine

logger = logging.getLogger("drivelegal.routes.chat")
router = APIRouter(tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main endpoint.  Accepts a natural-language traffic law question
    plus a location object and returns a grounded, location-specific answer.
    """
    if not req.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    loc_str = f"{req.location.city}, {req.location.state}, {req.location.country}"
    logger.info(f"Query | location={loc_str} | message={req.message!r}")

    # ── 1. RAG answer ──────────────────────────────────────────────────────
    try:
        result = get_answer(
            query=req.message,
            city=req.location.city,
            state=req.location.state,
            country=req.location.country,
        )
        answer = result["answer"]
        raw_sources = result.get("sources", [])
        offline = result.get("offline_fallback", False)
    except Exception as exc:
        logger.error(f"RAG pipeline error: {exc}")
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable.")

    # ── 2. Challan lookup (structured JSON, not LLM) ───────────────────────
    fine_amount = lookup_fine(
        query=req.message,
        city=req.location.city,
        state=req.location.state,
    )

    # ── 3. Build source objects ────────────────────────────────────────────
    sources = [
        Source(
            law_section=s.metadata.get("law_section"),
            category=s.metadata.get("category"),
            region=s.metadata.get("region"),
            text_snippet=s.page_content[:200],
        )
        for s in raw_sources
    ]

    return ChatResponse(
        answer=answer,
        fine_amount=fine_amount,
        sources=sources,
        offline_fallback=offline,
    )