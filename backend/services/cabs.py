"""Cab estimation service – mock (uses Geoapify distance in live mode)."""
from __future__ import annotations
import math
from ..models.providers import CabEstimate
from .base import with_fallback
from ..config import get_settings


CAB_RATES_PER_KM = {
    "Auto": 15,
    "Hatchback": 12,
    "Sedan": 14,
    "SUV": 18,
    "Luxury": 25,
}

# Approx distances for common Indian city pairs (km)
CITY_DISTANCES: dict[tuple[str, str], float] = {
    ("Delhi", "Agra"): 210,
    ("Delhi", "Jaipur"): 280,
    ("Mumbai", "Pune"): 150,
    ("Bengaluru", "Mysuru"): 150,
    ("Hyderabad", "Bengaluru"): 570,
    ("Chennai", "Bengaluru"): 350,
    ("Delhi", "Mumbai"): 1400,
}


def _estimate_distance(origin: str, destination: str) -> float:
    key = (origin.title(), destination.title())
    rev = (destination.title(), origin.title())
    return CITY_DISTANCES.get(key) or CITY_DISTANCES.get(rev) or 250.0


class CabService:
    async def estimate_cab(self, origin: str, destination: str, cab_type: str = "Sedan") -> CabEstimate:
        raise NotImplementedError


class MockCabService(CabService):
    async def estimate_cab(self, origin: str, destination: str, cab_type: str = "Sedan") -> CabEstimate:
        dist = _estimate_distance(origin, destination)
        rate = CAB_RATES_PER_KM.get(cab_type, 14)
        fare = round(dist * rate)
        duration = int(dist / 60 * 60)  # ~60 km/h
        return CabEstimate(
            cab_type=cab_type, provider="Mock Cabs",
            origin=origin, destination=destination,
            distance_km=dist, fare_inr=fare,
            duration_minutes=duration, source="mock",
        )


def get_cab_service() -> CabService:
    return MockCabService()
