"""Pooled purchasing at the same served demand as two school orders.

A lower unit price can be offset by hub labor and spoilage. Served grams
stay equal so the handling cost is not confused with feeding more pupils.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core import (
    PHASE_CONSUME,
    PHASE_EXPIRY,
    PHASE_POLICY,
    PHASE_SETTLE,
    CAD_CENTS,
    GRAMS,
    ApplyExpiry,
    ConsumeFood,
    IntroduceLot,
    Metric,
    OpenAccount,
    TransferCash,
    TransferLot,
)

from sim.policies.session import memo_cents, settle, world

SERVED_GRAMS = 400
SCHOOL_ORDER_GRAMS = 200
DECENTRAL_CENTS_PER_100G = 40
POOLED_CENTS_PER_100G = 30
HUB_LABOR_CENTS = 30
DISPOSAL_CENTS = 10


@dataclass(frozen=True, slots=True)
class ProcurementResult:
    mode: str
    spoilage_grams: int
    evidence_state: str
    state: object
    events: tuple
    served_grams: int
    food_cents: int
    hub_labor_cents: int
    disposal_cents: int
    delivered_cost_cents: int
    waste_grams: int
    metrics: tuple[Metric, ...]
    note: str


def run_procurement(mode: str, *, spoilage_grams: int = 0) -> ProcurementResult:
    if mode not in {"decentralized", "pooled"}:
        raise ValueError(mode)
    if spoilage_grams < 0 or spoilage_grams % 100 != 0:
        raise ValueError("spoilage_grams must be a non-negative multiple of 100")
    if mode == "decentralized" and spoilage_grams != 0:
        raise ValueError("this fixture keeps spoilage on the hub")
    state = world(f"procure-{mode}-{spoilage_grams}", "procurement-nested")
    commands: list = [
        OpenAccount("open-ext", 0, PHASE_POLICY, "acct-ext", "ext", "external", True),
        OpenAccount("open-hub", 0, PHASE_POLICY, "acct-hub", "hub", "hub", False),
        OpenAccount("open-a", 0, PHASE_POLICY, "acct-a", "school-a", "school", False),
        OpenAccount("open-b", 0, PHASE_POLICY, "acct-b", "school-b", "school", False),
        TransferCash("fund-hub", 0, PHASE_POLICY, "acct-ext", "acct-hub", 100000, "appropriation"),
        TransferCash("fund-a", 0, PHASE_POLICY, "acct-ext", "acct-a", 100000, "appropriation"),
        TransferCash("fund-b", 0, PHASE_POLICY, "acct-ext", "acct-b", 100000, "appropriation"),
    ]
    if mode == "decentralized":
        for school, account in (("school-a", "acct-a"), ("school-b", "acct-b")):
            cents = SCHOOL_ORDER_GRAMS // 100 * DECENTRAL_CENTS_PER_100G
            commands.extend(
                [
                    TransferCash(f"pay-{school}", 0, PHASE_POLICY, account, "acct-ext", cents, "inventory_payment"),
                    IntroduceLot(
                        f"lot-{school}",
                        0,
                        PHASE_POLICY,
                        f"lot-{school}",
                        "produce.fresh",
                        school,
                        school,
                        SCHOOL_ORDER_GRAMS,
                        cents,
                        None,
                    ),
                ]
            )
        for school in ("school-a", "school-b"):
            commands.append(ConsumeFood(f"eat-{school}", 6, PHASE_CONSUME, school, f"lot-{school}", SCHOOL_ORDER_GRAMS))
    else:
        bought = SERVED_GRAMS + spoilage_grams
        cents = bought // 100 * POOLED_CENTS_PER_100G
        commands.extend(
            [
                TransferCash("pay-hub", 0, PHASE_POLICY, "acct-hub", "acct-ext", cents, "inventory_payment"),
                TransferCash("hub-labor", 0, PHASE_POLICY, "acct-hub", "acct-ext", HUB_LABOR_CENTS, "labor"),
                IntroduceLot("lot-hub", 0, PHASE_POLICY, "lot-hub", "produce.fresh", "hub", "hub", bought, cents, 40),
                TransferLot("to-a", 2, PHASE_SETTLE, "lot-hub", SCHOOL_ORDER_GRAMS, "school-a", "school-a"),
                TransferLot("to-b", 2, PHASE_SETTLE, "lot-hub", SCHOOL_ORDER_GRAMS, "school-b", "school-b"),
                ConsumeFood("eat-a", 6, PHASE_CONSUME, "school-a", "lot-hub.to-a", SCHOOL_ORDER_GRAMS),
                ConsumeFood("eat-b", 6, PHASE_CONSUME, "school-b", "lot-hub.to-b", SCHOOL_ORDER_GRAMS),
            ]
        )
        if spoilage_grams:
            commands.extend(
                [
                    TransferCash("disposal", 30, PHASE_SETTLE, "acct-hub", "acct-ext", DISPOSAL_CENTS, "disposal"),
                    ApplyExpiry("spoil", 40, PHASE_EXPIRY),
                ]
            )
    state, events = settle(state, commands)
    food = 0
    labor = 0
    disposal = 0
    for account in ("acct-a", "acct-b", "acct-hub"):
        food += memo_cents(state, account, "inventory_payment", leaving=True)
        labor += memo_cents(state, account, "labor", leaving=True)
        disposal += memo_cents(state, account, "disposal", leaving=True)
    waste = sum(movement.grams for movement in state.movements if movement.kind == "waste")
    return ProcurementResult(
        mode=mode,
        spoilage_grams=spoilage_grams,
        evidence_state="illustrative",
        state=state,
        events=events,
        served_grams=state.consumed_grams,
        food_cents=food,
        hub_labor_cents=labor,
        disposal_cents=disposal,
        delivered_cost_cents=food + labor + disposal,
        waste_grams=waste,
        metrics=(
            Metric("served_grams", state.consumed_grams, GRAMS),
            Metric("delivered_cost", food + labor + disposal, CAD_CENTS),
        ),
        note="Delivered cost is food plus hub labor plus disposal. Served grams are the meals, not the purchased mass.",
    )
