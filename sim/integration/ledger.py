"""Ports backed by one kernel. Test doubles are never authoritative here.

Adapters submit commands; only core changes WorldState. The atomic context
discards every candidate event when a multi-command mechanism fails.
"""
from contextlib import contextmanager

from sim.core import (
    PHASE_SETTLE, DisposeLot, IntroduceLot, LotOutput, MoveLot, OpenAccount,
    RecognizeNonMassLoss, ReleaseReservation, ReserveResources, SplitLot,
    TransferCash, TransformLot, account_by_id, apply_command, empty_state,
    invariant_problems, load_catalog, lot_by_id, spendable_cents,
)
from sim.policies.core_interface.ledger import Conservation, JournalEntry, LedgerError, LotView, WasteRecord
from sim.logistics.core_interface.protocol import CashPosting, CoreRejection, LotSnapshot, ReservationGrant


class KernelLedger:
    def __init__(self, run_id="integrated", *, catalog=None):
        self.catalog = catalog or load_catalog()
        self.state = empty_state(run_id=run_id, scenario_id="integrated-illustrative",
            catalog_id=self.catalog.catalog_id, catalog_sha256=self.catalog.sha256,
            known_product_ids=tuple(p.product_id for p in self.catalog.products))
        self.events = []
        self.now = 0
        self._serial = 0
        self._opening_grams = 0

    def _id(self, prefix="op"):
        self._serial += 1
        return f"{prefix}-{self._serial}"

    def _apply(self, command):
        transition = apply_command(self.state, command)
        if transition.status != "accepted":
            raise LedgerError(f"{command.command_id}: {transition.reason}: {transition.detail}")
        self.state = transition.state
        self.events.extend(transition.events)
        return transition

    def at(self, second):
        if type(second) is not int or second < self.state.second:
            raise LedgerError("integration clock cannot move backwards")
        self.now = second

    @contextmanager
    def atomic(self):
        saved = (self.state, len(self.events), self._serial, self._opening_grams, self.now)
        try:
            yield self
            problems = invariant_problems(self.state)
            if problems:
                raise LedgerError("; ".join(problems))
        except Exception:
            self.state, length, self._serial, self._opening_grams, self.now = saved
            del self.events[length:]
            raise

    def policy(self, function, command):
        with self.atomic():
            self.at(command.now)
            return function(self, command)

    def ensure_account(self, account, kind="external"):
        if account_by_id(self.state, account) is None:
            self._apply(OpenAccount(self._id("open"), self.now, PHASE_SETTLE,
                account, account, kind, account == "external:opening"))

    def endow(self, account, cents, *, memo):
        if type(cents) is not int or cents < 0 or account == "external:opening":
            raise LedgerError("invalid opening endowment")
        self.ensure_account("external:opening")
        self.ensure_account(account)
        if cents:
            self._apply(TransferCash(self._id("endow"), self.now, PHASE_SETTLE,
                "external:opening", account, cents, memo))

    def cash(self, account):
        found = account_by_id(self.state, account)
        return found.settled_cents if found else 0

    def spendable(self, account):
        found = account_by_id(self.state, account)
        return spendable_cents(found) if found else 0

    def transfer(self, src, dst, cents, *, memo):
        if type(cents) is not int or cents < 0:
            raise LedgerError("invalid transfer cents")
        if cents:
            self.ensure_account(dst)
            self._apply(TransferCash(self._id("cash"), self.now, PHASE_SETTLE, src, dst, cents, memo))

    def reserve_cash(self, account, cents, *, key):
        command_id = self._id("cash-hold")
        self._apply(ReserveResources(command_id, self.now, PHASE_SETTLE, account, account, cents))
        return f"rsv.{command_id}"

    def release_cash(self, reservation_id):
        self._release(reservation_id)

    def _release(self, reservation_id):
        self._apply(ReleaseReservation(self._id("release"), self.now, PHASE_SETTLE, reservation_id))

    def _introduce(self, *, product_id, owner, custody, grams, acquisition_cents,
                   unsafe_after, source_kind, input_class, mass_kind="import"):
        self.ensure_account(owner)
        lot_id = self._id("lot")
        self._apply(IntroduceLot(self._id("introduce"), self.now, PHASE_SETTLE,
            lot_id, product_id, owner, custody, grams, acquisition_cents, unsafe_after,
            source_kind, input_class, mass_kind))
        return lot_id

    def open_lot(self, **kwargs):
        lot_id = self._introduce(**kwargs)
        self._opening_grams += kwargs["grams"]
        return lot_id

    def buy_lot(self, *, payer, payee, cents, memo, **kwargs):
        with self.atomic():
            self.transfer(payer, payee, cents, memo=memo)
            return self._introduce(acquisition_cents=cents, **kwargs)

    def add_material(self, **kwargs):
        return self._introduce(source_kind="added", mass_kind="added_material", **kwargs)

    def reserve_lot(self, lot_id, destination):
        lot = self.lot(lot_id)
        if self.reserved_grams(lot_id):
            raise LedgerError("lot already reserved")
        command_id = self._id("lot-hold")
        self._apply(ReserveResources(command_id, self.now, PHASE_SETTLE,
            destination, None, 0, lot_id, lot.grams))
        return f"rsv.{command_id}"

    def release_lot(self, reservation_id):
        self._release(reservation_id)

    def reserved_grams(self, lot_id):
        return self._lot(lot_id).reserved_grams

    def take(self, lot_id, grams):
        lot = self._lot(lot_id)
        if grams == lot.grams and not lot.reserved_grams and lot.journey_id is None:
            return lot_id
        child_id = self._id("split-lot")
        self._apply(SplitLot(self._id("split"), self.now, PHASE_SETTLE, lot_id, grams, child_id))
        return child_id

    def transfer_lot(self, lot_id, *, owner, custody):
        self.ensure_account(owner)
        self._apply(MoveLot(self._id("move"), self.now, PHASE_SETTLE, lot_id, owner, custody, None))

    def _dispose(self, lot_id, grams, disposition, reason):
        before = self._lot(lot_id).acquisition_cents
        self._apply(DisposeLot(self._id(disposition), self.now, PHASE_SETTLE, lot_id, grams, disposition, reason))
        remaining = lot_by_id(self.state, lot_id)
        return before - (remaining.acquisition_cents if remaining else 0)

    def consume(self, lot_id, grams, *, reason):
        return self._dispose(lot_id, grams, "consume", reason)

    def write_off(self, lot_id, grams, *, reason):
        return self._dispose(lot_id, grams, "waste", reason)

    def export_lot(self, lot_id, *, reason):
        return self._dispose(lot_id, self._lot(lot_id).grams, "export", reason)

    def replace_lot(self, lot_id, outputs):
        typed = []
        for output in outputs:
            if output.grams:
                self.ensure_account(output.owner)
            typed.append(LotOutput(self._id("output"), output.product_id, output.owner, output.custody,
                output.grams, output.acquisition_cents, output.unsafe_after,
                output.source_kind, output.input_class, output.disposition, output.reason))
        self._apply(TransformLot(self._id("transform"), self.now, PHASE_SETTLE, lot_id, tuple(typed)))
        return tuple(o.lot_id for o in typed if o.grams and o.disposition == "stock")

    def recognize_non_mass_loss(self, cents, *, reason):
        if cents:
            self._apply(RecognizeNonMassLoss(self._id("loss"), self.now, PHASE_SETTLE, cents, reason))

    def _lot(self, lot_id):
        lot = lot_by_id(self.state, lot_id)
        if lot is None:
            raise LedgerError(f"unknown lot {lot_id}")
        return lot

    def lot(self, lot_id):
        lot = self._lot(lot_id)
        return LotView(lot.lot_id, lot.product_id, lot.owner_id,
            lot.place_id or f"journey:{lot.journey_id}", lot.grams, lot.acquisition_cents,
            lot.unsafe_after if lot.unsafe_after is not None else 10**15,
            lot.source_kind, lot.input_class, lot.parents)

    def lots(self):
        return tuple(self.lot(lot.lot_id) for lot in self.state.lots if lot.journey_id is None)

    def journal(self):
        rows = []
        for entry in self.state.journal:
            debit = next(line for line in entry.lines if line.cents < 0)
            credit = next(line for line in entry.lines if line.cents > 0)
            rows.append(JournalEntry(debit.account_id, credit.account_id, credit.cents, debit.memo))
        return tuple(rows)

    def waste_records(self):
        known = {lot.lot_id: lot for event in self.events for lot in getattr(event.payload, "lots", ())}
        return tuple(WasteRecord(m.grams, m.acquisition_cents_recognized, m.kind, m.product_id,
            known[m.from_lot_id].input_class, m.parent_lot_ids)
            for m in self.state.movements if m.kind in {"waste", "process_loss"})

    def conservation(self):
        state = self.state
        return Conservation({a.account_id: a.settled_cents for a in state.accounts},
            sum(a.settled_cents for a in state.accounts), self._opening_grams,
            state.imported_grams - self._opening_grams, state.added_grams,
            sum(l.grams for l in state.lots), state.consumed_grams, state.loss_grams,
            state.exported_grams,
            sum(m.acquisition_cents_recognized for m in state.movements if m.kind in {"waste", "process_loss"}),
            sum(m.acquisition_cents_recognized for m in state.movements if m.kind == "consume"),
            state.non_mass_loss_cents)


class KernelLogisticsPort:
    def __init__(self, ledger):
        self.ledger = ledger
        self.storage = {p.product_id: ("chilled" if p.storage_class == "refrigerated" else p.storage_class)
                        for p in ledger.catalog.products}

    def lot(self, lot_id):
        lot = self.ledger._lot(lot_id)
        holders = [r.holder_id for r in self.ledger.state.reservations if r.lot_id == lot_id]
        return LotSnapshot(lot.lot_id, lot.product_id, lot.owner_id,
            "journey" if lot.journey_id else "place", lot.place_id, lot.journey_id,
            lot.grams, self.storage[lot.product_id],
            lot.unsafe_after if lot.unsafe_after is not None else 10**15,
            holders[0] if holders else None)

    def reserve(self, lot_id, holder_id, second):
        self.ledger.at(second)
        reservation_id = self.ledger.reserve_lot(lot_id, holder_id)
        return ReservationGrant(reservation_id, lot_id, holder_id, second)

    def release(self, reservation_id, second):
        self.ledger.at(second)
        self.ledger.release_lot(reservation_id)

    def move_custody(self, lot_id, *, holder_id, place_id, journey_id, second):
        self.ledger.at(second)
        lot = self.ledger._lot(lot_id)
        self.ledger._apply(MoveLot(self.ledger._id("custody"), second, PHASE_SETTLE,
            lot_id, lot.owner_id, place_id, journey_id, holder_id))

    def transfer_ownership(self, lot_id, new_owner_id, holder_id, second):
        self.ledger.at(second)
        self.ledger.ensure_account(new_owner_id)
        lot = self.ledger._lot(lot_id)
        self.ledger._apply(MoveLot(self.ledger._id("handoff"), second, PHASE_SETTLE,
            lot_id, new_owner_id, lot.place_id, lot.journey_id, holder_id))

    def post(self, posting_id, debit_account, credit_account, cents, reason, second):
        self.ledger.at(second)
        self.ledger.ensure_account(credit_account)
        transition = apply_command(self.ledger.state, TransferCash(posting_id, second, PHASE_SETTLE,
            debit_account, credit_account, cents, reason))
        if transition.status != "accepted":
            raise CoreRejection(f"posting refused: {transition.reason}")
        self.ledger.state = transition.state
        self.ledger.events.extend(transition.events)
        return CashPosting(posting_id, debit_account, credit_account, cents, reason, second)
