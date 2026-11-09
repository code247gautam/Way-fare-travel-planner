"""Airport lookup service – mock only."""
from __future__ import annotations
from ..models.providers import AirportResult
from .base import load_json


class AirportService:
    async def get_airport(self, iata_code: str) -> AirportResult | None:
        raise NotImplementedError

    async def search_airports(self, query: str) -> list[AirportResult]:
        raise NotImplementedError


class MockAirportService(AirportService):
    async def get_airport(self, iata_code: str) -> AirportResult | None:
        data = load_json("airports.json")
        for a in data:
            if a["iata_code"].upper() == iata_code.upper():
                return AirportResult(**a, source="mock")
        return None

    async def search_airports(self, query: str) -> list[AirportResult]:
        data = load_json("airports.json")
        q = query.lower()
        results = [AirportResult(**a, source="mock") for a in data if q in a["city"].lower() or q in a["iata_code"].lower()]
        return results or [AirportResult(**data[0], source="mock")]


def get_airport_service() -> AirportService:
    return MockAirportService()
