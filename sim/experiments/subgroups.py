"""Subgroup counts from the frozen synthetic population.

A district average can hide a band with less cash or less time.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sim.district import build_population


@dataclass(frozen=True, slots=True)
class SubgroupReport:
    evidence_state: str
    household_count: int
    income_counts: tuple[tuple[str, int], ...]
    mobility_by_income: tuple[tuple[str, str, int], ...]
    eligible_pupils_by_school: tuple[tuple[str, int], ...]
    ineligible_pupils: int
    note: str


def population_subgroups(controls: dict, places: dict) -> SubgroupReport:
    population = build_population(controls, places)
    income = Counter(household.income_band for household in population.households)
    mobility: Counter[tuple[str, str]] = Counter(
        (household.income_band, household.mobility) for household in population.households
    )
    eligible: Counter[str] = Counter(pupil.school_id for pupil in population.pupils if pupil.eligible)
    ineligible = sum(1 for pupil in population.pupils if not pupil.eligible)
    return SubgroupReport(
        evidence_state="illustrative",
        household_count=len(population.households),
        income_counts=tuple(sorted(income.items())),
        mobility_by_income=tuple((income_band, mobility_kind, count) for (income_band, mobility_kind), count in sorted(mobility.items())),
        eligible_pupils_by_school=tuple(sorted(eligible.items())),
        ineligible_pupils=ineligible,
        note="Counts match the frozen quotas. They are not a Census table and not a deprivation ranking.",
    )
