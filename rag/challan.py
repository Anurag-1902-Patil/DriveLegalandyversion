"""
DriveLegal – Challan Calculator
Looks up fine amounts from the structured fines.json dataset.
This is intentionally NOT LLM-based — accuracy is guaranteed via data.
"""

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("drivelegal.challan")

FINES_PATH = os.path.join("data", "fines.json")

# ── Keyword maps for fuzzy matching from natural language ──────────────────
VIOLATION_KEYWORDS: dict[str, list[str]] = {
    "red_light":        ["red light", "signal", "traffic light", "jump signal"],
    "speeding":         ["speed", "speeding", "overspeed", "over speed"],
    "no_helmet":        ["helmet", "no helmet", "without helmet"],
    "no_seatbelt":      ["seatbelt", "seat belt", "without seatbelt", "no seatbelt"],
    "drunk_driving":    ["drunk", "dui", "drink and drive", "alcohol", "drunken"],
    "mobile_phone":     ["mobile", "phone", "cell", "talking while driving"],
    "wrong_way":        ["wrong way", "wrong side", "one way"],
    "no_insurance":     ["insurance", "no insurance", "without insurance"],
    "no_license":       ["license", "licence", "driving without license", "no license"],
    "no_registration":  ["registration", "rc", "rc book", "no registration"],
    "triple_riding":    ["triple", "three persons", "triple riding"],
    "overloading":      ["overload", "overloading", "excess weight"],
    "no_pollution_cert":["pollution", "puc", "emission"],
    "parking":          ["parking", "no parking", "illegal parking"],
}

VEHICLE_KEYWORDS: dict[str, list[str]] = {
    "bike":         ["bike", "motorcycle", "two wheeler", "2 wheeler", "scooter", "moped"],
    "car":          ["car", "four wheeler", "4 wheeler", "sedan", "suv", "hatchback"],
    "auto":         ["auto", "autorickshaw", "three wheeler", "3 wheeler"],
    "truck":        ["truck", "lorry", "heavy vehicle", "goods vehicle"],
    "bus":          ["bus", "minibus", "coach"],
}


def _load_fines() -> dict:
    if not os.path.exists(FINES_PATH):
        logger.warning(f"fines.json not found at {FINES_PATH}")
        return {}
    with open(FINES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _detect_violation(query: str) -> Optional[str]:
    q = query.lower()
    for violation, keywords in VIOLATION_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return violation
    return None


def _detect_vehicle(query: str) -> str:
    q = query.lower()
    for vehicle, keywords in VEHICLE_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return vehicle
    return "default"   # generic fallback


def lookup_fine(query: str, city: str = "", state: str = "") -> Optional[str]:
    """
    Returns a formatted fine range string like '₹1,000 – ₹2,000'
    or None if not found.

    Lookup priority: city → state → national
    """
    fines = _load_fines()
    if not fines:
        return None

    violation = _detect_violation(query)
    vehicle   = _detect_vehicle(query)

    if not violation:
        return None

    # Cascade: city → state → national
    for scope in [city.lower(), state.lower(), "national"]:
        region_data = fines.get(scope, {})
        violation_data = region_data.get(violation, {})
        amount = violation_data.get(vehicle) or violation_data.get("default")
        if amount:
            logger.info(f"Fine found | scope={scope} | violation={violation} | vehicle={vehicle}")
            return amount

    return None