"""
DriveLegal – geocoding/offline_geocoder.py

Fully offline reverse geocoder using the `reverse_geocoder` library.
That library ships a bundled CSV of ~220,000 world cities — no internet
needed at runtime.

Usage:
    from geocoding.offline_geocoder import resolve, LocationResult

    result = resolve(18.5204, 73.8567)   # Pune coords
    print(result.city, result.state, result.country)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("drivelegal.geocoder")

# ---------------------------------------------------------------------------
# Lazy-load the reverse_geocoder library so startup isn't penalised if the
# package isn't installed yet (we fall back gracefully).
# ---------------------------------------------------------------------------
_rg = None


def _get_rg():
    """Import reverse_geocoder on first use (it loads a ~2 MB CSV once)."""
    global _rg
    if _rg is None:
        try:
            import reverse_geocoder as rg_lib   # type: ignore
            _rg = rg_lib
            logger.info("reverse_geocoder library loaded (offline mode).")
        except ImportError:
            logger.error(
                "reverse_geocoder not installed. "
                "Run: pip install reverse_geocoder"
            )
    return _rg


# ---------------------------------------------------------------------------
# ISO-3166 country-code → full name mapping (subset covering India + common)
# ---------------------------------------------------------------------------
_COUNTRY_NAMES: dict[str, str] = {
    "IN": "India",
    "US": "United States",
    "GB": "United Kingdom",
    "AU": "Australia",
    "CN": "China",
    "JP": "Japan",
    "DE": "Germany",
    "FR": "France",
    "CA": "Canada",
    "BR": "Brazil",
    "SG": "Singapore",
    "AE": "UAE",
    "PK": "Pakistan",
    "BD": "Bangladesh",
    "NP": "Nepal",
    "LK": "Sri Lanka",
}

# India: administrative region (admin1) code → state name
# reverse_geocoder returns admin1 codes like "MH", "DL", etc. for India.
_INDIA_STATES: dict[str, str] = {
    "Andaman and Nicobar Islands": "Andaman and Nicobar Islands",
    "Andhra Pradesh": "Andhra Pradesh",
    "Arunachal Pradesh": "Arunachal Pradesh",
    "Assam": "Assam",
    "Bihar": "Bihar",
    "Chandigarh": "Chandigarh",
    "Chhattisgarh": "Chhattisgarh",
    "Dadra and Nagar Haveli": "Dadra and Nagar Haveli",
    "Daman and Diu": "Daman and Diu",
    "Delhi": "Delhi",
    "Goa": "Goa",
    "Gujarat": "Gujarat",
    "Haryana": "Haryana",
    "Himachal Pradesh": "Himachal Pradesh",
    "Jammu and Kashmir": "Jammu and Kashmir",
    "Jharkhand": "Jharkhand",
    "Karnataka": "Karnataka",
    "Kerala": "Kerala",
    "Ladakh": "Ladakh",
    "Lakshadweep": "Lakshadweep",
    "Madhya Pradesh": "Madhya Pradesh",
    "Maharashtra": "Maharashtra",
    "Manipur": "Manipur",
    "Meghalaya": "Meghalaya",
    "Mizoram": "Mizoram",
    "Nagaland": "Nagaland",
    "Odisha": "Odisha",
    "Puducherry": "Puducherry",
    "Punjab": "Punjab",
    "Rajasthan": "Rajasthan",
    "Sikkim": "Sikkim",
    "Tamil Nadu": "Tamil Nadu",
    "Telangana": "Telangana",
    "Tripura": "Tripura",
    "Uttar Pradesh": "Uttar Pradesh",
    "Uttarakhand": "Uttarakhand",
    "West Bengal": "West Bengal",
    # Common alternate spellings returned by the library
    "NCT of Delhi": "Delhi",
    "National Capital Territory of Delhi": "Delhi",
}


@dataclass
class LocationResult:
    """Resolved location from GPS coordinates."""
    city: str
    state: str
    country: str
    lat: float
    lon: float
    accuracy_m: Optional[float] = None
    raw_admin1: str = field(default="", repr=False)
    raw_cc: str = field(default="", repr=False)

    def as_context_string(self) -> str:
        """Human-readable string suitable for injection into LLM prompts."""
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts)

    def as_dict(self) -> dict:
        return {
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "lat": self.lat,
            "lon": self.lon,
            "accuracy_m": self.accuracy_m,
        }


def resolve(
    lat: float,
    lon: float,
    accuracy_m: Optional[float] = None,
) -> Optional[LocationResult]:
    """
    Convert GPS coordinates to a human-readable location.

    Uses the bundled reverse_geocoder dataset (~220k cities).
    Completely offline — no HTTP calls made.

    Args:
        lat: Latitude (decimal degrees, −90 to +90).
        lon: Longitude (decimal degrees, −180 to +180).
        accuracy_m: GPS accuracy in metres (optional, stored for context).

    Returns:
        LocationResult on success, None if library unavailable or coords invalid.
    """
    # --- Validate coordinates ---
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        logger.warning("Invalid coordinates: lat=%s lon=%s", lat, lon)
        return None

    rg = _get_rg()
    if rg is None:
        logger.error("reverse_geocoder library not available.")
        return None

    try:
        # Query is synchronous; returns a list with one result dict.
        results = rg.search([(lat, lon)], mode=1, verbose=False)
        if not results:
            logger.warning("No geocoding result for lat=%s lon=%s", lat, lon)
            return None

        hit = results[0]
        raw_city: str    = hit.get("name", "Unknown")
        raw_admin1: str  = hit.get("admin1", "")
        raw_cc: str      = hit.get("cc", "")

        # Resolve country name from ISO code
        country = _COUNTRY_NAMES.get(raw_cc, raw_cc) if raw_cc else "Unknown"

        # Normalise Indian state names
        if raw_cc == "IN":
            state = _INDIA_STATES.get(raw_admin1, raw_admin1)
        else:
            state = raw_admin1

        logger.debug(
            "Resolved (%.4f, %.4f) → %s, %s, %s",
            lat, lon, raw_city, state, country,
        )
        return LocationResult(
            city=raw_city,
            state=state,
            country=country,
            lat=lat,
            lon=lon,
            accuracy_m=accuracy_m,
            raw_admin1=raw_admin1,
            raw_cc=raw_cc,
        )

    except Exception as exc:
        logger.error("Geocoding error: %s", exc, exc_info=True)
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two GPS points in kilometres.
    Useful for checking if the user has moved significantly.
    """
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
