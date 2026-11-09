"""Visa information service – mock only."""
from __future__ import annotations
from ..models.providers import VisaInfo
from .base import load_json


class VisaService:
    async def get_visa_info(self, nationality: str, destination_country: str) -> VisaInfo:
        raise NotImplementedError


class MockVisaService(VisaService):
    async def get_visa_info(self, nationality: str, destination_country: str) -> VisaInfo:
        data = load_json("visa.json")
        for v in data:
            if (v["nationality"].lower() == nationality.lower() and
                    v["destination_country"].lower() == destination_country.lower()):
                return VisaInfo(**v, source="mock")
        return VisaInfo(
            nationality=nationality, destination_country=destination_country,
            visa_required=False, notes="Visa info unavailable. Please check official government sources.",
            source="mock",
        )


def get_visa_service() -> VisaService:
    return MockVisaService()
