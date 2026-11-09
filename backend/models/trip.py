"""Trip domain models."""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class TripPreferences(BaseModel):
    """Extracted travel preferences from user chat."""
    origin: str
    destination: str
    start_date: str  # ISO date YYYY-MM-DD
    end_date: str
    num_adults: int = 1
    num_children: int = 0
    budget_inr: Optional[float] = None
    trip_type: Literal["domestic", "international"] = "domestic"
    transport_preference: Optional[str] = None  # "train", "flight", "bus", "flexible"
    accommodation_type: Optional[str] = None    # "hotel", "stays", "hostel", "any"
    interests: list[str] = Field(default_factory=list)
    clarifying_question: Optional[str] = None   # if model needs one more answer


class Activity(BaseModel):
    """Single activity on an itinerary day."""
    time: str
    title: str
    description: str
    location: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    category: str = "sightseeing"  # sightseeing, food, transport, accommodation
    cost_inr: Optional[float] = None
    booking_ref: Optional[str] = None
    source: Literal["live", "mock"] = "mock"


class TransportOption(BaseModel):
    """A transport leg option."""
    mode: Literal["train", "flight", "bus", "cab"]
    provider_name: str
    service_id: str
    departure: str
    arrival: str
    origin: str
    destination: str
    price_inr: float
    duration_minutes: int
    class_or_type: Optional[str] = None
    availability: Optional[int] = None
    source: Literal["live", "mock"] = "mock"
    badges: list[str] = Field(default_factory=list)  # Cheapest, Fastest, Best Value


class StayOption(BaseModel):
    """A stay option."""
    id: str
    name: str
    city: str
    price_per_night: float
    currency: str = "INR"
    rating: Optional[float] = None
    image: Optional[str] = None
    url: Optional[str] = None
    source: Literal["live", "mock"] = "mock"
    best_value: bool = False
    badges: list[str] = Field(default_factory=list)


class ItineraryDay(BaseModel):
    """One day of the itinerary."""
    date: str
    day_number: int
    city: str
    activities: list[Activity] = Field(default_factory=list)
    transport: Optional[TransportOption] = None
    stay: Optional[StayOption] = None
    weather_summary: Optional[str] = None


class Itinerary(BaseModel):
    """Full trip itinerary."""
    trip_id: str
    title: str
    preferences: TripPreferences
    days: list[ItineraryDay] = Field(default_factory=list)
    total_budget_inr: float = 0.0
    granite_summary: str = ""
    created_at: str = ""
    source: Literal["live", "mock"] = "mock"


class PriceComparison(BaseModel):
    """Price comparison across transport or stays."""
    category: str  # "transport" or "stays"
    options: list[TransportOption | StayOption] = Field(default_factory=list)
    granite_reason: str = ""


class ReplanResult(BaseModel):
    """Smart replan output."""
    trip_id: str
    disruption_description: str
    granite_explanation: str
    before_days: list[ItineraryDay] = Field(default_factory=list)
    after_days: list[ItineraryDay] = Field(default_factory=list)
    approved: bool = False
