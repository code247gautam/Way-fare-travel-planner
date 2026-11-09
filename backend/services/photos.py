"""Destination photos service – mock only."""
from __future__ import annotations
from ..models.providers import PhotoResult
from .base import load_json


class PhotoService:
    async def get_photos(self, place: str) -> PhotoResult:
        raise NotImplementedError


class MockPhotoService(PhotoService):
    async def get_photos(self, place: str) -> PhotoResult:
        data = load_json("photos.json")
        for city, urls in data.items():
            if city.lower() in place.lower():
                return PhotoResult(place=place, photos=urls, source="mock")
        return PhotoResult(place=place, photos=[], source="mock")


def get_photo_service() -> PhotoService:
    return MockPhotoService()
