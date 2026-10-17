"""In-memory core adapter.

Cash is integer cents. Food is integer grams. Every cash movement is a
transfer, including opening endowments, which come from ``external:opening``.
That source account is allowed to be negative so the full set of accounts
sums to zero. Other accounts have no credit line.

Acquisition cents travel with lots. Splits use floor division. A write-off
recognizes acquisition once and does not post a second cash expense. Disposal
fees, wages, rent, and supplier payments are ordinary transfers.

This adapter is intentionally small. It does not schedule time, persist
events, or deduplicate commands. The kernel owns those.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sim.policies.core_interface.allocate import partial_acquisition


class LedgerError(Exception):
    """A caller asked the ledger to break an accounting invariant."""


@dataclass(frozen=True)
class LotView:
    lot_id: str
    product_id: str
    owner: str
    custody: str
    grams: int
    acquisition_cents: int
    unsafe_after: int
    source_kind: str
    input_class: str
    parents: tuple[str, ...]


@dataclass(frozen=True)
class JournalEntry:
    from_account: str
    to_account: str
    cents: int
    memo: str


@dataclass(frozen=True)
class WasteRecord:
    grams: int
    acquisition_cents: int
    reason: str
    product_id: str
    input_class: str
    parents: tuple[str, ...]


@dataclass(frozen=True)
class Conservation:
    cents_by_account: dict[str, int]
    cents_sum: int
    grams_opening: int
    grams_imported: int
    grams_added: int
    grams_on_hand: int
    grams_consumed: int
    grams_waste: int
    grams_exported: int
    writeoff_acquisition_cents: int
    consumed_acquisition_cents: int
    non_mass_loss_cents: int

    @property
    def grams_balanced(self) -> bool:
        entered = self.grams_opening + self.grams_imported + self.grams_added
        left = self.grams_on_hand + self.grams_consumed + self.grams_waste + self.grams_exported
        return entered == left


@dataclass(frozen=True)
class OutputDraft:
    grams: int
    acquisition_cents: int
    product_id: str
    owner: str
    custody: str
    unsafe_after: int
    source_kind: str
    input_class: str
    disposition: str
    reason: str


@dataclass
class _Lot:
    lot_id: str
    product_id: str
    owner: str
    custody: str
    grams: int
    acquisition_cents: int
    unsafe_after: int
    source_kind: str
    input_class: str
    parents: tuple[str, ...]
    active: bool


@dataclass
class _Reservation:
    reservation_id: str
    lot_id: str
    grams: int
    destination: str
    active: bool


@dataclass
class _CashHold:
    reservation_id: str
    account: str
    cents: int
    key: str
    active: bool


class CoreLedger(Protocol):
    """Operations policies require from ``sim.core``.

    Names here are the seam. The authoritative core can use different internal
    names as long as an adapter preserves these results and invariants.
    """

    def endow(self, account: str, cents: int, *, memo: str) -> None: ...

    def cash(self, account: str) -> int: ...

    def spendable(self, account: str) -> int: ...

    def transfer(self, src: str, dst: str, cents: int, *, memo: str) -> None: ...

    def reserve_cash(self, account: str, cents: int, *, key: str) -> str: ...

    def release_cash(self, reservation_id: str) -> None: ...

    def open_lot(
        self,
        *,
        product_id: str,
        owner: str,
        custody: str,
        grams: int,
        acquisition_cents: int,
        unsafe_after: int,
        source_kind: str,
        input_class: str,
    ) -> str: ...

    def buy_lot(
        self,
        *,
        payer: str,
        payee: str,
        product_id: str,
        owner: str,
        custody: str,
        grams: int,
        cents: int,
        unsafe_after: int,
        source_kind: str,
        input_class: str,
        memo: str,
    ) -> str: ...

    def add_material(
        self,
        *,
        product_id: str,
        owner: str,
        custody: str,
        grams: int,
        acquisition_cents: int,
        unsafe_after: int,
        input_class: str,
    ) -> str: ...

    def reserve_lot(self, lot_id: str, destination: str) -> str: ...

    def release_lot(self, reservation_id: str) -> None: ...

    def reserved_grams(self, lot_id: str) -> int: ...

    def take(self, lot_id: str, grams: int) -> str: ...

    def transfer_lot(self, lot_id: str, *, owner: str, custody: str) -> None: ...

    def consume(self, lot_id: str, grams: int, *, reason: str) -> int: ...

    def write_off(self, lot_id: str, grams: int, *, reason: str) -> int: ...

    def export_lot(self, lot_id: str, *, reason: str) -> int: ...

    def replace_lot(self, lot_id: str, outputs: tuple[OutputDraft, ...]) -> tuple[str, ...]: ...

    def recognize_non_mass_loss(self, cents: int, *, reason: str) -> None: ...

    def lots(self) -> tuple[LotView, ...]: ...

    def lot(self, lot_id: str) -> LotView: ...

    def waste_records(self) -> tuple[WasteRecord, ...]: ...

    def journal(self) -> tuple[JournalEntry, ...]: ...

    def conservation(self) -> Conservation: ...


class InMemoryCore:
    """Reference adapter used until ``sim.core`` is wired in."""

    _OPENING = "external:opening"

    def __init__(self) -> None:
        self._balances: dict[str, int] = {self._OPENING: 0}
        self._lots: dict[str, _Lot] = {}
        self._lot_seq = 0
        self._reservation_seq = 0
        self._lot_reservations: dict[str, _Reservation] = {}
        self._cash_reservations: dict[str, _CashHold] = {}
        self._journal: list[JournalEntry] = []
        self._waste: list[WasteRecord] = []
        self._grams_opening = 0
        self._grams_imported = 0
        self._grams_added = 0
        self._grams_consumed = 0
        self._grams_waste = 0
        self._grams_exported = 0
        self._writeoff_cents = 0
        self._consumed_cents = 0
        self._non_mass_loss = 0

    def endow(self, account: str, cents: int, *, memo: str) -> None:
        if cents < 0:
            raise LedgerError("endowment cannot be negative")
        if account == self._OPENING:
            raise LedgerError("opening source is reserved")
        self._balances.setdefault(account, 0)
        if cents == 0:
            return
        self._balances[self._OPENING] -= cents
        self._balances[account] += cents
        self._journal.append(JournalEntry(self._OPENING, account, cents, memo))

    def cash(self, account: str) -> int:
        return self._balances.get(account, 0)

    def spendable(self, account: str) -> int:
        held = sum(
            item.cents
            for item in self._cash_reservations.values()
            if item.active and item.account == account
        )
        return self.cash(account) - held

    def transfer(self, src: str, dst: str, cents: int, *, memo: str) -> None:
        if cents < 0:
            raise LedgerError("transfer cents cannot be negative")
        if cents == 0:
            return
        if src == dst:
            raise LedgerError("transfer requires two accounts")
        if src == self._OPENING:
            raise LedgerError("endow opening balances; do not transfer them")
        if self.spendable(src) < cents:
            raise LedgerError(f"{src} cannot spend {cents}")
        self._balances.setdefault(dst, 0)
        self._balances[src] -= cents
        self._balances[dst] += cents
        self._journal.append(JournalEntry(src, dst, cents, memo))

    def reserve_cash(self, account: str, cents: int, *, key: str) -> str:
        if cents <= 0:
            raise LedgerError("cash reservation must be positive")
        if self.spendable(account) < cents:
            raise LedgerError(f"{account} cannot reserve {cents}")
        self._reservation_seq += 1
        reservation_id = f"cash-{self._reservation_seq:04d}"
        self._cash_reservations[reservation_id] = _CashHold(
            reservation_id, account, cents, key, True
        )
        return reservation_id

    def release_cash(self, reservation_id: str) -> None:
        hold = self._cash_reservations.get(reservation_id)
        if hold is None or not hold.active:
            raise LedgerError("cash reservation is not active")
        hold.active = False

    def open_lot(
        self,
        *,
        product_id: str,
        owner: str,
        custody: str,
        grams: int,
        acquisition_cents: int,
        unsafe_after: int,
        source_kind: str,
        input_class: str,
    ) -> str:
        return self._mint(
            product_id=product_id,
            owner=owner,
            custody=custody,
            grams=grams,
            acquisition_cents=acquisition_cents,
            unsafe_after=unsafe_after,
            source_kind=source_kind,
            input_class=input_class,
            parents=(),
            bucket="opening",
        )

    def buy_lot(
        self,
        *,
        payer: str,
        payee: str,
        product_id: str,
        owner: str,
        custody: str,
        grams: int,
        cents: int,
        unsafe_after: int,
        source_kind: str,
        input_class: str,
        memo: str,
    ) -> str:
        if grams <= 0:
            raise LedgerError("purchase requires grams")
        if cents < 0:
            raise LedgerError("purchase cents cannot be negative")
        self.transfer(payer, payee, cents, memo=memo)
        return self._mint(
            product_id=product_id,
            owner=owner,
            custody=custody,
            grams=grams,
            acquisition_cents=cents,
            unsafe_after=unsafe_after,
            source_kind=source_kind,
            input_class=input_class,
            parents=(),
            bucket="import",
        )

    def add_material(
        self,
        *,
        product_id: str,
        owner: str,
        custody: str,
        grams: int,
        acquisition_cents: int,
        unsafe_after: int,
        input_class: str,
    ) -> str:
        return self._mint(
            product_id=product_id,
            owner=owner,
            custody=custody,
            grams=grams,
            acquisition_cents=acquisition_cents,
            unsafe_after=unsafe_after,
            source_kind="added",
            input_class=input_class,
            parents=(),
            bucket="added",
        )

    def reserve_lot(self, lot_id: str, destination: str) -> str:
        lot = self._active(lot_id)
        if self.reserved_grams(lot_id) > 0:
            raise LedgerError("lot already reserved")
        self._reservation_seq += 1
        reservation_id = f"lot-{self._reservation_seq:04d}"
        self._lot_reservations[reservation_id] = _Reservation(
            reservation_id, lot.lot_id, lot.grams, destination, True
        )
        return reservation_id

    def release_lot(self, reservation_id: str) -> None:
        reservation = self._lot_reservations.get(reservation_id)
        if reservation is None or not reservation.active:
            raise LedgerError("lot reservation is not active")
        reservation.active = False

    def reserved_grams(self, lot_id: str) -> int:
        return sum(
            item.grams
            for item in self._lot_reservations.values()
            if item.active and item.lot_id == lot_id
        )

    def take(self, lot_id: str, grams: int) -> str:
        lot = self._active(lot_id)
        if grams <= 0 or grams > lot.grams:
            raise LedgerError("take exceeds the lot")
        if self.reserved_grams(lot_id) > 0:
            raise LedgerError("reserved lot cannot be taken")
        if grams == lot.grams:
            return lot_id
        moved = partial_acquisition(lot.acquisition_cents, lot.grams, grams)
        lot.grams -= grams
        lot.acquisition_cents -= moved
        return self._mint(
            product_id=lot.product_id,
            owner=lot.owner,
            custody=lot.custody,
            grams=grams,
            acquisition_cents=moved,
            unsafe_after=lot.unsafe_after,
            source_kind=lot.source_kind,
            input_class=lot.input_class,
            parents=(lot.lot_id,),
            bucket=None,
        )

    def transfer_lot(self, lot_id: str, *, owner: str, custody: str) -> None:
        lot = self._active(lot_id)
        if self.reserved_grams(lot_id) > 0:
            raise LedgerError("release the reservation before transfer")
        lot.owner = owner
        lot.custody = custody

    def consume(self, lot_id: str, grams: int, *, reason: str) -> int:
        return self._remove(lot_id, grams, "consumed", reason)

    def write_off(self, lot_id: str, grams: int, *, reason: str) -> int:
        return self._remove(lot_id, grams, "waste", reason)

    def export_lot(self, lot_id: str, *, reason: str) -> int:
        lot = self._active(lot_id)
        return self._remove(lot_id, lot.grams, "exported", reason)

    def replace_lot(self, lot_id: str, outputs: tuple[OutputDraft, ...]) -> tuple[str, ...]:
        lot = self._active(lot_id)
        if self.reserved_grams(lot_id) > 0:
            raise LedgerError("reserved lot cannot be transformed")
        grams = sum(item.grams for item in outputs)
        cents = sum(item.acquisition_cents for item in outputs)
        if grams != lot.grams or cents != lot.acquisition_cents:
            raise LedgerError("transform must conserve grams and acquisition cents")
        if any(item.grams < 0 or item.acquisition_cents < 0 for item in outputs):
            raise LedgerError("transform outputs cannot be negative")
        if any(item.grams == 0 and item.acquisition_cents != 0 for item in outputs):
            raise LedgerError("acquisition cents require grams")
        parents = (lot.lot_id,)
        self._retire(lot)
        created: list[str] = []
        for item in outputs:
            if item.grams == 0:
                continue
            if item.disposition == "waste":
                self._grams_waste += item.grams
                self._writeoff_cents += item.acquisition_cents
                self._waste.append(
                    WasteRecord(
                        item.grams,
                        item.acquisition_cents,
                        item.reason,
                        item.product_id,
                        item.input_class,
                        parents,
                    )
                )
            elif item.disposition == "stock":
                created.append(
                    self._mint(
                        product_id=item.product_id,
                        owner=item.owner,
                        custody=item.custody,
                        grams=item.grams,
                        acquisition_cents=item.acquisition_cents,
                        unsafe_after=item.unsafe_after,
                        source_kind=item.source_kind,
                        input_class=item.input_class,
                        parents=parents,
                        bucket=None,
                    )
                )
            else:
                raise LedgerError("unknown output disposition")
        return tuple(created)

    def recognize_non_mass_loss(self, cents: int, *, reason: str) -> None:
        if cents < 0:
            raise LedgerError("non-mass loss cannot be negative")
        if cents == 0:
            return
        if not reason:
            raise LedgerError("non-mass loss needs a reason")
        self._non_mass_loss += cents

    def lots(self) -> tuple[LotView, ...]:
        active = [self._view(lot) for lot in self._lots.values() if lot.active]
        active.sort(key=lambda lot: lot.lot_id)
        return tuple(active)

    def lot(self, lot_id: str) -> LotView:
        return self._view(self._active(lot_id))

    def waste_records(self) -> tuple[WasteRecord, ...]:
        return tuple(self._waste)

    def journal(self) -> tuple[JournalEntry, ...]:
        return tuple(self._journal)

    def conservation(self) -> Conservation:
        on_hand = sum(lot.grams for lot in self._lots.values() if lot.active)
        return Conservation(
            cents_by_account=dict(self._balances),
            cents_sum=sum(self._balances.values()),
            grams_opening=self._grams_opening,
            grams_imported=self._grams_imported,
            grams_added=self._grams_added,
            grams_on_hand=on_hand,
            grams_consumed=self._grams_consumed,
            grams_waste=self._grams_waste,
            grams_exported=self._grams_exported,
            writeoff_acquisition_cents=self._writeoff_cents,
            consumed_acquisition_cents=self._consumed_cents,
            non_mass_loss_cents=self._non_mass_loss,
        )

    def _mint(
        self,
        *,
        product_id: str,
        owner: str,
        custody: str,
        grams: int,
        acquisition_cents: int,
        unsafe_after: int,
        source_kind: str,
        input_class: str,
        parents: tuple[str, ...],
        bucket: str | None,
    ) -> str:
        if grams <= 0 or acquisition_cents < 0:
            raise LedgerError("lot grams must be positive and acquisition nonnegative")
        self._lot_seq += 1
        lot_id = f"lot-{self._lot_seq:04d}"
        self._lots[lot_id] = _Lot(
            lot_id,
            product_id,
            owner,
            custody,
            grams,
            acquisition_cents,
            unsafe_after,
            source_kind,
            input_class,
            parents,
            True,
        )
        if bucket == "opening":
            self._grams_opening += grams
        elif bucket == "import":
            self._grams_imported += grams
        elif bucket == "added":
            self._grams_added += grams
        elif bucket is not None:
            raise LedgerError("unknown mass bucket")
        return lot_id

    def _active(self, lot_id: str) -> _Lot:
        lot = self._lots.get(lot_id)
        if lot is None or not lot.active:
            raise LedgerError(f"unknown lot {lot_id}")
        return lot

    def _view(self, lot: _Lot) -> LotView:
        return LotView(
            lot.lot_id,
            lot.product_id,
            lot.owner,
            lot.custody,
            lot.grams,
            lot.acquisition_cents,
            lot.unsafe_after,
            lot.source_kind,
            lot.input_class,
            lot.parents,
        )

    def _retire(self, lot: _Lot) -> None:
        lot.active = False
        lot.grams = 0
        lot.acquisition_cents = 0

    def _remove(self, lot_id: str, grams: int, bucket: str, reason: str) -> int:
        lot = self._active(lot_id)
        if grams <= 0 or grams > lot.grams:
            raise LedgerError("removal exceeds the lot")
        if self.reserved_grams(lot_id) > 0:
            raise LedgerError("reserved lot cannot be removed")
        if not reason:
            raise LedgerError("removal needs a reason")
        if grams == lot.grams:
            recognized = lot.acquisition_cents
            product_id = lot.product_id
            input_class = lot.input_class
            parents = (lot.lot_id,)
            self._retire(lot)
        else:
            recognized = partial_acquisition(lot.acquisition_cents, lot.grams, grams)
            product_id = lot.product_id
            input_class = lot.input_class
            parents = (lot.lot_id,)
            lot.grams -= grams
            lot.acquisition_cents -= recognized
        if bucket == "consumed":
            self._grams_consumed += grams
            self._consumed_cents += recognized
        elif bucket == "waste":
            self._grams_waste += grams
            self._writeoff_cents += recognized
            self._waste.append(
                WasteRecord(grams, recognized, reason, product_id, input_class, parents)
            )
        elif bucket == "exported":
            self._grams_exported += grams
        else:
            raise LedgerError("unknown removal bucket")
        return recognized
