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

from rag.jurisdiction import get_fine_lookup_scopes

logger = logging.getLogger("drivelegal.challan")

FINES_PATH = os.path.join("data", "fines.json")

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "EUR": "€",
    "USD": "$",
    "SAR": "SAR",
}

STATIC_EXCHANGE_RATES = {
    "INR": 0.012,
    "EUR": 1.08,
    "USD": 1.0,
    "SAR": 0.27,
}

EUROPEAN_UNION_COUNTRIES = {
    "at", "be", "bg", "hr", "cy", "cz", "dk", "ee", "fi", "fr", "de", "gr", "hu",
    "ie", "it", "lv", "lt", "lu", "mt", "nl", "pl", "pt", "ro", "sk", "si", "es", "se"
}

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


def _normalize_country(country: Optional[str]) -> str:
    if not country:
        return ""
    return country.strip().lower()


def _find_currency_code(country: Optional[str], amount: Optional[str]) -> tuple[str, str]:
    if amount:
        upper_amount = amount.upper()
        if "₹" in amount or "INR" in upper_amount:
            return "INR", CURRENCY_SYMBOLS["INR"]
        if "€" in amount or "EUR" in upper_amount:
            return "EUR", CURRENCY_SYMBOLS["EUR"]
        if "$" in amount or "USD" in upper_amount:
            return "USD", CURRENCY_SYMBOLS["USD"]
        if "SAR" in upper_amount:
            return "SAR", CURRENCY_SYMBOLS["SAR"]

    normalized_country = _normalize_country(country)
    if normalized_country in {"india", "indian"}:
        return "INR", CURRENCY_SYMBOLS["INR"]
    if normalized_country in {"saudi arabia", "saudi", "ksa"}:
        return "SAR", CURRENCY_SYMBOLS["SAR"]
    if normalized_country in {"us", "usa", "united states", "united states of america", "america"}:
        return "USD", CURRENCY_SYMBOLS["USD"]
    if normalized_country in {"eu", "europe", "european union", "european"} or normalized_country in EUROPEAN_UNION_COUNTRIES:
        return "EUR", CURRENCY_SYMBOLS["EUR"]
    if normalized_country in {"germany", "france", "spain", "italy", "netherlands", "belgium", "portugal", "poland", "sweden", "finland", "denmark", "austria", "ireland", "greece", "luxembourg", "croatia", "slovakia", "slovenia", "czechia", "bulgaria", "romania", "hungary", "latvia", "lithuania", "estonia", "cyprus", "malta"}:
        return "EUR", CURRENCY_SYMBOLS["EUR"]
    return "INR", CURRENCY_SYMBOLS["INR"]


def _extract_amount_value(amount: Optional[str]) -> Optional[float]:
    if not amount:
        return None
    matches = re.findall(r"\d[\d,\.]*", amount)
    if not matches:
        return None
    cleaned = matches[0].replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _build_usd_equivalent(amount: Optional[str], currency_code: str) -> tuple[Optional[float], Optional[str]]:
    if not amount:
        return None, None
    rate = STATIC_EXCHANGE_RATES.get(currency_code)
    if rate is None:
        return None, None
    value = _extract_amount_value(amount)
    if value is None:
        return None, None
    usd_value = round(value * rate, 2)
    return usd_value, f"≈ ${usd_value:.2f}"


def lookup_fine_details(
    query: str,
    city: str = "",
    state: str = "",
    country: str = "India",
    amount_override: Optional[str] = None,
) -> Optional[dict]:
    """
    Returns a structured fine payload with the original amount string,
    currency metadata, and an optional USD equivalent.
    """
    fines = _load_fines()
    if not fines:
        return None

    violation = _detect_violation(query)
    vehicle = _detect_vehicle(query)

    if not violation:
        return None

    for scope in get_fine_lookup_scopes(city, state, country):
        region_data = fines.get(scope, {})
        violation_data = region_data.get(violation, {})
        amount = amount_override or violation_data.get(vehicle) or violation_data.get("default")
        if amount:
            logger.info(f"Fine found | scope={scope} | violation={violation} | vehicle={vehicle}")
            currency_code, currency_symbol = _find_currency_code(country, amount)
            usd_equivalent, usd_equivalent_display = _build_usd_equivalent(amount, currency_code)
            return {
                "display_amount": amount,
                "currency_code": currency_code,
                "currency_symbol": currency_symbol,
                "usd_equivalent": usd_equivalent,
                "usd_equivalent_display": usd_equivalent_display,
            }

    return None


def lookup_fine(query: str, city: str = "", state: str = "", country: str = "India") -> Optional[str]:
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

    # Cascade: city → state/province → country → regional bloc → international convention
    for scope in get_fine_lookup_scopes(city, state, country):
        region_data = fines.get(scope, {})
        violation_data = region_data.get(violation, {})
        amount = violation_data.get(vehicle) or violation_data.get("default")
        if amount:
            logger.info(f"Fine found | scope={scope} | violation={violation} | vehicle={vehicle}")
            return amount

    return None