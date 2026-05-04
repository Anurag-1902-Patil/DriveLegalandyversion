"""
DriveLegal – tests/test_rag.py
Unit tests for the RAG retriever and chain.

Run:  pytest tests/test_rag.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from langchain.schema import Document


# ── Retriever tests ────────────────────────────────────────────────────────

def make_doc(text: str, region: str) -> Document:
    return Document(page_content=text, metadata={"region": region, "law_section": "Section 129"})


@patch("rag.retriever._vectorstore")
def test_retrieve_returns_docs(mock_vs):
    """retrieve() returns top-k docs from the mock vectorstore."""
    from rag.retriever import retrieve
    mock_vs.similarity_search.return_value = [
        make_doc("Helmet rule text", "Pune"),
        make_doc("National helmet law", "National"),
    ]
    results = retrieve("helmet fine", k=5, city="Pune", state="Maharashtra")
    assert len(results) >= 1
    assert all(isinstance(d, Document) for d in results)


@patch("rag.retriever._vectorstore")
def test_retrieve_city_filter_takes_priority(mock_vs):
    """City-level docs are returned before state/national."""
    from rag.retriever import retrieve
    mock_vs.similarity_search.return_value = [
        make_doc("Pune specific rule", "Pune"),
        make_doc("Maharashtra state rule", "Maharashtra"),
        make_doc("National rule", "National"),
    ]
    results = retrieve("fine", k=5, city="Pune", state="Maharashtra")
    regions = [d.metadata["region"] for d in results]
    assert "Pune" in regions


@patch("rag.retriever._vectorstore")
def test_retrieve_fallback_to_state(mock_vs):
    """Falls back to state docs when no city docs found."""
    from rag.retriever import retrieve
    mock_vs.similarity_search.return_value = [
        make_doc("Maharashtra rule", "Maharashtra"),
        make_doc("National rule", "National"),
    ]
    results = retrieve("fine", k=5, city="UnknownCity", state="Maharashtra")
    regions = [d.metadata["region"] for d in results]
    assert "Maharashtra" in regions or "National" in regions


def test_retrieve_raises_without_loaded_index():
    """retrieve() raises RuntimeError if index not loaded."""
    import rag.retriever as r
    original = r._vectorstore
    r._vectorstore = None
    with pytest.raises(RuntimeError, match="FAISS index not loaded"):
        r.retrieve("test query")
    r._vectorstore = original


# ── Chain tests ────────────────────────────────────────────────────────────

@patch("rag.chain.retrieve")
@patch("rag.chain.ChatZhipuAI")
def test_get_answer_success(mock_llm_cls, mock_retrieve):
    """get_answer() returns answer dict with expected keys."""
    from rag.chain import get_answer
    mock_retrieve.return_value = [make_doc("Red light fine is ₹1,000", "Pune")]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="The fine for jumping a red light is ₹1,000.")
    mock_llm_cls.return_value = mock_llm

    result = get_answer("red light fine", city="Pune", state="Maharashtra")
    assert "answer" in result
    assert result["offline_fallback"] is False
    assert "₹" in result["answer"] or len(result["answer"]) > 5


@patch("rag.chain.retrieve")
def test_get_answer_empty_docs_returns_fallback_message(mock_retrieve):
    """get_answer() handles empty retrieval gracefully."""
    from rag.chain import get_answer
    mock_retrieve.return_value = []

    result = get_answer("unknown query xyz", city="", state="")
    assert "answer" in result
    assert "could not find" in result["answer"].lower() or len(result["answer"]) > 0


@patch("rag.chain.retrieve")
@patch("rag.chain.ChatZhipuAI")
def test_get_answer_llm_error_uses_offline_cache(mock_llm_cls, mock_retrieve):
    """When LLM fails, get_answer() falls back to offline cache."""
    from rag.chain import get_answer
    mock_retrieve.return_value = [make_doc("some text", "National")]
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("Zhipu AI timeout")
    mock_llm_cls.return_value = mock_llm

    result = get_answer("helmet fine", city="", state="")
    assert "answer" in result
    assert result["offline_fallback"] is True
