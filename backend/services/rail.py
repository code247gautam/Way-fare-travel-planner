"""Rail service – live (RailRadar) + mock + fallback wrapper."""
from __future__ import annotations
import logging
from typing import Optional
import httpx
from ..config import get_settings
from ..models.providers import TrainResult
from .base import load_json, with_fallback

logger = logging.getLogger(__name__)


class RailService:
    """Interface for rail search and status."""

    async def search_trains(
        self,
        origin: str,
        destination: str,
        date: Optional[str] = None,
    ) -> list[TrainResult]:
        raise NotImplementedError

    async def get_pnr_status(self, pnr: str) -> dict:
        raise NotImplementedError

    async def get_disruptions(self) -> list[dict]:
        raise NotImplementedError


class MockRailService(RailService):
    """Mock implementation using backend/data/trains.json."""

    async def search_trains(self, origin: str, destination: str, date: Optional[str] = None) -> list[TrainResult]:
        data = load_json("trains.json")
        results = []
        for t in data:
            results.append(TrainResult(**t, source="mock"))
        return results

    async def get_pnr_status(self, pnr: str) -> dict:
        return {"pnr": pnr, "status": "CONFIRMED", "train": "12951", "source": "mock"}

    async def get_disruptions(self) -> list[dict]:
        return []


class LiveRailService(RailService):
    """Live implementation using RailRadar API."""

    BASE_URL = "https://api.railradar.in/v1"

    def __init__(self, token: str) -> None:
        self.token = token
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )

    async def search_trains(self, origin: str, destination: str, date: Optional[str] = None) -> list[TrainResult]:
        params = {"from": origin, "to": destination}
        if date:
            params["date"] = date
        resp = await self.client.get("/trains/search", params=params)
        resp.raise_for_status()
        data = resp.json().get("trains", [])
        return [TrainResult(**t, source="live") for t in data]

    async def get_pnr_status(self, pnr: str) -> dict:
        resp = await self.client.get(f"/pnr/{pnr}")
        resp.raise_for_status()
        result = resp.json()
        result["source"] = "live"
        return result

    async def get_disruptions(self) -> list[dict]:
        resp = await self.client.get("/exceptions")
        resp.raise_for_status()
        return resp.json().get("exceptions", [])


class FallbackRailService(RailService):
    """Tries live; falls back to mock on any error."""

    def __init__(self, live: LiveRailService, mock: MockRailService) -> None:
        self._live = live
        self._mock = mock

    async def search_trains(self, origin: str, destination: str, date: Optional[str] = None) -> list[TrainResult]:
        result, source = await with_fallback(
            lambda: self._live.search_trains(origin, destination, date),
            lambda: self._mock.search_trains(origin, destination, date),
            cache_key=f"trains:{origin}:{destination}:{date}",
            ttl=300,
        )
        for t in result:
            t.source = source
        return result

    async def get_pnr_status(self, pnr: str) -> dict:
        result, _ = await with_fallback(
            lambda: self._live.get_pnr_status(pnr),
            lambda: self._mock.get_pnr_status(pnr),
        )
        return result

    async def get_disruptions(self) -> list[dict]:
        result, _ = await with_fallback(
            lambda: self._live.get_disruptions(),
            lambda: self._mock.get_disruptions(),
        )
        return result


def get_rail_service() -> RailService:
    s = get_settings()
    if s.use_live_railradar and s.railradar_token:
        return FallbackRailService(
            LiveRailService(s.railradar_token),
            MockRailService(),
        )
    return MockRailService()
