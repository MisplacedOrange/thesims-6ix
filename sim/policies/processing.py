"""Rescue and purchased inputs stay separate. A shift cap is an upper bound.

The edible split follows the frozen catalog recipe: 400 g fresh becomes
300 g prepared and 100 g process loss. Announced plant capacity is not
used as throughput.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core import (
    PHASE_EXPIRY,
    PHASE_POLICY,
    PHASE_SETTLE,
    CAD_CENTS,
    GRAMS,
    ApplyExpiry,
    IntroduceLot,
    Metric,
    OpenAccount,
    ProcessBatch,
    TransferCash,
    lots_for_owner,
    split_mass_by_ratio,
)

from sim.policies.session import memo_cents, settle, world

SHIFT_INPUT_GRAMS = 400
PURCHASED_CENTS = 120
LABOR_CENTS = 100


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    rescue_eligible: bool
    evidence_state: str
    state: object
    events: tuple
    rescued_input_grams: int
    purchased_input_grams: int
    purchased_grams_remaining: int
    edible_grams: int
    process_loss_grams: int
    waste_grams: int
    labor_cents: int
    purchased_food_cents: int
    fiscal_transfer_cents: int
    metrics: tuple[Metric, ...]
    note: str


def run_processing(*, rescue_eligible: bool) -> ProcessingResult:
    edible, loss = split_mass_by_ratio(SHIFT_INPUT_GRAMS, 3, 4, "process_loss")
    state = world("processing", "processing-only")
    rescue_unsafe = None if rescue_eligible else 1
    commands: list = [
        OpenAccount("open-ext", 0, PHASE_POLICY, "acct-ext", "ext", "external", True),
        OpenAccount("open-m", 0, PHASE_POLICY, "acct-m", "muni", "municipality", False),
        OpenAccount("open-p", 0, PHASE_POLICY, "acct-p", "plant", "processor", False),
        TransferCash("fund", 0, PHASE_POLICY, "acct-ext", "acct-m", PURCHASED_CENTS + LABOR_CENTS, "appropriation"),
        TransferCash("to-p", 0, PHASE_POLICY, "acct-m", "acct-p", PURCHASED_CENTS + LABOR_CENTS, "operating_subsidy"),
        TransferCash("buy-in", 0, PHASE_POLICY, "acct-p", "acct-ext", PURCHASED_CENTS, "inventory_payment"),
        IntroduceLot("lot-rescue", 0, PHASE_POLICY, "lot-rescue", "produce.fresh", "plant", "plant", SHIFT_INPUT_GRAMS, 0, rescue_unsafe),
        IntroduceLot(
            "lot-bought",
            0,
            PHASE_POLICY,
            "lot-bought",
            "produce.fresh",
            "plant",
            "plant",
            SHIFT_INPUT_GRAMS,
            PURCHASED_CENTS,
            100000,
        ),
        TransferCash("labor", 0, PHASE_POLICY, "acct-p", "acct-ext", LABOR_CENTS, "labor"),
    ]
    if not rescue_eligible:
        commands.append(ApplyExpiry("expire", 1, PHASE_EXPIRY))
    source = "lot-rescue" if rescue_eligible else "lot-bought"
    commands.append(
        ProcessBatch(
            "batch",
            2,
            PHASE_SETTLE,
            "plant",
            source,
            SHIFT_INPUT_GRAMS,
            "produce.prepared",
            edible,
            loss,
            "plant",
            100000,
        )
    )
    state, events = settle(state, commands)
    remaining = sum(lot.grams for lot in lots_for_owner(state, "plant") if lot.product_id == "produce.fresh")
    edible_grams = sum(lot.grams for lot in lots_for_owner(state, "plant") if lot.product_id == "produce.prepared")
    waste = sum(movement.grams for movement in state.movements if movement.kind == "waste")
    process_loss = sum(movement.grams for movement in state.movements if movement.kind == "process_loss")
    return ProcessingResult(
        rescue_eligible=rescue_eligible,
        evidence_state="illustrative",
        state=state,
        events=events,
        rescued_input_grams=SHIFT_INPUT_GRAMS if rescue_eligible else 0,
        purchased_input_grams=0 if rescue_eligible else SHIFT_INPUT_GRAMS,
        purchased_grams_remaining=remaining,
        edible_grams=edible_grams,
        process_loss_grams=process_loss,
        waste_grams=waste,
        labor_cents=memo_cents(state, "acct-p", "labor", leaving=True),
        purchased_food_cents=memo_cents(state, "acct-p", "inventory_payment", leaving=True),
        fiscal_transfer_cents=memo_cents(state, "acct-m", "operating_subsidy", leaving=True),
        metrics=(
            Metric("edible_grams", edible_grams, GRAMS),
            Metric("labor", LABOR_CENTS, CAD_CENTS),
            Metric("purchased_food", PURCHASED_CENTS, CAD_CENTS),
        ),
        note=(
            "One shift accepts 400 g. Rescue is used first when it is still safe. "
            "Purchased food is not relabeled as rescue, and the announced annual capacity is not throughput."
        ),
    )
