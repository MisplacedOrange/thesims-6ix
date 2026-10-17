"""Economic records. Amounts inside these records are already settled integers.

Replay writes the records it is given. It does not recompute prices, yields,
or who won a contended lot.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core.version import KERNEL_VERSION


ACTOR_KINDS = (
    "household",
    "retailer",
    "municipality",
    "processor",
    "school",
    "external",
    "carrier",
    "hub",
)


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    owner_id: str
    kind: str
    settled_cents: int
    reserved_cents: int
    allows_credit: bool


@dataclass(frozen=True, slots=True)
class FoodLot:
    lot_id: str
    product_id: str
    owner_id: str
    place_id: str
    journey_id: str | None
    grams: int
    reserved_grams: int
    unsafe_after: int | None
    parents: tuple[str, ...]
    acquisition_cents: int


@dataclass(frozen=True, slots=True)
class Reservation:
    reservation_id: str
    holder_id: str
    cash_account_id: str | None
    max_cents: int
    lot_id: str | None
    grams: int
    second: int
    command_id: str


@dataclass(frozen=True, slots=True)
class JournalLine:
    account_id: str
    cents: int
    memo: str


@dataclass(frozen=True, slots=True)
class JournalEntry:
    entry_id: str
    command_id: str
    sequence: int
    second: int
    lines: tuple[JournalLine, ...]


@dataclass(frozen=True, slots=True)
class FoodMovement:
    movement_id: str
    command_id: str
    sequence: int
    kind: str
    product_id: str
    grams: int
    from_owner_id: str | None
    to_owner_id: str | None
    from_lot_id: str | None
    to_lot_id: str | None
    parent_lot_ids: tuple[str, ...]
    acquisition_cents_recognized: int
    acquisition_cents_introduced: int


@dataclass(frozen=True, slots=True)
class ChoiceRecord:
    decision_id: str
    household_id: str
    option_id: str
    origin: str
    observation_hash: str
    revision: int
    explanation: str | None


@dataclass(frozen=True, slots=True)
class WorldState:
    schema_version: int
    kernel_version: str
    run_id: str
    scenario_id: str
    catalog_id: str
    catalog_sha256: str
    second: int
    phase: int
    next_sequence: int
    last_event_id: str | None
    accounts: tuple[Account, ...]
    lots: tuple[FoodLot, ...]
    reservations: tuple[Reservation, ...]
    journal: tuple[JournalEntry, ...]
    movements: tuple[FoodMovement, ...]
    choices: tuple[ChoiceRecord, ...]
    applied_command_ids: tuple[str, ...]
    imported_grams: int
    added_grams: int
    consumed_grams: int
    loss_grams: int
    exported_grams: int
    known_product_ids: tuple[str, ...]


def fresh_state(
    *,
    run_id: str,
    scenario_id: str,
    catalog_id: str,
    catalog_sha256: str,
    known_product_ids: tuple[str, ...],
) -> WorldState:
    return WorldState(
        schema_version=1,
        kernel_version=KERNEL_VERSION,
        run_id=run_id,
        scenario_id=scenario_id,
        catalog_id=catalog_id,
        catalog_sha256=catalog_sha256,
        second=0,
        phase=0,
        next_sequence=1,
        last_event_id=None,
        accounts=(),
        lots=(),
        reservations=(),
        journal=(),
        movements=(),
        choices=(),
        applied_command_ids=(),
        imported_grams=0,
        added_grams=0,
        consumed_grams=0,
        loss_grams=0,
        exported_grams=0,
        known_product_ids=known_product_ids,
    )
