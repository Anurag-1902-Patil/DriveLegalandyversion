"""
DriveLegal – scripts/preprocess.py
Reads raw files from data/raw/, cleans and chunks them,
tags each chunk with metadata, and writes data/processed/chunks.json.

Supported file types:
  .txt, .md   — plain text
  .pdf        — extracts text from each page
  .csv        — each row becomes a text chunk

Run:  python scripts/preprocess.py
"""

import csv
import json
import os
import re
import sys
import uuid
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pdfplumber
except ImportError:
    print("[ERROR] pdfplumber not installed. Run: pip install pdfplumber")
    sys.exit(1)

from langchain.text_splitter import RecursiveCharacterTextSplitter

RAW_DIR       = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
OUTPUT_FILE   = PROCESSED_DIR / "chunks.json"

REGION_HINTS = {
    "pune": "Pune", "mumbai": "Mumbai", "maharashtra": "Maharashtra",
    "delhi": "Delhi", "bangalore": "Bangalore", "bengaluru": "Bangalore",
    "karnataka": "Karnataka", "chennai": "Chennai", "tamil nadu": "Tamil Nadu",
    "hyderabad": "Hyderabad", "telangana": "Telangana",
    "ahmedabad": "Ahmedabad", "gujarat": "Gujarat",
    "kolkata": "Kolkata", "west bengal": "West Bengal",
    "india": "National", "motor vehicles act": "National",
    "mva": "National", "morth": "National", "national": "National",
    # ── International Treaty Tier ─────────────────────────────────────────
    "vienna convention": "Vienna Convention on Road Traffic",
    "vienna_convention_1968": "Vienna Convention on Road Traffic",
    "united nations model": "UN Model Road Safety Legislation",
    "un model": "UN Model Road Safety Legislation",
    "un_model_road_safety": "UN Model Road Safety Legislation",
    "un secretary-general": "UN Model Road Safety Legislation",
    "decade of action for road safety": "UN Model Road Safety Legislation",
    "eu directive 2015": "EU Directive 2015/413",
    "eu_directive_2015_413": "EU Directive 2015/413",
    "directive 2015/413": "EU Directive 2015/413",
    "cross-border enforcement": "EU Directive 2015/413",
    "cross-border exchange": "EU Directive 2015/413",
    "vehicle registration data": "EU Directive 2015/413",
    "contracting part": "Vienna Convention on Road Traffic",  # covers "Contracting Party/ies"
    "signatory": "Vienna Convention on Road Traffic",
}

CATEGORY_HINTS = {
    "helmet": "Safety Equipment", "seatbelt": "Safety Equipment", "seat belt": "Safety Equipment",
    "speed": "Speed Violations", "drunk": "Impaired Driving", "alcohol": "Impaired Driving",
    "license": "Documentation", "licence": "Documentation", "insurance": "Documentation",
    "registration": "Documentation", "rc book": "Documentation",
    "signal": "Traffic Signals", "red light": "Traffic Signals", "traffic light": "Traffic Signals",
    "parking": "Parking", "overload": "Vehicle Standards", "pollution": "Vehicle Standards",
    "puc": "Vehicle Standards", "emission": "Vehicle Standards",
    "mobile": "Distracted Driving", "phone": "Distracted Driving",
    "overtaking": "Road Behaviour", "lane": "Road Behaviour", "pedestrian": "Road Behaviour",
    "accident": "Accident Procedures", "hit and run": "Accident Procedures",
    "challan": "Enforcement", "fine": "Enforcement", "penalty": "Enforcement",
    # ── Treaty-specific category hints ──────────────────────────────────
    "right-hand traffic": "Road Behaviour", "priority road": "Road Behaviour",
    "right of way": "Road Behaviour", "yield": "Road Behaviour",
    "motorway": "Road Behaviour", "carriageway": "Road Behaviour",
    "cross-border": "Enforcement", "mutual recognition": "Enforcement",
    "blood alcohol": "Impaired Driving", "bac": "Impaired Driving",
    "breath test": "Impaired Driving", "drug-impaired": "Impaired Driving",
    "child restraint": "Safety Equipment", "booster seat": "Safety Equipment",
    "international driving permit": "Documentation", "idp": "Documentation",
    "domestic driving permit": "Documentation",
    "vehicle registration data": "Documentation",
    "contracting party": "International Treaty", "signatory": "International Treaty",
    "member state": "International Treaty", "directive": "International Treaty",
    "speed limiter": "Vehicle Standards", "anti-lock": "Vehicle Standards",
    "electronic stability": "Vehicle Standards", "automatic emergency": "Vehicle Standards",
}

LAW_PATTERNS = [
    r"section\s+(\d+[A-Za-z]*)", r"sec\.\s*(\d+[A-Za-z]*)",
    r"rule\s+(\d+[A-Za-z]*)", r"article\s+(\d+[A-Za-z]*)",
    r"annex\s+(\d+[A-Za-z]*)", r"part\s+(I{1,3}V?|VI{0,3}|\d+[A-Za-z]*)",
]

# ── Treaty corpus tier helpers ─────────────────────────────────────────────
TREATY_REGION_NAMES = {
    "Vienna Convention on Road Traffic",
    "UN Model Road Safety Legislation",
    "EU Directive 2015/413",
}


def infer_corpus_tier(region: str) -> str:
    """Return 'treaty', 'national', 'state', or 'city' based on region tag."""
    if region in TREATY_REGION_NAMES:
        return "treaty"
    if region == "National":
        return "national"
    # Heuristic: known Indian state names → 'state'; everything else → 'city'
    known_states = {
        "Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
        "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
        "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
        "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
        "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
        "J&K", "Delhi",
    }
    if region in known_states:
        return "state"
    return "city"


def infer_region(text, filename):
    combined = (text + " " + filename).lower()
    for hint, region in REGION_HINTS.items():
        if hint in combined:
            return region
    return "National"


def infer_category(text):
    tl = text.lower()
    for hint, cat in CATEGORY_HINTS.items():
        if hint in tl:
            return cat
    return "General"


def extract_law_section(text):
    for p in LAW_PATTERNS:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return f"Section {m.group(1)}"
    return ""


def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x20-\x7E\n]", "", text)
    return text.strip()


def load_pdf(path):
    pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text and text.strip():
                    pages.append(f"[Page {i+1}]\n{text}")
        print(f"    Extracted {len(pages)} pages")
    except Exception as e:
        print(f"    [WARN] Could not read PDF: {e}")
    return "\n\n".join(pages)


def load_csv(path):
    rows = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                parts = [f"{k}: {v.strip()}" for k, v in row.items() if v and v.strip()]
                if parts:
                    rows.append(" | ".join(parts))
        print(f"    Extracted {len(rows)} rows")
    except Exception as e:
        print(f"    [WARN] Could not read CSV: {e}")
    return "\n".join(rows)


def load_raw_files():
    documents = []
    if not RAW_DIR.exists():
        RAW_DIR.mkdir(parents=True)
        return []

    supported = {".txt", ".md", ".pdf", ".csv"}
    for path in sorted(RAW_DIR.iterdir()):
        if path.suffix.lower() not in supported:
            continue
        print(f"  Loading: {path.name}")
        if path.suffix.lower() in {".txt", ".md"}:
            content = path.read_text(encoding="utf-8", errors="ignore")
        elif path.suffix.lower() == ".pdf":
            content = load_pdf(path)
        elif path.suffix.lower() == ".csv":
            content = load_csv(path)
        else:
            continue
        content = clean_text(content)
        if len(content) < 20:
            print(f"    [WARN] Too little content, skipping.")
            continue
        documents.append({"filename": path.name, "filetype": path.suffix.lower(), "content": content})
        print(f"    {len(content):,} characters")
    return documents


def chunk_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400, chunk_overlap=60,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = []
    for doc in documents:
        for i, piece in enumerate(splitter.split_text(doc["content"])):
            region = infer_region(piece, doc["filename"])
            chunks.append({
                "id": str(uuid.uuid4()),
                "text": piece,
                "metadata": {
                    "source":      doc["filename"],
                    "filetype":    doc["filetype"],
                    "chunk_index": i,
                    "region":      region,
                    "category":    infer_category(piece),
                    "law_section": extract_law_section(piece),
                    "corpus_tier": infer_corpus_tier(region),  # NEW
                },
            })
    return chunks


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nLoading files from: {RAW_DIR.resolve()}")
    print("-" * 40)

    docs = load_raw_files()
    if not docs:
        print("\n[ERROR] No supported files in data/raw/")
        print("Add .txt, .pdf, or .csv files and re-run.")
        sys.exit(1)

    print(f"\nLoaded {len(docs)} file(s). Chunking...")
    chunks = chunk_documents(docs)
    print(f"Generated {len(chunks)} chunks.")

    OUTPUT_FILE.write_text(json.dumps(chunks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved -> {OUTPUT_FILE}")

    regions = Counter(c["metadata"]["region"] for c in chunks)
    print("\n-- Chunks by region --")
    for r, n in regions.most_common():
        print(f"  {r}: {n}")

    cats = Counter(c["metadata"]["category"] for c in chunks)
    print("\n-- Chunks by category --")
    for c, n in cats.most_common():
        print(f"  {c}: {n}")

    print("\nPreprocessing complete!")


if __name__ == "__main__":
    main()