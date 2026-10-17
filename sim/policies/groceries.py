"""Municipal grocery price rule and operating costs.

The store is closed unless a scenario opens it. A household discount is a
municipal transfer. It is not a reduction in the food's resource cost.
Illustrative cents, not a Toronto shelf price or an adopted budget.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core import (
    PHASE_POLICY,
    PHASE_SETTLE,
    GRAMS,
    CAD_CENTS,
    IntroduceLot,
    Metric,
    OpenAccount,
    PurchaseLot,
    TransferCash,
    account_for_owner,
    cash_before_subsidy,
    cash_funding_gap,
    funded_discount,
    lots_for_owner,
    operating_result,
)

from sim.policies.session import memo_cents, settle, world

LIST_CENTS = 200
REQUESTED_DISCOUNT_CENTS = 80
BASKET_GRAMS = 400
STOCK_GRAMS = 1000
INVENTORY_PAYMENT_CENTS = 300
LABOR_CENTS = 100
OCCUPANCY_CENTS = 80
OPERATING_SUBSIDY_CENTS = 500
APPROPRIATION_CENTS = 2000
HOUSEHOLD_CASH_CENTS = 1000


@dataclass(frozen=True, slots=True)
class GroceryResult:
    mode: str
    evidence_state: str
    state: object
    events: tuple
    household_payment_cents: int
    price_subsidy_cents: int
    operating_subsidy_cents: int
    fiscal_outlay_cents: int
    resource_cash_cents: int
    cogs_cents: int
    cash_before_subsidy_cents: int
    cash_funding_gap_cents: int
    operating_result_cents: int
    household_grams: int
    store_grams: int
    metrics: tuple[Metric, ...]
    note: str


def run_municipal_grocery(mode: str) -> GroceryResult:
    """``closed``, ``open_full``, or ``open_exhausted``.

    Closed is the planning baseline: no operating pilot. Open posts an
    operating subsidy and a separate till subsidy capped by the remaining
    discount budget (80 full, 50 exhausted).
    """

    if mode not in {"closed", "open_full", "open_exhausted"}:
        raise ValueError(mode)
    state = world(f"grocery-{mode}", "groceries-only")
    commands: list = [
        OpenAccount("open-ext", 0, PHASE_POLICY, "acct-ext", "ext", "external", True),
        OpenAccount("open-m", 0, PHASE_POLICY, "acct-m", "muni", "municipality", False),
        OpenAccount("open-s", 0, PHASE_POLICY, "acct-s", "store-m", "retailer", False),
        OpenAccount("open-r", 0, PHASE_POLICY, "acct-r", "store-r", "retailer", False),
        OpenAccount("open-h", 0, PHASE_POLICY, "acct-h", "hh", "household", False),
        TransferCash("cash-h", 0, PHASE_POLICY, "acct-ext", "acct-h", HOUSEHOLD_CASH_CENTS, "opening_balance"),
        IntroduceLot("lot-r", 0, PHASE_POLICY, "lot-r", "produce.fresh", "store-r", "store-r", STOCK_GRAMS, INVENTORY_PAYMENT_CENTS, None),
    ]
    discount_budget = 0
    if mode != "closed":
        discount_budget = 80 if mode == "open_full" else 50
        commands.extend(
            [
                TransferCash("approp", 0, PHASE_POLICY, "acct-ext", "acct-m", APPROPRIATION_CENTS, "appropriation"),
                TransferCash("op-sub", 0, PHASE_POLICY, "acct-m", "acct-s", OPERATING_SUBSIDY_CENTS, "operating_subsidy"),
                TransferCash("stock-pay", 0, PHASE_POLICY, "acct-s", "acct-ext", INVENTORY_PAYMENT_CENTS, "inventory_payment"),
                IntroduceLot(
                    "lot-s",
                    0,
                    PHASE_POLICY,
                    "lot-s",
                    "produce.fresh",
                    "store-m",
                    "store-m",
                    STOCK_GRAMS,
                    INVENTORY_PAYMENT_CENTS,
                    None,
                ),
                TransferCash("labor", 0, PHASE_POLICY, "acct-s", "acct-ext", LABOR_CENTS, "labor"),
                TransferCash("occupancy", 0, PHASE_POLICY, "acct-s", "acct-ext", OCCUPANCY_CENTS, "occupancy"),
            ]
        )
    household_pays, subsidy = funded_discount(LIST_CENTS, REQUESTED_DISCOUNT_CENTS, discount_budget)
    if mode == "closed":
        commands.append(
            PurchaseLot("buy-r", 2, PHASE_SETTLE, "acct-h", "acct-r", "home-hh", "lot-r", BASKET_GRAMS, LIST_CENTS)
        )
    else:
        commands.append(
            PurchaseLot("buy-s", 2, PHASE_SETTLE, "acct-h", "acct-s", "home-hh", "lot-s", BASKET_GRAMS, household_pays)
        )
        if subsidy > 0:
            commands.append(TransferCash("till-sub", 2, PHASE_SETTLE, "acct-m", "acct-s", subsidy, "price_subsidy"))
    state, events = settle(state, commands)
    price_subsidy = memo_cents(state, "acct-m", "price_subsidy", leaving=True)
    operating_subsidy = memo_cents(state, "acct-m", "operating_subsidy", leaving=True)
    inventory = memo_cents(state, "acct-s", "inventory_payment", leaving=True)
    labor = memo_cents(state, "acct-s", "labor", leaving=True)
    occupancy = memo_cents(state, "acct-s", "occupancy", leaving=True)
    household_payment = memo_cents(state, "acct-h", f"purchase:produce.fresh:{BASKET_GRAMS}", leaving=True)
    cogs = _cogs(state)
    before = cash_before_subsidy(household_payment if mode != "closed" else 0, inventory, labor + occupancy)
    gap = cash_funding_gap(0, 0, before)
    result = operating_result(
        sales_revenue=household_payment if mode != "closed" else 0,
        operating_subsidy=operating_subsidy + price_subsidy,
        cost_of_food_sold=cogs if mode != "closed" else 0,
        inventory_writeoffs=0,
        labor=labor,
        occupancy=occupancy,
        energy=0,
        logistics=0,
        disposal_charges=0,
        other_overhead=0,
    )
    household_grams = sum(lot.grams for lot in lots_for_owner(state, "hh"))
    store_grams = sum(lot.grams for lot in lots_for_owner(state, "store-m"))
    metrics = (
        Metric("household_payment", household_payment, CAD_CENTS),
        Metric("fiscal_outlay", operating_subsidy + price_subsidy, CAD_CENTS),
        Metric("resource_cash", inventory + labor + occupancy, CAD_CENTS),
        Metric("household_grams", household_grams, GRAMS),
    )
    note = (
        "Household savings equal the till transfer. Store receipts of that basket still equal the list price "
        "because the municipality pays the discount. Resource cash is inventory, labor, and occupancy, counted once."
    )
    return GroceryResult(
        mode=mode,
        evidence_state="illustrative",
        state=state,
        events=events,
        household_payment_cents=household_payment,
        price_subsidy_cents=price_subsidy,
        operating_subsidy_cents=operating_subsidy,
        fiscal_outlay_cents=operating_subsidy + price_subsidy,
        resource_cash_cents=inventory + labor + occupancy,
        cogs_cents=cogs if mode != "closed" else 0,
        cash_before_subsidy_cents=before,
        cash_funding_gap_cents=gap,
        operating_result_cents=result,
        household_grams=household_grams,
        store_grams=store_grams,
        metrics=metrics,
        note=note,
    )


def _cogs(state) -> int:
    recognized = sum(
        movement.acquisition_cents_recognized
        for movement in state.movements
        if movement.kind == "consume"
    )
    del recognized
    sold = 0
    for lot in lots_for_owner(state, "hh"):
        sold += lot.acquisition_cents
    account = account_for_owner(state, "store-m")
    del account
    return sold
