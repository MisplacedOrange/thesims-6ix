"""Compile one command into settled patches, and check conservation.

The compiler is the only place that decides cents and grams. The reducer in
``kernel.py`` applies the patches it is given.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sim.core.commands import (
    PHASE_ARRIVAL,
    PHASE_CHOICE,
    PHASE_CONSUME,
    PHASE_EXPIRY,
    PHASE_POLICY,
    PHASE_SETTLE,
    ApplyExpiry,
    Command,
    ConsumeFood,
    IntroduceLot,
    OpenAccount,
    ProcessBatch,
    PurchaseLot,
    RecordChoice,
    ReleaseReservation,
    ReserveResources,
    TransferCash,
    TransferLot,
)
from sim.core.events import (
    AccountsSet,
    ChoicesAppended,
    JournalAppended,
    LotsSet,
    MovementsAppended,
    ReservationsSet,
)
from sim.core.models import (
    ACTOR_KINDS,
    Account,
    ChoiceRecord,
    FoodLot,
    FoodMovement,
    JournalEntry,
    JournalLine,
    Reservation,
    WorldState,
)
from sim.core.reasons import (
    CREDIT_NOT_AUTHORIZED,
    CREDIT_NOT_RESERVABLE,
    DUPLICATE_ACCOUNT,
    DUPLICATE_LOT,
    DUPLICATE_OWNER,
    INSUFFICIENT_CASH,
    INSUFFICIENT_STOCK,
    INVALID_HASH,
    INVALID_ID,
    INVALID_KIND,
    INVALID_MEMO,
    INVALID_ORIGIN,
    MASS_NOT_CONSERVED,
    NON_INTEGER,
    NON_POSITIVE,
    NOT_OWNER,
    RESERVATION_CONFLICT,
    RESERVATION_EMPTY,
    RESERVATION_EXCEEDED,
    SAME_ACCOUNT,
    UNKNOWN_ACCOUNT,
    UNKNOWN_LOT,
    UNKNOWN_PRODUCT,
    UNKNOWN_RESERVATION,
    UNSAFE_LOT,
    WRONG_PHASE,
)
from sim.core.units import allocate_largest_remainder, require_int, valid_id, valid_sha256

_ORIGINS = frozenset({"rule", "llm", "recorded", "fallback"})
_LOSS_KINDS = frozenset({"process_loss", "waste"})


@dataclass(frozen=True, slots=True)
class Rejection:
    code: str
    detail: str


def account_by_id(state: WorldState, account_id: str) -> Account | None:
    for account in state.accounts:
        if account.account_id == account_id:
            return account
    return None


def account_for_owner(state: WorldState, owner_id: str) -> Account | None:
    matches = [account for account in state.accounts if account.owner_id == owner_id]
    if len(matches) != 1:
        return None
    return matches[0]


def lot_by_id(state: WorldState, lot_id: str) -> FoodLot | None:
    for lot in state.lots:
        if (lot.place_id is None) == (lot.journey_id is None):
            problems.append(f"lot custody must be exactly one place or journey: {lot.lot_id}")
        if lot.lot_id == lot_id:
            return lot
    return None


def lots_for_owner(state: WorldState, owner_id: str) -> tuple[FoodLot, ...]:
    return tuple(lot for lot in state.lots if lot.owner_id == owner_id)


def reservation_by_id(state: WorldState, reservation_id: str) -> Reservation | None:
    for reservation in state.reservations:
        if reservation.reservation_id == reservation_id:
            return reservation
    return None


def spendable_cents(account: Account) -> int:
    return account.settled_cents - account.reserved_cents


def available_grams(lot: FoodLot) -> int:
    return 0 if lot.journey_id is not None else lot.grams - lot.reserved_grams


def invariant_problems(state: WorldState) -> tuple[str, ...]:
    problems: list[str] = []
    account_ids = [account.account_id for account in state.accounts]
    if len(account_ids) != len(set(account_ids)):
        problems.append("duplicate account id")
    owner_ids = [account.owner_id for account in state.accounts]
    if len(owner_ids) != len(set(owner_ids)):
        problems.append("duplicate account owner")
    lot_ids = [lot.lot_id for lot in state.lots]
    if len(lot_ids) != len(set(lot_ids)):
        problems.append("duplicate lot id")
    reservation_ids = [reservation.reservation_id for reservation in state.reservations]
    if len(reservation_ids) != len(set(reservation_ids)):
        problems.append("duplicate reservation id")
    if len(state.applied_command_ids) != len(set(state.applied_command_ids)):
        problems.append("duplicate applied command id")
    if sum(account.settled_cents for account in state.accounts) != 0:
        problems.append("settled cents do not balance to zero")
    reserved_cash: dict[str, int] = {}
    reserved_grams: dict[str, int] = {}
    for reservation in state.reservations:
        if reservation.max_cents < 0 or reservation.grams < 0:
            problems.append(f"negative reservation {reservation.reservation_id}")
        if reservation.cash_account_id is not None:
            reserved_cash[reservation.cash_account_id] = (
                reserved_cash.get(reservation.cash_account_id, 0) + reservation.max_cents
            )
        if reservation.lot_id is not None:
            reserved_grams[reservation.lot_id] = reserved_grams.get(reservation.lot_id, 0) + reservation.grams
    for account in state.accounts:
        if account.reserved_cents < 0:
            problems.append(f"negative reserved cents on {account.account_id}")
        if reserved_cash.get(account.account_id, 0) != account.reserved_cents:
            problems.append(f"reserved cents diverge on {account.account_id}")
        if account.allows_credit:
            if account.kind != "external" or account.reserved_cents != 0:
                problems.append(f"credit account {account.account_id} is not a clean external contra")
        elif account.settled_cents < 0 or spendable_cents(account) < 0:
            problems.append(f"overspend on {account.account_id}")
    for lot in state.lots:
        if lot.grams < 0 or lot.reserved_grams < 0 or lot.reserved_grams > lot.grams:
            problems.append(f"invalid grams on {lot.lot_id}")
        if lot.acquisition_cents < 0:
            problems.append(f"negative acquisition on {lot.lot_id}")
        if reserved_grams.get(lot.lot_id, 0) != lot.reserved_grams:
            problems.append(f"reserved grams diverge on {lot.lot_id}")
        if lot.product_id not in state.known_product_ids:
            problems.append(f"unknown product on {lot.lot_id}")
    on_hand = sum(lot.grams for lot in state.lots)
    if state.imported_grams + state.added_grams != on_hand + state.consumed_grams + state.loss_grams + state.exported_grams:
        problems.append("food mass does not balance")
    if sum(movement.grams for movement in state.movements if movement.kind == "import") != state.imported_grams:
        problems.append("import counter diverges from movements")
    if sum(movement.grams for movement in state.movements if movement.kind == "added_material") != state.added_grams:
        problems.append("added counter diverges from movements")
    if sum(movement.grams for movement in state.movements if movement.kind == "consume") != state.consumed_grams:
        problems.append("consumed counter diverges from movements")
    if sum(movement.grams for movement in state.movements if movement.kind in _LOSS_KINDS) != state.loss_grams:
        problems.append("loss counter diverges from movements")
    if sum(movement.grams for movement in state.movements if movement.kind == "export") != state.exported_grams:
        problems.append("export counter diverges from movements")
    journal_totals: dict[str, int] = {}
    for entry in state.journal:
        if sum(line.cents for line in entry.lines) != 0:
            problems.append(f"unbalanced journal entry {entry.entry_id}")
        for line in entry.lines:
            journal_totals[line.account_id] = journal_totals.get(line.account_id, 0) + line.cents
    for account in state.accounts:
        if journal_totals.get(account.account_id, 0) != account.settled_cents:
            problems.append(f"settled cents diverge from the journal on {account.account_id}")
    introduced = sum(movement.acquisition_cents_introduced for movement in state.movements)
    recognized = sum(movement.acquisition_cents_recognized for movement in state.movements)
    remaining = sum(lot.acquisition_cents for lot in state.lots)
    if introduced != recognized + remaining:
        problems.append("acquisition cents are not conserved")
    return tuple(problems)


def compile_command(state: WorldState, command: Command) -> tuple[object, ...] | Rejection:
    handler = _HANDLERS.get(type(command))
    if handler is None:
        from sim.core.operations import compile_operation
        return compile_operation(state, command)
    return handler(state, command)


def _phase(command: Command, allowed: frozenset[int]) -> Rejection | None:
    if command.phase not in allowed:
        return Rejection(WRONG_PHASE, f"phase {command.phase} is not allowed for {type(command).__name__}")
    return None


def _positive(value: object, field: str) -> tuple[int | None, Rejection | None]:
    try:
        number = require_int(value, field)
    except ValueError as exc:
        return None, Rejection(NON_INTEGER, str(exc))
    if number <= 0:
        return None, Rejection(NON_POSITIVE, field)
    return number, None


def _nonnegative(value: object, field: str) -> tuple[int | None, Rejection | None]:
    try:
        number = require_int(value, field)
    except ValueError as exc:
        return None, Rejection(NON_INTEGER, str(exc))
    if number < 0:
        return None, Rejection(NON_POSITIVE, field)
    return number, None


def _optional_second(value: object, field: str) -> tuple[int | None, Rejection | None]:
    if value is None:
        return None, None
    try:
        number = require_int(value, field)
    except ValueError as exc:
        return None, Rejection(NON_INTEGER, str(exc))
    if number < 0:
        return None, Rejection(NON_POSITIVE, field)
    return number, None


def _memo(memo: object) -> Rejection | None:
    if not isinstance(memo, str) or not memo or len(memo) > 80 or any(ord(char) < 32 for char in memo):
        return Rejection(INVALID_MEMO, "memo must be 1..80 visible characters")
    return None


def _require_id(value: object, field: str) -> Rejection | None:
    if not valid_id(value):
        return Rejection(INVALID_ID, field)
    return None


def _unsafe(lot: FoodLot, second: int) -> bool:
    return lot.unsafe_after is not None and lot.unsafe_after <= second


def _split_acquisition(total: int, take_grams: int, keep_grams: int) -> tuple[int, int]:
    if take_grams <= 0:
        return 0, total
    if keep_grams <= 0:
        return total, 0
    shares = allocate_largest_remainder(total, (("keep", keep_grams), ("take", take_grams)))
    return shares["take"], shares["keep"]


def _flows(state: WorldState, *, imported: int = 0, added: int = 0, consumed: int = 0, loss: int = 0, exported: int = 0) -> dict[str, int]:
    return {
        "imported_grams": state.imported_grams + imported,
        "added_grams": state.added_grams + added,
        "consumed_grams": state.consumed_grams + consumed,
        "loss_grams": state.loss_grams + loss,
        "exported_grams": state.exported_grams + exported,
    }


def _sort_accounts(accounts: tuple[Account, ...]) -> tuple[Account, ...]:
    return tuple(sorted(accounts, key=lambda account: account.account_id))


def _sort_lots(lots: tuple[FoodLot, ...]) -> tuple[FoodLot, ...]:
    return tuple(sorted(lots, key=lambda lot: lot.lot_id))


def _compile_open(state: WorldState, command: OpenAccount) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_POLICY, PHASE_SETTLE}))
    if rejected:
        return rejected
    for field in (command.account_id, command.owner_id):
        rejected = _require_id(field, "account identity")
        if rejected:
            return rejected
    if command.kind not in ACTOR_KINDS:
        return Rejection(INVALID_KIND, command.kind)
    if command.allows_credit and command.kind != "external":
        return Rejection(CREDIT_NOT_AUTHORIZED, "only the external contra account may allow credit")
    if not isinstance(command.allows_credit, bool):
        return Rejection(NON_INTEGER, "allows_credit must be a boolean")
    if account_by_id(state, command.account_id) is not None:
        return Rejection(DUPLICATE_ACCOUNT, command.account_id)
    if any(account.owner_id == command.owner_id for account in state.accounts):
        return Rejection(DUPLICATE_OWNER, command.owner_id)
    account = Account(
        account_id=command.account_id,
        owner_id=command.owner_id,
        kind=command.kind,
        settled_cents=0,
        reserved_cents=0,
        allows_credit=command.allows_credit,
    )
    return (AccountsSet(accounts=(account,)),)


def _compile_transfer(state: WorldState, command: TransferCash) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_POLICY, PHASE_SETTLE}))
    if rejected:
        return rejected
    rejected = _memo(command.memo)
    if rejected:
        return rejected
    cents, rejected = _positive(command.cents, "cents")
    if rejected or cents is None:
        return rejected or Rejection(NON_POSITIVE, "cents")
    source = account_by_id(state, command.from_account_id)
    target = account_by_id(state, command.to_account_id)
    if source is None or target is None:
        return Rejection(UNKNOWN_ACCOUNT, "transfer account")
    if source.account_id == target.account_id:
        return Rejection(SAME_ACCOUNT, source.account_id)
    if not source.allows_credit and spendable_cents(source) < cents:
        return Rejection(INSUFFICIENT_CASH, source.account_id)
    new_source = replace(source, settled_cents=source.settled_cents - cents)
    new_target = replace(target, settled_cents=target.settled_cents + cents)
    entry = JournalEntry(
        entry_id=command.command_id,
        command_id=command.command_id,
        sequence=0,
        second=command.second,
        lines=(
            JournalLine(source.account_id, -cents, command.memo),
            JournalLine(target.account_id, cents, command.memo),
        ),
    )
    return (
        AccountsSet(accounts=_sort_accounts((new_source, new_target))),
        JournalAppended(entries=(entry,)),
    )


def _compile_introduce(state: WorldState, command: IntroduceLot) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_POLICY, PHASE_SETTLE}))
    if rejected:
        return rejected
    for field in (command.lot_id, command.product_id, command.owner_id, command.place_id):
        rejected = _require_id(field, "lot identity")
        if rejected:
            return rejected
    grams, rejected = _positive(command.grams, "grams")
    if rejected or grams is None:
        return rejected or Rejection(NON_POSITIVE, "grams")
    acquisition, rejected = _nonnegative(command.acquisition_cents, "acquisition_cents")
    if rejected or acquisition is None:
        return rejected or Rejection(NON_INTEGER, "acquisition_cents")
    unsafe_after, rejected = _optional_second(command.unsafe_after, "unsafe_after")
    if rejected:
        return rejected
    if command.product_id not in state.known_product_ids:
        return Rejection(UNKNOWN_PRODUCT, command.product_id)
    if account_for_owner(state, command.owner_id) is None:
        return Rejection(UNKNOWN_ACCOUNT, command.owner_id)
    if lot_by_id(state, command.lot_id) is not None:
        return Rejection(DUPLICATE_LOT, command.lot_id)
    if command.mass_kind not in {"import", "added_material"}:
        return Rejection(INVALID_KIND, "mass_kind")
    if not valid_id(command.source_kind) or not valid_id(command.input_class):
        return Rejection(INVALID_ID, "food provenance")
    lot = FoodLot(
        lot_id=command.lot_id,
        product_id=command.product_id,
        owner_id=command.owner_id,
        place_id=command.place_id,
        journey_id=None,
        grams=grams,
        reserved_grams=0,
        unsafe_after=unsafe_after,
        parents=(),
        acquisition_cents=acquisition,
        source_kind=command.source_kind,
        input_class=command.input_class,
    )
    movement = FoodMovement(
        movement_id=f"{command.command_id}:import:0",
        command_id=command.command_id,
        sequence=0,
        kind=command.mass_kind,
        product_id=command.product_id,
        grams=grams,
        from_owner_id=None,
        to_owner_id=command.owner_id,
        from_lot_id=None,
        to_lot_id=command.lot_id,
        parent_lot_ids=(),
        acquisition_cents_recognized=0,
        acquisition_cents_introduced=acquisition,
    )
    return (
        LotsSet(remove_ids=(), lots=(lot,)),
        MovementsAppended(movements=(movement,), **_flows(
            state, imported=grams if command.mass_kind == "import" else 0,
            added=grams if command.mass_kind == "added_material" else 0)),
    )


def _compile_reserve(state: WorldState, command: ReserveResources) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_SETTLE}))
    if rejected:
        return rejected
    rejected = _require_id(command.holder_id, "holder_id")
    if rejected:
        return rejected
    max_cents, rejected = _nonnegative(command.max_cents, "max_cents")
    grams, rejected_grams = _nonnegative(command.grams, "grams")
    if rejected:
        return rejected
    if rejected_grams:
        return rejected_grams
    if max_cents is None or grams is None:
        return Rejection(NON_INTEGER, "reservation size")
    has_cash = command.cash_account_id is not None
    has_lot = command.lot_id is not None
    if has_cash != (max_cents > 0) or has_lot != (grams > 0) or (not has_cash and not has_lot):
        return Rejection(RESERVATION_EMPTY, "declare cash, stock, or both, with a positive size")
    if has_cash and account_for_owner(state, command.holder_id) is None:
        return Rejection(UNKNOWN_ACCOUNT, command.holder_id)
    payloads: list[object] = []
    accounts: list[Account] = []
    lots: list[FoodLot] = []
    if has_cash:
        rejected = _require_id(command.cash_account_id, "cash_account_id")
        if rejected:
            return rejected
        account = account_by_id(state, command.cash_account_id or "")
        if account is None:
            return Rejection(UNKNOWN_ACCOUNT, command.cash_account_id or "")
        if account.owner_id != command.holder_id:
            return Rejection(RESERVATION_CONFLICT, "cash account owner")
        if account.allows_credit:
            return Rejection(CREDIT_NOT_RESERVABLE, account.account_id)
        if spendable_cents(account) < max_cents:
            return Rejection(INSUFFICIENT_CASH, account.account_id)
        accounts.append(replace(account, reserved_cents=account.reserved_cents + max_cents))
    if has_lot:
        rejected = _require_id(command.lot_id, "lot_id")
        if rejected:
            return rejected
        lot = lot_by_id(state, command.lot_id or "")
        if lot is None:
            return Rejection(UNKNOWN_LOT, command.lot_id or "")
        if _unsafe(lot, command.second):
            return Rejection(UNSAFE_LOT, lot.lot_id)
        if available_grams(lot) < grams:
            return Rejection(INSUFFICIENT_STOCK, lot.lot_id)
        lots.append(replace(lot, reserved_grams=lot.reserved_grams + grams))
    reservation_id = f"rsv.{command.command_id}"
    if not valid_id(reservation_id) or reservation_by_id(state, reservation_id) is not None:
        return Rejection(INVALID_ID, reservation_id)
    if accounts:
        payloads.append(AccountsSet(accounts=_sort_accounts(tuple(accounts))))
    if lots:
        payloads.append(LotsSet(remove_ids=(), lots=_sort_lots(tuple(lots))))
    payloads.append(
        ReservationsSet(
            remove_ids=(),
            reservations=(
                Reservation(
                    reservation_id=reservation_id,
                    holder_id=command.holder_id,
                    cash_account_id=command.cash_account_id,
                    max_cents=max_cents,
                    lot_id=command.lot_id,
                    grams=grams,
                    second=command.second,
                    command_id=command.command_id,
                ),
            ),
        )
    )
    return tuple(payloads)


def _compile_release(state: WorldState, command: ReleaseReservation) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_SETTLE}))
    if rejected:
        return rejected
    rejected = _require_id(command.reservation_id, "reservation_id")
    if rejected:
        return rejected
    reservation = reservation_by_id(state, command.reservation_id)
    if reservation is None:
        return Rejection(UNKNOWN_RESERVATION, command.reservation_id)
    payloads: list[object] = []
    if reservation.cash_account_id is not None:
        account = account_by_id(state, reservation.cash_account_id)
        if account is None:
            return Rejection(UNKNOWN_ACCOUNT, reservation.cash_account_id)
        payloads.append(
            AccountsSet(accounts=(replace(account, reserved_cents=account.reserved_cents - reservation.max_cents),))
        )
    if reservation.lot_id is not None:
        lot = lot_by_id(state, reservation.lot_id)
        if lot is None:
            return Rejection(UNKNOWN_LOT, reservation.lot_id)
        payloads.append(
            LotsSet(
                remove_ids=(),
                lots=(replace(lot, reserved_grams=lot.reserved_grams - reservation.grams),),
            )
        )
    payloads.append(ReservationsSet(remove_ids=(reservation.reservation_id,), reservations=()))
    return tuple(payloads)


def _moved_lot(
    source: FoodLot,
    *,
    command_id: str,
    grams: int,
    owner_id: str,
    place_id: str,
    journey_id: str | None,
    acquisition_cents: int,
) -> tuple[str, FoodLot]:
    child_id = f"{source.lot_id}.{command_id}"
    child = FoodLot(
        lot_id=child_id,
        product_id=source.product_id,
        owner_id=owner_id,
        place_id=None if journey_id is not None else place_id,
        journey_id=journey_id,
        grams=grams,
        reserved_grams=0,
        unsafe_after=source.unsafe_after,
        parents=(source.lot_id,),
        acquisition_cents=acquisition_cents,
        source_kind=source.source_kind,
        input_class=source.input_class,
    )
    return child_id, child


def _compile_purchase(state: WorldState, command: PurchaseLot) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_SETTLE}))
    if rejected:
        return rejected
    for field in (command.buyer_account_id, command.seller_account_id, command.destination_place_id, command.lot_id):
        rejected = _require_id(field, "purchase identity")
        if rejected:
            return rejected
    grams, rejected = _positive(command.grams, "grams")
    cents, rejected_cents = _positive(command.cents, "cents")
    if rejected:
        return rejected
    if rejected_cents:
        return rejected_cents
    if grams is None or cents is None:
        return Rejection(NON_POSITIVE, "purchase size")
    buyer = account_by_id(state, command.buyer_account_id)
    seller = account_by_id(state, command.seller_account_id)
    lot = lot_by_id(state, command.lot_id)
    if buyer is None or seller is None:
        return Rejection(UNKNOWN_ACCOUNT, "purchase account")
    if lot is None:
        return Rejection(UNKNOWN_LOT, command.lot_id)
    if buyer.account_id == seller.account_id:
        return Rejection(SAME_ACCOUNT, buyer.account_id)
    if lot.owner_id != seller.owner_id:
        return Rejection(NOT_OWNER, lot.lot_id)
    if lot.journey_id is not None:
        return Rejection(INSUFFICIENT_STOCK, "lot is in transit")
    if _unsafe(lot, command.second):
        return Rejection(UNSAFE_LOT, lot.lot_id)
    reservation = None
    if command.reservation_id is not None:
        rejected = _require_id(command.reservation_id, "reservation_id")
        if rejected:
            return rejected
        reservation = reservation_by_id(state, command.reservation_id)
        if reservation is None:
            return Rejection(UNKNOWN_RESERVATION, command.reservation_id)
        if reservation.holder_id != buyer.owner_id or reservation.cash_account_id != buyer.account_id:
            return Rejection(RESERVATION_CONFLICT, "holder")
        if reservation.lot_id != lot.lot_id:
            return Rejection(RESERVATION_CONFLICT, "lot")
        if grams > reservation.grams or cents > reservation.max_cents:
            return Rejection(RESERVATION_EXCEEDED, reservation.reservation_id)
        free_grams = lot.grams - lot.reserved_grams + reservation.grams
        free_cash = spendable_cents(buyer) + reservation.max_cents
    else:
        free_grams = available_grams(lot)
        free_cash = spendable_cents(buyer)
    if grams > free_grams:
        return Rejection(INSUFFICIENT_STOCK, lot.lot_id)
    if not buyer.allows_credit and cents > free_cash:
        return Rejection(INSUFFICIENT_CASH, buyer.account_id)
    released_cents = reservation.max_cents if reservation is not None else 0
    released_grams = reservation.grams if reservation is not None else 0
    take_acq, keep_acq = _split_acquisition(lot.acquisition_cents, grams, lot.grams - grams)
    child_id, child = _moved_lot(
        lot,
        command_id=command.command_id,
        grams=grams,
        owner_id=buyer.owner_id,
        place_id=command.destination_place_id,
        journey_id=None,
        acquisition_cents=take_acq,
    )
    if not valid_id(child_id) or lot_by_id(state, child_id) is not None:
        return Rejection(INVALID_ID, child_id)
    remaining = lot.grams - grams
    reserved_after = lot.reserved_grams - released_grams
    remove_ids: tuple[str, ...] = ()
    written: list[FoodLot] = [child]
    if remaining == 0:
        if reserved_after != 0:
            return Rejection(INSUFFICIENT_STOCK, lot.lot_id)
        remove_ids = (lot.lot_id,)
    else:
        written.append(
            replace(lot, grams=remaining, reserved_grams=reserved_after, acquisition_cents=keep_acq)
        )
    new_buyer = replace(
        buyer,
        settled_cents=buyer.settled_cents - cents,
        reserved_cents=buyer.reserved_cents - released_cents,
    )
    new_seller = replace(seller, settled_cents=seller.settled_cents + cents)
    entry = JournalEntry(
        entry_id=command.command_id,
        command_id=command.command_id,
        sequence=0,
        second=command.second,
        lines=(
            JournalLine(buyer.account_id, -cents, f"purchase:{lot.product_id}:{grams}"),
            JournalLine(seller.account_id, cents, f"purchase:{lot.product_id}:{grams}"),
        ),
    )
    movement = FoodMovement(
        movement_id=f"{command.command_id}:transfer:0",
        command_id=command.command_id,
        sequence=0,
        kind="transfer",
        product_id=lot.product_id,
        grams=grams,
        from_owner_id=lot.owner_id,
        to_owner_id=buyer.owner_id,
        from_lot_id=lot.lot_id,
        to_lot_id=child_id,
        parent_lot_ids=(lot.lot_id,),
        acquisition_cents_recognized=0,
        acquisition_cents_introduced=0,
    )
    payloads: list[object] = []
    if reservation is not None:
        payloads.append(ReservationsSet(remove_ids=(reservation.reservation_id,), reservations=()))
    payloads.extend(
        (
            AccountsSet(accounts=_sort_accounts((new_buyer, new_seller))),
            LotsSet(remove_ids=remove_ids, lots=_sort_lots(tuple(written))),
            JournalAppended(entries=(entry,)),
            MovementsAppended(movements=(movement,), **_flows(state)),
        )
    )
    return tuple(payloads)


def _compile_consume(state: WorldState, command: ConsumeFood) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_CONSUME}))
    if rejected:
        return rejected
    rejected = _require_id(command.actor_id, "actor_id") or _require_id(command.lot_id, "lot_id")
    if rejected:
        return rejected
    grams, rejected = _positive(command.grams, "grams")
    if rejected or grams is None:
        return rejected or Rejection(NON_POSITIVE, "grams")
    lot = lot_by_id(state, command.lot_id)
    if lot is None:
        return Rejection(UNKNOWN_LOT, command.lot_id)
    if lot.owner_id != command.actor_id:
        return Rejection(NOT_OWNER, lot.lot_id)
    if _unsafe(lot, command.second):
        return Rejection(UNSAFE_LOT, lot.lot_id)
    if grams > available_grams(lot):
        return Rejection(INSUFFICIENT_STOCK, lot.lot_id)
    take_acq, keep_acq = _split_acquisition(lot.acquisition_cents, grams, lot.grams - grams)
    movement = FoodMovement(
        movement_id=f"{command.command_id}:consume:0",
        command_id=command.command_id,
        sequence=0,
        kind="consume",
        product_id=lot.product_id,
        grams=grams,
        from_owner_id=lot.owner_id,
        to_owner_id=None,
        from_lot_id=lot.lot_id,
        to_lot_id=None,
        parent_lot_ids=lot.parents,
        acquisition_cents_recognized=take_acq,
        acquisition_cents_introduced=0,
    )
    if grams == lot.grams:
        lots = LotsSet(remove_ids=(lot.lot_id,), lots=())
    else:
        lots = LotsSet(
            remove_ids=(),
            lots=(replace(lot, grams=lot.grams - grams, acquisition_cents=keep_acq),),
        )
    return (lots, MovementsAppended(movements=(movement,), **_flows(state, consumed=grams)))


def _compile_transfer_lot(state: WorldState, command: TransferLot) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_ARRIVAL, PHASE_SETTLE}))
    if rejected:
        return rejected
    for field in (command.lot_id, command.new_owner_id, command.new_place_id):
        rejected = _require_id(field, "transfer identity")
        if rejected:
            return rejected
    if command.new_journey_id is not None:
        rejected = _require_id(command.new_journey_id, "new_journey_id")
        if rejected:
            return rejected
    grams, rejected = _positive(command.grams, "grams")
    if rejected or grams is None:
        return rejected or Rejection(NON_POSITIVE, "grams")
    lot = lot_by_id(state, command.lot_id)
    if lot is None:
        return Rejection(UNKNOWN_LOT, command.lot_id)
    if account_for_owner(state, command.new_owner_id) is None:
        return Rejection(UNKNOWN_ACCOUNT, command.new_owner_id)
    if _unsafe(lot, command.second):
        return Rejection(UNSAFE_LOT, lot.lot_id)
    arriving = lot.journey_id is not None and command.phase == PHASE_ARRIVAL and command.new_journey_id is None
    transferable = lot.grams - lot.reserved_grams if arriving else available_grams(lot)
    if grams > transferable:
        return Rejection(INSUFFICIENT_STOCK, lot.lot_id)
    take_acq, keep_acq = _split_acquisition(lot.acquisition_cents, grams, lot.grams - grams)
    child_id, child = _moved_lot(
        lot,
        command_id=command.command_id,
        grams=grams,
        owner_id=command.new_owner_id,
        place_id=command.new_place_id,
        journey_id=command.new_journey_id,
        acquisition_cents=take_acq,
    )
    if not valid_id(child_id):
        return Rejection(INVALID_ID, child_id)
    if grams == lot.grams:
        lots = LotsSet(remove_ids=(lot.lot_id,), lots=(child,))
    else:
        lots = LotsSet(
            remove_ids=(),
            lots=_sort_lots((child, replace(lot, grams=lot.grams - grams, acquisition_cents=keep_acq))),
        )
    movement = FoodMovement(
        movement_id=f"{command.command_id}:transfer:0",
        command_id=command.command_id,
        sequence=0,
        kind="transfer",
        product_id=lot.product_id,
        grams=grams,
        from_owner_id=lot.owner_id,
        to_owner_id=command.new_owner_id,
        from_lot_id=lot.lot_id,
        to_lot_id=child_id,
        parent_lot_ids=(lot.lot_id,),
        acquisition_cents_recognized=0,
        acquisition_cents_introduced=0,
    )
    return (lots, MovementsAppended(movements=(movement,), **_flows(state)))


def _compile_process(state: WorldState, command: ProcessBatch) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_SETTLE}))
    if rejected:
        return rejected
    for field in (command.processor_id, command.lot_id, command.output_product_id, command.output_place_id):
        rejected = _require_id(field, "process identity")
        if rejected:
            return rejected
    input_grams, rejected = _positive(command.input_grams, "input_grams")
    if rejected or input_grams is None:
        return rejected or Rejection(NON_POSITIVE, "input_grams")
    edible, rejected = _nonnegative(command.edible_grams, "edible_grams")
    loss, rejected_loss = _nonnegative(command.loss_grams, "loss_grams")
    added, rejected_added = _nonnegative(command.added_grams, "added_grams")
    if rejected:
        return rejected
    if rejected_loss:
        return rejected_loss
    if rejected_added:
        return rejected_added
    if edible is None or loss is None or added is None:
        return Rejection(NON_INTEGER, "process mass")
    unsafe_after, rejected = _optional_second(command.unsafe_after, "unsafe_after")
    if rejected:
        return rejected
    if input_grams + added != edible + loss:
        return Rejection(MASS_NOT_CONSERVED, "input plus added material must equal edible output plus loss")
    if command.output_product_id not in state.known_product_ids:
        return Rejection(UNKNOWN_PRODUCT, command.output_product_id)
    lot = lot_by_id(state, command.lot_id)
    if lot is None:
        return Rejection(UNKNOWN_LOT, command.lot_id)
    if lot.owner_id != command.processor_id:
        return Rejection(NOT_OWNER, lot.lot_id)
    if _unsafe(lot, command.second):
        return Rejection(UNSAFE_LOT, lot.lot_id)
    if input_grams > available_grams(lot):
        return Rejection(INSUFFICIENT_STOCK, lot.lot_id)
    take_acq, keep_acq = _split_acquisition(lot.acquisition_cents, input_grams, lot.grams - input_grams)
    if edible > 0 and loss > 0:
        parts = allocate_largest_remainder(take_acq, (("edible", edible), ("loss", loss)))
    elif edible > 0:
        parts = {"edible": take_acq, "loss": 0}
    else:
        parts = {"edible": 0, "loss": take_acq}
    remove_ids: tuple[str, ...] = ()
    written: list[FoodLot] = []
    if input_grams == lot.grams:
        remove_ids = (lot.lot_id,)
    else:
        written.append(replace(lot, grams=lot.grams - input_grams, acquisition_cents=keep_acq))
    movements: list[FoodMovement] = []
    if added > 0:
        movements.append(
            FoodMovement(
                movement_id=f"{command.command_id}:added_material:0",
                command_id=command.command_id,
                sequence=0,
                kind="added_material",
                product_id="mass.added",
                grams=added,
                from_owner_id=None,
                to_owner_id=command.processor_id,
                from_lot_id=None,
                to_lot_id=None,
                parent_lot_ids=(lot.lot_id,),
                acquisition_cents_recognized=0,
                acquisition_cents_introduced=0,
            )
        )
    if edible > 0:
        output_id = f"{lot.lot_id}.{command.command_id}.out"
        if not valid_id(output_id):
            return Rejection(INVALID_ID, output_id)
        written.append(
            FoodLot(
                lot_id=output_id,
                product_id=command.output_product_id,
                owner_id=command.processor_id,
                place_id=command.output_place_id,
                journey_id=None,
                grams=edible,
                reserved_grams=0,
                unsafe_after=unsafe_after,
                parents=(lot.lot_id,),
                acquisition_cents=parts["edible"],
                source_kind=lot.source_kind,
                input_class=lot.input_class,
            )
        )
        movements.append(
            FoodMovement(
                movement_id=f"{command.command_id}:process_output:0",
                command_id=command.command_id,
                sequence=0,
                kind="process_output",
                product_id=command.output_product_id,
                grams=edible,
                from_owner_id=None,
                to_owner_id=command.processor_id,
                from_lot_id=lot.lot_id,
                to_lot_id=output_id,
                parent_lot_ids=(lot.lot_id,),
                acquisition_cents_recognized=0,
                acquisition_cents_introduced=0,
            )
        )
    if loss > 0:
        movements.append(
            FoodMovement(
                movement_id=f"{command.command_id}:process_loss:0",
                command_id=command.command_id,
                sequence=0,
                kind="process_loss",
                product_id=lot.product_id,
                grams=loss,
                from_owner_id=lot.owner_id,
                to_owner_id=None,
                from_lot_id=lot.lot_id,
                to_lot_id=None,
                parent_lot_ids=(lot.lot_id,),
                acquisition_cents_recognized=parts["loss"],
                acquisition_cents_introduced=0,
            )
        )
    return (
        LotsSet(remove_ids=remove_ids, lots=_sort_lots(tuple(written))),
        MovementsAppended(movements=tuple(movements), **_flows(state, added=added, loss=loss)),
    )


def _compile_expiry(state: WorldState, command: ApplyExpiry) -> tuple[object, ...] | Rejection:
    rejected = _phase(command, frozenset({PHASE_EXPIRY}))
    if rejected:
        return rejected
    expired = tuple(
        lot for lot in state.lots if lot.unsafe_after is not None and lot.unsafe_after <= command.second and lot.grams > 0
    )
    if not expired:
        return ()
    expired_ids = {lot.lot_id for lot in expired}
    dropped = tuple(reservation for reservation in state.reservations if reservation.lot_id in expired_ids)
    account_updates: dict[str, Account] = {}
    for reservation in dropped:
        if reservation.cash_account_id is None:
            continue
        account = account_updates.get(reservation.cash_account_id) or account_by_id(state, reservation.cash_account_id)
        if account is None:
            return Rejection(UNKNOWN_ACCOUNT, reservation.cash_account_id)
        account_updates[account.account_id] = replace(
            account, reserved_cents=account.reserved_cents - reservation.max_cents
        )
    movements = []
    for index, lot in enumerate(expired):
        movements.append(
            FoodMovement(
                movement_id=f"{command.command_id}:waste:{index}",
                command_id=command.command_id,
                sequence=0,
                kind="waste",
                product_id=lot.product_id,
                grams=lot.grams,
                from_owner_id=lot.owner_id,
                to_owner_id=None,
                from_lot_id=lot.lot_id,
                to_lot_id=None,
                parent_lot_ids=lot.parents,
                acquisition_cents_recognized=lot.acquisition_cents,
                acquisition_cents_introduced=0,
            )
        )
    payloads: list[object] = []
    if account_updates:
        payloads.append(AccountsSet(accounts=_sort_accounts(tuple(account_updates.values()))))
    payloads.append(LotsSet(remove_ids=tuple(sorted(expired_ids)), lots=()))
    if dropped:
        payloads.append(
            ReservationsSet(remove_ids=tuple(sorted(reservation.reservation_id for reservation in dropped)), reservations=())
        )
    waste_grams = sum(lot.grams for lot in expired)
    payloads.append(MovementsAppended(movements=tuple(movements), **_flows(state, loss=waste_grams)))
    return tuple(payloads)


def _compile_choice(state: WorldState, command: RecordChoice) -> tuple[object, ...] | Rejection:
    del state
    rejected = _phase(command, frozenset({PHASE_CHOICE}))
    if rejected:
        return rejected
    for field in (command.decision_id, command.household_id, command.option_id):
        rejected = _require_id(field, "choice identity")
        if rejected:
            return rejected
    if command.origin not in _ORIGINS:
        return Rejection(INVALID_ORIGIN, command.origin)
    if not valid_sha256(command.observation_hash):
        return Rejection(INVALID_HASH, "observation_hash")
    try:
        revision = require_int(command.revision, "revision")
    except ValueError as exc:
        return Rejection(NON_INTEGER, str(exc))
    if revision < 0:
        return Rejection(NON_POSITIVE, "revision")
    if command.explanation is not None:
        if (
            not isinstance(command.explanation, str)
            or len(command.explanation) > 400
            or any(ord(char) < 32 for char in command.explanation)
        ):
            return Rejection(INVALID_MEMO, "explanation must be at most 400 visible characters")
    record = ChoiceRecord(
        decision_id=command.decision_id,
        household_id=command.household_id,
        option_id=command.option_id,
        origin=command.origin,
        observation_hash=command.observation_hash,
        revision=revision,
        explanation=command.explanation,
    )
    return (ChoicesAppended(choices=(record,)),)


_HANDLERS = {
    OpenAccount: _compile_open,
    TransferCash: _compile_transfer,
    IntroduceLot: _compile_introduce,
    ReserveResources: _compile_reserve,
    ReleaseReservation: _compile_release,
    PurchaseLot: _compile_purchase,
    ConsumeFood: _compile_consume,
    TransferLot: _compile_transfer_lot,
    ProcessBatch: _compile_process,
    ApplyExpiry: _compile_expiry,
    RecordChoice: _compile_choice,
}
