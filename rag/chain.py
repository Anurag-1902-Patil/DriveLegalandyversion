"""
DriveLegal – rag/chain.py
RAG chain using local Ollama (Mistral) with offline fallback and fuzzy keyword matching.
"""

import json
import logging
import os
from typing import Any, Dict

from langchain_community.chat_models import ChatOllama
from langchain.prompts import PromptTemplate
from rag.retriever import retrieve

logger = logging.getLogger("drivelegal.chain")
CACHE_PATH = os.path.join("data", "cache.json")

SYSTEM_TEMPLATE = """You are DriveLegal, an AI road safety assistant for India.
Use ONLY the context provided below to answer the question.
If the context does not contain enough information, say:
  "I could not find specific data for your location. Please verify with the official RTO."
Never invent fine amounts or law sections.
Always mention if a rule is national (Motor Vehicles Act 1988) vs state-specific.

Context:
{context}

Question: {question}

Answer clearly and concisely in 2-4 sentences. If a fine is mentioned, state it with the disclaimer that amounts are indicative."""

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template=SYSTEM_TEMPLATE,
)


def _load_cache() -> list:
    if not os.path.exists(CACHE_PATH):
        return []
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize(text: str) -> str:
    """Normalize text for better matching."""
    replacements = {
        "drinking and driving": "drunk driving",
        "drinking & driving": "drunk driving",
        "drink driving": "drunk driving",
        "drunken driving": "drunk driving",
        "two wheeler": "bike",
        "two-wheeler": "bike",
        "motorbike": "bike",
        "motorcycle": "bike",
        "four wheeler": "car",
        "four-wheeler": "car",
        "seatbelt": "seat belt",
        "licence": "license",
        "no helmet": "helmet",
        "without helmet": "helmet",
        "jumping red light": "red light",
        "running red light": "red light",
        "jump signal": "red light",
        "traffic signal": "signal",
        "traffic light": "signal",
        "mobile phone": "mobile",
        "cell phone": "mobile",
        "using phone": "mobile",
        "puc certificate": "pollution",
        "pollution certificate": "pollution",
        "rc book": "registration",
        "vehicle registration": "registration",
        "driving licence": "license",
        "driving license": "license",
    }
    text = text.lower()
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _offline_fallback(query: str) -> Dict[str, Any]:
    """Keyword match against cache with normalization."""
    cache = _load_cache()
    normalized_query = _normalize(query)

    best, best_score = None, 0
    for entry in cache:
        keywords = entry.get("keywords", [])
        score = sum(1 for kw in keywords if _normalize(kw) in normalized_query)
        if score > best_score:
            best, best_score = entry, score

    if best and best_score > 0:
        return {
            "answer": best["answer"],
            "sources": [],
            "offline_fallback": True,
        }

    # Last resort — search FAISS even in offline mode
    try:
        docs = retrieve(normalized_query, k=3)
        if docs:
            best_doc = docs[0]
            return {
                "answer": (
                    f"{best_doc.page_content[:300]}... "
                    f"(Source: {best_doc.metadata.get('source', 'Traffic Law Database')})"
                ),
                "sources": docs,
                "offline_fallback": True,
            }
    except Exception:
        pass

    return {
        "answer": (
            "I could not find specific information for your query. "
            "Please verify with the official RTO or visit https://morth.nic.in"
        ),
        "sources": [],
        "offline_fallback": True,
    }


def get_answer(query: str, city: str, state: str, country: str = "India") -> Dict[str, Any]:
    """Run RAG pipeline. Falls back to offline cache if Ollama (Mistral) unavailable."""
    try:
        docs = retrieve(query, k=5, city=city, state=state, country=country)

        if not docs:
            return {
                "answer": "I could not find specific data for your location. Please verify with the official RTO.",
                "sources": [],
                "offline_fallback": False,
            }

        context = "\n\n".join(
            f"[{d.metadata.get('region', 'India')} | {d.metadata.get('law_section', '')}]\n{d.page_content}"
            for d in docs
        )

        llm = ChatOllama(model="mistral", temperature=0)
        prompt = QA_PROMPT.format(context=context, question=query)
        response = llm.invoke(prompt)

        return {
            "answer": response.content.strip(),
            "sources": docs,
            "offline_fallback": False,
        }

    except Exception as exc:
        logger.warning(f"LLM unavailable, using offline fallback. Reason: {exc}")
        return _offline_fallback(query)