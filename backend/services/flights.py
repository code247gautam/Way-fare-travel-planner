"""Flight service – mock only (live Aviationstack in Stage 3)."""
from __future__ import annotations
from ..models.providers import FlightResult
from .base import load_json, with_fallback
from ..config import get_settings
import httpx


class FlightService:
    async def search_flights(self, origin: str, destination: str, date: str | None = None) -> list[FlightResult]:
        raise NotImplementedError

    async def get_flight_status(self, flight_number: str) -> FlightResult | None:
        raise NotImplementedError


class MockFlightService(FlightService):
    async def search_flights(self, origin: str, destination: str, date: str | None = None) -> list[FlightResult]:
        data = load_json("flights.json")
        results = []
        for f in data:
            if (f["origin"].upper() == origin.upper() and f["destination"].upper() == destination.upper()):
                results.append(FlightResult(**f, source="mock"))
        if not results:
            results = [FlightResult(**f, source="mock") for f in data[:3]]
        return results

    async def get_flight_status(self, flight_number: str) -> FlightResult | None:
        data = load_json("flights.json")
        for f in data:
            if f["flight_number"] == flight_number:
                return FlightResult(**f, source="mock")
        return None


class LiveFlightService(FlightService):
    BASE_URL = "http://api.aviationstack.com/v1"  # Free plan requires HTTP

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=15.0)

    async def search_flights(self, origin: str, destination: str, date: str | None = None) -> list[FlightResult]:
        params = {"access_key": self.api_key, "dep_iata": origin, "arr_iata": destination}
        resp = await self.client.get("/flights", params=params)
        resp.raise_for_status()
        flights = resp.json().get("data", [])
        results = []
        for f in flights:
            try:
                results.append(FlightResult(
                    flight_number=f["flight"]["iata"],
                    airline=f["airline"]["name"],
                    origin=f["departure"]["iata"],
                    destination=f["arrival"]["iata"],
                    departure=f["departure"].get("scheduled", ""),
                    arrival=f["arrival"].get("scheduled", ""),
                    duration_minutes=0,
                    fare_inr=0.0,
                    status=f.get("flight_status", "SCHEDULED").upper(),
                    source="live",
                ))
            except Exception:
                continue
        return results

    async def get_flight_status(self, flight_number: str) -> FlightResult | None:
        params = {"access_key": self.api_key, "flight_iata": flight_number}
        resp = await self.client.get("/flights", params=params)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return None
        f = data[0]
        return FlightResult(
            flight_number=flight_number,
            airline=f["airline"]["name"],
            origin=f["departure"]["iata"],
            destination=f["arrival"]["iata"],
            departure=f["departure"].get("scheduled", ""),
            arrival=f["arrival"].get("scheduled", ""),
            duration_minutes=0,
            fare_inr=0.0,
            status=f.get("flight_status", "SCHEDULED").upper(),
            source="live",
        )


class FallbackFlightService(FlightService):
    def __init__(self, live: LiveFlightService, mock: MockFlightService) -> None:
        self._live, self._mock = live, mock

    async def search_flights(self, origin: str, destination: str, date: str | None = None) -> list[FlightResult]:
        result, source = await with_fallback(
            lambda: self._live.search_flights(origin, destination, date),
            lambda: self._mock.search_flights(origin, destination, date),
            cache_key=f"flights:{origin}:{destination}:{date}",
            ttl=300,
        )
        for f in result:
            f.source = source
        return result

    async def get_flight_status(self, flight_number: str) -> FlightResult | None:
        result, _ = await with_fallback(
            lambda: self._live.get_flight_status(flight_number),
            lambda: self._mock.get_flight_status(flight_number),
        )
        return result


def get_flight_service() -> FlightService:
    s = get_settings()
    if s.use_live_aviationstack and s.aviationstack_api_key:
        return FallbackFlightService(LiveFlightService(s.aviationstack_api_key), MockFlightService())
    return MockFlightService()
