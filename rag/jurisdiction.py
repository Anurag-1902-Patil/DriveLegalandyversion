"""
DriveLegal – jurisdiction hierarchy helpers.
Shared helpers for city → state/province → country → regional bloc → international treaty.

Treaty tier (Vienna Convention 1968, UN Model Road Safety Legislation,
EU Directive 2015/413) is prepended to the cascade for foreign-country queries
because these instruments define the baseline applicable to all signatory nations.
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

# ── Treaty tier labels ────────────────────────────────────────────────────────
# These must exactly match the region values written by preprocess.py / ingest_treaties.py.

VIENNA_CONVENTION_LABEL = "Vienna Convention on Road Traffic"
UN_MODEL_LEGISLATION_LABEL = "UN Model Road Safety Legislation"
EU_DIRECTIVE_2015_413_LABEL = "EU Directive 2015/413"

# Deprecated alias kept for backward compatibility with existing Qdrant points
INTERNATIONAL_CONVENTION_LABEL = VIENNA_CONVENTION_LABEL

# All treaty labels in priority order (Vienna first as the foundational instrument)
TREATY_LABELS: List[str] = [
    VIENNA_CONVENTION_LABEL,
    UN_MODEL_LEGISLATION_LABEL,
    EU_DIRECTIVE_2015_413_LABEL,
]


def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    return text.strip().lower()


def _is_india(country: str) -> bool:
    normalized = _normalize(country)
    return normalized in {"india", "indian", "bharat"}


def is_foreign_country_query(country: str) -> bool:
    """Return True when the resolved country is not India and not empty.

    Used by the retriever to decide whether to inject the treaty tier at the
    front of the cascade (foreign-country queries) or append it at the end
    (domestic queries, where national law is the primary source).
    """
    return bool(_normalize(country)) and not _is_india(country)


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


def _treaty_labels_for_country(country: str) -> List[str]:
    """Return the subset of treaty labels relevant to the country.

    EU Directive 2015/413 is only relevant for EU member states; the Vienna
    Convention and UN Model are applicable globally.
    """
    bloc = get_regional_bloc(country)
    labels = [VIENNA_CONVENTION_LABEL, UN_MODEL_LEGISLATION_LABEL]
    if bloc == "EU":
        labels.append(EU_DIRECTIVE_2015_413_LABEL)
    return labels


def get_fine_lookup_scopes(city: str = "", state: str = "", country: str = "") -> List[str]:
    """Return ordered lookup scopes for the challan/fine calculator.

    For foreign-country queries: treaty tier is prepended so treaty-level
    fine ranges surface even when no country-specific entry exists.
    For domestic (India) queries: treaty tier is appended as last resort.
    """
    scopes: list[str] = []
    foreign = is_foreign_country_query(country)

    # Treaty tier — front for foreign, back for domestic
    treaty_labels = _treaty_labels_for_country(country)
    if foreign:
        scopes.extend(treaty_labels)

    if city:
        scopes.append(_normalize(city))
    if state:
        scopes.append(_normalize(state))
    scopes.extend(_country_scope_keys(country))
    if bloc := get_regional_bloc(country):
        scopes.append(_normalize(bloc))

    if not foreign:
        scopes.extend(treaty_labels)

    return [scope for scope in scopes if scope]


def get_retriever_scopes(city: str = "", state: str = "", country: str = "") -> List[str]:
    """Return ordered Qdrant filter scopes for the vector retriever.

    Cascade for foreign-country queries (e.g. country="Germany"):
      Vienna Convention → UN Model → EU Directive (if EU) →
      city → state → country → regional bloc → no-filter

    Cascade for domestic (India) queries:
      city → state → country → "National" → regional bloc →
      Vienna Convention → UN Model → no-filter

    The empty string "" at the end triggers an unfiltered search as final fallback.
    """
    scopes: list[str] = []
    foreign = is_foreign_country_query(country)

    # ── Treaty tier — prepended for foreign queries ───────────────────────────
    treaty_labels = _treaty_labels_for_country(country)
    if foreign:
        scopes.extend(treaty_labels)

    # ── Geographic cascade ────────────────────────────────────────────────────
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

    # ── Treaty tier — appended for domestic queries ───────────────────────────
    if not foreign:
        scopes.extend(treaty_labels)

    return scopes


# ── Query-level destination country detection ─────────────────────────────────
# Maps lowercase country name / demonym / common abbreviation → canonical name.
# Sorted longest-first at runtime so "united kingdom" matches before "kingdom".

_COUNTRY_NAMES: dict[str, str] = {
    # Europe
    "france": "France", "french": "France",
    "germany": "Germany", "german": "Germany",
    "italy": "Italy", "italian": "Italy",
    "spain": "Spain", "spanish": "Spain",
    "portugal": "Portugal", "portuguese": "Portugal",
    "netherlands": "Netherlands", "dutch": "Netherlands", "holland": "Netherlands",
    "belgium": "Belgium", "belgian": "Belgium",
    "switzerland": "Switzerland", "swiss": "Switzerland",
    "austria": "Austria", "austrian": "Austria",
    "sweden": "Sweden", "swedish": "Sweden",
    "norway": "Norway", "norwegian": "Norway",
    "denmark": "Denmark", "danish": "Denmark",
    "finland": "Finland", "finnish": "Finland",
    "poland": "Poland", "polish": "Poland",
    "czech republic": "Czechia", "czechia": "Czechia", "czech": "Czechia",
    "slovakia": "Slovakia", "slovak": "Slovakia",
    "hungary": "Hungary", "hungarian": "Hungary",
    "romania": "Romania", "romanian": "Romania",
    "bulgaria": "Bulgaria", "bulgarian": "Bulgaria",
    "croatia": "Croatia", "croatian": "Croatia",
    "slovenia": "Slovenia", "slovenian": "Slovenia",
    "greece": "Greece", "greek": "Greece",
    "ireland": "Ireland", "irish": "Ireland",
    "luxembourg": "Luxembourg",
    "malta": "Malta",
    "cyprus": "Cyprus",
    "estonia": "Estonia",
    "latvia": "Latvia",
    "lithuania": "Lithuania",
    "iceland": "Iceland",
    "united kingdom": "United Kingdom", "uk": "United Kingdom",
    "britain": "United Kingdom", "england": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom",
    "turkey": "Turkey", "turkish": "Turkey",
    "russia": "Russia", "russian": "Russia",
    "ukraine": "Ukraine", "ukrainian": "Ukraine",
    # Americas
    "united states": "United States", "usa": "United States",
    "america": "United States", "us ": "United States",
    "canada": "Canada", "canadian": "Canada",
    "mexico": "Mexico", "mexican": "Mexico",
    "brazil": "Brazil", "brazilian": "Brazil",
    "argentina": "Argentina", "argentinian": "Argentina",
    "colombia": "Colombia",
    "chile": "Chile",
    # Asia-Pacific
    "japan": "Japan", "japanese": "Japan",
    "china": "China", "chinese": "China",
    "south korea": "South Korea", "korea": "South Korea", "korean": "South Korea",
    "australia": "Australia", "australian": "Australia",
    "new zealand": "New Zealand",
    "singapore": "Singapore", "singaporean": "Singapore",
    "malaysia": "Malaysia", "malaysian": "Malaysia",
    "thailand": "Thailand", "thai": "Thailand",
    "indonesia": "Indonesia", "indonesian": "Indonesia",
    "vietnam": "Vietnam", "vietnamese": "Vietnam",
    "philippines": "Philippines", "filipino": "Philippines",
    "cambodia": "Cambodia",
    "myanmar": "Myanmar", "burma": "Myanmar",
    "laos": "Laos",
    "taiwan": "Taiwan",
    "hong kong": "Hong Kong",
    "nepal": "Nepal", "nepalese": "Nepal",
    "sri lanka": "Sri Lanka",
    "bangladesh": "Bangladesh",
    "pakistan": "Pakistan", "pakistani": "Pakistan",
    # Middle East / GCC
    "united arab emirates": "United Arab Emirates",
    "uae": "United Arab Emirates", "dubai": "United Arab Emirates",
    "abu dhabi": "United Arab Emirates",
    "saudi arabia": "Saudi Arabia", "ksa": "Saudi Arabia", "saudi": "Saudi Arabia",
    "qatar": "Qatar",
    "bahrain": "Bahrain",
    "kuwait": "Kuwait",
    "oman": "Oman",
    "israel": "Israel",
    "jordan": "Jordan",
    "egypt": "Egypt",
    # Africa
    "south africa": "South Africa",
    "kenya": "Kenya",
    "nigeria": "Nigeria",
    "ethiopia": "Ethiopia",
    "ghana": "Ghana",
    "tanzania": "Tanzania",
    "morocco": "Morocco",
}

# Words that look like countries but are Indian — never treat as foreign destination
_INDIA_TERMS: frozenset[str] = frozenset({
    "india", "indian", "bharat", "hindustan",
    "kashmir", "ladakh", "goa", "kerala", "karnataka", "maharashtra",
    "delhi", "mumbai", "pune", "bangalore", "bengaluru", "hyderabad",
    "chennai", "kolkata", "ahmedabad", "rajasthan", "gujarat",
    "uttar pradesh", "madhya pradesh", "tamil nadu", "andhra pradesh",
    "west bengal", "bihar", "punjab", "haryana",
})


def detect_destination_country(query: str) -> Optional[str]:
    """Detect if the user's query mentions a specific foreign country as a driving destination.

    Returns the canonical country name (e.g. "France", "Germany") if a non-India
    foreign country is unambiguously found in the query text, otherwise returns None.

    Used by the chat route to override GPS-resolved location so the retriever
    uses the treaty-first foreign-country cascade instead of the India cascade.

    Examples:
        "What are the rules for driving in France?"  → "France"
        "Do I need an IDP in Germany?"               → "Germany"
        "Fine for no helmet in Pune?"                → None  (India city)
        "speeding rules"                             → None  (no country)
    """
    q = _normalize(query)
    # Check India terms first — if the query is about India, return None immediately
    for term in _INDIA_TERMS:
        if term in q:
            return None
    # Match longest country name first to avoid partial matches
    for name, canonical in sorted(_COUNTRY_NAMES.items(), key=lambda x: -len(x[0])):
        if name in q:
            return canonical
    return None
