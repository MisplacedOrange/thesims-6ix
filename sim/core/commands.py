"""Commands are the only way to propose an economic change.

A command is an intent. ``apply_command`` either rejects it or returns the
events that settle it. Callers outside ``sim.core`` should construct these
types and should not post balances themselves.
"""

from __future__ import annotations

from dataclasses import dataclass

PHASE_POLICY = 1
PHASE_EXPIRY = 2
PHASE_ARRIVAL = 3
PHASE_CHOICE = 4
PHASE_SETTLE = 5
PHASE_CONSUME = 6


@dataclass(frozen=True, slots=True)
class OpenAccount:
    command_id: str
    second: int
    phase: int
    account_id: str
    owner_id: str
    kind: str
    allows_credit: bool = False


@dataclass(frozen=True, slots=True)
class TransferCash:
    command_id: str
    second: int
    phase: int
    from_account_id: str
    to_account_id: str
    cents: int
    memo: str


@dataclass(frozen=True, slots=True)
class IntroduceLot:
    command_id: str
    second: int
    phase: int
    lot_id: str
    product_id: str
    owner_id: str
    place_id: str
    grams: int
    acquisition_cents: int
    unsafe_after: int | None


@dataclass(frozen=True, slots=True)
class ReserveResources:
    command_id: str
    second: int
    phase: int
    holder_id: str
    cash_account_id: str | None = None
    max_cents: int = 0
    lot_id: str | None = None
    grams: int = 0


@dataclass(frozen=True, slots=True)
class ReleaseReservation:
    command_id: str
    second: int
    phase: int
    reservation_id: str


@dataclass(frozen=True, slots=True)
class PurchaseLot:
    command_id: str
    second: int
    phase: int
    buyer_account_id: str
    seller_account_id: str
    destination_place_id: str
    lot_id: str
    grams: int
    cents: int
    reservation_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConsumeFood:
    command_id: str
    second: int
    phase: int
    actor_id: str
    lot_id: str
    grams: int


@dataclass(frozen=True, slots=True)
class TransferLot:
    command_id: str
    second: int
    phase: int
    lot_id: str
    grams: int
    new_owner_id: str
    new_place_id: str
    new_journey_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessBatch:
    command_id: str
    second: int
    phase: int
    processor_id: str
    lot_id: str
    input_grams: int
    output_product_id: str
    edible_grams: int
    loss_grams: int
    output_place_id: str
    unsafe_after: int | None
    added_grams: int = 0


@dataclass(frozen=True, slots=True)
class ApplyExpiry:
    command_id: str
    second: int
    phase: int


@dataclass(frozen=True, slots=True)
class RecordChoice:
    command_id: str
    second: int
    phase: int
    decision_id: str
    household_id: str
    option_id: str
    origin: str
    observation_hash: str
    revision: int
    explanation: str | None = None


Command = (
    OpenAccount
    | TransferCash
    | IntroduceLot
    | ReserveResources
    | ReleaseReservation
    | PurchaseLot
    | ConsumeFood
    | TransferLot
    | ProcessBatch
    | ApplyExpiry
    | RecordChoice
)
