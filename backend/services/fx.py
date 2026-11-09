"""FX service – Exchange Rate API live + mock."""
from __future__ import annotations
import httpx
from ..config import get_settings
from ..models.providers import FxResult
from .base import load_json, with_fallback


class FxService:
    async def convert(self, amount: float, from_currency: str, to_currency: str) -> FxResult:
        raise NotImplementedError


class MockFxService(FxService):
    async def convert(self, amount: float, from_currency: str, to_currency: str) -> FxResult:
        data = load_json("fx.json")
        rates = data["rates"]
        rate = rates.get(from_currency, {}).get(to_currency)
        if rate is None:
            # Try reverse
            rev = rates.get(to_currency, {}).get(from_currency)
            rate = 1.0 / rev if rev else 1.0
        return FxResult(
            from_currency=from_currency, to_currency=to_currency,
            rate=rate, converted_amount=round(amount * rate, 2), source="mock",
        )


class LiveFxService(FxService):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)

    async def convert(self, amount: float, from_currency: str, to_currency: str) -> FxResult:
        url = f"https://v6.exchangerate-api.com/v6/{self.api_key}/latest/{from_currency}"
        resp = await self.client.get(url)
        resp.raise_for_status()
        rates = resp.json().get("conversion_rates", {})
        rate = rates.get(to_currency, 1.0)
        return FxResult(
            from_currency=from_currency, to_currency=to_currency,
            rate=rate, converted_amount=round(amount * rate, 2), source="live",
        )


class FallbackFxService(FxService):
    def __init__(self, live: LiveFxService, mock: MockFxService) -> None:
        self._live, self._mock = live, mock

    async def convert(self, amount: float, from_currency: str, to_currency: str) -> FxResult:
        result, _ = await with_fallback(
            lambda: self._live.convert(amount, from_currency, to_currency),
            lambda: self._mock.convert(amount, from_currency, to_currency),
            cache_key=f"fx:{from_currency}:{to_currency}",
            ttl=3600,
        )
        return result


def get_fx_service() -> FxService:
    s = get_settings()
    if s.use_live_fx and s.exchange_rate_api_key:
        return FallbackFxService(LiveFxService(s.exchange_rate_api_key), MockFxService())
    return MockFxService()
