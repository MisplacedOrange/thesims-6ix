"""Scenario builders for logistics tests.

Distances below are declared metres. Tests that lock a result repeat the
arithmetic beside the assertion instead of calling back into the engine.
"""

from __future__ import annotations

from sim.logistics.core_interface.memory import MemoryCore
from sim.logistics.core_interface.protocol import LotSnapshot
from sim.logistics.engine import LogisticsEngine
from sim.logistics.models import (
    CarrierSpec,
    Corridor,
    DeliveryOrder,
    FleetConfig,
    ScenarioContext,
    straight_leg,
)

HUB = "hub"
LOCKER = "locker"
HOME = "home"


def context(population: tuple[str, ...] = ("hh-1", "hh-2", "hh-3", "hh-4"), **overrides) -> ScenarioContext:
    values = {
        "seed": 17,
        "baseline_id": "district-baseline",
        "catalog_version": "catalog-1",
        "epoch_second": 1_700_000_000,
        "population_ids": population,
    }
    values.update(overrides)
    return ScenarioContext(**values)


def fleet(**overrides) -> FleetConfig:
    values = {
        "hub_id": HUB,
        "hub_position_m": (0, 0),
        "operating_account": "carrier-operating",
        "external_account": "external-energy-labor",
        "prep_seconds": 5,
        "load_seconds": 10,
        "unload_seconds": 10,
        "ground_cents_per_metre": 2,
        "ground_cents_per_service_second": 1,
        "drone_cents_per_metre": 3,
        "drone_cents_per_flight_second": 1,
        "drone_cents_per_service_second": 1,
        "fallback_handling_cents": 50,
        "queue_id": "hub-dispatch",
        "queue_waiting_capacity": 8,
        "bay_servers": 1,
        "drone_pad_servers": 1,
    }
    values.update(overrides)
    return FleetConfig(**values)


def van(carrier_id: str = "van-1", **overrides) -> CarrierSpec:
    values = {
        "carrier_id": carrier_id,
        "kind": "van",
        "payload_grams": 5_000,
        "cold_chain": False,
        "speed_m_per_s": 10,
        "congestion_milli": 1000,
        "shift_start": 0,
        "shift_end": 100_000,
        "energy_capacity": 0,
        "energy_remaining": 0,
        "energy_per_metre": 0,
        "reserve_energy": 0,
        "charge_per_second": 0,
        "home_position_m": (0, 0),
    }
    values.update(overrides)
    return CarrierSpec(**values)


def drone(carrier_id: str = "drone-1", **overrides) -> CarrierSpec:
    values = {
        "carrier_id": carrier_id,
        "kind": "drone",
        "payload_grams": 5_000,
        "cold_chain": False,
        "speed_m_per_s": 20,
        "congestion_milli": 1000,
        "shift_start": 0,
        "shift_end": 100_000,
        "energy_capacity": 1_000,
        "energy_remaining": 1_000,
        "energy_per_metre": 1,
        "reserve_energy": 100,
        "charge_per_second": 100,
        "home_position_m": (0, 0),
    }
    values.update(overrides)
    return CarrierSpec(**values)


def corridor(**overrides) -> Corridor:
    values = {
        "corridor_id": "hub-locker",
        "hub_id": HUB,
        "locker_id": LOCKER,
        "waypoints_m": ((0, 0), (300, 0)),
        "distance_m": 300,
        "eligible": True,
        "approval": "approved_in_scenario",
        "site_open_second": 0,
        "site_close_second": 100_000,
        "weather": (),
    }
    values.update(overrides)
    return Corridor(**values)


def lot(
    lot_id: str,
    grams: int = 1_000,
    *,
    place_id: str = HUB,
    storage_class: str = "ambient",
    unsafe_after_second: int = 10**12,
) -> LotSnapshot:
    return LotSnapshot(
        lot_id=lot_id,
        product_id="produce",
        owner_id="hub-owner",
        custody="place",
        place_id=place_id,
        journey_id=None,
        grams=grams,
        storage_class=storage_class,
        unsafe_after_second=unsafe_after_second,
        reserved_by=None,
    )


def direct_order(
    order_id: str,
    recipient_id: str,
    lot_id: str,
    *,
    grams: int = 1_000,
    distance_m: int = 300,
    door_id: str | None = None,
    storage_class: str = "ambient",
) -> DeliveryOrder:
    door = door_id or f"door-{recipient_id}"
    outbound = straight_leg(f"{order_id}-out", HUB, door, (0, 0), (distance_m, 0), distance_m)
    inbound = straight_leg(f"{order_id}-back", door, HUB, (distance_m, 0), (0, 0), distance_m)
    return DeliveryOrder(
        order_id=order_id,
        recipient_id=recipient_id,
        origin_place_id=HUB,
        destination_place_id=door,
        lot_ids=(lot_id,),
        grams=grams,
        storage_class=storage_class,
        requested_second=0,
        preferred_mode="ground",
        ground_out=outbound,
        ground_return=inbound,
    )


def drone_order(
    order_id: str,
    recipient_id: str,
    lot_id: str,
    *,
    grams: int = 1_000,
    allow_ground_fallback: bool,
    handoff: str = "collect",
    pickup_window_seconds: int = 100,
    walk_distance_m: int = 60,
    walk_speed_m_per_s: int = 2,
    include_ground_legs: bool = False,
) -> DeliveryOrder:
    walk = straight_leg(f"{order_id}-walk", HOME, LOCKER, (300, 60), (300, 0), walk_distance_m)
    ground_out = ground_return = approach = fallback_out = fallback_return = None
    if include_ground_legs or allow_ground_fallback:
        door = f"door-{recipient_id}"
        ground_out = straight_leg(f"{order_id}-ground-out", HUB, door, (0, 0), (300, 0), 300)
        ground_return = straight_leg(f"{order_id}-ground-back", door, HUB, (300, 0), (0, 0), 300)
        approach = straight_leg(f"{order_id}-approach", HUB, LOCKER, (0, 0), (300, 0), 300)
        fallback_out = straight_leg(f"{order_id}-locker-door", LOCKER, door, (300, 0), (300, 100), 100)
        fallback_return = straight_leg(f"{order_id}-door-hub", door, HUB, (300, 100), (0, 0), 400)
    return DeliveryOrder(
        order_id=order_id,
        recipient_id=recipient_id,
        origin_place_id=HUB,
        destination_place_id=f"door-{recipient_id}",
        lot_ids=(lot_id,),
        grams=grams,
        storage_class="ambient",
        requested_second=0,
        preferred_mode="drone",
        allow_ground_fallback=allow_ground_fallback,
        handoff=handoff,
        pickup_window_seconds=pickup_window_seconds,
        walk_speed_m_per_s=walk_speed_m_per_s,
        corridor_id="hub-locker",
        locker_place_id=LOCKER,
        ground_out=ground_out,
        ground_return=ground_return,
        fallback_approach=approach,
        fallback_out=fallback_out,
        fallback_return=fallback_return,
        walk=walk,
    )


def engine_for(
    orders: list[DeliveryOrder],
    lots: list[LotSnapshot],
    carriers: list[CarrierSpec],
    corridors: list[Corridor] | None = None,
    fleet_config: FleetConfig | None = None,
    scenario: ScenarioContext | None = None,
    submit: bool = True,
) -> tuple[LogisticsEngine, MemoryCore]:
    core = MemoryCore(lots)
    world = LogisticsEngine(
        scenario or context(),
        fleet_config or fleet(),
        carriers,
        corridors or [],
        core,
    )
    if submit:
        for order in orders:
            world.submit_order(order)
    return world, core


def kinds(world: LogisticsEngine) -> list[str]:
    return [event.kind for event in world.events]


def of_kind(world: LogisticsEngine, kind: str) -> list:
    return [event for event in world.events if event.kind == kind]
