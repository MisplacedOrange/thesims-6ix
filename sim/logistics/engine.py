"""Deterministic logistics engine.

The kernel is expected to submit every order for a second before advancing
through that second, then call ``advance_to``. Orders admitted at the same
second are ordered by a seeded rank, not by submission order.

Within a second the engine finishes completions (phase 10), handoffs and
pickups (phase 20), then dispatch (phase 30). A stage lasts at least one
second. One vehicle carries one consignment per trip. Assignment is the
earliest free feasible vehicle, breaking ties by carrier id.

Drone corridors fly only when the scenario record allows it. Weather, site
hours, energy, payload, and a missed locker handoff reassign the order to a
van when the order allows fallback. Pre-launch fallback leaves the food at
the hub. A missed handoff leaves it in the locker and the van collects it.

Operating cost is posted once, as a balanced pair, when the order reaches a
terminal state. The hash covers this state and the committed events. It omits
``cosmetic_note``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.logistics.carriers import (
    downtime_blocker,
    energy_blocker,
    recharge_plan,
    shift_blocker,
    static_blocker,
)
from sim.logistics.compatibility import LogisticsOutcome, RunFingerprint
from sim.logistics.core_interface.protocol import CorePort
from sim.logistics.drones import permission_blocker, site_hours_blocker, weather_blocker
from sim.logistics.errors import LogisticsError
from sim.logistics.events import (
    CARRIER_UNAVAILABLE,
    CHARGING_COMPLETED,
    CHARGING_STARTED,
    COST_ALLOCATED,
    CUSTOMER_PICKUP_COMPLETED,
    CUSTOMER_PICKUP_STARTED,
    DELIVERY_COMPLETED,
    DELIVERY_EXCLUDED,
    DELIVERY_FAILED,
    DELIVERY_UNSERVED,
    DRONE_FLIGHT_COMPLETED,
    DRONE_FLIGHT_STARTED,
    GROUND_FALLBACK_ASSIGNED,
    HANDOFF_FAILED,
    JOURNEY_ARRIVED,
    JOURNEY_STARTED,
    LOADING_COMPLETED,
    LOADING_STARTED,
    NOTIFICATION_SENT,
    PREPARATION_COMPLETED,
    PREPARATION_STARTED,
    QUEUE_ADVANCED,
    QUEUE_JOINED,
    QUEUE_REJECTED,
    ROUTE_INELIGIBLE,
    SERVICE_STARTED,
    UNLOADING_COMPLETED,
    UNLOADING_STARTED,
    WEATHER_EXCLUDED,
    LogisticsEvent,
)
from sim.logistics.hashing import economic_hash
from sim.logistics.metrics import CRITICAL_COMPONENTS, MetricSet, build_metrics
from sim.logistics.models import CarrierSpec, Corridor, DeliveryOrder, FleetConfig, ScenarioContext
from sim.logistics.queues import WaitEntry, WaitingLine
from sim.logistics.ranking import admission_rank
from sim.logistics.units import require_nonnegative, travel_seconds

PHASE_COMPLETE = 10
PHASE_HANDOFF = 20
PHASE_DISPATCH = 30

EXCLUSION_REASONS = frozenset(
    {"no_approval", "ineligible", "missing_corridor", "weather", "site_hours", "unsafe_lot"}
)

STATUS_FOR_STAGE = {
    "preparation": "preparing",
    "loading": "loading",
    "access_transfer": "in_transit",
    "flight": "in_transit",
    "unloading": "unloading",
    "failed_pickup_wait": "awaiting_pickup",
}


def _components() -> dict[str, int]:
    names = CRITICAL_COMPONENTS + ("return_travel",)
    return {name: 0 for name in names}


def _flag(value: bool) -> int:
    return 1 if value else 0


@dataclass(frozen=True)
class _Stage:
    component: str
    duration: int
    start_kind: str
    end_kind: str
    waypoints: tuple[tuple[int, int], ...]
    place_id: str
    distance_m: int
    effects: tuple[str, ...]
    leg: str
    journey_id: str | None


@dataclass(frozen=True)
class _Plan:
    stages: tuple[_Stage, ...]
    distance_m: int
    duration: int
    service_seconds: int
    flight_seconds: int


@dataclass(frozen=True)
class _Action:
    second: int
    phase: int
    seq: int
    rank: int
    kind: str
    order_id: str
    carrier_id: str


class _Order:
    def __init__(self, spec: DeliveryOrder, rank: int) -> None:
        self.spec = spec
        self.rank = rank
        self.status = "pending"
        self.mode = ""
        self.reasons: tuple[str, ...] = ()
        self.components = _components()
        self.operating_cents = 0
        self.fallback_count = 0
        self.completed_by = ""
        self.billed_ground_distance_m = 0
        self.billed_ground_service_seconds = 0
        self.billed_drone_distance_m = 0
        self.billed_drone_flight_seconds = 0
        self.billed_drone_service_seconds = 0
        self.duplicate_handling = False
        self.handoff_failed = False
        self.food_at_locker = False
        self.reserved = False
        self.released = False
        self.reservation_ids: list[str] = []
        self.closed = False
        self.ready_second = spec.requested_second
        self.last_event_id: str | None = None
        self.carrier_id: str | None = None
        self.walk_seconds = 0
        self.pickup_depart: int | None = None
        self.pickup_arrive: int | None = None
        self.collection_second: int | None = None


class _Carrier:
    def __init__(self, spec: CarrierSpec) -> None:
        self.spec = spec
        self.status = "idle"
        self.energy_remaining = spec.energy_remaining
        self.energy_when_free = spec.energy_remaining
        self.energy_consumed = 0
        self.free_at = 0
        self.position = spec.home_position_m
        self.active_order_id: str | None = None
        self.stages: tuple[_Stage, ...] = ()
        self.stage_index = 0
        self.stage_started = 0
        self.pending_charge = 0
        self.live: _Stage | None = None


class LogisticsEngine:
    """Sole writer of logistics state for one run. Accounting goes through ``core``."""

    def __init__(
        self,
        context: ScenarioContext,
        fleet: FleetConfig,
        carriers: tuple[CarrierSpec, ...] | list[CarrierSpec],
        corridors: tuple[Corridor, ...] | list[Corridor],
        core: CorePort,
    ) -> None:
        self.context = context
        self.fleet = fleet
        self.core = core
        self.carriers: dict[str, _Carrier] = {}
        for spec in sorted(carriers, key=lambda item: item.carrier_id):
            if spec.carrier_id in self.carriers:
                raise LogisticsError(f"duplicate carrier {spec.carrier_id}")
            self.carriers[spec.carrier_id] = _Carrier(spec)
        self.corridors = {}
        for corridor in corridors:
            if corridor.corridor_id in self.corridors:
                raise LogisticsError(f"duplicate corridor {corridor.corridor_id}")
            self.corridors[corridor.corridor_id] = corridor
        if any(carrier.spec.kind == "drone" for carrier in self.carriers.values()) and fleet.drone_pad_servers < 1:
            raise LogisticsError("a drone fleet needs at least one pad server")
        self.waiting = WaitingLine(fleet.queue_id, fleet.queue_waiting_capacity)
        self.orders: dict[str, _Order] = {}
        self.actions: list[_Action] = []
        self.events: list[LogisticsEvent] = []
        self.postings: list[dict[str, object]] = []
        self.sequence = 1
        self.action_seq = 1
        self.horizon = -1
        self.clock_second = -1
        self.clock_phase = -1
        self.bay_in_use = 0
        self.pad_in_use = 0
        self.bay_free_at = 0
        self.pad_free_at = 0
        self.cosmetic_note = ""
        self._lots_taken: set[str] = set()

    def submit_order(self, order: DeliveryOrder) -> None:
        """Buffer an order. It is admitted when the clock advances through its second."""

        if order.order_id in self.orders:
            raise LogisticsError(f"duplicate order {order.order_id}")
        if order.requested_second <= self.horizon:
            raise LogisticsError("order is at or before the settled logistics horizon")
        if order.recipient_id not in self.context.population_ids:
            raise LogisticsError("recipient is outside the scenario population")
        self._validate_lots(order)
        self._validate_route_endpoints(order)
        if order.preferred_mode == "drone":
            if order.corridor_id not in self.corridors:
                raise LogisticsError(f"unknown corridor {order.corridor_id}")
        rank = admission_rank(self.context.seed, f"dispatch|{order.requested_second}", order.recipient_id)
        self.orders[order.order_id] = _Order(order, rank)
        self._schedule(order.requested_second, PHASE_DISPATCH, "dispatch", order.order_id, "", rank)

    def advance_to(self, second: int) -> tuple[LogisticsEvent, ...]:
        """Process every action at or before ``second``. The target is inclusive."""

        target = require_nonnegative("second", second)
        if target < self.horizon:
            raise LogisticsError("cannot move the logistics clock backwards")
        begin = len(self.events)
        steps = 0
        while True:
            steps += 1
            if steps > 100_000:
                raise LogisticsError("logistics event loop did not advance")
            due = [action for action in self.actions if action.second <= target]
            if not due:
                break
            due.sort(key=lambda action: (action.second, action.phase, action.rank, action.seq))
            nxt = due[0]
            if nxt.second != self.clock_second:
                self.clock_phase = -1
                self.clock_second = nxt.second
            if nxt.phase < self.clock_phase:
                self._defer(nxt)
                continue
            self.clock_phase = nxt.phase
            if nxt.kind == "dispatch":
                group = [
                    action
                    for action in due
                    if action.second == nxt.second and action.phase == nxt.phase and action.kind == "dispatch"
                ]
                group.sort(key=lambda action: (action.rank, action.seq))
                self._drop(group)
                self._run_dispatch(group, nxt.second)
            else:
                self._drop([nxt])
                self._run(nxt)
        self.horizon = target
        self.clock_second = target
        self.clock_phase = -1
        return tuple(self.events[begin:])

    def economic_hash(self) -> str:
        return economic_hash(self.canonical_state())

    def canonical_state(self) -> dict[str, object]:
        """Economic document. Cosmetic notes are not included."""

        return {
            "actions": [
                {
                    "carrier_id": action.carrier_id,
                    "kind": action.kind,
                    "order_id": action.order_id,
                    "phase": action.phase,
                    "rank": action.rank,
                    "second": action.second,
                    "seq": action.seq,
                }
                for action in sorted(self.actions, key=lambda action: (action.second, action.phase, action.rank, action.seq))
            ],
            "baseline_id": self.context.baseline_id,
            "bay_free_at": self.bay_free_at,
            "bay_in_use": self.bay_in_use,
            "carriers": [self._carrier_state(carrier) for carrier in self._carriers()],
            "catalog_version": self.context.catalog_version,
            "clock_phase": self.clock_phase,
            "corridors": [self._corridor_state(corridor) for corridor in self._corridor_list()],
            "epoch_second": self.context.epoch_second,
            "events": [event.economic_dict() for event in self.events],
            "fleet": self._fleet_state(),
            "horizon": self.horizon,
            "orders": [self._order_state(order) for order in self._order_list()],
            "pad_free_at": self.pad_free_at,
            "pad_in_use": self.pad_in_use,
            "population_ids": list(sorted(self.context.population_ids)),
            "postings": list(self.postings),
            "seed": self.context.seed,
            "version": self.context.model_version,
            "waiting": [
                {"enqueued_second": entry.enqueued_second, "order_id": entry.order_id, "rank": entry.rank}
                for entry in self.waiting.entries
            ],
        }

    def metrics(self) -> MetricSet:
        energy = sum(carrier.energy_consumed for carrier in self.carriers.values())
        return build_metrics(tuple(self._order_list()), energy)

    def fingerprint(self) -> RunFingerprint:
        return RunFingerprint(
            unit_system=self.context.unit_system,
            population_ids=tuple(sorted(self.context.population_ids)),
            baseline_id=self.context.baseline_id,
            catalog_version=self.context.catalog_version,
            epoch_second=self.context.epoch_second,
            model_version=self.context.model_version,
        )

    def outcome(self) -> LogisticsOutcome:
        return LogisticsOutcome(self.fingerprint(), self.metrics(), self.economic_hash())

    def _run_dispatch(self, group: list[_Action], second: int) -> None:
        fresh: list[_Order] = []
        for action in group:
            if not action.order_id:
                continue
            order = self.orders[action.order_id]
            if order.status == "pending":
                fresh.append(order)
        fresh.sort(key=lambda order: (order.rank, order.spec.order_id))
        for order in fresh:
            self._admit(order, second)
        self._pump(second)

    def _admit(self, order: _Order, second: int) -> None:
        if self._unsafe(order, second + self.fleet.prep_seconds):
            order.reasons = ("unsafe_lot",)
            self._close(order, second, "excluded")
            return
        mode, reasons = self._resolve(order, second)
        order.reasons = reasons
        if mode == "terminal":
            for reason in reasons:
                self._emit_blocker(order, reason, second)
            self._close(order, second, self._status_for(reasons))
            return
        if reasons:
            for reason in reasons:
                self._emit_blocker(order, reason, second)
            order.fallback_count = 1
            order.mode = "ground"
            self._emit(
                GROUND_FALLBACK_ASSIGNED,
                order,
                second,
                reason=",".join(reasons),
                place_id=self.fleet.hub_id,
            )
        else:
            order.mode = mode
        if self._try_claim(order, second, announce_queue=True):
            return
        if not self._eventually(self._kind_for(order), order, second):
            reason = self._failure_reason(self._kind_for(order), order, second)
            order.reasons = order.reasons + (reason,)
            self._emit_blocker(order, reason, second)
            self._close(order, second, self._status_for(order.reasons))
            return
        if self.waiting.full():
            order.reasons = order.reasons + ("queue_capacity",)
            self._emit(
                QUEUE_REJECTED,
                order,
                second,
                reason="queue_capacity",
                place_id=self.fleet.hub_id,
                queue_position=None,
            )
            self._close(order, second, "unserved")
            return
        self._enqueue(order, second)

    def _pump(self, second: int) -> None:
        while self.waiting.entries:
            head = self.waiting.entries[0]
            order = self.orders[head.order_id]
            if self._unsafe(order, second + self.fleet.prep_seconds):
                self.waiting.pop_head()
                self._emit_advances(second)
                order.reasons = order.reasons + ("unsafe_lot",)
                self._close(order, second, "excluded")
                continue
            if not self._can_start_now(order, second):
                return
            self.waiting.pop_head()
            self._emit_advances(second)
            if not self._try_claim(order, second, announce_queue=False):
                raise LogisticsError(f"{order.spec.order_id} was feasible but was not claimed")

    def _try_claim(self, order: _Order, second: int, *, announce_queue: bool) -> bool:
        if order.closed:
            return False
        if not self._slot_free(order):
            return False
        carrier = self._pick(order, second)
        if carrier is None:
            return False
        plan = self._compile(order, carrier)
        consumption = plan.distance_m * carrier.spec.energy_per_metre
        if energy_blocker(
            carrier.energy_remaining,
            plan.distance_m,
            carrier.spec.energy_per_metre,
            carrier.spec.reserve_energy,
        ):
            raise LogisticsError("claimed a carrier that fails its energy reserve")
        self._reserve(order, second)
        order.components["queue"] += second - order.ready_second
        self._add_billing(order, carrier, plan)
        carrier.energy_remaining -= consumption
        carrier.energy_consumed += consumption
        charge, restored = recharge_plan(
            carrier.energy_remaining,
            carrier.spec.energy_capacity,
            carrier.spec.charge_per_second,
        )
        carrier.pending_charge = charge
        carrier.energy_when_free = restored
        carrier.free_at = second + plan.duration + charge
        carrier.active_order_id = order.spec.order_id
        carrier.stages = plan.stages
        carrier.stage_index = 0
        order.carrier_id = carrier.spec.carrier_id
        if self._needs_bay(order):
            self.bay_in_use += 1
            self.bay_free_at = second + self.fleet.prep_seconds + self.fleet.load_seconds
        if self._needs_pad(order):
            self.pad_in_use += 1
            self.pad_free_at = second + self.fleet.prep_seconds + self.fleet.load_seconds
        if announce_queue:
            self._emit(
                QUEUE_JOINED,
                order,
                second,
                carrier=carrier,
                place_id=self.fleet.hub_id,
                queue_position=0,
                reason="admitted",
            )
        self._emit(
            SERVICE_STARTED,
            order,
            second,
            carrier=carrier,
            place_id=self.fleet.hub_id,
            reason=order.mode,
        )
        self._start_stage(carrier, second)
        return True

    def _enqueue(self, order: _Order, second: int) -> None:
        self._reserve(order, second)
        position = self.waiting.push(
            WaitEntry(order.spec.order_id, order.spec.recipient_id, order.rank, second)
        )
        order.status = "queued"
        self._emit(
            QUEUE_JOINED,
            order,
            second,
            place_id=self.fleet.hub_id,
            queue_position=position,
            reason="waiting",
        )

    def _resolve(self, order: _Order, second: int) -> tuple[str, tuple[str, ...]]:
        if order.spec.preferred_mode == "ground":
            return "ground", ()
        reasons: list[str] = []
        corridor = self.corridors.get(order.spec.corridor_id or "")
        if corridor is None:
            reasons.append("missing_corridor")
        else:
            permission = permission_blocker(corridor)
            if permission:
                reasons.append(permission)
            elif self._all_static("drone", order):
                reasons.append(self._failure_reason("drone", order, second))
            elif not self._eventually("drone", order, second):
                reasons.append(self._failure_reason("drone", order, second))
        if not reasons:
            return "drone", ()
        return self._fallback_or_terminal(order, second, tuple(reasons))

    def _fallback_or_terminal(self, order: _Order, second: int, reasons: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
        if order.spec.allow_ground_fallback and self._eventually("van", order, second):
            return "ground", reasons
        if order.spec.allow_ground_fallback:
            extra = self._failure_reason("van", order, second)
            return "terminal", reasons + (extra,)
        return "terminal", reasons

    def _run(self, action: _Action) -> None:
        if action.kind == "stage_end":
            self._on_stage_end(self.carriers[action.carrier_id], action.second)
            return
        if action.kind == "pickup_end":
            self._on_pickup(self.orders[action.order_id], action.second)
            return
        if action.kind == "charge_end":
            self._on_charge_end(self.carriers[action.carrier_id], action.second)
            return
        raise LogisticsError(f"unknown action {action.kind}")

    def _start_stage(self, carrier: _Carrier, second: int) -> None:
        stage = carrier.stages[carrier.stage_index]
        if stage.duration < 1:
            raise LogisticsError("a logistics stage must last at least one second")
        carrier.stage_started = second
        carrier.live = stage
        carrier.status = stage.component or "busy"
        order = self.orders[carrier.active_order_id or ""]
        if (
            not order.closed
            and order.carrier_id == carrier.spec.carrier_id
            and stage.component in STATUS_FOR_STAGE
        ):
            order.status = STATUS_FOR_STAGE[stage.component]
        if stage.waypoints:
            carrier.position = stage.waypoints[0]
        if stage.start_kind:
            self._emit(
                stage.start_kind,
                order,
                second,
                carrier=carrier,
                place_id=stage.place_id,
                leg=stage.leg,
                waypoints=stage.waypoints,
                depart=second,
                arrive=second + stage.duration,
                journey_id=stage.journey_id,
                include_lots=True,
            )
        self._schedule(
            second + stage.duration,
            PHASE_COMPLETE,
            "stage_end",
            order.spec.order_id,
            carrier.spec.carrier_id,
            0,
        )

    def _on_stage_end(self, carrier: _Carrier, second: int) -> None:
        stage = carrier.stages[carrier.stage_index]
        elapsed = second - carrier.stage_started
        if elapsed != stage.duration:
            raise LogisticsError("stage ended at a different time than it was assigned")
        if carrier.active_order_id is None:
            raise LogisticsError("stage ended without an order")
        order = self.orders[carrier.active_order_id]
        if stage.component:
            order.components[stage.component] += elapsed
        if stage.waypoints:
            carrier.position = stage.waypoints[-1]
        if stage.end_kind:
            self._emit(
                stage.end_kind,
                order,
                second,
                carrier=carrier,
                place_id=stage.place_id,
                leg=stage.leg,
                waypoints=stage.waypoints,
                depart=carrier.stage_started,
                arrive=second,
                journey_id=stage.journey_id,
                include_lots=True,
            )
        for effect in stage.effects:
            self._effect(effect, order, carrier, second, stage)
        carrier.stage_index += 1
        if carrier.stage_index < len(carrier.stages):
            self._start_stage(carrier, second)
        else:
            self._carrier_finished(carrier, second)

    def _effect(self, effect: str, order: _Order, carrier: _Carrier, second: int, stage: _Stage) -> None:
        if effect == "to_journey":
            self._move_all(order, second, place_id=None, journey_id=self._following_journey(carrier))
        elif effect == "to_locker":
            self._move_all(order, second, place_id=order.spec.locker_place_id, journey_id=None)
            order.food_at_locker = True
        elif effect == "to_hub":
            self._move_all(order, second, place_id=order.spec.origin_place_id, journey_id=None)
        elif effect == "bay_release":
            self._release_slot("bay", second)
        elif effect == "pad_release":
            self._release_slot("pad", second)
        elif effect == "notify":
            self._emit(
                NOTIFICATION_SENT,
                order,
                second,
                carrier=carrier,
                place_id=order.spec.locker_place_id,
                reason="locker_ready",
                include_lots=True,
            )
        elif effect == "begin_pickup":
            self._begin_pickup(order, carrier, second)
        elif effect == "handoff_hold":
            order.handoff_failed = True
            self._emit(
                HANDOFF_FAILED,
                order,
                second,
                carrier=carrier,
                place_id=order.spec.locker_place_id,
                reason=self._handoff_reason(order),
                include_lots=True,
            )
        elif effect == "handoff_fallback":
            self._handoff_fallback(order, carrier, second)
        elif effect == "deliver_ground":
            self._give(order, second)
        elif effect == "fail_closed":
            self._close(order, second, "failed")
        else:
            raise LogisticsError(f"unknown stage effect {effect}")

    def _handoff_fallback(self, order: _Order, carrier: _Carrier, second: int) -> None:
        order.handoff_failed = True
        order.fallback_count += 1
        order.mode = "ground"
        order.ready_second = second
        self._emit(
            HANDOFF_FAILED,
            order,
            second,
            carrier=carrier,
            place_id=order.spec.locker_place_id,
            reason=self._handoff_reason(order),
            include_lots=True,
        )
        self._emit(
            GROUND_FALLBACK_ASSIGNED,
            order,
            second,
            reason="handoff_failed",
            place_id=order.spec.locker_place_id,
        )
        accepted = False
        if self._try_claim(order, second, announce_queue=True):
            accepted = True
        elif self._eventually("van", order, second) and not self.waiting.full():
            self._enqueue(order, second)
            accepted = True
        order.duplicate_handling = accepted
        if not accepted:
            reason = "queue_capacity" if self.waiting.full() else self._failure_reason("van", order, second)
            order.reasons = order.reasons + (reason,)
            self._emit_blocker(order, reason, second)
            self._close(order, second, "failed")

    def _begin_pickup(self, order: _Order, carrier: _Carrier, second: int) -> None:
        walk = self._walk_seconds(order)
        order.walk_seconds = walk
        arrive = second + walk
        order.pickup_depart = second
        order.pickup_arrive = arrive
        order.status = "awaiting_pickup"
        journey_id = f"journey-{order.spec.order_id}-walk"
        self._move_all(order, second, place_id=None, journey_id=journey_id)
        waypoints = order.spec.walk.waypoints_m if order.spec.walk is not None else ()
        self._emit(
            CUSTOMER_PICKUP_STARTED,
            order,
            second,
            carrier=carrier,
            place_id=order.spec.locker_place_id,
            leg="walk",
            waypoints=waypoints,
            depart=second,
            arrive=arrive,
            journey_id=journey_id,
            include_lots=True,
        )
        phase = PHASE_HANDOFF if walk == 0 else PHASE_COMPLETE
        self._schedule(arrive, phase, "pickup_end", order.spec.order_id, "", order.rank)

    def _on_pickup(self, order: _Order, second: int) -> None:
        if order.closed:
            raise LogisticsError("pickup completed after the order closed")
        order.components["customer_pickup"] += order.walk_seconds
        waypoints = order.spec.walk.waypoints_m if order.spec.walk is not None else ()
        self._emit(
            CUSTOMER_PICKUP_COMPLETED,
            order,
            second,
            place_id=order.spec.destination_place_id,
            leg="walk",
            waypoints=waypoints,
            depart=order.pickup_depart,
            arrive=order.pickup_arrive,
            include_lots=True,
        )
        self._give(order, second)

    def _give(self, order: _Order, second: int) -> None:
        for lot_id in order.spec.lot_ids:
            self.core.transfer_ownership(lot_id, order.spec.recipient_id, order.spec.order_id, second)
            self.core.move_custody(
                lot_id,
                holder_id=order.spec.order_id,
                place_id=order.spec.destination_place_id,
                journey_id=None,
                second=second,
            )
        self._release(order, second)
        self._close(order, second, "completed")

    def _close(self, order: _Order, second: int, status: str) -> None:
        if order.closed:
            raise LogisticsError(f"{order.spec.order_id} was closed twice")
        order.closed = True
        order.status = status
        order.operating_cents = self._money(order)
        if status == "completed":
            order.collection_second = second
            order.completed_by = order.mode
        kind = {
            "completed": DELIVERY_COMPLETED,
            "failed": DELIVERY_FAILED,
            "excluded": DELIVERY_EXCLUDED,
            "unserved": DELIVERY_UNSERVED,
        }[status]
        self._emit(
            kind,
            order,
            second,
            reason=",".join(order.reasons),
            include_lots=True,
            place_id=order.spec.destination_place_id if status == "completed" else order.spec.origin_place_id,
        )
        if order.operating_cents > 0:
            self._post(order, second)
            self._emit(
                COST_ALLOCATED,
                order,
                second,
                cents=order.operating_cents,
                reason="operating_cost",
                place_id=self.fleet.hub_id,
            )
        if order.reservation_ids:
            self._release(order, second)

    def _carrier_finished(self, carrier: _Carrier, second: int) -> None:
        if carrier.pending_charge >= 1:
            carrier.status = "charging"
            point = (carrier.position,)
            order = self.orders[carrier.active_order_id] if carrier.active_order_id else None
            self._emit(
                CHARGING_STARTED,
                order,
                second,
                carrier=carrier,
                place_id=self.fleet.hub_id,
                waypoints=point,
                depart=second,
                arrive=second + carrier.pending_charge,
                leg="charge",
            )
            self._schedule(
                second + carrier.pending_charge,
                PHASE_COMPLETE,
                "charge_end",
                carrier.active_order_id or "",
                carrier.spec.carrier_id,
                0,
            )
            return
        self._become_idle(carrier, second)

    def _on_charge_end(self, carrier: _Carrier, second: int) -> None:
        duration = carrier.pending_charge
        carrier.energy_remaining = carrier.energy_when_free
        carrier.pending_charge = 0
        order = self.orders[carrier.active_order_id] if carrier.active_order_id else None
        self._emit(
            CHARGING_COMPLETED,
            order,
            second,
            carrier=carrier,
            place_id=self.fleet.hub_id,
            depart=second - duration,
            arrive=second,
            leg="charge",
        )
        self._become_idle(carrier, second)

    def _become_idle(self, carrier: _Carrier, second: int) -> None:
        carrier.status = "idle"
        carrier.active_order_id = None
        carrier.position = carrier.spec.home_position_m
        carrier.free_at = second
        carrier.live = None
        self._schedule(second, PHASE_DISPATCH, "dispatch", "", carrier.spec.carrier_id, 10**12)

    def _release_slot(self, kind: str, second: int) -> None:
        if kind == "bay":
            if self.bay_in_use <= 0:
                raise LogisticsError("released a free loading bay")
            self.bay_in_use -= 1
            self.bay_free_at = second
        else:
            if self.pad_in_use <= 0:
                raise LogisticsError("released a free drone pad")
            self.pad_in_use -= 1
            self.pad_free_at = second
        self._schedule(second, PHASE_DISPATCH, "dispatch", "", "", 10**12)

    def _compile(self, order: _Order, carrier: _Carrier) -> _Plan:
        if carrier.spec.kind == "drone":
            return self._compile_drone(order, carrier)
        return self._compile_ground(order, carrier)

    def _compile_ground(self, order: _Order, carrier: _Carrier) -> _Plan:
        spec = order.spec
        fleet = self.fleet
        speed = carrier.spec.speed_m_per_s
        congestion = carrier.spec.congestion_milli
        if order.food_at_locker:
            if spec.fallback_approach is None or spec.fallback_out is None or spec.fallback_return is None:
                raise LogisticsError("locker fallback is missing route legs")
            before = (spec.fallback_approach,)
            outbound = spec.fallback_out
            inbound = spec.fallback_return
            load_point = outbound.origin_m
            load_place = outbound.origin_place_id
            load_effects = ("to_journey",)
        else:
            if spec.ground_out is None or spec.ground_return is None:
                raise LogisticsError("ground delivery is missing route legs")
            before = ()
            outbound = spec.ground_out
            inbound = spec.ground_return
            load_point = fleet.hub_position_m
            load_place = fleet.hub_id
            load_effects = ("to_journey", "bay_release")
        stages: list[_Stage] = [
            self._still(
                "preparation",
                fleet.prep_seconds,
                PREPARATION_STARTED,
                PREPARATION_COMPLETED,
                fleet.hub_position_m,
                fleet.hub_id,
                (),
                "preparation",
            )
        ]
        for leg in before:
            self._append_road(stages, order, carrier, leg, "approach")
        stages.append(
            self._still(
                "loading",
                fleet.load_seconds,
                LOADING_STARTED,
                LOADING_COMPLETED,
                load_point,
                load_place,
                load_effects,
                "loading",
            )
        )
        self._append_road(stages, order, carrier, outbound, "outbound")
        stages.append(
            self._still(
                "unloading",
                fleet.unload_seconds,
                UNLOADING_STARTED,
                UNLOADING_COMPLETED,
                outbound.destination_m,
                outbound.destination_place_id,
                ("deliver_ground",),
                "unloading",
            )
        )
        self._append_road(stages, order, carrier, inbound, "return", component="return_travel")
        distance = sum(leg.distance_m for leg in before) + outbound.distance_m + inbound.distance_m
        duration = sum(stage.duration for stage in stages)
        return _Plan(tuple(stages), distance, duration, fleet.load_seconds + fleet.unload_seconds, 0)

    def _compile_drone(self, order: _Order, carrier: _Carrier) -> _Plan:
        if order.spec.corridor_id is None:
            raise LogisticsError("drone plan without a corridor")
        corridor = self.corridors[order.spec.corridor_id]
        fleet = self.fleet
        flight = travel_seconds(corridor.distance_m, carrier.spec.speed_m_per_s, carrier.spec.congestion_milli)
        fail = self._will_fail(order)
        fallback = order.spec.allow_ground_fallback
        locker_point = corridor.waypoints_m[-1]
        unload_effects = ["to_locker", "notify"]
        if not fail:
            unload_effects.append("begin_pickup")
        stages: list[_Stage] = [
            self._still(
                "preparation",
                fleet.prep_seconds,
                PREPARATION_STARTED,
                PREPARATION_COMPLETED,
                fleet.hub_position_m,
                fleet.hub_id,
                (),
                "preparation",
            ),
            self._still(
                "loading",
                fleet.load_seconds,
                LOADING_STARTED,
                LOADING_COMPLETED,
                fleet.hub_position_m,
                fleet.hub_id,
                ("to_journey", "pad_release"),
                "loading",
            ),
            _Stage(
                "flight",
                flight,
                DRONE_FLIGHT_STARTED,
                DRONE_FLIGHT_COMPLETED,
                corridor.waypoints_m,
                corridor.locker_id,
                corridor.distance_m,
                (),
                "flight",
                f"journey-{order.spec.order_id}-flight",
            ),
            self._still(
                "unloading",
                fleet.unload_seconds,
                UNLOADING_STARTED,
                UNLOADING_COMPLETED,
                locker_point,
                corridor.locker_id,
                tuple(unload_effects),
                "unloading",
            ),
        ]
        if fail:
            wait = order.spec.pickup_window_seconds if order.spec.pickup_window_seconds >= 1 else 1
            effect = "handoff_fallback" if fallback else "handoff_hold"
            stages.append(
                self._still(
                    "failed_pickup_wait",
                    wait,
                    "",
                    "",
                    locker_point,
                    corridor.locker_id,
                    (effect,),
                    "wait",
                )
            )
            if not fallback:
                stages.append(
                    self._still(
                        "loading",
                        fleet.load_seconds,
                        LOADING_STARTED,
                        LOADING_COMPLETED,
                        locker_point,
                        corridor.locker_id,
                        ("to_journey",),
                        "reload",
                    )
                )
        stages.append(
            _Stage(
                "return_travel",
                flight,
                DRONE_FLIGHT_STARTED,
                DRONE_FLIGHT_COMPLETED,
                tuple(reversed(corridor.waypoints_m)),
                corridor.hub_id,
                corridor.distance_m,
                (),
                "return",
                f"journey-{order.spec.order_id}-return",
            )
        )
        if fail and not fallback:
            stages.append(
                self._still(
                    "unloading",
                    fleet.unload_seconds,
                    UNLOADING_STARTED,
                    UNLOADING_COMPLETED,
                    fleet.hub_position_m,
                    fleet.hub_id,
                    ("to_hub", "fail_closed"),
                    "hub_unload",
                )
            )
        service = fleet.load_seconds + fleet.unload_seconds
        if fail and not fallback:
            service += fleet.load_seconds + fleet.unload_seconds
        duration = sum(stage.duration for stage in stages)
        return _Plan(
            tuple(stages),
            corridor.distance_m * 2,
            duration,
            service,
            flight * 2,
        )

    def _append_road(
        self,
        stages: list[_Stage],
        order: _Order,
        carrier: _Carrier,
        leg,
        leg_name: str,
        component: str = "access_transfer",
    ) -> None:
        duration = travel_seconds(leg.distance_m, carrier.spec.speed_m_per_s, carrier.spec.congestion_milli)
        if duration < 1:
            return
        stages.append(
            _Stage(
                component,
                duration,
                JOURNEY_STARTED,
                JOURNEY_ARRIVED,
                leg.waypoints_m,
                leg.destination_place_id,
                leg.distance_m,
                (),
                leg_name,
                f"journey-{order.spec.order_id}-{leg_name}",
            )
        )

    def _still(
        self,
        component: str,
        duration: int,
        start_kind: str,
        end_kind: str,
        point: tuple[int, int],
        place_id: str,
        effects: tuple[str, ...],
        leg: str,
    ) -> _Stage:
        return _Stage(component, duration, start_kind, end_kind, (point,), place_id, 0, effects, leg, None)

    def _assess(self, carrier: _Carrier, order: _Order, start: int) -> str | None:
        static = static_blocker(carrier.spec, order.spec.grams, order.spec.storage_class)
        if static:
            return static
        plan = self._compile(order, carrier)
        if downtime_blocker(carrier.spec.downtime, start, start + plan.duration):
            return "maintenance"
        energy = carrier.energy_remaining if carrier.status == "idle" else carrier.energy_when_free
        if energy_blocker(energy, plan.distance_m, carrier.spec.energy_per_metre, carrier.spec.reserve_energy):
            return "energy_reserve"
        if shift_blocker(carrier.spec.shift_start, carrier.spec.shift_end, start, plan.duration):
            return "shift"
        if carrier.spec.kind == "drone":
            return self._drone_timing_blocker(order, carrier, start)
        return None

    def _drone_timing_blocker(self, order: _Order, carrier: _Carrier, start: int) -> str | None:
        if order.spec.corridor_id is None:
            return "missing_corridor"
        corridor = self.corridors[order.spec.corridor_id]
        permission = permission_blocker(corridor)
        if permission:
            return permission
        flight = travel_seconds(corridor.distance_m, carrier.spec.speed_m_per_s, carrier.spec.congestion_milli)
        flight_start = start + self.fleet.prep_seconds + self.fleet.load_seconds
        flight_end = flight_start + flight
        if weather_blocker(corridor, flight_start, flight_end):
            return "weather"
        return site_hours_blocker(corridor, flight_end, self.fleet.unload_seconds)

    def _pick(self, order: _Order, second: int) -> _Carrier | None:
        kind = self._kind_for(order)
        found: list[_Carrier] = []
        for carrier in self.carriers.values():
            if carrier.spec.kind != kind or carrier.status != "idle" or carrier.free_at > second:
                continue
            if self._assess(carrier, order, second) is None:
                found.append(carrier)
        found.sort(key=lambda carrier: (carrier.free_at, carrier.spec.carrier_id))
        return found[0] if found else None

    def _eventually(self, kind: str, order: _Order, second: int) -> bool:
        for carrier in self._of_kind(kind):
            if static_blocker(carrier.spec, order.spec.grams, order.spec.storage_class):
                continue
            start = self._earliest_start(carrier, kind, order, second)
            if self._assess(carrier, order, start) is None:
                return True
        return False

    def _failure_reason(self, kind: str, order: _Order, second: int) -> str:
        carriers = self._of_kind(kind)
        if not carriers:
            return "no_carrier"
        statics = [static_blocker(carrier.spec, order.spec.grams, order.spec.storage_class) for carrier in carriers]
        if all(statics):
            return next(reason for reason in statics if reason)
        last = "no_carrier"
        for carrier in carriers:
            if static_blocker(carrier.spec, order.spec.grams, order.spec.storage_class):
                continue
            start = self._earliest_start(carrier, kind, order, second)
            reason = self._assess(carrier, order, start)
            if reason is None:
                return "no_carrier"
            last = reason
        return last

    def _all_static(self, kind: str, order: _Order) -> bool:
        carriers = self._of_kind(kind)
        if not carriers:
            return True
        return all(
            static_blocker(carrier.spec, order.spec.grams, order.spec.storage_class) is not None
            for carrier in carriers
        )

    def _earliest_start(self, carrier: _Carrier, kind: str, order: _Order, second: int) -> int:
        start = max(second, carrier.free_at, carrier.spec.shift_start)
        if kind == "van" and not order.food_at_locker and self.bay_in_use >= self.fleet.bay_servers:
            start = max(start, self.bay_free_at)
        if kind == "drone" and self.pad_in_use >= self.fleet.drone_pad_servers:
            start = max(start, self.pad_free_at)
        return start

    def _of_kind(self, kind: str) -> list[_Carrier]:
        found = [carrier for carrier in self.carriers.values() if carrier.spec.kind == kind]
        found.sort(key=lambda carrier: carrier.spec.carrier_id)
        return found

    def _can_start_now(self, order: _Order, second: int) -> bool:
        return self._slot_free(order) and self._pick(order, second) is not None

    def _slot_free(self, order: _Order) -> bool:
        if self._needs_bay(order):
            return self.bay_in_use < self.fleet.bay_servers
        if self._needs_pad(order):
            return self.pad_in_use < self.fleet.drone_pad_servers
        return True

    def _needs_bay(self, order: _Order) -> bool:
        return order.mode == "ground" and not order.food_at_locker

    def _needs_pad(self, order: _Order) -> bool:
        return order.mode == "drone"

    def _kind_for(self, order: _Order) -> str:
        return "drone" if order.mode == "drone" else "van"

    def _add_billing(self, order: _Order, carrier: _Carrier, plan: _Plan) -> None:
        if carrier.spec.kind == "drone":
            order.billed_drone_distance_m += plan.distance_m
            order.billed_drone_flight_seconds += plan.flight_seconds
            order.billed_drone_service_seconds += plan.service_seconds
        else:
            order.billed_ground_distance_m += plan.distance_m
            order.billed_ground_service_seconds += plan.service_seconds

    def _money(self, order: _Order) -> int:
        fleet = self.fleet
        cents = (
            order.billed_ground_distance_m * fleet.ground_cents_per_metre
            + order.billed_ground_service_seconds * fleet.ground_cents_per_service_second
            + order.billed_drone_distance_m * fleet.drone_cents_per_metre
            + order.billed_drone_flight_seconds * fleet.drone_cents_per_flight_second
            + order.billed_drone_service_seconds * fleet.drone_cents_per_service_second
        )
        if order.duplicate_handling:
            cents += fleet.fallback_handling_cents
        return cents

    def _will_fail(self, order: _Order) -> bool:
        if order.spec.handoff == "miss":
            return True
        return self._walk_seconds(order) > order.spec.pickup_window_seconds

    def _walk_seconds(self, order: _Order) -> int:
        if order.spec.walk is None:
            return 0
        return travel_seconds(order.spec.walk.distance_m, order.spec.walk_speed_m_per_s, 1000)

    def _handoff_reason(self, order: _Order) -> str:
        if order.spec.handoff == "miss":
            return "miss"
        return "walk_exceeds_window"

    def _unsafe(self, order: _Order, load_start: int) -> bool:
        return any(self.core.lot(lot_id).unsafe_after_second <= load_start for lot_id in order.spec.lot_ids)

    def _reserve(self, order: _Order, second: int) -> None:
        if order.reserved:
            return
        for lot_id in order.spec.lot_ids:
            grant = self.core.reserve(lot_id, order.spec.order_id, second)
            order.reservation_ids.append(grant.reservation_id)
        order.reserved = True

    def _release(self, order: _Order, second: int) -> None:
        for reservation_id in list(order.reservation_ids):
            self.core.release(reservation_id, second)
        order.reservation_ids = []
        order.released = True

    def _move_all(self, order: _Order, second: int, *, place_id: str | None, journey_id: str | None) -> None:
        for lot_id in order.spec.lot_ids:
            self.core.move_custody(
                lot_id,
                holder_id=order.spec.order_id,
                place_id=place_id,
                journey_id=journey_id,
                second=second,
            )

    def _following_journey(self, carrier: _Carrier) -> str:
        for stage in carrier.stages[carrier.stage_index + 1 :]:
            if stage.journey_id:
                return stage.journey_id
        raise LogisticsError("loading finished without a following journey")

    def _post(self, order: _Order, second: int) -> None:
        posting_id = f"post-{order.spec.order_id}-operating"
        posting = self.core.post(
            posting_id,
            self.fleet.operating_account,
            self.fleet.external_account,
            order.operating_cents,
            "logistics_operating_cost",
            second,
        )
        self.postings.append(
            {
                "cents": posting.cents,
                "credit_account": posting.credit_account,
                "debit_account": posting.debit_account,
                "order_id": order.spec.order_id,
                "posting_id": posting.posting_id,
                "second": posting.second,
            }
        )

    def _emit_blocker(self, order: _Order, reason: str, second: int) -> None:
        if reason in {"no_approval", "ineligible", "missing_corridor"}:
            kind = ROUTE_INELIGIBLE
        elif reason == "weather":
            kind = WEATHER_EXCLUDED
        elif reason == "queue_capacity":
            kind = QUEUE_REJECTED
        else:
            kind = CARRIER_UNAVAILABLE
        self._emit(kind, order, second, reason=reason, place_id=self.fleet.hub_id)

    def _emit_advances(self, second: int) -> None:
        for order_id, position in self.waiting.positions():
            self._emit(
                QUEUE_ADVANCED,
                self.orders[order_id],
                second,
                place_id=self.fleet.hub_id,
                queue_position=position,
                reason="advanced",
            )

    def _status_for(self, reasons: tuple[str, ...]) -> str:
        if any(reason in EXCLUSION_REASONS for reason in reasons):
            return "excluded"
        return "unserved"

    def _emit(
        self,
        kind: str,
        order: _Order | None,
        second: int,
        *,
        carrier: _Carrier | None = None,
        place_id: str | None = None,
        leg: str = "",
        waypoints: tuple[tuple[int, int], ...] = (),
        depart: int | None = None,
        arrive: int | None = None,
        queue_position: int | None = None,
        cents: int | None = None,
        reason: str = "",
        journey_id: str | None = None,
        include_lots: bool = False,
    ) -> LogisticsEvent:
        causes = (order.last_event_id,) if order is not None and order.last_event_id else ()
        event = LogisticsEvent(
            event_id=f"logi-{self.sequence:08d}",
            sequence=self.sequence,
            second=second,
            phase=self.clock_phase,
            kind=kind,
            causes=causes,
            actor_id=order.spec.recipient_id if order is not None else "",
            place_id=place_id,
            vehicle_id=carrier.spec.carrier_id if carrier is not None else None,
            order_id=order.spec.order_id if order is not None else None,
            leg=leg,
            waypoints_m=waypoints,
            depart_second=depart,
            arrive_second=arrive,
            queue_id=self.fleet.queue_id if queue_position is not None or kind in {QUEUE_JOINED, QUEUE_ADVANCED, QUEUE_REJECTED} else None,
            queue_position=queue_position,
            grams=order.spec.grams if order is not None else None,
            cents=cents,
            reason=reason,
            lot_ids=order.spec.lot_ids if include_lots and order is not None else (),
            reservation_ids=tuple(order.reservation_ids) if include_lots and order is not None else (),
            journey_id=journey_id,
        )
        self.sequence += 1
        self.events.append(event)
        if order is not None:
            order.last_event_id = event.event_id
        return event

    def _schedule(
        self,
        second: int,
        phase: int,
        kind: str,
        order_id: str,
        carrier_id: str,
        rank: int,
    ) -> None:
        action = _Action(second, phase, self.action_seq, rank, kind, order_id, carrier_id)
        self.action_seq += 1
        self.actions.append(action)

    def _defer(self, action: _Action) -> None:
        self._drop([action])
        self.actions.append(
            _Action(
                action.second + 1,
                action.phase,
                action.seq,
                action.rank,
                action.kind,
                action.order_id,
                action.carrier_id,
            )
        )

    def _drop(self, actions: list[_Action]) -> None:
        gone = {id(action) for action in actions}
        self.actions = [action for action in self.actions if id(action) not in gone]

    def _validate_lots(self, order: DeliveryOrder) -> None:
        total = 0
        for lot_id in order.lot_ids:
            if lot_id in self._lots_taken:
                raise LogisticsError(f"lot {lot_id} is already on an order")
            lot = self.core.lot(lot_id)
            if lot.storage_class != order.storage_class:
                raise LogisticsError(f"lot {lot_id} storage class does not match the order")
            if lot.custody != "place" or lot.place_id != order.origin_place_id:
                raise LogisticsError(f"lot {lot_id} is not at the order origin")
            if lot.reserved_by is not None:
                raise LogisticsError(f"lot {lot_id} is already reserved")
            total += lot.grams
        if total != order.grams:
            raise LogisticsError("order grams must equal the sum of its lots")
        self._lots_taken.update(order.lot_ids)

    def _validate_route_endpoints(self, order: DeliveryOrder) -> None:
        if order.ground_out is not None:
            if order.ground_out.origin_place_id != order.origin_place_id:
                raise LogisticsError("ground outbound must start at the origin")
            if order.ground_out.destination_place_id != order.destination_place_id:
                raise LogisticsError("ground outbound must end at the destination")
        if order.ground_return is not None and order.ground_return.destination_place_id != order.origin_place_id:
            raise LogisticsError("ground return must end at the origin")
        if order.walk is not None and order.locker_place_id is not None:
            if order.walk.destination_place_id != order.locker_place_id:
                raise LogisticsError("the customer walk must end at the locker")

    def _carriers(self) -> list[_Carrier]:
        return [self.carriers[key] for key in sorted(self.carriers)]

    def _order_list(self) -> list[_Order]:
        return [self.orders[key] for key in sorted(self.orders)]

    def _corridor_list(self) -> list[Corridor]:
        return [self.corridors[key] for key in sorted(self.corridors)]

    def _fleet_state(self) -> dict[str, object]:
        fleet = self.fleet
        return {
            "bay_servers": fleet.bay_servers,
            "drone_cents_per_flight_second": fleet.drone_cents_per_flight_second,
            "drone_cents_per_metre": fleet.drone_cents_per_metre,
            "drone_cents_per_service_second": fleet.drone_cents_per_service_second,
            "drone_pad_servers": fleet.drone_pad_servers,
            "external_account": fleet.external_account,
            "fallback_handling_cents": fleet.fallback_handling_cents,
            "ground_cents_per_metre": fleet.ground_cents_per_metre,
            "ground_cents_per_service_second": fleet.ground_cents_per_service_second,
            "hub_id": fleet.hub_id,
            "load_seconds": fleet.load_seconds,
            "operating_account": fleet.operating_account,
            "prep_seconds": fleet.prep_seconds,
            "queue_id": fleet.queue_id,
            "queue_waiting_capacity": fleet.queue_waiting_capacity,
            "unload_seconds": fleet.unload_seconds,
        }

    def _carrier_state(self, carrier: _Carrier) -> dict[str, object]:
        spec = carrier.spec
        return {
            "active_order_id": carrier.active_order_id,
            "carrier_id": spec.carrier_id,
            "charge_per_second": spec.charge_per_second,
            "cold_chain": _flag(spec.cold_chain),
            "congestion_milli": spec.congestion_milli,
            "energy_capacity": spec.energy_capacity,
            "energy_consumed": carrier.energy_consumed,
            "energy_per_metre": spec.energy_per_metre,
            "energy_remaining": carrier.energy_remaining,
            "energy_when_free": carrier.energy_when_free,
            "free_at": carrier.free_at,
            "kind": spec.kind,
            "payload_grams": spec.payload_grams,
            "pending_charge": carrier.pending_charge,
            "position_m": [carrier.position[0], carrier.position[1]],
            "reserve_energy": spec.reserve_energy,
            "shift_end": spec.shift_end,
            "shift_start": spec.shift_start,
            "speed_m_per_s": spec.speed_m_per_s,
            "stage_index": carrier.stage_index,
            "stages": [
                {"component": stage.component, "duration": stage.duration, "leg": stage.leg}
                for stage in carrier.stages
            ],
            "status": carrier.status,
        }

    def _order_state(self, order: _Order) -> dict[str, object]:
        return {
            "billed_drone_distance_m": order.billed_drone_distance_m,
            "billed_drone_flight_seconds": order.billed_drone_flight_seconds,
            "billed_drone_service_seconds": order.billed_drone_service_seconds,
            "billed_ground_distance_m": order.billed_ground_distance_m,
            "billed_ground_service_seconds": order.billed_ground_service_seconds,
            "carrier_id": order.carrier_id,
            "collection_second": order.collection_second,
            "completed_by": order.completed_by,
            "components": dict(sorted(order.components.items())),
            "duplicate_handling": _flag(order.duplicate_handling),
            "fallback_count": order.fallback_count,
            "food_at_locker": _flag(order.food_at_locker),
            "grams": order.spec.grams,
            "handoff_failed": _flag(order.handoff_failed),
            "mode": order.mode,
            "operating_cents": order.operating_cents,
            "order_id": order.spec.order_id,
            "rank": order.rank,
            "reasons": list(order.reasons),
            "recipient_id": order.spec.recipient_id,
            "status": order.status,
        }

    def _corridor_state(self, corridor: Corridor) -> dict[str, object]:
        return {
            "approval": corridor.approval,
            "corridor_id": corridor.corridor_id,
            "distance_m": corridor.distance_m,
            "eligible": _flag(corridor.eligible),
            "locker_id": corridor.locker_id,
            "site_close_second": corridor.site_close_second,
            "site_open_second": corridor.site_open_second,
        }
