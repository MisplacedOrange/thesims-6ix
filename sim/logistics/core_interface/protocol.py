"""Thin port that ``sim.core`` is expected to implement.

Logistics never edits cash balances or gram quantities. It asks the core to
reserve a lot, move custody between a place and a journey, transfer ownership
when a recipient actually receives food, and post one balanced cash pair for
operating cost. The in-memory adapter in this package is a contract double
for tests. It is not the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class CoreRejection(ValueError):
    """The core refused a logistics request because it would break the ledger."""


@dataclass(frozen=True)
class LotSnapshot:
    lot_id: str
    product_id: str
    owner_id: str
    custody: str
    place_id: str | None
    journey_id: str | None
    grams: int
    storage_class: str
    unsafe_after_second: int
    reserved_by: str | None


@dataclass(frozen=True)
class ReservationGrant:
    reservation_id: str
    lot_id: str
    holder_id: str
    second: int


@dataclass(frozen=True)
class CashPosting:
    posting_id: str
    debit_account: str
    credit_account: str
    cents: int
    reason: str
    second: int


@runtime_checkable
class CorePort(Protocol):
    """Operations the kernel's accounting owner must provide.

    ``move_custody`` takes exactly one of ``place_id`` or ``journey_id``.
    ``post`` is one balanced pair: ``cents`` leaves ``debit_account`` and
    enters ``credit_account``. Duplicate reservation and posting ids are
    rejected so a retried command cannot settle twice.
    """

    def lot(self, lot_id: str) -> LotSnapshot:
        """Return the current lot. Missing ids raise ``KeyError``."""

    def reserve(self, lot_id: str, holder_id: str, second: int) -> ReservationGrant:
        """Hold the lot for a single holder. A second holder is rejected."""

    def release(self, reservation_id: str, second: int) -> None:
        """Release a reservation exactly once."""

    def move_custody(
        self,
        lot_id: str,
        *,
        holder_id: str,
        place_id: str | None,
        journey_id: str | None,
        second: int,
    ) -> None:
        """Change custody without changing grams or owner."""

    def transfer_ownership(self, lot_id: str, new_owner_id: str, holder_id: str, second: int) -> None:
        """Change owner. Grams stay on the lot. The holder must be the reservation."""

    def post(
        self,
        posting_id: str,
        debit_account: str,
        credit_account: str,
        cents: int,
        reason: str,
        second: int,
    ) -> CashPosting:
        """Post a balanced pair. ``cents`` is a positive integer."""
