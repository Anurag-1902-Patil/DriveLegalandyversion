"""
DriveLegal – scripts/ingest_treaties.py
One-shot script: reads only the three international treaty text files from
data/raw/, chunks them, tags every chunk with corpus_tier="treaty", embeds
them, and UPSERTS them into the existing Qdrant collection.

Unlike migrate_to_qdrant.py this script does NOT wipe the collection — it
adds treaty chunks alongside the existing national/state corpus.

Treaty files expected in data/raw/:
  - vienna_convention_1968.txt
  - un_model_road_safety_legislation.txt
  - eu_directive_2015_413.txt

Run once after the normal migration:
  python scripts/ingest_treaties.py

Re-running is safe: Qdrant upsert is idempotent on the same point IDs.
"""

import hashlib
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import List

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain.text_splitter import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer

# ── Configuration ──────────────────────────────────────────────────────────
RAW_DIR         = Path("data/raw")
QDRANT_PATH     = os.path.join("data", "qdrant_db")
COLLECTION_NAME = "drivelegal_chunks"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE      = 50

# Maps filename stem → canonical region tag (must match preprocess.py REGION_HINTS)
TREATY_FILES: dict[str, str] = {
    "vienna_convention_1968":          "Vienna Convention on Road Traffic",
    "un_model_road_safety_legislation": "UN Model Road Safety Legislation",
    "eu_directive_2015_413":           "EU Directive 2015/413",
}

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("ingest_treaties")


def _stable_uuid(seed: str) -> str:
    """Generate a deterministic UUID from a string seed.

    Using a stable ID means re-running the script upserts (not duplicates)
    the same chunks.
    """
    return str(uuid.UUID(bytes=hashlib.md5(seed.encode()).digest()))


def load_treaty_files() -> List[dict]:
    """Read treaty text files and return raw document dicts."""
    documents = []
    for stem, region in TREATY_FILES.items():
        path = RAW_DIR / f"{stem}.txt"
        if not path.exists():
            logger.warning(f"Treaty file not found (skipping): {path}")
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        content = " ".join(content.split())  # collapse whitespace
        if len(content) < 50:
            logger.warning(f"Treaty file too short (skipping): {path}")
            continue
        logger.info(f"Loaded '{stem}' — {len(content):,} chars → region='{region}'")
        documents.append({"stem": stem, "region": region, "content": content})
    return documents


def chunk_documents(documents: List[dict]) -> List[dict]:
    """Chunk treaty documents and tag each chunk with corpus_tier='treaty'."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=60,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = []
    for doc in documents:
        pieces = splitter.split_text(doc["content"])
        for i, piece in enumerate(pieces):
            # Stable ID: hash of (stem, chunk_index) so re-runs don't duplicate
            seed = f"{doc['stem']}::{i}"
            chunks.append({
                "id":   _stable_uuid(seed),
                "text": piece,
                "metadata": {
                    "source":      f"{doc['stem']}.txt",
                    "chunk_index": i,
                    "region":      doc["region"],
                    "category":    "International Treaty",
                    "law_section": "",
                    "corpus_tier": "treaty",
                },
            })
        logger.info(f"  '{doc['stem']}' → {len(pieces)} chunks")
    logger.info(f"Total treaty chunks generated: {len(chunks)}")
    return chunks


def embed_chunks(chunks: List[dict]) -> List[List[float]]:
    """Embed all chunks using the same model as the main collection."""
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = [c["text"] for c in chunks]
    logger.info(f"Encoding {len(texts)} treaty chunks...")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    logger.info(f"Embedding complete. Shape: {embeddings.shape}")
    return embeddings.tolist()


def upsert_to_qdrant(chunks: List[dict], embeddings: List[List[float]]) -> None:
    """Upsert treaty chunks into the existing Qdrant collection.

    Uses Qdrant's upsert (not insert) so the script is idempotent: re-running
    it replaces existing points with the same ID rather than creating duplicates.
    """
    logger.info(f"Connecting to Qdrant at: {QDRANT_PATH}")
    client = QdrantClient(path=QDRANT_PATH)

    # Verify the target collection exists
    try:
        info = client.get_collection(COLLECTION_NAME)
        logger.info(
            f"Collection '{COLLECTION_NAME}' found — {info.points_count} existing points."
        )
    except Exception as e:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' not found at {QDRANT_PATH}. "
            f"Run python scripts/migrate_to_qdrant.py first.\nError: {e}"
        )

    # Build PointStructs — IDs must be integers for Qdrant, so we convert the
    # stable UUID to a large integer via its first 8 bytes.
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        # Convert UUID hex to a 64-bit integer (Qdrant supports uint64 IDs)
        uid_int = int(chunk["id"].replace("-", ""), 16) % (2 ** 63)
        point = PointStruct(
            id=uid_int,
            vector=embedding,
            payload={
                "text":        chunk["text"],
                "law_section": chunk["metadata"]["law_section"],
                "category":    chunk["metadata"]["category"],
                "region":      chunk["metadata"]["region"],
                "corpus_tier": chunk["metadata"]["corpus_tier"],
            },
        )
        points.append(point)

    logger.info(f"Upserting {len(points)} treaty points in batches of {BATCH_SIZE}...")
    for i in range(0, len(points), BATCH_SIZE):
        batch = points[i : i + BATCH_SIZE]
        client.upsert(collection_name=COLLECTION_NAME, points=batch)
        logger.info(f"  Upserted batch {i // BATCH_SIZE + 1} ({len(batch)} points)")

    info_after = client.get_collection(COLLECTION_NAME)
    logger.info(
        f"Upsert complete. Collection '{COLLECTION_NAME}' now has "
        f"{info_after.points_count} points."
    )


def main():
    logger.info("=== DriveLegal Treaty Corpus Ingestion ===")

    # Step 1: Load treaty files
    docs = load_treaty_files()
    if not docs:
        logger.error(
            "No treaty files found in data/raw/. "
            "Expected: vienna_convention_1968.txt, "
            "un_model_road_safety_legislation.txt, eu_directive_2015_413.txt"
        )
        sys.exit(1)

    # Step 2: Chunk
    chunks = chunk_documents(docs)

    # Step 3: Embed
    embeddings = embed_chunks(chunks)

    # Step 4: Upsert to Qdrant
    upsert_to_qdrant(chunks, embeddings)

    logger.info("✓ Treaty corpus ingestion completed successfully!")
    logger.info(
        "Next step: restart the DriveLegal API server so the updated "
        "Qdrant index is loaded into memory."
    )


if __name__ == "__main__":
    main()
