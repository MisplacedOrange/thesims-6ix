"""Committed logistics events.

The renderer interpolates movement from these records. It does not invent
positions between frames that the log does not justify. Each movement event
carries waypoints in integer metres, a departure second, and an arrival
second. Stationary work (loading, charging, preparation) carries the place
and the same time bounds so a queue or a bay can be shown.

``cosmetic_note`` is display text. It is excluded from the economic hash.
"""

from __future__ import annotations

from dataclasses import dataclass

# Kinds the scene needs in order to show queues, vans, and drone paths.
PREPARATION_STARTED = "PreparationStarted"
PREPARATION_COMPLETED = "PreparationCompleted"
QUEUE_JOINED = "QueueJoined"
QUEUE_ADVANCED = "QueueAdvanced"
QUEUE_REJECTED = "QueueRejected"
SERVICE_STARTED = "ServiceStarted"
LOADING_STARTED = "LoadingStarted"
LOADING_COMPLETED = "LoadingCompleted"
JOURNEY_STARTED = "JourneyStarted"
JOURNEY_ARRIVED = "JourneyArrived"
UNLOADING_STARTED = "UnloadingStarted"
UNLOADING_COMPLETED = "UnloadingCompleted"
DRONE_FLIGHT_STARTED = "DroneFlightStarted"
DRONE_FLIGHT_COMPLETED = "DroneFlightCompleted"
NOTIFICATION_SENT = "NotificationSent"
CUSTOMER_PICKUP_STARTED = "CustomerPickupStarted"
CUSTOMER_PICKUP_COMPLETED = "CustomerPickupCompleted"
HANDOFF_FAILED = "HandoffFailed"
GROUND_FALLBACK_ASSIGNED = "GroundFallbackAssigned"
ROUTE_INELIGIBLE = "RouteIneligible"
WEATHER_EXCLUDED = "WeatherExcluded"
CARRIER_UNAVAILABLE = "CarrierUnavailable"
CHARGING_STARTED = "ChargingStarted"
CHARGING_COMPLETED = "ChargingCompleted"
DELIVERY_COMPLETED = "DeliveryCompleted"
DELIVERY_FAILED = "DeliveryFailed"
DELIVERY_EXCLUDED = "DeliveryExcluded"
DELIVERY_UNSERVED = "DeliveryUnserved"
COST_ALLOCATED = "CostAllocated"

MOVEMENT_KINDS = frozenset(
    {
        JOURNEY_STARTED,
        DRONE_FLIGHT_STARTED,
        CUSTOMER_PICKUP_STARTED,
    }
)


@dataclass(frozen=True)
class LogisticsEvent:
    event_id: str
    sequence: int
    second: int
    phase: int
    kind: str
    causes: tuple[str, ...]
    actor_id: str
    place_id: str | None = None
    vehicle_id: str | None = None
    order_id: str | None = None
    leg: str = ""
    waypoints_m: tuple[tuple[int, int], ...] = ()
    depart_second: int | None = None
    arrive_second: int | None = None
    queue_id: str | None = None
    queue_position: int | None = None
    grams: int | None = None
    cents: int | None = None
    reason: str = ""
    lot_ids: tuple[str, ...] = ()
    reservation_ids: tuple[str, ...] = ()
    journey_id: str | None = None
    cosmetic_note: str = ""

    def economic_dict(self) -> dict[str, object]:
        """Fields that enter the economic hash. Cosmetic text is omitted."""

        return {
            "arrive_second": self.arrive_second,
            "actor_id": self.actor_id,
            "causes": list(self.causes),
            "cents": self.cents,
            "depart_second": self.depart_second,
            "event_id": self.event_id,
            "grams": self.grams,
            "journey_id": self.journey_id,
            "kind": self.kind,
            "leg": self.leg,
            "lot_ids": list(self.lot_ids),
            "order_id": self.order_id,
            "phase": self.phase,
            "place_id": self.place_id,
            "queue_id": self.queue_id,
            "queue_position": self.queue_position,
            "reason": self.reason,
            "reservation_ids": list(self.reservation_ids),
            "second": self.second,
            "sequence": self.sequence,
            "vehicle_id": self.vehicle_id,
            "waypoints_m": [list(point) for point in self.waypoints_m],
        }
