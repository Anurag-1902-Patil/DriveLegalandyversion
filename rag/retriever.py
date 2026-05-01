"""
DriveLegal – FAISS Retriever
Loads the pre-built FAISS index from disk (once at startup) and exposes
a retrieve() function that returns the top-k most relevant law chunks,
filtered by location metadata.
"""

import os
import logging
from typing import List, Optional

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document

logger = logging.getLogger("drivelegal.retriever")

INDEX_PATH = os.path.join("data", "faiss_index")
_vectorstore: Optional[FAISS] = None          # module-level singleton


def load_index() -> None:
    """Load (or reload) the FAISS index from disk into the singleton."""
    global _vectorstore
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
    _vectorstore = FAISS.load_local(
        INDEX_PATH,
        embeddings,
        allow_dangerous_deserialization=True,   # safe: we own the index
    )
    logger.info(f"FAISS index loaded from {INDEX_PATH}")


def retrieve(
    query: str,
    k: int = 5,
    city: str = "",
    state: str = "",
    country: str = "India",
    similarity_threshold: float = 0.75,
) -> List[Document]:
    """
    Return top-k relevant law chunks for `query`, filtered by location.

    Location fallback cascade:
        city  →  state  →  country  →  no filter (national rules)
    """
    if _vectorstore is None:
        raise RuntimeError("FAISS index not loaded. Call load_index() first.")

    # Retrieve more than k so we can apply metadata filter afterwards
    candidates: List[Document] = _vectorstore.similarity_search(query, k=k * 3)

    # ── Location filter (cascade) ──────────────────────────────────────────
    def matches(doc: Document, scope: str) -> bool:
        return doc.metadata.get("region", "").lower() == scope.lower()

    for scope in [city, state, country, ""]:
        filtered = [d for d in candidates if matches(d, scope)] if scope else candidates
        if filtered:
            return filtered[:k]

    return candidates[:k]