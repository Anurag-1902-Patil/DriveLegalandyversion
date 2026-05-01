"""
DriveLegal – RAG Chain
Builds the LangChain RetrievalQA pipeline.  If OpenAI is unavailable,
falls back to the offline JSON cache.
"""

import json
import logging
import os
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS

from rag.retriever import retrieve, load_index

logger = logging.getLogger("drivelegal.chain")

CACHE_PATH = os.path.join("data", "cache.json")

# ── System / prompt template ───────────────────────────────────────────────
SYSTEM_TEMPLATE = """You are DriveLegal, an AI road safety assistant for India.
Use ONLY the context provided below to answer the question.
If the context does not contain enough information, say:
  "I could not find specific data for your location. Please verify with the official RTO."
Never invent fine amounts or law sections.
Always mention if a rule is national (Motor Vehicles Act 1988) vs state-specific.

Context:
{context}

Question: {question}

Answer clearly and concisely in 2–4 sentences. If a fine is mentioned, state it with the disclaimer that amounts are indicative."""

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template=SYSTEM_TEMPLATE,
)


def _load_cache() -> list:
    """Load the offline Q&A cache from disk."""
    if not os.path.exists(CACHE_PATH):
        return []
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _offline_fallback(query: str) -> Dict[str, Any]:
    """
    Simple keyword-match against the pre-cached Q&A pairs.
    Returns the best match or a generic fallback message.
    """
    cache = _load_cache()
    query_lower = query.lower()

    best, best_score = None, 0
    for entry in cache:
        keywords = entry.get("keywords", [])
        score = sum(1 for kw in keywords if kw.lower() in query_lower)
        if score > best_score:
            best, best_score = entry, score

    if best and best_score > 0:
        return {
            "answer": best["answer"],
            "sources": [],
            "offline_fallback": True,
        }

    return {
        "answer": (
            "I currently cannot reach the AI service. "
            "Please check your connection or try again shortly. "
            "For urgent queries, visit the official MoRTH website: https://morth.nic.in"
        ),
        "sources": [],
        "offline_fallback": True,
    }


def get_answer(query: str, city: str, state: str, country: str = "India") -> Dict[str, Any]:
    """
    Run the full RAG pipeline for a given query + location.
    Falls back to the offline cache if OpenAI is unavailable.
    """
    try:
        # ── 1. Retrieve relevant chunks ────────────────────────────────────
        docs = retrieve(query, k=5, city=city, state=state, country=country)

        if not docs:
            return {
                "answer": "I could not find specific data for your location. Please verify with the official RTO.",
                "sources": [],
                "offline_fallback": False,
            }

        # ── 2. Build context string ────────────────────────────────────────
        context = "\n\n".join(
            f"[{d.metadata.get('region', 'India')} | {d.metadata.get('law_section', '')}]\n{d.page_content}"
            for d in docs
        )

        # ── 3. Call LLM ────────────────────────────────────────────────────
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        prompt = QA_PROMPT.format(context=context, question=query)
        response = llm.invoke(prompt)

        return {
            "answer": response.content.strip(),
            "sources": docs,
            "offline_fallback": False,
        }

    except Exception as exc:
        logger.warning(f"LLM call failed, using offline cache. Reason: {exc}")
        return _offline_fallback(query)