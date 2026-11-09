"""Weather service – OpenWeather live + mock fallback."""
from __future__ import annotations
import logging
from datetime import date
import httpx
from ..config import get_settings
from ..models.providers import WeatherResult
from .base import load_json, with_fallback

logger = logging.getLogger(__name__)


class WeatherService:
    async def get_weather(self, city: str, for_date: str | None = None) -> WeatherResult:
        raise NotImplementedError

    async def get_forecast(self, city: str) -> list[WeatherResult]:
        raise NotImplementedError


class MockWeatherService(WeatherService):
    async def get_weather(self, city: str, for_date: str | None = None) -> WeatherResult:
        data = load_json("weather.json")
        today = for_date or str(date.today())
        for w in data:
            if w["city"].lower() == city.lower():
                w_copy = {k: v for k, v in w.items() if k != "date"}
                return WeatherResult(**w_copy, date=today, source="mock")
        # Default fallback
        return WeatherResult(
            city=city, date=today, temp_c=26.0, feels_like_c=27.0,
            humidity_pct=60, description="Pleasant", icon="01d",
            wind_kmh=12.0, source="mock",
        )

    async def get_forecast(self, city: str) -> list[WeatherResult]:
        base = await self.get_weather(city)
        return [base]


class LiveWeatherService(WeatherService):
    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, timeout=10.0)

    async def get_weather(self, city: str, for_date: str | None = None) -> WeatherResult:
        resp = await self.client.get("/weather", params={"q": city + ",IN", "appid": self.api_key, "units": "metric"})
        resp.raise_for_status()
        d = resp.json()
        return WeatherResult(
            city=city,
            date=for_date or str(date.today()),
            temp_c=d["main"]["temp"],
            feels_like_c=d["main"]["feels_like"],
            humidity_pct=d["main"]["humidity"],
            description=d["weather"][0]["description"].capitalize(),
            icon=d["weather"][0]["icon"],
            wind_kmh=round(d["wind"]["speed"] * 3.6, 1),
            source="live",
        )

    async def get_forecast(self, city: str) -> list[WeatherResult]:
        resp = await self.client.get("/forecast", params={"q": city + ",IN", "appid": self.api_key, "units": "metric", "cnt": 5})
        resp.raise_for_status()
        results = []
        for item in resp.json().get("list", []):
            results.append(WeatherResult(
                city=city,
                date=item["dt_txt"][:10],
                temp_c=item["main"]["temp"],
                feels_like_c=item["main"]["feels_like"],
                humidity_pct=item["main"]["humidity"],
                description=item["weather"][0]["description"].capitalize(),
                icon=item["weather"][0]["icon"],
                wind_kmh=round(item["wind"]["speed"] * 3.6, 1),
                source="live",
            ))
        return results


class FallbackWeatherService(WeatherService):
    def __init__(self, live: LiveWeatherService, mock: MockWeatherService) -> None:
        self._live, self._mock = live, mock

    async def get_weather(self, city: str, for_date: str | None = None) -> WeatherResult:
        result, _ = await with_fallback(
            lambda: self._live.get_weather(city, for_date),
            lambda: self._mock.get_weather(city, for_date),
            cache_key=f"weather:{city}:{for_date}",
            ttl=1800,
        )
        return result

    async def get_forecast(self, city: str) -> list[WeatherResult]:
        result, _ = await with_fallback(
            lambda: self._live.get_forecast(city),
            lambda: self._mock.get_forecast(city),
        )
        return result


def get_weather_service() -> WeatherService:
    s = get_settings()
    if s.use_live_weather and s.openweather_api_key:
        return FallbackWeatherService(LiveWeatherService(s.openweather_api_key), MockWeatherService())
    return MockWeatherService()
