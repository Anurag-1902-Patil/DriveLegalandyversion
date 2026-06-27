"""
DriveLegal – scripts/cache_rules.py
Generates / refreshes the offline Q&A cache (data/cache.json)
by running the top-50 most common queries through the live RAG
pipeline and saving the answers.

Use this to pre-populate cache.json before deployment so that
offline fallback has fresh, accurate content.

Run:  python scripts/cache_rules.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.retriever import load_index
from rag.chain import get_answer

OUTPUT_FILE = Path("data/cache.json")

# ── Seed queries that cover the most common traffic law questions ──────────
SEED_QUERIES = [
    {"keywords": ["red light", "signal", "pune"],         "query": "Fine for jumping a red light in Pune", "location": {"city": "Pune", "state": "Maharashtra"}},
    {"keywords": ["helmet", "bike", "pune"],              "query": "Fine for riding without helmet in Pune", "location": {"city": "Pune", "state": "Maharashtra"}},
    {"keywords": ["seatbelt", "car"],                     "query": "Fine for not wearing seatbelt in a car in Maharashtra", "location": {"city": "Mumbai", "state": "Maharashtra"}},
    {"keywords": ["drunk driving", "alcohol", "dui"],     "query": "Penalty for drunk driving in India", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["mobile phone", "phone", "driving"],    "query": "Fine for using mobile phone while driving", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["speeding", "over speed"],              "query": "Speed limit and fine for overspeeding in India", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["insurance", "no insurance"],           "query": "Penalty for driving without insurance", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["license", "no license"],               "query": "Fine for driving without a valid licence", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["registration", "rc book"],             "query": "Fine for driving without vehicle registration", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["triple riding", "three persons"],      "query": "Fine for triple riding on a two-wheeler", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["pollution", "puc"],                    "query": "Penalty for not having PUC certificate", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["wrong way", "one way"],                "query": "Fine for driving on the wrong side of the road", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["overloading", "excess load"],          "query": "Fine for vehicle overloading", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["parking", "no parking"],               "query": "Parking violation fine in Mumbai", "location": {"city": "Mumbai", "state": "Maharashtra"}},
    {"keywords": ["speed limit", "highway"],              "query": "Speed limits on national highways in India", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["minor driving", "underage"],           "query": "Penalty for underage driving in India", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["accident", "hit and run"],             "query": "What to do after a road accident in India", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["challan", "e-challan", "pay"],         "query": "How to pay an e-challan online", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["number plate", "registration plate"],  "query": "Rules for number plates in India", "location": {"city": "", "state": "", "country": "India"}},
    {"keywords": ["lane change", "overtaking"],           "query": "Rules for lane changing and overtaking in India", "location": {"city": "", "state": "", "country": "India"}},
]


def main():
    print("Loading Qdrant index…")
    load_index()

    cache = []
    for i, item in enumerate(SEED_QUERIES, 1):
        loc = item["location"]
        print(f"  [{i}/{len(SEED_QUERIES)}] {item['query']}")
        try:
            result = get_answer(
                query=item["query"],
                city=loc.get("city", ""),
                state=loc.get("state", ""),
                country=loc.get("country", "India"),
            )
            cache.append({
                "id":       i,
                "keywords": item["keywords"],
                "query":    item["query"],
                "answer":   result["answer"],
            })
        except Exception as exc:
            print(f"    [WARN] Failed: {exc}")

    OUTPUT_FILE.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nCache saved → {OUTPUT_FILE} ({len(cache)} entries)")


if __name__ == "__main__":
    main()
