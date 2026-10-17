"""Worked examples on top of the kernel.

``run_subsidy_example`` is the small baseline-versus-treatment settlement.
It is not the municipal-store policy model.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core.catalog import load_catalog
from sim.core.commands import PHASE_POLICY, PHASE_SETTLE, IntroduceLot, OpenAccount, PurchaseLot, TransferCash
from sim.core.fixture_io import load_fixture_spec
from sim.core.kernel import apply_commands, empty_state, state_hash
from sim.core.models import WorldState
from sim.core.reporting import (
    CAD_CENTS,
    GRAMS,
    Metric,
    funded_discount,
    paired_difference,
)
from sim.core.economy import account_for_owner, lots_for_owner


@dataclass(frozen=True, slots=True)
class SubsidyRun:
    label: str
    household_pays_cents: int
    subsidy_cents: int
    unfunded_discount_cents: int
    subsidy_budget_remaining_cents: int
    budget_exhausted: bool
    metrics: tuple[Metric, ...]
    state: WorldState
    state_hash: str


@dataclass(frozen=True, slots=True)
class SubsidyExample:
    opening_cash_cents: tuple[tuple[str, int], ...]
    baseline: SubsidyRun
    treatment: SubsidyRun
    exhausted: SubsidyRun
    treatment_minus_baseline: tuple[Metric, ...]
    exhausted_minus_baseline: tuple[Metric, ...]
    note: str


def open_fixture_world(run_id: str) -> WorldState:
    catalog = load_catalog()
    spec = load_fixture_spec()
    state = empty_state(
        run_id=run_id,
        scenario_id=spec["scenario_id"],
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog.sha256,
        known_product_ids=tuple(product.product_id for product in catalog.products),
    )
    commands: list[object] = [
        OpenAccount(
            command_id="open-acct-external",
            second=0,
            phase=PHASE_POLICY,
            account_id=spec["external_account_id"],
            owner_id=spec["external_owner_id"],
            kind="external",
            allows_credit=True,
        )
    ]
    for actor in spec["actors"]:
        commands.append(
            OpenAccount(
                command_id=f"open-acct-{actor['account_id']}",
                second=0,
                phase=PHASE_POLICY,
                account_id=actor["account_id"],
                owner_id=actor["actor_id"],
                kind=actor["kind"],
                allows_credit=False,
            )
        )
    for account_id, cents in spec["opening_cash_cents"].items():
        if cents == 0:
            continue
        commands.append(
            TransferCash(
                command_id=f"open-cash-{account_id}",
                second=0,
                phase=PHASE_POLICY,
                from_account_id=spec["external_account_id"],
                to_account_id=account_id,
                cents=cents,
                memo="opening_balance",
            )
        )
    for lot in spec["opening_lots"]:
        commands.append(
            IntroduceLot(
                command_id=f"open-lot-{lot['lot_id']}",
                second=0,
                phase=PHASE_POLICY,
                lot_id=lot["lot_id"],
                product_id=lot["product_id"],
                owner_id=lot["owner_id"],
                place_id=lot["place_id"],
                grams=lot["grams"],
                acquisition_cents=lot["acquisition_cents"],
                unsafe_after=lot["unsafe_after"],
            )
        )
    transitions = apply_commands(state, commands)
    failed = [transition for transition in transitions if transition.status != "accepted"]
    if failed:
        raise RuntimeError(failed[0].reason or "opening failed")
    return transitions[-1].state


def run_subsidy_example() -> SubsidyExample:
    spec = load_fixture_spec()["subsidy_example"]
    list_price = spec["list_price_cents"]
    requested = spec["requested_discount_cents"]
    grams = spec["basket_grams"]
    need = spec["reference_need_grams"]
    baseline = _run_case("baseline", budget=0, requested=requested, list_price=list_price, grams=grams, need=need)
    treatment = _run_case(
        "treatment",
        budget=spec["full_budget_cents"],
        requested=requested,
        list_price=list_price,
        grams=grams,
        need=need,
    )
    exhausted = _run_case(
        "exhausted",
        budget=spec["exhausted_budget_cents"],
        requested=requested,
        list_price=list_price,
        grams=grams,
        need=need,
    )
    opening = open_fixture_world("subsidy-opening-probe")
    return SubsidyExample(
        opening_cash_cents=tuple(
            (account.owner_id, account.settled_cents)
            for account in opening.accounts
            if account.kind != "external"
        ),
        baseline=baseline,
        treatment=treatment,
        exhausted=exhausted,
        treatment_minus_baseline=paired_difference(baseline.metrics, treatment.metrics),
        exhausted_minus_baseline=paired_difference(baseline.metrics, exhausted.metrics),
        note=(
            "Household savings equal the municipal cash transfer. Retailer cash receipts "
            "stay the same because the subsidy replaces part of the list price. Unfunded "
            "discount remains in the household price when the budget cannot cover the request. "
            "This is an illustrative settlement, not the municipal-store siting model."
        ),
    )


def _run_case(label: str, *, budget: int, requested: int, list_price: int, grams: int, need: int) -> SubsidyRun:
    pays, subsidy = funded_discount(list_price, requested, budget)
    state = open_fixture_world(f"subsidy-{label}")
    commands = []
    if subsidy > 0:
        commands.append(
            TransferCash(
                command_id=f"{label}-subsidy",
                second=1,
                phase=PHASE_POLICY,
                from_account_id="acct-M",
                to_account_id="acct-R",
                cents=subsidy,
                memo="operating_subsidy",
            )
        )
    commands.append(
        PurchaseLot(
            command_id=f"{label}-purchase",
            second=2,
            phase=PHASE_SETTLE,
            buyer_account_id="acct-H",
            seller_account_id="acct-R",
            destination_place_id="home-H",
            lot_id="lot-produce-open",
            grams=grams,
            cents=pays,
        )
    )
    transitions = apply_commands(state, commands)
    failed = [transition for transition in transitions if transition.status != "accepted"]
    if failed:
        raise RuntimeError(failed[0].detail or failed[0].reason)
    final = transitions[-1].state
    household = account_for_owner(final, "H")
    municipal = account_for_owner(final, "M")
    retailer = account_for_owner(final, "R")
    if household is None or municipal is None or retailer is None:
        raise RuntimeError("missing actor")
    food = sum(lot.grams for lot in lots_for_owner(final, "H"))
    metrics = (
        Metric("household_food_spend", pays, CAD_CENTS),
        Metric("municipal_subsidy", subsidy, CAD_CENTS),
        Metric("unfunded_discount", requested - subsidy, CAD_CENTS),
        Metric("retailer_cash", retailer.settled_cents, CAD_CENTS),
        Metric("household_food", food, GRAMS),
        Metric("unmet_need", need - food, GRAMS),
        Metric("municipal_cash", municipal.settled_cents, CAD_CENTS),
        Metric("household_cash", household.settled_cents, CAD_CENTS),
    )
    return SubsidyRun(
        label=label,
        household_pays_cents=pays,
        subsidy_cents=subsidy,
        unfunded_discount_cents=requested - subsidy,
        subsidy_budget_remaining_cents=budget - subsidy,
        budget_exhausted=budget - subsidy == 0 and budget > 0,
        metrics=metrics,
        state=final,
        state_hash=state_hash(final),
    )
