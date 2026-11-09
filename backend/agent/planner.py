"""Travel planner: tool-calling loop with Granite, pydantic validation, preference extraction."""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Any

from pydantic import ValidationError

from ..models.trip import TripPreferences, Itinerary, ItineraryDay, Activity, TransportOption, StayOption
from ..models.providers import TrainResult, FlightResult, BusResult, StayResult, WeatherResult, PlaceResult
from .granite_client import GraniteClient
from .prompts import PREFERENCE_EXTRACTION_PROMPT, SYSTEM_PROMPT, COMPARE_PROMPT
from .tool_schemas import TOOL_SCHEMAS
from ..services import (
    get_rail_service, get_weather_service, get_places_service, get_geocode_service,
    get_fx_service, get_flight_service, get_stays_service, get_bus_service,
    get_cab_service, get_airport_service, get_visa_service, get_photo_service,
    get_disruption_service,
)

logger = logging.getLogger(__name__)


class TravelPlanner:
    """Granite-powered travel planner with tool-calling loop."""

    def __init__(self, granite: GraniteClient) -> None:
        self.granite = granite

    async def extract_preferences(self, user_message: str, context: str = "") -> TripPreferences:
        """Extract and validate TripPreferences from user message. Retries once on failure."""
        prompt = PREFERENCE_EXTRACTION_PROMPT.format(
            user_message=user_message,
            context=context or "No prior context.",
        )
        try:
            raw = await self.granite.generate_json(prompt, system=SYSTEM_PROMPT)
        except Exception:
            # LLM unavailable or model error – fall back to heuristic extraction
            raw = _heuristic_extract(user_message)
        return await self._parse_preferences(raw, prompt)

    async def _parse_preferences(self, raw: str, original_prompt: str) -> TripPreferences:
        """Parse with one repair retry."""
        try:
            data = _extract_json(raw)
            return TripPreferences(**data)
        except (ValidationError, ValueError, json.JSONDecodeError) as err:
            logger.warning("Preference parse failed (%s), retrying with repair prompt.", err)
            from .prompts import REPAIR_PROMPT
            repair = REPAIR_PROMPT.format(error=str(err), original=raw)
            raw2 = await self.granite.generate_json(repair)
            try:
                data = _extract_json(raw2)
                return TripPreferences(**data)
            except Exception as err2:
                logger.error("Preference parse failed after repair: %s", err2)
                raise ValueError(f"Could not parse preferences: {err2}") from err2

    async def plan_trip(self, preferences: TripPreferences) -> Itinerary:
        """Build a full itinerary using the tool-calling loop."""
        trip_id = str(uuid.uuid4())
        tool_results: dict[str, Any] = {}

        # Gather data via tools
        train_opts = await self._call_search_trains(preferences)
        flight_opts = await self._call_search_flights(preferences)
        bus_opts = await self._call_search_buses(preferences)
        stays = await self._call_search_stays(preferences)
        places = await self._call_find_places(preferences.destination)
        weather = await self._call_get_weather(preferences)

        # Visa for international trips
        if preferences.trip_type == "international":
            visa = await get_visa_service().get_visa_info("Indian", preferences.destination)
        else:
            visa = None

        # Apply price comparison badges (normal planning only)
        self._apply_badges(train_opts, flight_opts, bus_opts, stays)

        # Ask Granite for itinerary summary
        granite_summary = await self._get_granite_summary(preferences)

        # Build itinerary days
        days = self._build_days(preferences, train_opts, flight_opts, bus_opts, stays, places, weather)

        total_budget = sum(
            (d.transport.price_inr if d.transport else 0) +
            (d.stay.price_per_night if d.stay else 0)
            for d in days
        )

        return Itinerary(
            trip_id=trip_id,
            title=f"{preferences.origin} → {preferences.destination}",
            preferences=preferences,
            days=days,
            total_budget_inr=round(total_budget),
            granite_summary=granite_summary,
            created_at=datetime.utcnow().isoformat(),
            source="mock",
        )

    async def _get_granite_summary(self, preferences: TripPreferences) -> str:
        prompt = (
            f"Write a 2-sentence trip summary for a {preferences.trip_type} trip from "
            f"{preferences.origin} to {preferences.destination} "
            f"({preferences.start_date} to {preferences.end_date}), "
            f"{preferences.num_adults} adult(s). Interests: {', '.join(preferences.interests) or 'general'}."
        )
        try:
            return await self.granite.generate(prompt, system=SYSTEM_PROMPT)
        except Exception:
            return (
                f"A wonderful {preferences.trip_type} trip from {preferences.origin} to "
                f"{preferences.destination} ({preferences.start_date} to {preferences.end_date}). "
                "Enjoy transport, stays, and sightseeing curated just for you."
            )

    async def chat(self, message: str, history: list[dict]) -> str:
        """Single-turn chat response from Granite."""
        from .prompts import CHAT_SYSTEM_PROMPT
        context = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
        prompt = f"{context}\nuser: {message}\nassistant:"
        try:
            reply = await self.granite.generate(prompt, system=CHAT_SYSTEM_PROMPT)
            return reply.strip() if reply else _heuristic_chat_reply(message)
        except Exception:
            return _heuristic_chat_reply(message)

    async def compare_prices(self, trains: list, flights: list, buses: list, stays: list) -> dict:
        """Get Granite reason for best value option."""
        all_transport = [
            {"id": t.train_number, "type": "train", "price_inr": min(t.fare_inr.values()) if t.fare_inr else 0,
             "duration_minutes": t.duration_minutes, "name": t.train_name}
            for t in trains
        ] + [
            {"id": f.flight_number, "type": "flight", "price_inr": f.fare_inr,
             "duration_minutes": f.duration_minutes, "name": f.airline}
            for f in flights
        ] + [
            {"id": b.bus_id, "type": "bus", "price_inr": b.fare_inr,
             "duration_minutes": b.duration_minutes, "name": b.operator}
            for b in buses
        ]
        prompt = COMPARE_PROMPT.format(options=json.dumps(all_transport[:8]))
        try:
            raw = await self.granite.generate_json(prompt, system=SYSTEM_PROMPT)
            data = _extract_json(raw)
            return data
        except Exception:
            # Fallback: pick cheapest as best value
            best = min(all_transport, key=lambda x: x["price_inr"], default={})
            return {
                "granite_reason": "The overnight train offers the best combination of cost and comfort for this route.",
                "best_value_id": best.get("id", ""),
            }

    # ── Tool call helpers ───────────────────────────────────────────────────────

    async def _call_search_trains(self, prefs: TripPreferences) -> list[TrainResult]:
        svc = get_rail_service()
        try:
            return await svc.search_trains(prefs.origin, prefs.destination, prefs.start_date)
        except Exception:
            return []

    async def _call_search_flights(self, prefs: TripPreferences) -> list[FlightResult]:
        svc = get_flight_service()
        try:
            return await svc.search_flights(prefs.origin, prefs.destination, prefs.start_date)
        except Exception:
            return []

    async def _call_search_buses(self, prefs: TripPreferences) -> list[BusResult]:
        svc = get_bus_service()
        try:
            return await svc.search_buses(prefs.origin, prefs.destination, prefs.start_date)
        except Exception:
            return []

    async def _call_search_stays(self, prefs: TripPreferences) -> list[StayResult]:
        svc = get_stays_service()
        try:
            return await svc.search_stays(prefs.destination, prefs.start_date, prefs.end_date)
        except Exception:
            return []

    async def _call_find_places(self, city: str) -> list[PlaceResult]:
        svc = get_places_service()
        try:
            return await svc.find_places(city)
        except Exception:
            return []

    async def _call_get_weather(self, prefs: TripPreferences) -> list[WeatherResult]:
        svc = get_weather_service()
        try:
            return [await svc.get_weather(prefs.destination, prefs.start_date)]
        except Exception:
            return []

    def _apply_badges(self, trains: list, flights: list, buses: list, stays: list) -> None:
        """Compute Cheapest, Fastest, Best Value badges and store in _badge_map."""
        all_t: list[Any] = list(trains) + list(flights) + list(buses)
        if not all_t:
            return

        def price(t: Any) -> float:
            if isinstance(t, TrainResult):
                return min(t.fare_inr.values()) if t.fare_inr else 9999999
            if isinstance(t, FlightResult):
                return t.fare_inr
            if isinstance(t, BusResult):
                return t.fare_inr
            return 9999999

        def duration(t: Any) -> int:
            return t.duration_minutes

        cheapest = min(all_t, key=price)
        fastest = min(all_t, key=duration)
        sorted_by_price = sorted(all_t, key=price)
        sorted_by_dur = sorted(all_t, key=duration)

        def score(t: Any) -> int:
            return sorted_by_price.index(t) + sorted_by_dur.index(t)

        best_value = min(all_t, key=score)

        # Store badges in a dict keyed by service id (not mutating provider models)
        self._badge_map: dict[str, list[str]] = {}
        for t in all_t:
            sid = getattr(t, "train_number", None) or getattr(t, "flight_number", None) or getattr(t, "bus_id", None) or ""
            self._badge_map[sid] = []

        def _sid(t: Any) -> str:
            return getattr(t, "train_number", None) or getattr(t, "flight_number", None) or getattr(t, "bus_id", None) or ""

        self._badge_map.setdefault(_sid(cheapest), []).append("Cheapest")
        self._badge_map.setdefault(_sid(fastest), []).append("Fastest")
        self._badge_map.setdefault(_sid(best_value), []).append("Best Value")

        # Stays
        if stays:
            sorted_stays = sorted(stays, key=lambda s: s.price_per_night)
            sorted_stays[0].best_value = True

    def _build_days(
        self,
        prefs: TripPreferences,
        trains: list, flights: list, buses: list,
        stays: list, places: list, weather: list,
    ) -> list[ItineraryDay]:
        start = date.fromisoformat(prefs.start_date)
        end = date.fromisoformat(prefs.end_date)
        total_days = (end - start).days + 1
        days = []

        # Pick best transport
        transport: TransportOption | None = None
        if trains and (prefs.transport_preference in ("train", None, "flexible")):
            t = next((x for x in trains if "Best Value" in x.badges), trains[0])
            transport = TransportOption(
                mode="train", provider_name=t.train_name, service_id=t.train_number,
                departure=t.departure, arrival=t.arrival, origin=prefs.origin, destination=prefs.destination,
                price_inr=min(t.fare_inr.values()) if t.fare_inr else 0,
                duration_minutes=t.duration_minutes, source=t.source, badges=t.badges,
            )
        elif flights and prefs.transport_preference == "flight":
            f = next((x for x in flights if "Best Value" in x.badges), flights[0])
            transport = TransportOption(
                mode="flight", provider_name=f.airline, service_id=f.flight_number,
                departure=f.departure, arrival=f.arrival, origin=prefs.origin, destination=prefs.destination,
                price_inr=f.fare_inr, duration_minutes=f.duration_minutes, source=f.source, badges=f.badges,
            )

        # Pick best stay
        stay_opt: StayOption | None = None
        if stays:
            s = next((x for x in stays if x.best_value), stays[0])
            stay_opt = StayOption(
                id=s.id, name=s.name, city=s.city, price_per_night=s.price_per_night,
                currency=s.currency, rating=s.rating, image=s.image, url=s.url,
                source=s.source, best_value=s.best_value,
            )

        weather_summary = weather[0].description if weather else None

        for i in range(total_days):
            day_date = start + timedelta(days=i)
            day_places = places[i * 2: i * 2 + 2] if places else []
            activities = []

            if i == 0 and transport:
                activities.append(Activity(
                    time=transport.departure, title=f"Depart {prefs.origin}",
                    description=f"Travel by {transport.mode} to {prefs.destination}.",
                    location=prefs.origin, category="transport",
                    cost_inr=transport.price_inr, source=transport.source,
                ))

            for pl in day_places:
                activities.append(Activity(
                    time="10:00" if not activities else "14:00",
                    title=f"Visit {pl.name}",
                    description=pl.address,
                    location=pl.name, lat=pl.lat, lon=pl.lon,
                    category="sightseeing", source=pl.source,
                ))

            days.append(ItineraryDay(
                date=str(day_date),
                day_number=i + 1,
                city=prefs.destination if i > 0 else prefs.origin,
                activities=activities,
                transport=transport if i == 0 else None,
                stay=stay_opt,
                weather_summary=weather_summary,
            ))

        return days


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a string (Granite sometimes adds prose)."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in: {text[:200]}")
    return json.loads(text[start: end + 1])


def _heuristic_extract(user_message: str) -> str:
    """
    Derive travel preferences from free text without Granite.
    Used when IBM watsonx.ai is not configured (no API key).
    Returns a JSON string compatible with TripPreferences.
    """
    import re
    from datetime import date, timedelta

    msg = user_message.lower()

    # Origin / destination heuristics
    cities = [
        "Delhi", "Mumbai", "Bengaluru", "Bangalore", "Chennai", "Kolkata",
        "Hyderabad", "Pune", "Jaipur", "Udaipur", "Goa", "Agra", "Varanasi",
        "Kochi", "Amritsar", "Mysuru", "Mysore",
        "London", "Dubai", "Paris", "Singapore", "Bangkok",
    ]
    found = [c for c in cities if c.lower() in msg]
    origin = found[0] if len(found) >= 1 else "Delhi"
    destination = found[1] if len(found) >= 2 else "Mumbai"

    # Adults
    adults_match = re.search(r'(\d+)\s*adult', msg)
    num_adults = int(adults_match.group(1)) if adults_match else 2

    # Children
    children_match = re.search(r'(\d+)\s*child', msg)
    num_children = int(children_match.group(1)) if children_match else 0

    # Days / duration
    days_match = re.search(r'(\d+)[- ]day', msg)
    num_days = int(days_match.group(1)) if days_match else 3

    today = date.today()
    start_date = str(today + timedelta(days=7))
    end_date = str(today + timedelta(days=7 + num_days - 1))

    # Trip type
    intl_keywords = ["london", "dubai", "paris", "singapore", "bangkok", "international"]
    trip_type = "international" if any(k in msg for k in intl_keywords) else "domestic"

    # Budget
    budget_match = re.search(r'(?:budget|rs\.?|₹|inr)\s*(\d[\d,]*)', msg)
    budget_inr = float(budget_match.group(1).replace(",", "")) if budget_match else None

    # Transport preference
    transport = None
    if "train" in msg:
        transport = "train"
    elif "flight" in msg or "fly" in msg:
        transport = "flight"
    elif "bus" in msg:
        transport = "bus"

    import json as _json
    return _json.dumps({
        "origin": origin,
        "destination": destination,
        "start_date": start_date,
        "end_date": end_date,
        "num_adults": num_adults,
        "num_children": num_children,
        "budget_inr": budget_inr,
        "trip_type": trip_type,
        "transport_preference": transport,
        "accommodation_type": "stays",
        "interests": [],
        "clarifying_question": None,
    })


def _heuristic_chat_reply(message: str) -> str:
    """Scripted chat reply when Granite is not configured."""
    msg = message.lower()
    if any(w in msg for w in ["hello", "hi", "hey", "start"]):
        return "Hi! I'm Wayfare. Tell me where you'd like to go — e.g. \"Plan a 4-day trip from Delhi to Goa for 2 adults\"."
    if any(w in msg for w in ["plan", "trip", "travel", "go to", "visit"]):
        return "Sure! To build your itinerary I need: origin, destination, travel dates, and number of travellers. For example: \"Delhi to Jaipur, 3 days, 2 adults\"."
    if any(w in msg for w in ["weather", "rain", "temperature"]):
        return "I can show weather for any city. Once you plan a trip, weather is shown on each day card automatically."
    if any(w in msg for w in ["cost", "price", "cheap", "budget"]):
        return "Head over to the Compare tab to see Cheapest, Fastest, and Best Value options across trains, flights, and buses."
    if any(w in msg for w in ["train", "flight", "bus", "cab"]):
        return "I search trains (RailRadar), flights (Aviationstack), buses, and cabs. Type your trip details and I'll show all options."
    return "I'm Wayfare, your AI travel assistant. Describe where you'd like to go and I'll build a full itinerary for you!"
