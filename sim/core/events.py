"""Committed events. Payloads carry the settled amounts and the replacement records.

A reducer applies these payloads as patches. It does not look up a price,
a yield, or an admission rank.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core.models import Account, ChoiceRecord, FoodLot, FoodMovement, JournalEntry, Reservation
from sim.core.version import EVENT_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class AccountsSet:
    accounts: tuple[Account, ...]
    kind: str = "accounts_set"


@dataclass(frozen=True, slots=True)
class LotsSet:
    remove_ids: tuple[str, ...]
    lots: tuple[FoodLot, ...]
    kind: str = "lots_set"


@dataclass(frozen=True, slots=True)
class ReservationsSet:
    remove_ids: tuple[str, ...]
    reservations: tuple[Reservation, ...]
    kind: str = "reservations_set"


@dataclass(frozen=True, slots=True)
class JournalAppended:
    entries: tuple[JournalEntry, ...]
    kind: str = "journal_appended"


@dataclass(frozen=True, slots=True)
class MovementsAppended:
    movements: tuple[FoodMovement, ...]
    imported_grams: int
    added_grams: int
    consumed_grams: int
    loss_grams: int
    exported_grams: int
    kind: str = "movements_appended"


@dataclass(frozen=True, slots=True)
class ChoicesAppended:
    choices: tuple[ChoiceRecord, ...]
    kind: str = "choices_appended"


@dataclass(frozen=True, slots=True)
class CommandRecorded:
    command_id: str
    kind: str = "command_recorded"


DomainEvent = (
    AccountsSet
    | LotsSet
    | ReservationsSet
    | JournalAppended
    | MovementsAppended
    | ChoicesAppended
    | CommandRecorded
)


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    schema_version: int
    run_id: str
    event_id: str
    sequence: int
    second: int
    phase: int
    kind: str
    causes: tuple[str, ...]
    command_id: str
    payload: DomainEvent


def event_schema_version() -> int:
    return EVENT_SCHEMA_VERSION
