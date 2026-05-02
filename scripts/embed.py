"""
DriveLegal – scripts/embed.py
Reads data/processed/chunks.json, embeds each chunk using
OpenAI text-embedding-ada-002, builds a FAISS index, and
saves it to data/faiss_index/.

Run:  python scripts/embed.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

CHUNKS_FILE  = Path("data/processed/chunks.json")
INDEX_PATH   = Path("data/faiss_index")
BATCH_SIZE   = 100   # embed N chunks at a time (avoids rate limits)


def load_chunks() -> list[Document]:
    if not CHUNKS_FILE.exists():
        print(f"[ERROR] {CHUNKS_FILE} not found. Run scripts/preprocess.py first.")
        sys.exit(1)

    raw = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    docs = [
        Document(
            page_content=chunk["text"],
            metadata=chunk["metadata"],
        )
        for chunk in raw
        if chunk.get("text", "").strip()
    ]
    print(f"Loaded {len(docs)} chunks from {CHUNKS_FILE}")
    return docs


def build_index(docs: list[Document]) -> FAISS:
    embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")

    print(f"Embedding {len(docs)} chunks in batches of {BATCH_SIZE}…")
    # Build index from the first batch, then add subsequent batches
    first_batch = docs[:BATCH_SIZE]
    vectorstore = FAISS.from_documents(first_batch, embeddings)
    print(f"  Batch 1/{-(-len(docs) // BATCH_SIZE)} done")

    for i, start in enumerate(range(BATCH_SIZE, len(docs), BATCH_SIZE), start=2):
        batch = docs[start : start + BATCH_SIZE]
        vectorstore.add_documents(batch)
        print(f"  Batch {i}/{-(-len(docs) // BATCH_SIZE)} done")

    return vectorstore


def test_retrieval(vectorstore: FAISS) -> None:
    print("\n── Retrieval test ──")
    test_query = "fine for jumping a red light in Pune on a bike"
    results = vectorstore.similarity_search(test_query, k=3)
    for j, r in enumerate(results, 1):
        print(f"  Result {j} | region={r.metadata.get('region')} | {r.page_content[:100]}…")


def main():
    docs = load_chunks()

    vectorstore = build_index(docs)

    INDEX_PATH.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(INDEX_PATH))
    print(f"\nFAISS index saved → {INDEX_PATH}/")

    test_retrieval(vectorstore)
    print("\nEmbedding complete. ✓")


if __name__ == "__main__":
    main()
