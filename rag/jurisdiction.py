"""
DriveLegal – jurisdiction hierarchy helpers.
Shared helpers for city → state/province → country → regional bloc → international convention.
"""

from __future__ import annotations
from typing import Iterable, List, Optional

EUROPEAN_UNION_COUNTRIES = {
    "at", "be", "bg", "hr", "cy", "cz", "dk", "ee", "fi", "fr", "de", "gr", "hu",
    "ie", "it", "lv", "lt", "lu", "mt", "nl", "pl", "pt", "ro", "sk", "si", "es", "se",
    "austria", "belgium", "bulgaria", "croatia", "czechia", "denmark", "estonia", "finland",
    "france", "germany", "greece", "hungary", "ireland", "italy", "latvia", "lithuania",
    "luxembourg", "malta", "netherlands", "poland", "portugal", "romania", "slovakia", "slovenia",
    "spain", "sweden",
}

ASEAN_COUNTRIES = {
    "brunei", "cambodia", "indonesia", "laos", "malaysia", "myanmar",
    "philippines", "singapore", "thailand", "vietnam",
}

GCC_COUNTRIES = {
    "bahrain", "ksa", "kuwait", "oman", "qatar", "saudi arabia", "saudi", "united arab emirates", "uae",
}

INTERNATIONAL_CONVENTION_LABEL = "Vienna Convention on Road Traffic"


def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    return text.strip().lower()


def _is_india(country: str) -> bool:
    normalized = _normalize(country)
    return normalized in {"india", "indian", "bharat"}


def _country_scope_keys(country: str) -> List[str]:
    normalized = _normalize(country)
    if not normalized:
        return []
    if _is_india(country):
        return [normalized, "national"]
    return [normalized]


def get_regional_bloc(country: str) -> Optional[str]:
    normalized = _normalize(country)
    if not normalized:
        return None
    if normalized in EUROPEAN_UNION_COUNTRIES or normalized in {"eu", "europe", "european union"}:
        return "EU"
    if normalized in ASEAN_COUNTRIES or normalized == "asean":
        return "ASEAN"
    if normalized in GCC_COUNTRIES or normalized == "gcc":
        return "GCC"
    return None


def get_fine_lookup_scopes(city: str = "", state: str = "", country: str = "") -> List[str]:
    scopes: list[str] = []
    if city:
        scopes.append(_normalize(city))
    if state:
        scopes.append(_normalize(state))
    scopes.extend(_country_scope_keys(country))
    if bloc := get_regional_bloc(country):
        scopes.append(_normalize(bloc))
    scopes.append(_normalize(INTERNATIONAL_CONVENTION_LABEL))
    return [scope for scope in scopes if scope]


def get_retriever_scopes(city: str = "", state: str = "", country: str = "") -> List[str]:
    scopes: list[str] = []
    if city:
        scopes.append(city.strip())
    if state:
        scopes.append(state.strip())
    if country:
        scopes.append(country.strip())
        if _is_india(country):
            scopes.append("National")
    if bloc := get_regional_bloc(country):
        scopes.append(bloc)
    scopes.append(INTERNATIONAL_CONVENTION_LABEL)
    scopes.append("")
    return scopes
