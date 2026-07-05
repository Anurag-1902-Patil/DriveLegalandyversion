"""
DriveLegal – tests/test_api.py
Integration tests for the FastAPI endpoints.

Run:  pytest tests/test_api.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Patch load_index so the app starts without loading the Qdrant index
with patch("rag.retriever.load_index"):
    from app.main import app

client = TestClient(app)

VALID_PAYLOAD = {
    "message": "What is the fine for jumping a red light?",
    "location": {
        "city":    "Pune",
        "state":   "Maharashtra",
        "country": "India",
    },
}


# ── Health check ───────────────────────────────────────────────────────────

def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── /chat validation ───────────────────────────────────────────────────────

def test_chat_rejects_empty_message():
    payload = {**VALID_PAYLOAD, "message": "  "}
    resp = client.post("/chat", json=payload)
    assert resp.status_code in (422, 400)


def test_chat_rejects_missing_location():
    payload = {"message": "fine for no helmet"}
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 422


def test_chat_rejects_too_short_message():
    payload = {**VALID_PAYLOAD, "message": "hi"}
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 422


# ── /chat happy path ───────────────────────────────────────────────────────

@patch("app.routes.chat.get_answer")
@patch("app.routes.chat.lookup_fine")
def test_chat_returns_expected_structure(mock_fine, mock_answer):
    mock_answer.return_value = {
        "answer":           "The fine for jumping a red light is ₹1,000.",
        "sources":          [],
        "offline_fallback": False,
    }
    mock_fine.return_value = "₹1,000"

    resp = client.post("/chat", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "disclaimer" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)
    assert data["fine_amount"] == "₹1,000"
    assert data["currency_code"] == "INR"
    assert data["usd_equivalent_display"] == "≈ $12.00"


@patch("app.routes.chat.get_answer")
@patch("app.routes.chat.lookup_fine")
def test_chat_offline_flag_propagated(mock_fine, mock_answer):
    mock_answer.return_value = {
        "answer":           "Cached answer about helmets.",
        "sources":          [],
        "offline_fallback": True,
    }
    mock_fine.return_value = None

    resp = client.post("/chat", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["offline_fallback"] is True


@patch("app.routes.chat.get_answer")
@patch("app.routes.chat.lookup_fine")
def test_chat_no_fine_when_not_applicable(mock_fine, mock_answer):
    mock_answer.return_value = {
        "answer":           "Here are the general traffic rules.",
        "sources":          [],
        "offline_fallback": False,
    }
    mock_fine.return_value = None

    resp = client.post("/chat", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["fine_amount"] is None


# ── Edge cases ─────────────────────────────────────────────────────────────

@patch("app.routes.chat.get_answer")
@patch("app.routes.chat.lookup_fine")
def test_chat_unknown_city_still_responds(mock_fine, mock_answer):
    """Unknown city should not crash — fallback to state/national."""
    mock_answer.return_value = {
        "answer":           "National rules apply.",
        "sources":          [],
        "offline_fallback": False,
    }
    mock_fine.return_value = None

    payload = {
        "message": "What are the speed limits?",
        "location": {"city": "NonExistentCity123", "state": "Maharashtra", "country": "India"},
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200


@patch("app.routes.chat.get_answer")
@patch("app.routes.chat.lookup_fine")
def test_chat_very_long_query_is_truncated_by_validation(mock_fine, mock_answer):
    """Messages over 500 chars are rejected by Pydantic."""
    long_msg = "a" * 501
    payload = {**VALID_PAYLOAD, "message": long_msg}
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 422
