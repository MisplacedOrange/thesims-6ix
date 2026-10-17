"""One-at-a-time sweeps. A single friendly parameter set is not a pass."""

from __future__ import annotations

from dataclasses import dataclass

from sim.policies import run_municipal_grocery, run_procurement


@dataclass(frozen=True, slots=True)
class SweepPoint:
    name: str
    parameter: int
    outcome_cents: int


def grocery_price_sweep() -> tuple[SweepPoint, ...]:
    closed = run_municipal_grocery("closed")
    exhausted = run_municipal_grocery("open_exhausted")
    full = run_municipal_grocery("open_full")
    return (
        SweepPoint("discount_budget_cents", 0, closed.household_payment_cents),
        SweepPoint("discount_budget_cents", 50, exhausted.household_payment_cents),
        SweepPoint("discount_budget_cents", 80, full.household_payment_cents),
    )


def procurement_spoilage_sweep() -> tuple[SweepPoint, ...]:
    fresh = run_procurement("pooled", spoilage_grams=0)
    spoiled = run_procurement("pooled", spoilage_grams=100)
    return (
        SweepPoint("spoilage_grams", 0, fresh.delivered_cost_cents),
        SweepPoint("spoilage_grams", 100, spoiled.delivered_cost_cents),
    )
