"""
DriveLegal – scripts/migrate_to_qdrant.py
One-time migration script: reads chunks.json, generates embeddings, uploads to Qdrant.

Changes from FAISS:
- Uses qdrant-client in local embedded mode (data persisted to disk at data/qdrant_db/)
- Reads all chunks from data/processed/chunks.json
- Embeds via HuggingFace all-MiniLM-L6-v2 (same as FAISS version)
- Creates Qdrant collection "drivelegal_chunks" with structured payloads
- Payload fields: text, law_section, category, region (for native filtering)
- Run once: python scripts/migrate_to_qdrant.py
"""

import json
import logging
import os
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

# ── Configuration ──────────────────────────────────────────────────────────
CHUNKS_PATH = os.path.join("data", "processed", "chunks.json")
QDRANT_PATH = os.path.join("data", "qdrant_db")
COLLECTION_NAME = "drivelegal_chunks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 embedding dimension
BATCH_SIZE = 100

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("migrate_to_qdrant")


def load_chunks() -> List[dict]:
    """Load all chunks from data/processed/chunks.json."""
    if not os.path.exists(CHUNKS_PATH):
        raise FileNotFoundError(f"Chunks file not found: {CHUNKS_PATH}")
    
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    logger.info(f"Loaded {len(chunks)} chunks from {CHUNKS_PATH}")
    return chunks


def embed_chunks(chunks: List[dict]) -> List[dict]:
    """Generate embeddings for all chunks using HuggingFace model."""
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    
    # Extract texts
    texts = [chunk["text"] for chunk in chunks]
    
    logger.info(f"Encoding {len(texts)} chunks...")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    
    logger.info(f"Embedding complete. Shape: {embeddings.shape}")
    return embeddings.tolist()


def migrate_to_qdrant(chunks: List[dict], embeddings: List[List[float]]) -> None:
    """Create Qdrant collection and upload all chunks with embeddings."""
    
    # Initialize Qdrant client in local embedded mode
    logger.info(f"Initializing Qdrant at {QDRANT_PATH}")
    os.makedirs(QDRANT_PATH, exist_ok=True)
    client = QdrantClient(path=QDRANT_PATH)
    
    # Recreate collection (delete if exists)
    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info(f"Deleted existing collection: {COLLECTION_NAME}")
    except Exception:
        pass
    
    # Create new collection with vector config
    logger.info(f"Creating collection: {COLLECTION_NAME}")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    
    # Prepare points (ID, vector, payload)
    logger.info("Preparing points for upload...")
    points = []
    
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point = PointStruct(
            id=idx,  # Use sequential ID (Qdrant requires unique integer IDs)
            vector=embedding,
            payload={
                "text": chunk["text"],
                "law_section": chunk["metadata"].get("law_section", ""),
                "category": chunk["metadata"].get("category", ""),
                "region": chunk["metadata"].get("region", ""),
            },
        )
        points.append(point)
    
    # Upload points in batches
    logger.info(f"Uploading {len(points)} points in batches of {BATCH_SIZE}...")
    for i in range(0, len(points), BATCH_SIZE):
        batch = points[i : i + BATCH_SIZE]
        client.upsert(collection_name=COLLECTION_NAME, points=batch)
        logger.info(f"  Uploaded batch {i // BATCH_SIZE + 1} ({len(batch)} points)")
    
    # Verify
    collection_info = client.get_collection(COLLECTION_NAME)
    logger.info(
        f"Migration complete! Collection '{COLLECTION_NAME}' has "
        f"{collection_info.points_count} points."
    )


def main():
    """Run the full migration pipeline."""
    try:
        # Step 1: Load chunks
        chunks = load_chunks()
        
        # Step 2: Generate embeddings
        embeddings = embed_chunks(chunks)
        
        # Step 3: Upload to Qdrant
        migrate_to_qdrant(chunks, embeddings)
        
        logger.info("✓ Migration to Qdrant completed successfully!")
        
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
