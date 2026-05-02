"""
DriveLegal – scripts/preprocess.py
Reads raw text/PDF files from data/raw/, cleans them,
chunks them into ~300-token pieces, tags each chunk with
metadata, and writes data/processed/chunks.json.

Run:  python scripts/preprocess.py
"""

import json
import os
import re
import sys
import uuid
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain.text_splitter import RecursiveCharacterTextSplitter

RAW_DIR       = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
OUTPUT_FILE   = PROCESSED_DIR / "chunks.json"

# ── Metadata inference heuristics ─────────────────────────────────────────
REGION_HINTS = {
    "pune":         "Pune",
    "mumbai":       "Mumbai",
    "maharashtra":  "Maharashtra",
    "delhi":        "Delhi",
    "bangalore":    "Bangalore",
    "bengaluru":    "Bangalore",
    "karnataka":    "Karnataka",
    "india":        "National",
    "motor vehicles act": "National",
    "mva":          "National",
}

CATEGORY_HINTS = {
    "helmet":       "Safety Equipment",
    "seatbelt":     "Safety Equipment",
    "speed":        "Speed Violations",
    "drunk":        "Impaired Driving",
    "alcohol":      "Impaired Driving",
    "license":      "Documentation",
    "licence":      "Documentation",
    "insurance":    "Documentation",
    "registration": "Documentation",
    "signal":       "Traffic Signals",
    "red light":    "Traffic Signals",
    "parking":      "Parking",
    "overload":     "Vehicle Standards",
    "pollution":    "Vehicle Standards",
}

LAW_SECTION_PATTERNS = [
    r"section\s+(\d+[A-Za-z]*)",
    r"sec\.\s*(\d+[A-Za-z]*)",
    r"§\s*(\d+[A-Za-z]*)",
    r"rule\s+(\d+[A-Za-z]*)",
]


def infer_region(text: str, filename: str) -> str:
    combined = (text + " " + filename).lower()
    for hint, region in REGION_HINTS.items():
        if hint in combined:
            return region
    return "National"


def infer_category(text: str) -> str:
    tl = text.lower()
    for hint, category in CATEGORY_HINTS.items():
        if hint in tl:
            return category
    return "General"


def extract_law_section(text: str) -> str:
    for pattern in LAW_SECTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"Section {match.group(1)}"
    return ""


def clean_text(text: str) -> str:
    """Basic cleaning: collapse whitespace, remove control chars."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x20-\x7E\n]", "", text)
    return text.strip()


def load_raw_files() -> list[dict]:
    """Load all .txt and .md files from data/raw/."""
    documents = []
    if not RAW_DIR.exists():
        print(f"[WARN] {RAW_DIR} does not exist. Creating it.")
        RAW_DIR.mkdir(parents=True)
        return []

    for path in RAW_DIR.iterdir():
        if path.suffix in {".txt", ".md"}:
            content = path.read_text(encoding="utf-8", errors="ignore")
            documents.append({"filename": path.name, "content": clean_text(content)})
            print(f"  Loaded: {path.name} ({len(content):,} chars)")

    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,          # ~300 tokens
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", " "],
    )

    chunks = []
    for doc in documents:
        pieces = splitter.split_text(doc["content"])
        for i, piece in enumerate(pieces):
            chunk = {
                "id":          str(uuid.uuid4()),
                "text":        piece,
                "metadata": {
                    "source":       doc["filename"],
                    "chunk_index":  i,
                    "region":       infer_region(piece, doc["filename"]),
                    "category":     infer_category(piece),
                    "law_section":  extract_law_section(piece),
                    "fine_amount":  "",   # manually fill where needed
                },
            }
            chunks.append(chunk)

    return chunks


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading raw files…")
    docs = load_raw_files()

    if not docs:
        print("[ERROR] No raw files found in data/raw/. Add .txt or .md files and re-run.")
        sys.exit(1)

    print(f"Chunking {len(docs)} document(s)…")
    chunks = chunk_documents(docs)
    print(f"Generated {len(chunks)} chunks.")

    OUTPUT_FILE.write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved → {OUTPUT_FILE}")

    # Quick sample
    print("\n── Sample chunk ──")
    if chunks:
        sample = chunks[0]
        print(f"Text:     {sample['text'][:120]}…")
        print(f"Metadata: {sample['metadata']}")


if __name__ == "__main__":
    main()
