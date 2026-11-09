"""Disruption detection service – aggregates rail and flight alerts."""
from __future__ import annotations
import uuid
from ..models.providers import DisruptionAlert
from .rail import get_rail_service
from .flights import get_flight_service


class DisruptionService:
    async def check_disruptions(self, train_numbers: list[str] | None = None,
                                 flight_numbers: list[str] | None = None) -> list[DisruptionAlert]:
        raise NotImplementedError

    async def simulate_disruption(self, service_id: str, service_type: str) -> DisruptionAlert:
        raise NotImplementedError


class MockDisruptionService(DisruptionService):
    async def check_disruptions(self, train_numbers: list[str] | None = None,
                                 flight_numbers: list[str] | None = None) -> list[DisruptionAlert]:
        return []

    async def simulate_disruption(self, service_id: str, service_type: str) -> DisruptionAlert:
        return DisruptionAlert(
            alert_id=str(uuid.uuid4()),
            type="cancellation",
            service_id=service_id,
            service_type=service_type,
            description=f"Demo disruption: {service_type} {service_id} has been cancelled.",
            affected_leg=service_id,
            source="mock",
        )


class LiveDisruptionService(DisruptionService):
    """Aggregates real alerts from RailRadar and Aviationstack."""

    async def check_disruptions(self, train_numbers: list[str] | None = None,
                                 flight_numbers: list[str] | None = None) -> list[DisruptionAlert]:
        alerts: list[DisruptionAlert] = []
        rail_svc = get_rail_service()
        raw = await rail_svc.get_disruptions()
        for item in raw:
            if not train_numbers or item.get("train_number") in train_numbers:
                alerts.append(DisruptionAlert(
                    alert_id=str(uuid.uuid4()),
                    type=item.get("type", "cancellation"),
                    service_id=item.get("train_number", ""),
                    service_type="train",
                    description=item.get("message", "Service disrupted"),
                    affected_leg=item.get("train_number"),
                    source="live",
                ))
        return alerts

    async def simulate_disruption(self, service_id: str, service_type: str) -> DisruptionAlert:
        return DisruptionAlert(
            alert_id=str(uuid.uuid4()),
            type="cancellation",
            service_id=service_id,
            service_type=service_type,
            description=f"Demo disruption: {service_type} {service_id} has been cancelled.",
            affected_leg=service_id,
            source="mock",
        )


def get_disruption_service() -> DisruptionService:
    return LiveDisruptionService()
