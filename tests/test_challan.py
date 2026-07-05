"""
DriveLegal – tests/test_challan.py
Unit tests for the challan (fine) calculator.

Run:  pytest tests/test_challan.py -v
"""

import json
import os
import pytest
from unittest.mock import patch, mock_open

SAMPLE_FINES = {
    "national": {
        "red_light":   {"default": "₹1,000 – ₹5,000", "bike": "₹1,000", "car": "₹5,000"},
        "no_helmet":   {"bike": "₹1,000", "default": "₹1,000"},
        "no_seatbelt": {"car": "₹1,000", "default": "₹1,000"},
        "drunk_driving": {"default": "₹10,000"},
    },
    "maharashtra": {
        "red_light": {"default": "₹1,000", "bike": "₹1,000"},
        "no_helmet": {"bike": "₹500 (old) / ₹1,000 (MV Act 2019)", "default": "₹1,000"},
    },
    "pune": {
        "red_light": {"default": "₹1,000", "bike": "₹1,000", "car": "₹1,000"},
        "no_helmet": {"bike": "₹1,000", "default": "₹1,000"},
        "parking":   {"default": "₹500 – ₹2,000 (tow charges extra)"},
    },
}


def patched_lookup(query, city="", state=""):
    """Runs lookup_fine against the sample fines fixture."""
    with patch("rag.challan.FINES_PATH", "data/fines.json"), \
         patch("builtins.open", mock_open(read_data=json.dumps(SAMPLE_FINES))), \
         patch("os.path.exists", return_value=True):
        from rag.challan import lookup_fine
        # Reload to pick up patched path
        import importlib
        import rag.challan as m
        importlib.reload(m)
        return m.lookup_fine(query, city=city, state=state)


# ── Violation detection ────────────────────────────────────────────────────

def test_detect_red_light_violation():
    from rag.challan import _detect_violation
    assert _detect_violation("fine for jumping a red light") == "red_light"
    assert _detect_violation("penalty for running a signal") == "red_light"


def test_detect_helmet_violation():
    from rag.challan import _detect_violation
    assert _detect_violation("riding without helmet") == "no_helmet"


def test_detect_drunk_driving():
    from rag.challan import _detect_violation
    assert _detect_violation("drink and drive penalty") == "drunk_driving"


def test_detect_no_violation_returns_none():
    from rag.challan import _detect_violation
    assert _detect_violation("what is the capital of France") is None


# ── Vehicle detection ──────────────────────────────────────────────────────

def test_detect_bike():
    from rag.challan import _detect_vehicle
    assert _detect_vehicle("fine for bike rider without helmet") == "bike"
    assert _detect_vehicle("penalty for motorcycle") == "bike"
    assert _detect_vehicle("two wheeler fine") == "bike"


def test_detect_car():
    from rag.challan import _detect_vehicle
    assert _detect_vehicle("car seatbelt fine") == "car"
    assert _detect_vehicle("four wheeler penalty") == "car"


def test_default_vehicle_when_unspecified():
    from rag.challan import _detect_vehicle
    assert _detect_vehicle("what is the fine?") == "default"


# ── Lookup logic ───────────────────────────────────────────────────────────

def test_city_scope_returns_city_fine():
    with patch("rag.challan._load_fines", return_value=SAMPLE_FINES):
        from rag import challan
        result = challan.lookup_fine("red light fine", city="pune", state="maharashtra")
    assert result is not None
    assert "₹" in result


def test_state_fallback_when_no_city():
    with patch("rag.challan._load_fines", return_value=SAMPLE_FINES):
        from rag import challan
        result = challan.lookup_fine("no helmet fine on bike", city="nashik", state="maharashtra")
    assert result is not None


def test_national_fallback():
    with patch("rag.challan._load_fines", return_value=SAMPLE_FINES):
        from rag import challan
        result = challan.lookup_fine("drunk driving penalty", city="", state="")
    assert result is not None
    assert "₹10,000" in result


def test_returns_none_for_unknown_violation():
    with patch("rag.challan._load_fines", return_value=SAMPLE_FINES):
        from rag import challan
        result = challan.lookup_fine("random irrelevant text here", city="pune", state="maharashtra")
    assert result is None


def test_lookup_fine_details_includes_currency_code_and_usd_hint():
    with patch("rag.challan._load_fines", return_value=SAMPLE_FINES):
        from rag import challan
        result = challan.lookup_fine_details("red light fine", city="pune", state="maharashtra", country="Germany")
    assert result is not None
    assert result["currency_code"] == "INR"
    assert result["display_amount"] == "₹1,000"
    assert result["usd_equivalent"] is not None


def test_returns_none_when_fines_file_missing():
    with patch("rag.challan._load_fines", return_value={}):
        from rag import challan
        result = challan.lookup_fine("red light fine")
    assert result is None


# ── Manual accuracy spot-checks ────────────────────────────────────────────

@pytest.mark.parametrize("query,city,state,expected_substring", [
    ("fine for jumping red light in Pune on a bike", "pune", "maharashtra", "₹"),
    ("no helmet fine",                               "",     "",            "₹"),
    ("drunk driving",                                "",     "",            "₹10,000"),
])
def test_accuracy_spot_checks(query, city, state, expected_substring):
    with patch("rag.challan._load_fines", return_value=SAMPLE_FINES):
        from rag import challan
        result = challan.lookup_fine(query, city=city, state=state)
    assert result is not None
    assert expected_substring in result
