"""One headless morning: a queue, a van, a purchase, a batch, and a meal.

The run is deterministic for a seed. It does not draw a scene.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core import (
    PHASE_CONSUME,
    PHASE_POLICY,
    PHASE_SETTLE,
    ConsumeFood,
    IntroduceLot,
    OpenAccount,
    ProcessBatch,
    PurchaseLot,
    RecordChoice,
    TransferCash,
    apply_command,
    empty_state,
    load_catalog,
    sha256_hex,
    state_hash,
)
from sim.logistics.carriers import Carrier, plan_loads
from sim.logistics.cues import AnimationCue, animation_cues
from sim.logistics.journeys import arrive_lot, child_lot_id, depart_lot
from sim.logistics.queues import queue_positions


def _world(run_id: str):
    catalog = load_catalog()
    return empty_state(
        run_id=run_id,
        scenario_id="baseline",
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog.sha256,
        known_product_ids=tuple(product.product_id for product in catalog.products),
    )


def _settle(state, commands: list):
    events: list = []
    for command in commands:
        transition = apply_command(state, command)
        if transition.status != "accepted":
            raise RuntimeError(f"{command.command_id} {transition.status} {transition.reason} {transition.detail}")
        events.extend(transition.events)
        state = transition.state
    return state, tuple(events)

TRAVEL_SECONDS = 120
DEPARTURE_SECOND = 100


@dataclass(frozen=True, slots=True)
class IntegratedRun:
    seed: int
    state: object
    events: tuple
    state_hash: str
    cues: tuple[AnimationCue, ...]
    loaded_order_ids: tuple[str, ...]
    missed_order_ids: tuple[str, ...]
    arrival_second: int


def run_integrated(seed: int = 17) -> IntegratedRun:
    positions = queue_positions(seed, "van-morning", ("hh-c", "hh-a", "hh-b"))
    orders = tuple((f"order-{actor_id}", 600) for actor_id, _rank in positions)
    carrier = Carrier("van-1", 1000, 0, 86400)
    plan = plan_loads(carrier, orders, DEPARTURE_SECOND)
    loaded = tuple(item for item in plan if item.status == "loaded")
    if len(loaded) != 1:
        raise RuntimeError("this morning's payload admits one 600 g order")
    state = _world(f"integrated-{seed}")
    commands: list = [
        OpenAccount("open-ext", 0, PHASE_POLICY, "acct-ext", "ext", "external", True),
        OpenAccount("open-hub", 0, PHASE_POLICY, "acct-hub", "hub", "hub", False),
        OpenAccount("open-van", 0, PHASE_POLICY, "acct-van", "van-1", "carrier", False),
        OpenAccount("open-school", 0, PHASE_POLICY, "acct-school", "school-a", "school", False),
        OpenAccount("open-store", 0, PHASE_POLICY, "acct-store", "store-r", "retailer", False),
        OpenAccount("open-plant", 0, PHASE_POLICY, "acct-plant", "plant", "processor", False),
        OpenAccount("open-hh", 0, PHASE_POLICY, "acct-hh", "hh-shop", "household", False),
        TransferCash("cash-hh", 0, PHASE_POLICY, "acct-ext", "acct-hh", 1000, "opening_balance"),
        IntroduceLot("lot-hub", 0, PHASE_POLICY, "lot-hub", "produce.fresh", "hub", "hub", 2000, 0, None),
        IntroduceLot("lot-store", 0, PHASE_POLICY, "lot-store", "produce.fresh", "store-r", "store-r", 1000, 300, None),
        IntroduceLot("lot-plant", 0, PHASE_POLICY, "lot-plant", "produce.fresh", "plant", "plant", 400, 0, None),
        IntroduceLot("lot-school", 0, PHASE_POLICY, "lot-school", "produce.fresh", "school-a", "school-a", 200, 60, None),
    ]
    for actor_id, rank in positions:
        decision = next(item for item in plan if item.order_id == f"order-{actor_id}")
        option = "queue:loaded" if decision.status == "loaded" else "queue:missed"
        commands.append(
            RecordChoice(
                f"q-{actor_id}",
                4,
                4,
                f"dec-{actor_id}",
                actor_id,
                option,
                "rule",
                sha256_hex({"rank": rank, "option": option}),
                0,
                f"rank {rank} {decision.status}",
            )
        )
    first = loaded[0]
    depart_id = f"depart-{first.order_id}"
    commands.append(depart_lot(depart_id, DEPARTURE_SECOND, "lot-hub", first.grams, "hub", "school-a", f"trip-{first.order_id}"))
    commands.append(
        PurchaseLot("buy-hh", 110, PHASE_SETTLE, "acct-hh", "acct-store", "home-hh-shop", "lot-store", 400, 200)
    )
    commands.append(
        ProcessBatch("batch-plant", 130, PHASE_SETTLE, "plant", "lot-plant", 400, "produce.prepared", 300, 100, "plant", None)
    )
    commands.append(ConsumeFood("serve-school", 140, PHASE_CONSUME, "school-a", "lot-school", 200))
    arrival = DEPARTURE_SECOND + TRAVEL_SECONDS
    travelling = child_lot_id("lot-hub", depart_id)
    commands.append(arrive_lot(f"arrive-{first.order_id}", arrival, travelling, first.grams, "school-a", "school-a"))
    state, events = _settle(state, commands)
    return IntegratedRun(
        seed=seed,
        state=state,
        events=events,
        state_hash=state_hash(state),
        cues=animation_cues(events),
        loaded_order_ids=tuple(item.order_id for item in loaded),
        missed_order_ids=tuple(item.order_id for item in plan if item.status != "loaded"),
        arrival_second=arrival,
    )
