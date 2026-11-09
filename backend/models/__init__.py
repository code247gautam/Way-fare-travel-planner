"""Pydantic models for Wayfare."""
from .trip import (
    TripPreferences,
    Itinerary,
    ItineraryDay,
    Activity,
    TransportOption,
    StayOption,
    PriceComparison,
    ReplanResult,
)
from .chat import ChatMessage, ChatRequest, ChatResponse
from .plan import PlanRequest, PlanResponse
from .share import ShareRequest, ShareResponse, ShareRole, Comment, CollabTrip
from .providers import (
    TrainResult,
    FlightResult,
    BusResult,
    CabEstimate,
    WeatherResult,
    PlaceResult,
    RouteResult,
    FxResult,
    AirportResult,
    VisaInfo,
    PhotoResult,
    StayResult,
    GeocodingResult,
    DisruptionAlert,
)

__all__ = [
    "TripPreferences", "Itinerary", "ItineraryDay", "Activity",
    "TransportOption", "StayOption", "PriceComparison", "ReplanResult",
    "ChatMessage", "ChatRequest", "ChatResponse",
    "PlanRequest", "PlanResponse",
    "ShareRequest", "ShareResponse", "ShareRole", "Comment", "CollabTrip",
    "TrainResult", "FlightResult", "BusResult", "CabEstimate",
    "WeatherResult", "PlaceResult", "RouteResult", "FxResult",
    "AirportResult", "VisaInfo", "PhotoResult", "StayResult",
    "GeocodingResult", "DisruptionAlert",
]
