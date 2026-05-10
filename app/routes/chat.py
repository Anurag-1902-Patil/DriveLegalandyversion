"""
DriveLegal – /chat and /health routes
POST /chat  → runs RAG pipeline + challan lookup → returns answer
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models import ChatRequest, ChatResponse, Source
from app.routes.location import get_store     # GPS in-memory store
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

    # ── Resolve effective location (GPS overrides manual dropdown) ───────────────
    gps_store = get_store()
    gps_location = gps_store.get_location_result()   # None if no fresh fix

    if gps_location:
        # GPS fix available and fresh — use it, ignore manual dropdown
        effective_city    = gps_location.city
        effective_state   = gps_location.state
        effective_country = gps_location.country
        gps_context       = gps_location.as_context_string()   # e.g. "Pune, Maharashtra, India"
        logger.info("Using GPS-resolved location: %s", gps_context)
    else:
        # No GPS fix — fall back to what the frontend sent
        effective_city    = req.location.city
        effective_state   = req.location.state
        effective_country = req.location.country
        gps_context       = ""
        logger.info("No GPS fix; using manual location: %s, %s", effective_city, effective_state)

    loc_str = f"{effective_city}, {effective_state}, {effective_country}"
    logger.info(f"Query | location={loc_str} | message={req.message!r}")

    # ── 1. RAG answer ──────────────────────────────────────────────────────
    try:
        result = get_answer(
            query=req.message,
            city=effective_city,
            state=effective_state,
            country=effective_country,
            gps_context=gps_context,
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
        city=effective_city,
        state=effective_state,
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
