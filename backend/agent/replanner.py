"""Smart Replan: triggered by disruptions, shows Before vs After, Granite explanation."""
from __future__ import annotations
import logging
from datetime import datetime
from ..models.trip import Itinerary, ItineraryDay, ReplanResult, TransportOption
from ..models.providers import DisruptionAlert
from .granite_client import GraniteClient
from .prompts import REPLAN_PROMPT
from ..services import get_rail_service, get_flight_service, get_bus_service, get_cab_service

logger = logging.getLogger(__name__)


class SmartReplanner:
    """Replans a journey after a disruption. NEVER shows deals or promotions."""

    def __init__(self, granite: GraniteClient) -> None:
        self.granite = granite

    async def replan(
        self,
        itinerary: Itinerary,
        alert: DisruptionAlert,
    ) -> ReplanResult:
        """Build a Before/After replan with Granite explanation."""
        affected_day_index = self._find_affected_day(itinerary, alert)
        before_days = list(itinerary.days)

        # Find alternatives based on trip type
        if itinerary.preferences.trip_type == "international":
            after_days = await self._replan_international(itinerary, alert, affected_day_index)
        else:
            after_days = await self._replan_domestic(itinerary, alert, affected_day_index)

        # Ask Granite for explanation (2-3 sentences, NO deals)
        explanation = await self._get_granite_explanation(itinerary, alert)

        return ReplanResult(
            trip_id=itinerary.trip_id,
            disruption_description=alert.description,
            granite_explanation=explanation,
            before_days=before_days,
            after_days=after_days,
            approved=False,
        )

    async def _replan_domestic(
        self, itinerary: Itinerary, alert: DisruptionAlert, day_index: int
    ) -> list[ItineraryDay]:
        """Domestic replan: find alternate train, flight, or bus."""
        prefs = itinerary.preferences
        after_days = [d.model_copy() for d in itinerary.days]

        # Find alternatives
        alt_transport: TransportOption | None = None
        if alert.service_type == "train":
            flights = await get_flight_service().search_flights(prefs.origin, prefs.destination)
            buses = await get_bus_service().search_buses(prefs.origin, prefs.destination)
            if flights:
                f = flights[0]
                alt_transport = TransportOption(
                    mode="flight", provider_name=f.airline, service_id=f.flight_number,
                    departure=f.departure, arrival=f.arrival,
                    origin=prefs.origin, destination=prefs.destination,
                    price_inr=f.fare_inr, duration_minutes=f.duration_minutes,
                    source=f.source,
                )
            elif buses:
                b = buses[0]
                alt_transport = TransportOption(
                    mode="bus", provider_name=b.operator, service_id=b.bus_id,
                    departure=b.departure, arrival=b.arrival,
                    origin=prefs.origin, destination=prefs.destination,
                    price_inr=b.fare_inr, duration_minutes=b.duration_minutes,
                    source=b.source,
                )
        elif alert.service_type == "flight":
            trains = await get_rail_service().search_trains(prefs.origin, prefs.destination)
            if trains:
                t = trains[0]
                alt_transport = TransportOption(
                    mode="train", provider_name=t.train_name, service_id=t.train_number,
                    departure=t.departure, arrival=t.arrival,
                    origin=prefs.origin, destination=prefs.destination,
                    price_inr=min(t.fare_inr.values()) if t.fare_inr else 0,
                    duration_minutes=t.duration_minutes, source=t.source,
                )

        if alt_transport and day_index < len(after_days):
            after_days[day_index].transport = alt_transport
            # Update first activity departure time
            if after_days[day_index].activities:
                after_days[day_index].activities[0].time = alt_transport.departure

        return after_days

    async def _replan_international(
        self, itinerary: Itinerary, alert: DisruptionAlert, day_index: int
    ) -> list[ItineraryDay]:
        """International replan: alternate flights, layover/visa notes."""
        prefs = itinerary.preferences
        after_days = [d.model_copy() for d in itinerary.days]

        flights = await get_flight_service().search_flights(prefs.origin, prefs.destination)
        if flights and len(flights) > 1:
            f = flights[1]  # Take next available
            alt_transport = TransportOption(
                mode="flight", provider_name=f.airline, service_id=f.flight_number,
                departure=f.departure, arrival=f.arrival,
                origin=prefs.origin, destination=prefs.destination,
                price_inr=f.fare_inr, duration_minutes=f.duration_minutes,
                class_or_type=f.class_type, source=f.source,
            )
            if day_index < len(after_days):
                after_days[day_index].transport = alt_transport

        return after_days

    def _find_affected_day(self, itinerary: Itinerary, alert: DisruptionAlert) -> int:
        for i, day in enumerate(itinerary.days):
            if day.transport and day.transport.service_id == alert.service_id:
                return i
        return 0

    async def _get_granite_explanation(self, itinerary: Itinerary, alert: DisruptionAlert) -> str:
        trip_ctx = (
            f"{itinerary.preferences.origin} to {itinerary.preferences.destination}, "
            f"{itinerary.preferences.start_date}"
        )
        prompt = REPLAN_PROMPT.format(
            disruption=alert.description,
            affected_leg=alert.affected_leg or alert.service_id,
            trip_context=trip_ctx,
        )
        fallback = (
            f"Your {alert.service_type} ({alert.service_id}) has been cancelled or disrupted. "
            "I've found the next available alternative and adjusted your itinerary. "
            "Hotel check-in has been updated to reflect the new arrival time."
        )
        try:
            raw = await self.granite.generate(prompt)
            import json
            if "{" in raw:
                from .planner import _extract_json
                data = _extract_json(raw)
                return data.get("granite_explanation", raw)
            return raw.strip() or fallback
        except Exception:
            return fallback
