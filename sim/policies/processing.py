"""Rescue, direct redistribution, and processing.

Baseline lots must already be reserved by the scenario. This mechanism will
not take them. Eligible unreserved lots are accepted earliest-expiry first,
up to shift capacity. Purchased farm input and rescued surplus keep separate
classes through the recipe. Added water is extra mass, not free food. Cold
storage applies to edible output still at the processor, after demand is met.

Idle shift labor can be paid when no eligible food arrives. Unit cost stays
undefined when nothing usable is delivered.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.policies.core_interface import CoreLedger, OutputDraft, largest_remainder
from sim.policies.evidence import require_evidence


@dataclass(frozen=True)
class PurchaseInput:
    product_id: str
    grams: int
    cents: int
    unsafe_after: int
    payee: str


@dataclass(frozen=True)
class ProcessingCommand:
    evidence_state: str
    processor_account: str
    processor_owner: str
    processor_custody: str
    now: int
    max_input_grams: int
    mode: str
    edible_num: int
    edible_den: int
    product_out: str
    output_unsafe_after: int
    transport_cents: int
    transport_payee: str
    transport_loss_num: int
    transport_loss_den: int
    labor_cents: int
    labor_payee: str
    pay_labor_if_idle: bool
    added_grams: int
    added_product_id: str
    cold_storage_grams: int
    demand_grams: int
    demand_owner: str
    demand_custody: str
    source_owners: tuple[str, ...]
    accepted_classes: tuple[str, ...]
    purchases: tuple[PurchaseInput, ...]


@dataclass(frozen=True)
class ProcessingResult:
    evidence_state: str
    mode: str
    output_product_id: str
    accepted_grams: int
    accepted_by_class: tuple[tuple[str, int], ...]
    unprocessed_grams: int
    skipped_reserved_grams: int
    expired_grams: int
    added_grams: int
    edible_grams: int
    edible_by_class: tuple[tuple[str, int], ...]
    process_loss_grams: int
    transport_spoilage_grams: int
    storage_spoilage_grams: int
    delivered_grams: int
    stored_grams: int
    purchased_input_cents: int
    purchase_unpaid_cents: int
    transport_cents: int
    transport_unpaid_cents: int
    labor_cents: int
    labor_unpaid_cents: int
    operating_cents: int
    usable_delivered_grams: int
    unit_cost_defined: bool


def apply_processing(ledger: CoreLedger, command: ProcessingCommand) -> ProcessingResult:
    """Accept, transform, and deliver one processor shift."""

    _validate(command)
    purchased_cents, purchase_unpaid = _buy_inputs(ledger, command)
    accepted, accepted_by_class, unprocessed, reserved_grams, expired_grams = _accept(
        ledger, command
    )
    transport_spoilage = _apply_transport_loss(ledger, accepted, command)
    alive = [lot_id for lot_id in accepted if _still_there(ledger, lot_id)]
    added_grams = 0
    if command.added_grams > 0 and alive:
        alive.append(_add_water(ledger, command))
        added_grams = command.added_grams
    edible_ids, edible_by_class, process_loss = _transform(ledger, alive, command)
    delivered = _deliver(ledger, command, edible_ids)
    stored, storage_spoilage = _enforce_storage(ledger, command, edible_ids)
    food_in = sum(accepted_by_class.values()) > 0
    labor, labor_unpaid = _pay(
        ledger,
        command.processor_account,
        command.labor_payee,
        command.labor_cents if (food_in or command.pay_labor_if_idle) else 0,
        "processor labor",
    )
    transport, transport_unpaid = _pay(
        ledger,
        command.processor_account,
        command.transport_payee,
        command.transport_cents if food_in else 0,
        "rescue transport",
    )
    output_product = command.product_out if command.mode == "process" else _direct_product(ledger, edible_ids)
    return ProcessingResult(
        evidence_state=command.evidence_state,
        mode=command.mode,
        output_product_id=output_product,
        accepted_grams=sum(accepted_by_class.values()),
        accepted_by_class=_pairs(accepted_by_class),
        unprocessed_grams=unprocessed,
        skipped_reserved_grams=reserved_grams,
        expired_grams=expired_grams,
        added_grams=added_grams,
        edible_grams=sum(edible_by_class.values()),
        edible_by_class=_pairs(edible_by_class),
        process_loss_grams=process_loss,
        transport_spoilage_grams=transport_spoilage,
        storage_spoilage_grams=storage_spoilage,
        delivered_grams=delivered,
        stored_grams=stored,
        purchased_input_cents=purchased_cents,
        purchase_unpaid_cents=purchase_unpaid,
        transport_cents=transport,
        transport_unpaid_cents=transport_unpaid,
        labor_cents=labor,
        labor_unpaid_cents=labor_unpaid,
        operating_cents=transport + labor,
        usable_delivered_grams=delivered,
        unit_cost_defined=delivered > 0,
    )


def _validate(command: ProcessingCommand) -> None:
    require_evidence(command.evidence_state)
    if command.mode not in ("process", "direct"):
        raise ValueError("mode must be process or direct")
    if command.mode == "direct" and command.added_grams:
        raise ValueError("added material belongs to a processing recipe")
    if command.edible_den <= 0 or command.edible_num < 0 or command.edible_num > command.edible_den:
        raise ValueError("edible yield must be a fraction between 0 and 1")
    if command.transport_loss_den <= 0 or not 0 <= command.transport_loss_num <= command.transport_loss_den:
        raise ValueError("transport loss fraction is invalid")
    magnitudes = (
        command.max_input_grams,
        command.transport_cents,
        command.labor_cents,
        command.added_grams,
        command.cold_storage_grams,
        command.demand_grams,
    )
    if any(value < 0 for value in magnitudes):
        raise ValueError("processing magnitudes must be nonnegative")
    for purchase in command.purchases:
        if purchase.grams <= 0 or purchase.cents < 0:
            raise ValueError("purchase is invalid")


def _buy_inputs(ledger: CoreLedger, command: ProcessingCommand) -> tuple[int, int]:
    paid = 0
    unpaid = 0
    for purchase in command.purchases:
        if ledger.spendable(command.processor_account) < purchase.cents:
            unpaid += purchase.cents
            continue
        ledger.buy_lot(
            payer=command.processor_account,
            payee=purchase.payee,
            product_id=purchase.product_id,
            owner=command.processor_owner,
            custody=command.processor_custody,
            grams=purchase.grams,
            cents=purchase.cents,
            unsafe_after=purchase.unsafe_after,
            source_kind="purchase",
            input_class="purchased",
            memo="farm purchase",
        )
        paid += purchase.cents
    return paid, unpaid


def _accept(
    ledger: CoreLedger, command: ProcessingCommand
) -> tuple[list[str], dict[str, int], int, int, int]:
    reserved_grams = 0
    expired_grams = 0
    candidates = []
    for lot in ledger.lots():
        if lot.owner not in command.source_owners or lot.input_class not in command.accepted_classes:
            continue
        if ledger.reserved_grams(lot.lot_id) > 0:
            reserved_grams += lot.grams
            continue
        if lot.unsafe_after <= command.now:
            expired_grams += lot.grams
            continue
        candidates.append(lot)
    candidates.sort(key=lambda lot: (lot.unsafe_after, lot.lot_id))
    capacity = command.max_input_grams
    accepted: list[str] = []
    by_class: dict[str, int] = {}
    unprocessed = 0
    for lot in candidates:
        if capacity == 0:
            unprocessed += lot.grams
            continue
        take_grams = min(lot.grams, capacity)
        unprocessed += lot.grams - take_grams
        piece = ledger.take(lot.lot_id, take_grams)
        view = ledger.lot(piece)
        if view.owner != command.processor_owner or view.custody != command.processor_custody:
            ledger.transfer_lot(
                piece,
                owner=command.processor_owner,
                custody=command.processor_custody,
            )
        accepted.append(piece)
        by_class[view.input_class] = by_class.get(view.input_class, 0) + view.grams
        capacity -= take_grams
    return accepted, by_class, unprocessed, reserved_grams, expired_grams


def _apply_transport_loss(ledger: CoreLedger, accepted: list[str], command: ProcessingCommand) -> int:
    spoiled = 0
    for lot_id in list(accepted):
        if not _still_there(ledger, lot_id):
            continue
        grams = ledger.lot(lot_id).grams
        loss = grams * command.transport_loss_num // command.transport_loss_den
        if loss <= 0:
            continue
        ledger.write_off(lot_id, loss, reason="transport")
        spoiled += loss
    return spoiled


def _add_water(ledger: CoreLedger, command: ProcessingCommand) -> str:
    return ledger.add_material(
        product_id=command.added_product_id,
        owner=command.processor_owner,
        custody=command.processor_custody,
        grams=command.added_grams,
        acquisition_cents=0,
        unsafe_after=command.output_unsafe_after,
        input_class="added",
    )


def _transform(
    ledger: CoreLedger, pieces: list[str], command: ProcessingCommand
) -> tuple[list[str], dict[str, int], int]:
    alive = [lot_id for lot_id in pieces if _still_there(ledger, lot_id)]
    edible_by_class: dict[str, int] = {}
    if not alive:
        return [], edible_by_class, 0
    if command.mode == "direct":
        for lot_id in alive:
            lot = ledger.lot(lot_id)
            edible_by_class[lot.input_class] = edible_by_class.get(lot.input_class, 0) + lot.grams
        return alive, edible_by_class, 0
    weights = {lot_id: ledger.lot(lot_id).grams for lot_id in alive}
    edible_total = sum(weights.values()) * command.edible_num // command.edible_den
    edible_split = largest_remainder(edible_total, weights)
    created: list[str] = []
    process_loss = 0
    for lot_id in alive:
        lot = ledger.lot(lot_id)
        edible_grams = edible_split[lot_id]
        loss_grams = lot.grams - edible_grams
        cents = largest_remainder(
            lot.acquisition_cents,
            {"edible": edible_grams, "loss": loss_grams},
        )
        outputs: list[OutputDraft] = []
        if edible_grams:
            outputs.append(
                OutputDraft(
                    grams=edible_grams,
                    acquisition_cents=cents["edible"],
                    product_id=command.product_out,
                    owner=command.processor_owner,
                    custody=command.processor_custody,
                    unsafe_after=command.output_unsafe_after,
                    source_kind="processed",
                    input_class=lot.input_class,
                    disposition="stock",
                    reason="edible",
                )
            )
            edible_by_class[lot.input_class] = edible_by_class.get(lot.input_class, 0) + edible_grams
        if loss_grams:
            outputs.append(
                OutputDraft(
                    grams=loss_grams,
                    acquisition_cents=cents["loss"],
                    product_id=lot.product_id,
                    owner=command.processor_owner,
                    custody=command.processor_custody,
                    unsafe_after=lot.unsafe_after,
                    source_kind="processed",
                    input_class=lot.input_class,
                    disposition="waste",
                    reason="process_loss",
                )
            )
            process_loss += loss_grams
        created.extend(ledger.replace_lot(lot_id, tuple(outputs)))
    return created, edible_by_class, process_loss


def _deliver(ledger: CoreLedger, command: ProcessingCommand, edible_ids: list[str]) -> int:
    if command.demand_grams <= 0:
        return 0
    delivered = 0
    remaining = command.demand_grams
    known = set(edible_ids)
    while remaining > 0:
        candidates = [
            lot
            for lot in ledger.lots()
            if lot.owner == command.processor_owner and _tracks(lot.lot_id, lot.parents, known)
        ]
        if not candidates:
            break
        candidates.sort(key=lambda lot: (lot.unsafe_after, lot.lot_id))
        lot = candidates[0]
        take_grams = min(lot.grams, remaining)
        piece = ledger.take(lot.lot_id, take_grams)
        ledger.transfer_lot(piece, owner=command.demand_owner, custody=command.demand_custody)
        known.add(piece)
        delivered += take_grams
        remaining -= take_grams
    edible_ids[:] = list(known)
    return delivered


def _enforce_storage(
    ledger: CoreLedger, command: ProcessingCommand, edible_ids: list[str]
) -> tuple[int, int]:
    known = set(edible_ids)

    def held() -> list:
        return [
            lot
            for lot in ledger.lots()
            if lot.owner == command.processor_owner and _tracks(lot.lot_id, lot.parents, known)
        ]

    spoiled = 0
    extra = sum(lot.grams for lot in held()) - command.cold_storage_grams
    while extra > 0:
        stocks = held()
        if not stocks:
            break
        stocks.sort(key=lambda lot: (lot.unsafe_after, lot.lot_id))
        lot = stocks[0]
        take_grams = min(lot.grams, extra)
        ledger.write_off(lot.lot_id, take_grams, reason="storage")
        spoiled += take_grams
        extra -= take_grams
    return sum(lot.grams for lot in held()), spoiled


def _pay(ledger: CoreLedger, src: str, dst: str, cents: int, memo: str) -> tuple[int, int]:
    if cents <= 0:
        return 0, 0
    if ledger.spendable(src) < cents:
        return 0, cents
    ledger.transfer(src, dst, cents, memo=memo)
    return cents, 0


def _direct_product(ledger: CoreLedger, edible_ids: list[str]) -> str:
    products = sorted(
        {
            lot.product_id
            for lot in ledger.lots()
            if _tracks(lot.lot_id, lot.parents, set(edible_ids))
        }
    )
    if len(products) == 1:
        return products[0]
    return ""


def _tracks(lot_id: str, parents: tuple[str, ...], known: set[str]) -> bool:
    return lot_id in known or any(parent in known for parent in parents)


def _still_there(ledger: CoreLedger, lot_id: str) -> bool:
    return any(lot.lot_id == lot_id for lot in ledger.lots())


def _pairs(weights: dict[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((key, value) for key, value in weights.items() if value))
