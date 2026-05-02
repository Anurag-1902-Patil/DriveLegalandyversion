"""
DriveLegal – rag/retriever.py
Loads the FAISS index using FREE local sentence-transformers embeddings.
No OpenAI API key needed for retrieval.
"""

import logging
import os
from typing import List, Optional

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document

logger = logging.getLogger("drivelegal.retriever")

INDEX_PATH = os.path.join("data", "faiss_index")
_vectorstore: Optional[FAISS] = None   # singleton


def load_index() -> None:
    """Load FAISS index from disk using local embeddings (no API key needed)."""
    global _vectorstore
    logger.info("Loading local embedding model...")
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    _vectorstore = FAISS.load_local(
        INDEX_PATH,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    logger.info(f"FAISS index loaded from {INDEX_PATH}")


def retrieve(
    query: str,
    k: int = 5,
    city: str = "",
    state: str = "",
    country: str = "India",
) -> List[Document]:
    """
    Return top-k relevant law chunks, filtered by location.
    Fallback cascade: city -> state -> country -> no filter
    """
    if _vectorstore is None:
        raise RuntimeError("FAISS index not loaded. Call load_index() first.")

    candidates: List[Document] = _vectorstore.similarity_search(query, k=k * 3)

    def matches(doc: Document, scope: str) -> bool:
        return doc.metadata.get("region", "").lower() == scope.lower()

    for scope in [city, state, country, ""]:
        filtered = [d for d in candidates if matches(d, scope)] if scope else candidates
        if filtered:
            return filtered[:k]

    return candidates[:k]