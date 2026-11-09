"""Shared service utilities: data loading, fallback wrapper, cache stub."""
from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_json(filename: str) -> Any:
    """Load a mock data file from backend/data."""
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── In-memory cache (dev fallback; production uses Cloudant) ─────────────────
_cache: dict[str, tuple[Any, float]] = {}


def cache_get(key: str, ttl_seconds: int = 3600) -> Any | None:
    """Return cached value if not expired."""
    if key in _cache:
        value, ts = _cache[key]
        if time.time() - ts < ttl_seconds:
            return value
        del _cache[key]
    return None


def cache_set(key: str, value: Any) -> None:
    _cache[key] = (value, time.time())


async def with_fallback(live_fn, mock_fn, cache_key: str | None = None, ttl: int = 3600):
    """
    Try live_fn(); on any exception fall back to mock_fn().
    Optionally caches live result.
    Returns (result, source) where source is 'live' or 'mock'.
    """
    if cache_key:
        cached = cache_get(cache_key, ttl)
        if cached is not None:
            return cached, "live"

    try:
        result = await live_fn()
        if cache_key:
            cache_set(cache_key, result)
        return result, "live"
    except Exception as exc:
        logger.warning("Live service failed (%s), falling back to mock: %s", cache_key, exc)
        result = await mock_fn()
        return result, "mock"
