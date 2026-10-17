"""Pure reporting helpers. They read integers and return integers.

They do not post journal entries and they do not rewrite a ledger into real dollars.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core.units import require_int, require_nonnegative

CAD_CENTS = "cad_cents"
GRAMS = "grams"
SIM_SECONDS = "sim_seconds"
METRES = "metres"
COUNT = "count"
METRIC_UNITS = (CAD_CENTS, GRAMS, SIM_SECONDS, METRES, COUNT)


@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    value: int
    unit: str


@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    message: str


class InputError(ValueError):
    def __init__(self, errors: tuple[FieldError, ...]):
        self.errors = errors
        text = "; ".join(f"{error.field}: {error.message}" for error in errors)
        super().__init__(text or "invalid input")


def paired_difference(baseline: tuple[Metric, ...], treatment: tuple[Metric, ...]) -> tuple[Metric, ...]:
    """Treatment minus baseline, one metric at a time, in the given order."""

    if tuple(metric.name for metric in baseline) != tuple(metric.name for metric in treatment):
        raise ValueError("incompatible metric names")
    if len({metric.name for metric in baseline}) != len(baseline):
        raise ValueError("duplicate metric name")
    deltas: list[Metric] = []
    for left, right in zip(baseline, treatment, strict=True):
        if left.unit != right.unit:
            raise ValueError(f"incompatible unit for {left.name}")
        if left.unit not in METRIC_UNITS or right.unit not in METRIC_UNITS:
            raise ValueError(f"unknown unit for {left.name}")
        deltas.append(Metric(left.name, right.value - left.value, left.unit))
    return tuple(deltas)


def funded_discount(
    list_price_cents: int,
    requested_discount_cents: int,
    subsidy_budget_cents: int,
) -> tuple[int, int]:
    """Return ``(household_pays_cents, subsidy_cents)``.

    The subsidy is the portion of the requested discount the budget can fund,
    and it cannot exceed the list price. The household pays the remainder.
    """

    list_price = require_nonnegative(list_price_cents, "list_price_cents")
    requested = require_nonnegative(requested_discount_cents, "requested_discount_cents")
    budget = require_nonnegative(subsidy_budget_cents, "subsidy_budget_cents")
    subsidy = min(requested, budget, list_price)
    return list_price - subsidy, subsidy


def cash_before_subsidy(
    sales_receipts: int,
    inventory_payments: int,
    other_operating_cash_payments: int,
) -> int:
    sales = require_nonnegative(sales_receipts, "sales_receipts")
    inventory = require_nonnegative(inventory_payments, "inventory_payments")
    other = require_nonnegative(other_operating_cash_payments, "other_operating_cash_payments")
    return sales - inventory - other


def cash_funding_gap(minimum_cash_reserve: int, opening_cash: int, before_subsidy: int) -> int:
    minimum = require_nonnegative(minimum_cash_reserve, "minimum_cash_reserve")
    opening = require_nonnegative(opening_cash, "opening_cash")
    before = require_int(before_subsidy, "before_subsidy")
    return max(0, minimum - opening - before)


def operating_result(
    *,
    sales_revenue: int,
    operating_subsidy: int,
    cost_of_food_sold: int,
    inventory_writeoffs: int,
    labor: int,
    occupancy: int,
    energy: int,
    logistics: int,
    disposal_charges: int,
    other_overhead: int,
) -> int:
    sales = require_nonnegative(sales_revenue, "sales_revenue")
    subsidy = require_nonnegative(operating_subsidy, "operating_subsidy")
    costs = (
        require_nonnegative(cost_of_food_sold, "cost_of_food_sold")
        + require_nonnegative(inventory_writeoffs, "inventory_writeoffs")
        + require_nonnegative(labor, "labor")
        + require_nonnegative(occupancy, "occupancy")
        + require_nonnegative(energy, "energy")
        + require_nonnegative(logistics, "logistics")
        + require_nonnegative(disposal_charges, "disposal_charges")
        + require_nonnegative(other_overhead, "other_overhead")
    )
    return sales + subsidy - costs
