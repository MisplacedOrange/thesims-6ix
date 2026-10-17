"""In-memory ``CorePort`` used until ``sim.core`` is wired in.

The double enforces the contract logistics depends on: one reservation per
lot, custody in exactly one place or journey, unchanged grams, and balanced
postings. It is intentionally small. It does not implement journals, prices,
or replay.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sim.logistics.core_interface.protocol import (
    CashPosting,
    CoreRejection,
    LotSnapshot,
    ReservationGrant,
)
from sim.logistics.units import require_int, require_nonnegative, require_positive


@dataclass
class MemoryCore:
    lots: dict[str, LotSnapshot]
    reservations: dict[str, ReservationGrant]
    postings: list[CashPosting]
    accounts: dict[str, int]

    def __init__(self, lots: tuple[LotSnapshot, ...] | list[LotSnapshot]) -> None:
        self.lots = {}
        self.reservations = {}
        self.postings = []
        self.accounts = {}
        for lot in lots:
            self._validate_lot(lot)
            if lot.lot_id in self.lots:
                raise CoreRejection(f"duplicate lot {lot.lot_id}")
            self.lots[lot.lot_id] = lot

    def lot(self, lot_id: str) -> LotSnapshot:
        try:
            return self.lots[lot_id]
        except KeyError as exc:
            raise KeyError(lot_id) from exc

    def reserve(self, lot_id: str, holder_id: str, second: int) -> ReservationGrant:
        require_nonnegative("second", second)
        if not holder_id:
            raise CoreRejection("reservation holder is required")
        lot = self.lot(lot_id)
        if lot.reserved_by is not None:
            raise CoreRejection(f"{lot_id} is already reserved by {lot.reserved_by}")
        reservation_id = f"res-{holder_id}-{lot_id}"
        if reservation_id in self.reservations:
            raise CoreRejection(f"duplicate reservation {reservation_id}")
        self.lots[lot_id] = replace(lot, reserved_by=holder_id)
        grant = ReservationGrant(reservation_id, lot_id, holder_id, second)
        self.reservations[reservation_id] = grant
        return grant

    def release(self, reservation_id: str, second: int) -> None:
        require_nonnegative("second", second)
        try:
            grant = self.reservations.pop(reservation_id)
        except KeyError as exc:
            raise CoreRejection(f"unknown reservation {reservation_id}") from exc
        lot = self.lot(grant.lot_id)
        if lot.reserved_by != grant.holder_id:
            raise CoreRejection("reservation holder does not match the lot")
        self.lots[grant.lot_id] = replace(lot, reserved_by=None)

    def move_custody(
        self,
        lot_id: str,
        *,
        holder_id: str,
        place_id: str | None,
        journey_id: str | None,
        second: int,
    ) -> None:
        require_nonnegative("second", second)
        lot = self._held(lot_id, holder_id)
        if (place_id is None) == (journey_id is None):
            raise CoreRejection("custody must be exactly one of place or journey")
        if place_id is not None and not place_id:
            raise CoreRejection("place_id cannot be empty")
        if journey_id is not None and not journey_id:
            raise CoreRejection("journey_id cannot be empty")
        if place_id is not None:
            self.lots[lot_id] = replace(lot, custody="place", place_id=place_id, journey_id=None)
        else:
            self.lots[lot_id] = replace(lot, custody="journey", place_id=None, journey_id=journey_id)

    def transfer_ownership(self, lot_id: str, new_owner_id: str, holder_id: str, second: int) -> None:
        require_nonnegative("second", second)
        if not new_owner_id:
            raise CoreRejection("new owner is required")
        lot = self._held(lot_id, holder_id)
        self.lots[lot_id] = replace(lot, owner_id=new_owner_id)

    def post(
        self,
        posting_id: str,
        debit_account: str,
        credit_account: str,
        cents: int,
        reason: str,
        second: int,
    ) -> CashPosting:
        require_nonnegative("second", second)
        amount = require_positive("cents", cents)
        if not posting_id or not debit_account or not credit_account:
            raise CoreRejection("posting id and both accounts are required")
        if debit_account == credit_account:
            raise CoreRejection("a posting needs two accounts")
        if any(item.posting_id == posting_id for item in self.postings):
            raise CoreRejection(f"duplicate posting {posting_id}")
        posting = CashPosting(posting_id, debit_account, credit_account, amount, reason, second)
        self.accounts[debit_account] = self.accounts.get(debit_account, 0) - amount
        self.accounts[credit_account] = self.accounts.get(credit_account, 0) + amount
        self.postings.append(posting)
        return posting

    def balance_cents(self) -> int:
        """Sum of account balances. A balanced book stays at zero."""

        return sum(self.accounts.values())

    def _held(self, lot_id: str, holder_id: str) -> LotSnapshot:
        lot = self.lot(lot_id)
        if lot.reserved_by != holder_id:
            raise CoreRejection(f"{lot_id} is not reserved by {holder_id}")
        return lot

    @staticmethod
    def _validate_lot(lot: LotSnapshot) -> None:
        require_nonnegative("grams", lot.grams)
        require_int("unsafe_after_second", lot.unsafe_after_second)
        if lot.custody not in {"place", "journey"}:
            raise CoreRejection("custody must be place or journey")
        if lot.custody == "place" and (not lot.place_id or lot.journey_id is not None):
            raise CoreRejection("a lot at a place has a place and no journey")
        if lot.custody == "journey" and (not lot.journey_id or lot.place_id is not None):
            raise CoreRejection("a lot in a journey has a journey and no place")
