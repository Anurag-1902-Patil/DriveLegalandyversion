"""
DriveLegal – rag/retriever.py
Loads Qdrant index using FREE local sentence-transformers embeddings (offline-first).
No external API key needed for retrieval.

Changes from FAISS:
- Uses qdrant-client in embedded mode (local disk at data/qdrant_db/)
- Vector database persisted locally—no cloud dependencies
- All filtering implemented via Qdrant's native Filter + FieldCondition API
- Same retrieve() signature and location cascade behavior
- Embedding model unchanged: all-MiniLM-L6-v2 (same as FAISS)
"""

import logging
import os
from typing import List, Optional

from langchain.schema import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("drivelegal.retriever")

# ── Configuration ──────────────────────────────────────────────────────────
QDRANT_PATH = os.path.join("data", "qdrant_db")
COLLECTION_NAME = "drivelegal_chunks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Global instances
_client: Optional[QdrantClient] = None
_embedder: Optional[SentenceTransformer] = None


def load_index() -> None:
    """
    Initialize Qdrant client and embedding model.
    Qdrant collection must exist (created by scripts/migrate_to_qdrant.py).
    """
    global _client, _embedder
    
    # Load embedding model
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    _embedder = SentenceTransformer(EMBEDDING_MODEL)
    
    # Initialize Qdrant client in embedded mode (local disk)
    logger.info(f"Initializing Qdrant at {QDRANT_PATH}")
    _client = QdrantClient(path=QDRANT_PATH)
    
    # Verify collection exists
    try:
        collection_info = _client.get_collection(COLLECTION_NAME)
        logger.info(
            f"Qdrant collection '{COLLECTION_NAME}' loaded with "
            f"{collection_info.points_count} points"
        )
    except Exception as e:
        raise RuntimeError(
            f"Qdrant collection '{COLLECTION_NAME}' not found at {QDRANT_PATH}. "
            f"Run: python scripts/migrate_to_qdrant.py\nError: {e}"
        )


def _build_region_filter(region: str) -> Optional[Filter]:
    """
    Build a Qdrant Filter for exact region matching.
    Returns None for empty region (no filter).
    """
    if not region:
        return None
    
    return Filter(
        must=[
            FieldCondition(
                key="region",
                match=MatchValue(value=region),
            )
        ]
    )


def retrieve(
    query: str,
    k: int = 5,
    city: str = "",
    state: str = "",
    country: str = "India",
) -> List[Document]:
    """
    Return top-k relevant law chunks, filtered by location (Qdrant native filtering).
    
    Fallback cascade:
    1. Try filtering by city
    2. If < k results, try state
    3. If < k results, try country
    4. If < k results, return unfiltered results
    
    Args:
        query: User question or search term
        k: Number of results to return (default: 5)
        city: City name (optional)
        state: State name (optional)
        country: Country (default: "India")
    
    Returns:
        List of LangChain Document objects with text and metadata
    """
    if _client is None or _embedder is None:
        raise RuntimeError(
            "Qdrant index not loaded. Call load_index() first."
        )
    
    # Embed the query
    query_embedding = _embedder.encode(
        query,
        normalize_embeddings=True,
    ).tolist()
    
    # Implement fallback cascade: city -> state -> country -> no filter
    scopes = [city, state, country, ""]
    accumulated_results = []
    seen_ids = set()
    
    for scope in scopes:
        # Build filter for this scope
        region_filter = _build_region_filter(scope)
        scope_label = f"'{scope}'" if scope else "NO FILTER"
        
        # Search with filter using query_points() (correct method for vector search)
        query_response = _client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            query_filter=region_filter,
            limit=k * 3,  # Request extra to handle any deduplication
            with_payload=True,
            with_vectors=False,
        )
        
        logger.debug(
            f"Scope {scope_label}: found {len(query_response.points)} results "
            f"(accumulated: {len(accumulated_results)})"
        )
        
        # Convert results to Document objects, deduplicating by ID
        for scored_point in query_response.points:
            if scored_point.id not in seen_ids:
                payload = scored_point.payload
                doc = Document(
                    page_content=payload["text"],
                    metadata={
                        "law_section": payload.get("law_section", ""),
                        "category": payload.get("category", ""),
                        "region": payload.get("region", ""),
                    },
                )
                accumulated_results.append(doc)
                seen_ids.add(scored_point.id)
        
        # If we have enough results, stop searching
        if len(accumulated_results) >= k:
            logger.debug(f"Stopping cascade at scope {scope_label}")
            break
    
    logger.info(f"retrieve() returning {len(accumulated_results)} docs for query: {query[:50]}")
    # Return exactly k results (or fewer if fewer available)
    return accumulated_results[:k]