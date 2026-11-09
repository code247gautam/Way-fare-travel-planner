"""Places service – Geoapify live + mock fallback."""
from __future__ import annotations
import httpx
from ..config import get_settings
from ..models.providers import PlaceResult
from .base import load_json, with_fallback


class PlacesService:
    async def find_places(self, city: str, category: str = "tourism") -> list[PlaceResult]:
        raise NotImplementedError


class MockPlacesService(PlacesService):
    async def find_places(self, city: str, category: str = "tourism") -> list[PlaceResult]:
        data = load_json("places.json")
        results = []
        for p in data:
            if city.lower() in p["address"].lower():
                results.append(PlaceResult(**p, source="mock"))
        if not results:
            results = [PlaceResult(**p, source="mock") for p in data[:3]]
        return results


class LivePlacesService(PlacesService):
    BASE_URL = "https://api.geoapify.com/v2"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=10.0)

    async def find_places(self, city: str, category: str = "tourism") -> list[PlaceResult]:
        from .geocode import LiveGeocodeService
        geo = LiveGeocodeService(self.api_key)
        loc = await geo.geocode(city)
        resp = await self.client.get(
            "/places",
            params={
                "categories": category,
                "filter": f"circle:{loc.lon},{loc.lat},5000",
                "limit": 10,
                "apiKey": self.api_key,
            },
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        results = []
        for f in features:
            props = f["properties"]
            coords = f["geometry"]["coordinates"]
            results.append(PlaceResult(
                place_id=props.get("place_id", ""),
                name=props.get("name", ""),
                category=props.get("categories", [category])[0] if props.get("categories") else category,
                address=props.get("formatted", city),
                lat=coords[1], lon=coords[0],
                rating=props.get("rating"),
                opening_hours=props.get("opening_hours"),
                source="live",
            ))
        return results


class FallbackPlacesService(PlacesService):
    def __init__(self, live: LivePlacesService, mock: MockPlacesService) -> None:
        self._live, self._mock = live, mock

    async def find_places(self, city: str, category: str = "tourism") -> list[PlaceResult]:
        result, _ = await with_fallback(
            lambda: self._live.find_places(city, category),
            lambda: self._mock.find_places(city, category),
            cache_key=f"places:{city}:{category}",
        )
        return result


def get_places_service() -> PlacesService:
    s = get_settings()
    if s.use_live_geoapify and s.geoapify_api_key:
        return FallbackPlacesService(LivePlacesService(s.geoapify_api_key), MockPlacesService())
    return MockPlacesService()
