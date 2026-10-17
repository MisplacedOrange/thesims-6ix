"""Municipal grocery pricing, subsidy, and store cash.

A store leaves planning only when funding, a site, and an operator are all
present. The operating subsidy is one cash transfer. Selling below acquisition
cost draws an authorization against that subsidy and does not post a second
transfer. When the authorization is exhausted, the price returns to
acquisition cost. Fee relief is forgone revenue, not cash. Spoilage recognizes
acquisition cost once; a disposal fee is a separate payment.

Reported operating result and cash funding gap follow the simulation spec.
They are allowed to differ. Capital cash is reported apart from operating cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.policies.core_interface import CoreLedger, plan_draw, quote_acquisition
from sim.policies.evidence import require_evidence

_OVERHEAD = ("labor", "occupancy", "energy", "logistics", "other")
_PRICING = ("at_cost", "subsidized_below_cost")


@dataclass(frozen=True)
class Shopper:
    household_id: str
    account: str
    requested_grams: int
    admission_rank: int
    travel_minutes: int
    time_budget_minutes: int


@dataclass(frozen=True)
class OverheadItem:
    kind: str
    cents: int
    payee: str


@dataclass(frozen=True)
class GroceryCommand:
    evidence_state: str
    funding_approved: bool
    site_ready: bool
    operator_ready: bool
    municipality_account: str
    store_account: str
    store_owner: str
    store_custody: str
    subsidy_cents: int
    price_support_cents: int
    minimum_cash_reserve: int
    purchase_grams: int
    purchase_cents: int
    purchase_payee: str
    product_id: str
    unsafe_after: int
    now: int
    pricing: str
    target_cents_per_1000g: int
    reference_cents_per_1000g: int
    overhead: tuple[OverheadItem, ...]
    shoppers: tuple[Shopper, ...]
    spoil_grams: int
    disposal_fee_cents: int
    disposal_payee: str
    fee_relief_cents: int
    capital_cents: int
    capital_payee: str


@dataclass(frozen=True)
class SaleRecord:
    household_id: str
    outcome: str
    grams: int
    paid_cents: int
    cogs_cents: int
    funded_gap_cents: int
    reference_cents: int
    savings_vs_reference_cents: int
    margin_not_charged_cents: int
    price_rule_applied: str


@dataclass(frozen=True)
class GroceryResult:
    evidence_state: str
    status: str
    subsidy_transferred_cents: int
    price_support_authorized_cents: int
    price_support_used_cents: int
    subsidy_exhausted: bool
    procurement_delayed: bool
    grams_purchased: int
    inventory_payments_cents: int
    sales_receipts_cents: int
    cogs_cents: int
    writeoff_cents: int
    labor_cents: int
    occupancy_cents: int
    energy_cents: int
    logistics_cents: int
    other_overhead_cents: int
    overhead_unpaid_cents: int
    disposal_cents: int
    disposal_unpaid_cents: int
    fee_relief_cents: int
    capital_cents: int
    capital_unpaid_cents: int
    operating_result_cents: int
    cash_before_subsidy_cents: int
    cash_funding_gap_cents: int
    funded_price_reduction_cents: int
    household_savings_vs_reference_cents: int
    external_resource_cents: int
    unmet_grams: int
    sales: tuple[SaleRecord, ...]


def apply_grocery(ledger: CoreLedger, command: GroceryCommand) -> GroceryResult:
    """Run one municipal-store operating cycle. Planning changes nothing."""

    _validate(command)
    opening_cash = ledger.cash(command.store_account)
    if not (command.funding_approved and command.site_ready and command.operator_ready):
        sales = tuple(
            _unsold(shopper, "not_operating")
            for shopper in _ordered(command.shoppers)
        )
        return _result(
            command,
            status="planning",
            opening_cash=opening_cash,
            sales=sales,
        )

    subsidy = min(command.subsidy_cents, ledger.spendable(command.municipality_account))
    ledger.transfer(
        command.municipality_account,
        command.store_account,
        subsidy,
        memo="operating subsidy",
    )
    support_authorized = min(command.price_support_cents, subsidy)

    capital = 0
    capital_unpaid = 0
    if command.capital_cents > 0:
        if ledger.spendable(command.municipality_account) >= command.capital_cents:
            ledger.transfer(
                command.municipality_account,
                command.capital_payee,
                command.capital_cents,
                memo="municipal store capital",
            )
            capital = command.capital_cents
        else:
            capital_unpaid = command.capital_cents

    overhead_paid = {kind: 0 for kind in _OVERHEAD}
    overhead_total = sum(item.cents for item in command.overhead)
    overhead_unpaid = 0
    if overhead_total > 0:
        if ledger.spendable(command.store_account) >= overhead_total:
            for item in command.overhead:
                ledger.transfer(
                    command.store_account,
                    item.payee,
                    item.cents,
                    memo=f"overhead {item.kind}",
                )
                overhead_paid[item.kind] += item.cents
        else:
            overhead_unpaid = overhead_total

    grams_purchased = 0
    inventory_payments = 0
    procurement_delayed = False
    if command.purchase_grams > 0:
        affordable = ledger.spendable(command.store_account) - command.minimum_cash_reserve
        if affordable >= command.purchase_cents:
            ledger.buy_lot(
                payer=command.store_account,
                payee=command.purchase_payee,
                product_id=command.product_id,
                owner=command.store_owner,
                custody=command.store_custody,
                grams=command.purchase_grams,
                cents=command.purchase_cents,
                unsafe_after=command.unsafe_after,
                source_kind="purchase",
                input_class="purchased",
                memo="municipal procurement",
            )
            grams_purchased = command.purchase_grams
            inventory_payments = command.purchase_cents
        else:
            procurement_delayed = True

    support_left = support_authorized
    exhausted = False
    sales: list[SaleRecord] = []
    for shopper in _ordered(command.shoppers):
        record, support_left, hit_cap = _sell(
            ledger, command, shopper, support_left
        )
        exhausted = exhausted or hit_cap
        sales.append(record)

    spoiled_grams, writeoff = _spoil(ledger, command)
    disposal = 0
    disposal_unpaid = 0
    if spoiled_grams > 0 and command.disposal_fee_cents > 0:
        if ledger.spendable(command.store_account) >= command.disposal_fee_cents:
            ledger.transfer(
                command.store_account,
                command.disposal_payee,
                command.disposal_fee_cents,
                memo="disposal fee",
            )
            disposal = command.disposal_fee_cents
        else:
            disposal_unpaid = command.disposal_fee_cents

    return _result(
        command,
        status="open",
        opening_cash=opening_cash,
        subsidy=subsidy,
        support_authorized=support_authorized,
        support_used=support_authorized - support_left,
        exhausted=exhausted,
        procurement_delayed=procurement_delayed,
        grams_purchased=grams_purchased,
        inventory_payments=inventory_payments,
        writeoff=writeoff,
        overhead_paid=overhead_paid,
        overhead_unpaid=overhead_unpaid,
        disposal=disposal,
        disposal_unpaid=disposal_unpaid,
        capital=capital,
        capital_unpaid=capital_unpaid,
        fee_relief=command.fee_relief_cents,
        sales=tuple(sales),
    )


def _validate(command: GroceryCommand) -> None:
    require_evidence(command.evidence_state)
    if command.pricing not in _PRICING:
        raise ValueError("unknown pricing rule")
    nonnegative = (
        command.subsidy_cents,
        command.price_support_cents,
        command.minimum_cash_reserve,
        command.purchase_grams,
        command.purchase_cents,
        command.target_cents_per_1000g,
        command.reference_cents_per_1000g,
        command.spoil_grams,
        command.disposal_fee_cents,
        command.fee_relief_cents,
        command.capital_cents,
    )
    if any(value < 0 for value in nonnegative):
        raise ValueError("grocery magnitudes must be nonnegative")
    for item in command.overhead:
        if item.kind not in _OVERHEAD or item.cents < 0:
            raise ValueError("unknown or negative overhead")
    for shopper in command.shoppers:
        if shopper.requested_grams < 0 or shopper.travel_minutes < 0:
            raise ValueError("shopper magnitudes must be nonnegative")
        if shopper.time_budget_minutes < 0:
            raise ValueError("time budget must be nonnegative")


def _ordered(shoppers: tuple[Shopper, ...]) -> tuple[Shopper, ...]:
    return tuple(sorted(shoppers, key=lambda shopper: (shopper.admission_rank, shopper.household_id)))


def _unsold(shopper: Shopper, outcome: str) -> SaleRecord:
    return SaleRecord(
        shopper.household_id,
        outcome,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        "",
    )


def _sell(
    ledger: CoreLedger,
    command: GroceryCommand,
    shopper: Shopper,
    support_left: int,
) -> tuple[SaleRecord, int, bool]:
    if shopper.travel_minutes > shopper.time_budget_minutes:
        return _unsold(shopper, "time_budget"), support_left, False
    if shopper.requested_grams == 0:
        return _unsold(shopper, "no_request"), support_left, False
    draws = plan_draw(
        ledger,
        owner=command.store_owner,
        product_id=command.product_id,
        grams=shopper.requested_grams,
        now=command.now,
    )
    if draws is None:
        return _unsold(shopper, "stockout"), support_left, False
    cogs = quote_acquisition(ledger, draws)
    support_before = support_left
    price, gap, rule, support_left, exhausted = _price(
        command, shopper.requested_grams, cogs, support_left
    )
    if ledger.spendable(shopper.account) < price:
        return _unsold(shopper, "unaffordable"), support_before, False
    ledger.transfer(
        shopper.account,
        command.store_account,
        price,
        memo=f"grocery sale {shopper.household_id}",
    )
    for lot_id, grams in draws:
        piece = ledger.take(lot_id, grams)
        ledger.transfer_lot(
            piece,
            owner=shopper.household_id,
            custody=f"home:{shopper.household_id}",
        )
    reference = shopper.requested_grams * command.reference_cents_per_1000g // 1000
    return (
        SaleRecord(
            household_id=shopper.household_id,
            outcome="sold",
            grams=shopper.requested_grams,
            paid_cents=price,
            cogs_cents=cogs,
            funded_gap_cents=gap,
            reference_cents=reference,
            savings_vs_reference_cents=max(0, reference - price),
            margin_not_charged_cents=max(0, reference - cogs),
            price_rule_applied=rule,
        ),
        support_left,
        exhausted,
    )


def _price(
    command: GroceryCommand,
    grams: int,
    cogs: int,
    support_left: int,
) -> tuple[int, int, str, int, bool]:
    if command.pricing == "at_cost":
        return cogs, 0, "at_cost", support_left, False
    target = grams * command.target_cents_per_1000g // 1000
    if target >= cogs:
        return cogs, 0, "at_cost", support_left, False
    gap = cogs - target
    if gap > support_left:
        return cogs, 0, "at_cost", support_left, True
    return target, gap, "subsidized", support_left - gap, False


def _spoil(ledger: CoreLedger, command: GroceryCommand) -> tuple[int, int]:
    left = command.spoil_grams
    spoiled = 0
    recognized = 0
    while left > 0:
        candidates = [
            lot
            for lot in ledger.lots()
            if lot.owner == command.store_owner
            and lot.product_id == command.product_id
            and ledger.reserved_grams(lot.lot_id) == 0
        ]
        if not candidates:
            break
        candidates.sort(key=lambda lot: (lot.unsafe_after, lot.lot_id))
        lot = candidates[0]
        take_grams = min(lot.grams, left)
        recognized += ledger.write_off(lot.lot_id, take_grams, reason="spoilage")
        spoiled += take_grams
        left -= take_grams
    return spoiled, recognized


def _result(
    command: GroceryCommand,
    *,
    status: str,
    opening_cash: int,
    sales: tuple[SaleRecord, ...] = (),
    subsidy: int = 0,
    support_authorized: int = 0,
    support_used: int = 0,
    exhausted: bool = False,
    procurement_delayed: bool = False,
    grams_purchased: int = 0,
    inventory_payments: int = 0,
    writeoff: int = 0,
    overhead_paid: dict[str, int] | None = None,
    overhead_unpaid: int = 0,
    disposal: int = 0,
    disposal_unpaid: int = 0,
    capital: int = 0,
    capital_unpaid: int = 0,
    fee_relief: int = 0,
) -> GroceryResult:
    paid = overhead_paid or {kind: 0 for kind in _OVERHEAD}
    sales_receipts = sum(sale.paid_cents for sale in sales)
    cogs = sum(sale.cogs_cents for sale in sales)
    funded = sum(sale.funded_gap_cents for sale in sales)
    savings = sum(sale.savings_vs_reference_cents for sale in sales)
    operating_cash = (
        paid["labor"]
        + paid["occupancy"]
        + paid["energy"]
        + paid["logistics"]
        + paid["other"]
        + disposal
    )
    if status != "open":
        cash_before_subsidy = 0
        gap = 0
        operating_result = 0
    else:
        cash_before_subsidy = sales_receipts - inventory_payments - operating_cash
        gap = max(0, command.minimum_cash_reserve - opening_cash - cash_before_subsidy)
        operating_result = (
            sales_receipts
            + subsidy
            - cogs
            - writeoff
            - paid["labor"]
            - paid["occupancy"]
            - paid["energy"]
            - paid["logistics"]
            - disposal
            - paid["other"]
        )
    unmet = sum(
        shopper.requested_grams
        for shopper, sale in zip(_ordered(command.shoppers), sales, strict=True)
        if sale.outcome not in ("sold", "no_request")
    )
    return GroceryResult(
        evidence_state=command.evidence_state,
        status=status,
        subsidy_transferred_cents=subsidy,
        price_support_authorized_cents=support_authorized,
        price_support_used_cents=support_used,
        subsidy_exhausted=exhausted,
        procurement_delayed=procurement_delayed,
        grams_purchased=grams_purchased,
        inventory_payments_cents=inventory_payments,
        sales_receipts_cents=sales_receipts,
        cogs_cents=cogs,
        writeoff_cents=writeoff,
        labor_cents=paid["labor"],
        occupancy_cents=paid["occupancy"],
        energy_cents=paid["energy"],
        logistics_cents=paid["logistics"],
        other_overhead_cents=paid["other"],
        overhead_unpaid_cents=overhead_unpaid,
        disposal_cents=disposal,
        disposal_unpaid_cents=disposal_unpaid,
        fee_relief_cents=fee_relief,
        capital_cents=capital,
        capital_unpaid_cents=capital_unpaid,
        operating_result_cents=operating_result,
        cash_before_subsidy_cents=cash_before_subsidy,
        cash_funding_gap_cents=gap,
        funded_price_reduction_cents=funded,
        household_savings_vs_reference_cents=savings,
        external_resource_cents=inventory_payments + operating_cash,
        unmet_grams=unmet,
        sales=sales,
    )
