"""Provider response models (normalised across live and mock sources)."""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class TrainResult(BaseModel):
    train_number: str
    train_name: str
    origin: str
    destination: str
    departure: str
    arrival: str
    duration_minutes: int
    classes: list[str] = Field(default_factory=list)
    fare_inr: dict[str, float] = Field(default_factory=dict)  # {"SL": 450, "3A": 1200}
    availability: dict[str, int] = Field(default_factory=dict)
    status: str = "ON_TIME"
    platform: Optional[str] = None
    source: Literal["live", "mock"] = "mock"


class FlightResult(BaseModel):
    flight_number: str
    airline: str
    origin: str
    destination: str
    departure: str
    arrival: str
    duration_minutes: int
    fare_inr: float
    class_type: str = "Economy"
    stops: int = 0
    layover_city: Optional[str] = None
    availability: int = 9
    status: str = "SCHEDULED"
    source: Literal["live", "mock"] = "mock"


class BusResult(BaseModel):
    bus_id: str
    operator: str
    origin: str
    destination: str
    departure: str
    arrival: str
    duration_minutes: int
    fare_inr: float
    bus_type: str = "AC Sleeper"
    availability: int = 20
    source: Literal["live", "mock"] = "mock"


class CabEstimate(BaseModel):
    cab_type: str  # Hatchback, Sedan, SUV, Auto
    provider: str
    origin: str
    destination: str
    distance_km: float
    fare_inr: float
    duration_minutes: int
    source: Literal["live", "mock"] = "mock"


class WeatherResult(BaseModel):
    city: str
    date: str
    temp_c: float
    feels_like_c: float
    humidity_pct: int
    description: str
    icon: str
    wind_kmh: float
    source: Literal["live", "mock"] = "mock"


class PlaceResult(BaseModel):
    place_id: str
    name: str
    category: str
    address: str
    lat: float
    lon: float
    rating: Optional[float] = None
    opening_hours: Optional[str] = None
    source: Literal["live", "mock"] = "mock"


class RouteResult(BaseModel):
    origin: str
    destination: str
    distance_km: float
    duration_minutes: int
    steps: list[str] = Field(default_factory=list)
    source: Literal["live", "mock"] = "mock"


class FxResult(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    converted_amount: float
    source: Literal["live", "mock"] = "mock"


class AirportResult(BaseModel):
    iata_code: str
    name: str
    city: str
    country: str
    lat: float
    lon: float
    source: Literal["live", "mock"] = "mock"


class VisaInfo(BaseModel):
    nationality: str
    destination_country: str
    visa_required: bool
    visa_type: Optional[str] = None
    notes: str = ""
    source: Literal["live", "mock"] = "mock"


class PhotoResult(BaseModel):
    place: str
    photos: list[str] = Field(default_factory=list)  # URLs or data URIs
    source: Literal["live", "mock"] = "mock"


class StayResult(BaseModel):
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


class GeocodingResult(BaseModel):
    query: str
    lat: float
    lon: float
    display_name: str
    country: str = "India"
    source: Literal["live", "mock"] = "mock"


class DisruptionAlert(BaseModel):
    alert_id: str
    type: Literal["cancellation", "delay", "diversion", "weather"]
    service_id: str
    service_type: Literal["train", "flight", "bus"]
    description: str
    affected_leg: Optional[str] = None
    source: Literal["live", "mock"] = "mock"
