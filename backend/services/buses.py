"""Bus service – mock only (no live provider)."""
from __future__ import annotations
from ..models.providers import BusResult
from .base import load_json


class BusService:
    async def search_buses(self, origin: str, destination: str, date: str | None = None) -> list[BusResult]:
        raise NotImplementedError


class MockBusService(BusService):
    async def search_buses(self, origin: str, destination: str, date: str | None = None) -> list[BusResult]:
        data = load_json("buses.json")
        results = []
        for b in data:
            if (b["origin"].lower() == origin.lower() and b["destination"].lower() == destination.lower()):
                results.append(BusResult(**b, source="mock"))
        if not results:
            results = [BusResult(**b, source="mock") for b in data[:2]]
        return results


def get_bus_service() -> BusService:
    return MockBusService()
