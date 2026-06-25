"""
DriveLegal – app/routes/location.py

Provides two endpoints for GPS coordinate management:
  POST /location/update  – receives a GPS fix from the frontend
  GET  /location/current – returns the latest GPS fix + resolved location

GPS data is stored in-memory only (never written to disk).
Fixes older than GPS_MAX_AGE_SECONDS are considered stale.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from geocoding.offline_geocoder import resolve, LocationResult

logger = logging.getLogger("drivelegal.routes.location")
router = APIRouter(prefix="/location", tags=["Location"])

# ---------------------------------------------------------------------------
# Configuration from environment (with defaults)
# ---------------------------------------------------------------------------
GPS_MAX_AGE_SECONDS: int = int(os.getenv("GPS_MAX_AGE_SECONDS", "60"))


# ---------------------------------------------------------------------------
# In-memory GPS store  (no disk writes — privacy safe)
# ---------------------------------------------------------------------------
class _GPSStore:
    """Thread-safe in-memory store for the latest GPS fix."""

    def __init__(self) -> None:
        self._lat: Optional[float] = None
        self._lon: Optional[float] = None
        self._accuracy: Optional[float] = None
        self._timestamp: Optional[float] = None   # Unix epoch (server time)
        self._resolved: Optional[LocationResult] = None

    def update(
        self,
        lat: float,
        lon: float,
        accuracy: Optional[float],
    ) -> LocationResult | None:
        """Store a new GPS fix and resolve the location offline."""
        self._lat = lat
        self._lon = lon
        self._accuracy = accuracy
        self._timestamp = time.time()

        # Resolve offline
        self._resolved = resolve(lat, lon, accuracy_m=accuracy)
        return self._resolved

    def get(self) -> Optional[dict]:
        """
        Return the current fix as a dict, or None if no fix or fix is stale.
        """
        if self._timestamp is None:
            return None
        age = time.time() - self._timestamp
        if age > GPS_MAX_AGE_SECONDS:
            return None

        return {
            "lat": self._lat,
            "lon": self._lon,
            "accuracy_m": self._accuracy,
            "age_seconds": round(age, 1),
            "resolved": self._resolved.as_dict() if self._resolved else None,
        }

    def is_fresh(self) -> bool:
        """True if a non-stale GPS fix is available."""
        return self.get() is not None

    def get_location_result(self) -> Optional[LocationResult]:
        """Return the LocationResult if fix is fresh, else None."""
        if not self.is_fresh():
            return None
        return self._resolved


# Singleton — shared across all requests in this process
_store = _GPSStore()


def get_store() -> _GPSStore:
    """Dependency-injection helper; returns the singleton GPS store."""
    return _store


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class GPSPayload(BaseModel):
    """Payload sent by the frontend GPS tracker."""
    lat: float = Field(..., ge=-90.0, le=90.0,  description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    accuracy: Optional[float] = Field(None, ge=0, description="Accuracy in metres (browser-reported)")
    client_timestamp: Optional[str] = Field(None, description="ISO-8601 timestamp from the client (informational)")


class GPSUpdateResponse(BaseModel):
    """Response returned after receiving a GPS update."""
    status: str
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    lat: float
    lon: float
    accuracy_m: Optional[float]


class CurrentLocationResponse(BaseModel):
    """Response returned for GET /location/current."""
    fix_available: bool
    age_seconds: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    accuracy_m: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    context_string: Optional[str] = None   # e.g. "Pune, Maharashtra, India"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/update", response_model=GPSUpdateResponse, summary="Receive GPS fix from browser")
async def update_location(payload: GPSPayload):
    """
    Accepts a GPS coordinate pair from the browser Geolocation API.
    Performs offline reverse geocoding to resolve city/state/country.
    Stores result in memory — never persisted to disk.
    """
    logger.info(
        "GPS update received: lat=%.5f lon=%.5f accuracy=%s",
        payload.lat, payload.lon, payload.accuracy,
    )

    location = _store.update(payload.lat, payload.lon, payload.accuracy)

    if location is None:
        # Geocoding failed (should be rare) — still accept the coordinates
        logger.warning("Offline geocoding returned None for (%.5f, %.5f)", payload.lat, payload.lon)
        return GPSUpdateResponse(
            status="ok_no_geocode",
            city=None,
            state=None,
            country=None,
            lat=payload.lat,
            lon=payload.lon,
            accuracy_m=payload.accuracy,
        )

    logger.info("Geocoded -> %s", location.as_context_string())
    return GPSUpdateResponse(
        status="ok",
        city=location.city,
        state=location.state,
        country=location.country,
        lat=payload.lat,
        lon=payload.lon,
        accuracy_m=payload.accuracy,
    )


@router.get("/current", response_model=CurrentLocationResponse, summary="Get latest GPS fix")
async def current_location():
    """
    Returns the most recent GPS fix stored in memory.
    Returns fix_available=false if no fix received yet or fix is stale
    (older than GPS_MAX_AGE_SECONDS, default 60 s).
    """
    fix = _store.get()
    if fix is None:
        return CurrentLocationResponse(fix_available=False)

    resolved = fix.get("resolved") or {}
    loc = _store.get_location_result()
    context_str = loc.as_context_string() if loc else None

    return CurrentLocationResponse(
        fix_available=True,
        age_seconds=fix["age_seconds"],
        lat=fix["lat"],
        lon=fix["lon"],
        accuracy_m=fix["accuracy_m"],
        city=resolved.get("city"),
        state=resolved.get("state"),
        country=resolved.get("country"),
        context_string=context_str,
    )
