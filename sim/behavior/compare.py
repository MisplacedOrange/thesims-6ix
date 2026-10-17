"""Counts of rule, fallback, and recorded choices. No provider is contacted."""

from __future__ import annotations

from dataclasses import dataclass

from sim.core import COUNT, Metric


@dataclass(frozen=True, slots=True)
class ChoiceRow:
    household_id: str
    income_band: str
    origin: str
    reason: str
    option_id: str


def summarize(rows: tuple[ChoiceRow, ...]) -> tuple[Metric, ...]:
    fallback = sum(1 for row in rows if row.origin == "fallback")
    rule = sum(1 for row in rows if row.origin == "rule")
    recorded = sum(1 for row in rows if row.origin == "recorded")
    llm = sum(1 for row in rows if row.origin == "llm")
    skipped = sum(1 for row in rows if row.reason == "not_selected_for_live_barrier")
    return (
        Metric("rule_choices", rule, COUNT),
        Metric("fallback_choices", fallback, COUNT),
        Metric("recorded_choices", recorded, COUNT),
        Metric("llm_choices", llm, COUNT),
        Metric("not_selected", skipped, COUNT),
    )


def by_income(rows: tuple[ChoiceRow, ...], income: str) -> tuple[ChoiceRow, ...]:
    return tuple(row for row in rows if row.income_band == income)
