"""Plan API models."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from .trip import TripPreferences, Itinerary


class PlanRequest(BaseModel):
    preferences: TripPreferences
    session_id: Optional[str] = None


class PlanResponse(BaseModel):
    trip_id: str
    itinerary: Itinerary
    share_token: Optional[str] = None
