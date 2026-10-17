"""Scenario records the logistics engine accepts.

Distances are declared integers in metres. Waypoints are the animation
geometry and are not remeasured. A corridor's approval flag is a modeling
condition inside the scenario, not a Transport Canada permission.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.logistics.errors import LogisticsError
from sim.logistics.units import UNIT_SYSTEM, require_int, require_nonnegative, require_positive

APPROVALS = frozenset({"no_approval", "conditional", "approved_in_scenario"})
STORAGE_CLASSES = frozenset({"ambient", "chilled", "frozen"})
COLD_CLASSES = frozenset({"chilled", "frozen"})
MODES = frozenset({"ground", "drone"})
HANDOFFS = frozenset({"collect", "miss"})


def _point(name: str, value: tuple[int, int]) -> tuple[int, int]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise LogisticsError(f"{name} must be an (x, y) metre pair")
    return (require_int(f"{name}.x", value[0]), require_int(f"{name}.y", value[1]))


@dataclass(frozen=True)
class ScenarioContext:
    """Identity shared by a baseline and its paired treatment."""

    seed: int
    baseline_id: str
    catalog_version: str
    epoch_second: int
    population_ids: tuple[str, ...]
    unit_system: str = UNIT_SYSTEM
    model_version: str = "logistics-1"

    def __post_init__(self) -> None:
        require_nonnegative("seed", self.seed)
        require_nonnegative("epoch_second", self.epoch_second)
        if not self.baseline_id or not self.catalog_version:
            raise LogisticsError("baseline_id and catalog_version are required")
        if self.unit_system != UNIT_SYSTEM:
            raise LogisticsError(f"unit_system must be {UNIT_SYSTEM}")
        if not self.population_ids:
            raise LogisticsError("population_ids must name the scenario households")
        if len(set(self.population_ids)) != len(self.population_ids):
            raise LogisticsError("population_ids must be unique")
        if any(not item for item in self.population_ids):
            raise LogisticsError("population_ids cannot contain an empty id")


@dataclass(frozen=True)
class FleetConfig:
    hub_id: str
    hub_position_m: tuple[int, int]
    operating_account: str
    external_account: str
    prep_seconds: int
    load_seconds: int
    unload_seconds: int
    ground_cents_per_metre: int
    ground_cents_per_service_second: int
    drone_cents_per_metre: int
    drone_cents_per_flight_second: int
    drone_cents_per_service_second: int
    fallback_handling_cents: int
    queue_id: str
    queue_waiting_capacity: int
    bay_servers: int
    drone_pad_servers: int

    def __post_init__(self) -> None:
        if not self.hub_id or not self.queue_id:
            raise LogisticsError("hub_id and queue_id are required")
        if not self.operating_account or not self.external_account:
            raise LogisticsError("operating and external accounts are required")
        if self.operating_account == self.external_account:
            raise LogisticsError("operating and external accounts must differ")
        object.__setattr__(self, "hub_position_m", _point("hub_position_m", self.hub_position_m))
        require_positive("prep_seconds", self.prep_seconds)
        require_positive("load_seconds", self.load_seconds)
        require_positive("unload_seconds", self.unload_seconds)
        for name in (
            "ground_cents_per_metre",
            "ground_cents_per_service_second",
            "drone_cents_per_metre",
            "drone_cents_per_flight_second",
            "drone_cents_per_service_second",
            "fallback_handling_cents",
            "queue_waiting_capacity",
        ):
            require_nonnegative(name, getattr(self, name))
        require_positive("bay_servers", self.bay_servers)
        require_nonnegative("drone_pad_servers", self.drone_pad_servers)


@dataclass(frozen=True)
class CarrierSpec:
    carrier_id: str
    kind: str
    payload_grams: int
    cold_chain: bool
    speed_m_per_s: int
    congestion_milli: int
    shift_start: int
    shift_end: int
    energy_capacity: int
    energy_remaining: int
    energy_per_metre: int
    reserve_energy: int
    charge_per_second: int
    home_position_m: tuple[int, int]
    downtime: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        if not self.carrier_id:
            raise LogisticsError("carrier_id is required")
        if self.kind not in {"van", "drone"}:
            raise LogisticsError("carrier kind must be van or drone")
        if not isinstance(self.cold_chain, bool):
            raise LogisticsError("cold_chain must be a bool")
        require_positive("payload_grams", self.payload_grams)
        require_positive("speed_m_per_s", self.speed_m_per_s)
        require_positive("congestion_milli", self.congestion_milli)
        require_nonnegative("shift_start", self.shift_start)
        require_int("shift_end", self.shift_end)
        if self.shift_end <= self.shift_start:
            raise LogisticsError("shift_end must be after shift_start")
        require_nonnegative("energy_capacity", self.energy_capacity)
        require_nonnegative("energy_remaining", self.energy_remaining)
        require_nonnegative("energy_per_metre", self.energy_per_metre)
        require_nonnegative("reserve_energy", self.reserve_energy)
        require_nonnegative("charge_per_second", self.charge_per_second)
        if self.energy_remaining > self.energy_capacity:
            raise LogisticsError("energy_remaining cannot exceed energy_capacity")
        if self.reserve_energy > self.energy_capacity:
            raise LogisticsError("reserve_energy cannot exceed energy_capacity")
        object.__setattr__(self, "home_position_m", _point("home_position_m", self.home_position_m))
        windows: list[tuple[int, int]] = []
        for index, window in enumerate(self.downtime):
            windows.append(_window(f"downtime[{index}]", window))
        object.__setattr__(self, "downtime", tuple(windows))


@dataclass(frozen=True)
class RouteLeg:
    leg_id: str
    origin_place_id: str
    destination_place_id: str
    origin_m: tuple[int, int]
    destination_m: tuple[int, int]
    waypoints_m: tuple[tuple[int, int], ...]
    distance_m: int

    def __post_init__(self) -> None:
        if not self.leg_id or not self.origin_place_id or not self.destination_place_id:
            raise LogisticsError("a route leg needs ids for itself and both places")
        require_nonnegative("distance_m", self.distance_m)
        origin = _point("origin_m", self.origin_m)
        destination = _point("destination_m", self.destination_m)
        object.__setattr__(self, "origin_m", origin)
        object.__setattr__(self, "destination_m", destination)
        points = tuple(_point("waypoint", point) for point in self.waypoints_m)
        object.__setattr__(self, "waypoints_m", points)
        if self.distance_m == 0:
            if origin != destination:
                raise LogisticsError("a zero-distance leg must start and end at the same point")
            return
        if len(points) < 2:
            raise LogisticsError("a positive-distance leg needs at least two waypoints")
        if points[0] != origin or points[-1] != destination:
            raise LogisticsError("waypoints must start at the origin and end at the destination")


def straight_leg(
    leg_id: str,
    origin_place_id: str,
    destination_place_id: str,
    origin_m: tuple[int, int],
    destination_m: tuple[int, int],
    distance_m: int,
) -> RouteLeg:
    """Build a leg whose animation path is the declared endpoints.

    ``distance_m`` is the economic length. It is not derived from the
    coordinates, so a road detour can be longer than the straight segment.
    """

    if distance_m == 0:
        waypoints = (origin_m,)
    else:
        waypoints = (origin_m, destination_m)
    return RouteLeg(
        leg_id=leg_id,
        origin_place_id=origin_place_id,
        destination_place_id=destination_place_id,
        origin_m=origin_m,
        destination_m=destination_m,
        waypoints_m=waypoints,
        distance_m=distance_m,
    )


@dataclass(frozen=True)
class Corridor:
    corridor_id: str
    hub_id: str
    locker_id: str
    waypoints_m: tuple[tuple[int, int], ...]
    distance_m: int
    eligible: bool
    approval: str
    site_open_second: int
    site_close_second: int
    weather: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        if not self.corridor_id or not self.hub_id or not self.locker_id:
            raise LogisticsError("corridor ids are required")
        if not isinstance(self.eligible, bool):
            raise LogisticsError("eligible must be a bool")
        if self.approval not in APPROVALS:
            raise LogisticsError("approval must be no_approval, conditional, or approved_in_scenario")
        require_positive("corridor.distance_m", self.distance_m)
        points = tuple(_point("corridor.waypoint", point) for point in self.waypoints_m)
        if len(points) < 2:
            raise LogisticsError("a corridor needs at least two waypoints")
        object.__setattr__(self, "waypoints_m", points)
        require_nonnegative("site_open_second", self.site_open_second)
        require_int("site_close_second", self.site_close_second)
        if self.site_close_second <= self.site_open_second:
            raise LogisticsError("site hours must be a non-empty half-open interval")
        windows = tuple(_window(f"weather[{index}]", window) for index, window in enumerate(self.weather))
        object.__setattr__(self, "weather", windows)


@dataclass(frozen=True)
class DeliveryOrder:
    order_id: str
    recipient_id: str
    origin_place_id: str
    destination_place_id: str
    lot_ids: tuple[str, ...]
    grams: int
    storage_class: str
    requested_second: int
    preferred_mode: str
    allow_ground_fallback: bool = False
    handoff: str = "collect"
    pickup_window_seconds: int = 0
    walk_speed_m_per_s: int = 1
    corridor_id: str | None = None
    locker_place_id: str | None = None
    ground_out: RouteLeg | None = None
    ground_return: RouteLeg | None = None
    fallback_approach: RouteLeg | None = None
    fallback_out: RouteLeg | None = None
    fallback_return: RouteLeg | None = None
    walk: RouteLeg | None = None

    def __post_init__(self) -> None:
        for name in ("order_id", "recipient_id", "origin_place_id", "destination_place_id"):
            if not getattr(self, name):
                raise LogisticsError(f"{name} is required")
        if not self.lot_ids or any(not lot_id for lot_id in self.lot_ids):
            raise LogisticsError("lot_ids must be a non-empty tuple of ids")
        require_positive("grams", self.grams)
        if self.storage_class not in STORAGE_CLASSES:
            raise LogisticsError("storage_class must be ambient, chilled, or frozen")
        require_nonnegative("requested_second", self.requested_second)
        if self.preferred_mode not in MODES:
            raise LogisticsError("preferred_mode must be ground or drone")
        if not isinstance(self.allow_ground_fallback, bool):
            raise LogisticsError("allow_ground_fallback must be a bool")
        if self.handoff not in HANDOFFS:
            raise LogisticsError("handoff must be collect or miss")
        require_nonnegative("pickup_window_seconds", self.pickup_window_seconds)
        require_positive("walk_speed_m_per_s", self.walk_speed_m_per_s)
        if self.preferred_mode == "ground" or self.allow_ground_fallback:
            _require_leg_pair(self.ground_out, self.ground_return, "ground")
        if self.preferred_mode == "drone":
            if not self.corridor_id or not self.locker_place_id or self.walk is None:
                raise LogisticsError("a drone order needs a corridor, a locker, and a walk leg")
        if self.allow_ground_fallback and self.preferred_mode == "drone":
            _require_leg_pair(self.fallback_out, self.fallback_return, "locker fallback")
            if self.fallback_approach is None:
                raise LogisticsError("locker fallback requires an approach leg from the hub")


def _require_leg_pair(outbound: RouteLeg | None, inbound: RouteLeg | None, label: str) -> None:
    if outbound is None or inbound is None:
        raise LogisticsError(f"{label} routing requires an outbound leg and a return leg")


def _window(name: str, window: tuple[int, int]) -> tuple[int, int]:
    if not isinstance(window, tuple) or len(window) != 2:
        raise LogisticsError(f"{name} must be a (start, end) second pair")
    start = require_nonnegative(f"{name}.start", window[0])
    end = require_int(f"{name}.end", window[1])
    if end <= start:
        raise LogisticsError(f"{name} must be a non-empty half-open interval")
    return (start, end)
