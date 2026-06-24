#!/usr/bin/env python
"""Quick test of Qdrant retrieval"""
from rag.retriever import load_index, retrieve

print("Loading Qdrant index...")
load_index()

print("\nTesting query: 'penalty for using phone while driving'")
results = retrieve('penalty for using phone while driving', k=5, city='', state='', country='India')

print(f"Results found: {len(results)}")
for i, doc in enumerate(results[:3]):
    print(f"\n--- Result {i+1} ---")
    print(f"Text: {doc.page_content[:200]}")
    print(f"Region: {doc.metadata.get('region')}")
    print(f"Category: {doc.metadata.get('category')}")
