"""Stays service – Airbnb via RapidAPI live + mock with defensive normalizer."""
from __future__ import annotations
import logging
from typing import Any
import httpx
from ..config import get_settings
from ..models.providers import StayResult
from .base import load_json, with_fallback

logger = logging.getLogger(__name__)


def _normalize_airbnb(raw: Any) -> StayResult | None:
    """Defensive normalizer for Airbnb RapidAPI response (schema unverified)."""
    try:
        listing = raw.get("listing") or raw
        price_raw = (
            listing.get("price", {}) or
            raw.get("price", {}) or
            {}
        )
        price_inr = float(
            price_raw.get("amount") or
            price_raw.get("rate") or
            listing.get("price_per_night") or
            raw.get("price_per_night", 0)
        )
        return StayResult(
            id=str(listing.get("id") or raw.get("id", "airbnb-unknown")),
            name=str(listing.get("name") or raw.get("name", "Airbnb Listing")),
            city=str(listing.get("city") or raw.get("city", "")),
            price_per_night=price_inr,
            currency="INR",
            rating=float(listing.get("avg_rating") or raw.get("rating") or 0) or None,
            image=str(listing.get("picture_url") or raw.get("image", "")),
            url=str(listing.get("url") or raw.get("url", "")),
            source="live",
            best_value=False,
        )
    except Exception as exc:
        logger.warning("Airbnb normalizer failed: %s", exc)
        return None


class StaysService:
    async def search_stays(self, city: str, check_in: str, check_out: str) -> list[StayResult]:
        raise NotImplementedError


class MockStaysService(StaysService):
    async def search_stays(self, city: str, check_in: str, check_out: str) -> list[StayResult]:
        data = load_json("stays.json")
        results = []
        for s in data:
            if s["city"].lower() == city.lower():
                s_copy = {k: v for k, v in s.items() if k != "source"}
                results.append(StayResult(**s_copy, source="mock"))
        if not results:
            results = [StayResult(**{k: v for k, v in s.items() if k != "source"}, source="mock") for s in data[:3]]
        return results


class LiveAirbnbService(StaysService):
    BASE_URL = "https://airbnb19.p.rapidapi.com"

    def __init__(self, api_key: str) -> None:
        self.headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "airbnb19.p.rapidapi.com",
        }
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, headers=self.headers, timeout=15.0)

    async def search_stays(self, city: str, check_in: str, check_out: str) -> list[StayResult]:
        resp = await self.client.get(
            "/api/v1/searchPropertyByPlace",
            params={"placeName": city, "checkIn": check_in, "checkOut": check_out},
        )
        resp.raise_for_status()
        raw_list = resp.json().get("data", {}).get("list", [])
        results = [n for item in raw_list if (n := _normalize_airbnb(item)) is not None]
        return results


class FallbackStaysService(StaysService):
    def __init__(self, live: LiveAirbnbService, mock: MockStaysService) -> None:
        self._live, self._mock = live, mock

    async def search_stays(self, city: str, check_in: str, check_out: str) -> list[StayResult]:
        result, _ = await with_fallback(
            lambda: self._live.search_stays(city, check_in, check_out),
            lambda: self._mock.search_stays(city, check_in, check_out),
            cache_key=f"stays:{city}:{check_in}:{check_out}",
        )
        return result


def get_stays_service() -> StaysService:
    s = get_settings()
    if s.use_live_airbnb and s.rapidapi_key:
        return FallbackStaysService(LiveAirbnbService(s.rapidapi_key), MockStaysService())
    return MockStaysService()
