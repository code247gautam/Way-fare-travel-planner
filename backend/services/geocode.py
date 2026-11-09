"""Geocoding service – Geoapify live + mock fallback."""
from __future__ import annotations
import httpx
from ..config import get_settings
from ..models.providers import GeocodingResult
from .base import load_json, with_fallback


class GeocodeService:
    async def geocode(self, query: str) -> GeocodingResult:
        raise NotImplementedError


class MockGeocodeService(GeocodeService):
    async def geocode(self, query: str) -> GeocodingResult:
        data = load_json("geocoding.json")
        cities = data["cities"]
        for name, info in cities.items():
            if name.lower() in query.lower():
                return GeocodingResult(
                    query=query, lat=info["lat"], lon=info["lon"],
                    display_name=name, country=info["country"], source="mock",
                )
        return GeocodingResult(query=query, lat=28.6139, lon=77.209, display_name="Delhi", country="India", source="mock")


class LiveGeocodeService(GeocodeService):
    BASE_URL = "https://api.geoapify.com/v1"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=10.0)

    async def geocode(self, query: str) -> GeocodingResult:
        resp = await self.client.get("/geocode/search", params={"text": query, "apiKey": self.api_key, "format": "json"})
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            raise ValueError(f"No geocoding results for: {query}")
        r = results[0]
        return GeocodingResult(
            query=query, lat=r["lat"], lon=r["lon"],
            display_name=r.get("formatted", query),
            country=r.get("country", "India"),
            source="live",
        )


class FallbackGeocodeService(GeocodeService):
    def __init__(self, live: LiveGeocodeService, mock: MockGeocodeService) -> None:
        self._live, self._mock = live, mock

    async def geocode(self, query: str) -> GeocodingResult:
        result, _ = await with_fallback(
            lambda: self._live.geocode(query),
            lambda: self._mock.geocode(query),
            cache_key=f"geocode:{query}",
        )
        return result


def get_geocode_service() -> GeocodeService:
    s = get_settings()
    if s.use_live_geoapify and s.geoapify_api_key:
        return FallbackGeocodeService(LiveGeocodeService(s.geoapify_api_key), MockGeocodeService())
    return MockGeocodeService()
