"""Delivery metrics in their original units.

Counts are orders. Time is seconds. Money is Canadian cents. Distance is
metres. Energy is the carrier's own integer energy unit, which is a scenario
parameter and not a measured kilowatt-hour.

Door-to-collection components are summed only over completed orders. They
partition the customer's critical path:

    queue + preparation + access transfer + loading + flight
        + unloading + customer pickup + failed pickup wait

Return legs and empty repositioning run in parallel or after collection, so
they are not added to that sum. Operating cost does include them.

``cost_per_completed_order`` divides all allocated operating cents by
completed orders only. Unserved and failed orders stay out of the denominator.
When nothing is completed the ratio is undefined. It is not reported as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

CRITICAL_COMPONENTS = (
    "queue",
    "preparation",
    "loading",
    "access_transfer",
    "flight",
    "unloading",
    "customer_pickup",
    "failed_pickup_wait",
)


class _Order(Protocol):
    status: str
    components: dict[str, int]
    operating_cents: int
    fallback_count: int
    completed_by: str
    billed_ground_distance_m: int
    billed_drone_distance_m: int
    billed_drone_flight_seconds: int
    handoff_failed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Metric:
    name: str
    value: int
    unit: str
    description: str


@dataclass(frozen=True)
class Ratio:
    """A quotient stored as integers. ``defined`` is false when the denominator is 0."""

    name: str
    numerator: int
    denominator: int
    numerator_unit: str
    denominator_unit: str
    description: str

    @property
    def defined(self) -> bool:
        return self.denominator > 0


@dataclass(frozen=True)
class MetricSet:
    counts: tuple[Metric, ...]
    quantities: tuple[Metric, ...]
    ratios: tuple[Ratio, ...]

    def count(self, name: str) -> Metric:
        return _find(self.counts, name)

    def quantity(self, name: str) -> Metric:
        return _find(self.quantities, name)

    def ratio(self, name: str) -> Ratio:
        for item in self.ratios:
            if item.name == name:
                return item
        raise KeyError(name)

    def integers(self) -> tuple[Metric, ...]:
        return self.counts + self.quantities


def _find(items: tuple[Metric, ...], name: str) -> Metric:
    for item in items:
        if item.name == name:
            return item
    raise KeyError(name)


def critical_path_seconds(components: dict[str, int]) -> int:
    return sum(components[name] for name in CRITICAL_COMPONENTS)


def build_metrics(orders: tuple[_Order, ...] | list[_Order], energy_units: int) -> MetricSet:
    completed = tuple(order for order in orders if order.status == "completed")
    failed = tuple(order for order in orders if order.status == "failed")
    unserved = tuple(order for order in orders if order.status == "unserved")
    excluded = tuple(order for order in orders if order.status == "excluded")

    def completed_component(name: str) -> int:
        return sum(order.components[name] for order in completed)

    door = sum(critical_path_seconds(order.components) for order in completed)
    cost = sum(order.operating_cents for order in orders)
    distance = sum(order.billed_ground_distance_m + order.billed_drone_distance_m for order in orders)
    flight = sum(order.billed_drone_flight_seconds for order in orders)
    completed_count = len(completed)

    counts = (
        Metric("completed_orders", completed_count, "orders", "Deliveries the recipient collected."),
        Metric("failed_orders", len(failed), "orders", "Attempts that moved food and did not complete."),
        Metric("unserved_orders", len(unserved), "orders", "Orders refused because capacity, shift, energy, or payload could not take them."),
        Metric("excluded_orders", len(excluded), "orders", "Orders excluded by route eligibility, weather, site hours, or unsafe food."),
        Metric("fallback_orders", sum(1 for order in orders if order.fallback_count > 0), "orders", "Drone requests that were reassigned to a van."),
        Metric("handoff_failures", sum(1 for order in orders if order.handoff_failed), "orders", "Locker handoffs the customer did not collect inside the window."),
        Metric("ground_completed_orders", sum(1 for order in completed if order.completed_by == "ground"), "orders", "Completed orders whose last mode was a van."),
        Metric("drone_completed_orders", sum(1 for order in completed if order.completed_by == "drone"), "orders", "Completed orders collected from a drone locker."),
        Metric("queue_rejections", sum(1 for order in orders if "queue_capacity" in order.reasons), "orders", "Orders rejected because the waiting line was full."),
    )
    quantities = (
        Metric("completed_door_to_collection_seconds", door, "seconds", "Sum of critical-path seconds over completed orders."),
        Metric("completed_queue_seconds", completed_component("queue"), "seconds", "Waiting time before service, completed orders."),
        Metric("completed_preparation_seconds", completed_component("preparation"), "seconds", "Preparation seconds on the critical path, completed orders."),
        Metric("completed_loading_seconds", completed_component("loading"), "seconds", "Loading seconds on the critical path, completed orders."),
        Metric("completed_access_transfer_seconds", completed_component("access_transfer"), "seconds", "Ground travel seconds on the critical path, completed orders."),
        Metric("completed_flight_seconds", completed_component("flight"), "seconds", "Outbound flight seconds on the critical path, completed orders."),
        Metric("completed_unloading_seconds", completed_component("unloading"), "seconds", "Unloading seconds on the critical path, completed orders."),
        Metric("completed_customer_pickup_seconds", completed_component("customer_pickup"), "seconds", "Customer walk seconds on the critical path, completed orders."),
        Metric("completed_failed_pickup_wait_seconds", completed_component("failed_pickup_wait"), "seconds", "Locker wait that preceded a completed ground fallback."),
        Metric("allocated_operating_cost_cents", cost, "cents", "All carrier operating cents, including failed and fallback work."),
        Metric("vehicle_distance_m", distance, "metres", "Declared metres travelled by vans and drones, including returns."),
        Metric("vehicle_flight_seconds", flight, "seconds", "Drone flight seconds including return legs and failed attempts."),
        Metric("energy_consumed_units", energy_units, "energy_units", "Scenario energy units consumed. Not a measured kilowatt-hour."),
    )
    ratios = (
        Ratio(
            "cost_per_completed_order",
            cost,
            completed_count,
            "cents",
            "orders",
            "Allocated operating cents divided by completed orders. Undefined when nothing is completed.",
        ),
        Ratio(
            "mean_door_to_collection",
            door,
            completed_count,
            "seconds",
            "orders",
            "Mean critical-path seconds per completed order. Undefined when nothing is completed.",
        ),
    )
    return MetricSet(counts, quantities, ratios)
