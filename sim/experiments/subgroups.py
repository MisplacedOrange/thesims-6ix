"""Unweighted subgroup summaries and households who come out worse."""

from __future__ import annotations

from dataclasses import dataclass

from sim.experiments.adapters import HouseholdMetric, ReplicationResult
from sim.experiments.errors import ExperimentError

DIMENSIONS = ("income_band", "household_size", "area_id", "mobility", "school_eligible")


@dataclass(frozen=True)
class SubgroupRow:
    cell_id: str
    dimension: str
    group: str
    outcome: str
    count: int
    mean: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class WorseOff:
    cell_id: str
    household_id: str
    seed: int
    outcome: str
    baseline: float
    treatment: float


def subgroup_report(
    cell_results: tuple[tuple[int, ReplicationResult], ...],
    *,
    cell_id: str,
    outcomes: tuple[str, ...],
) -> tuple[SubgroupRow, ...]:
    rows: list[SubgroupRow] = []
    for outcome in outcomes:
        grouped: dict[tuple[str, str], list[float]] = {}
        for _seed, result in cell_results:
            if not result.completed:
                continue
            for household in result.households:
                value = _metric(household, outcome)
                if value is None:
                    continue
                for dimension in DIMENSIONS:
                    key = (dimension, _group_label(household, dimension))
                    grouped.setdefault(key, []).append(value)
        for dimension, group in sorted(grouped):
            values = grouped[(dimension, group)]
            rows.append(
                SubgroupRow(
                    cell_id=cell_id,
                    dimension=dimension,
                    group=group,
                    outcome=outcome,
                    count=len(values),
                    mean=sum(values) / len(values),
                    minimum=min(values),
                    maximum=max(values),
                )
            )
    return tuple(rows)


def worse_off(
    baseline: tuple[tuple[int, ReplicationResult], ...],
    treatment: tuple[tuple[int, ReplicationResult], ...],
    *,
    cell_id: str,
    outcomes: tuple[str, ...],
) -> tuple[WorseOff, ...]:
    by_seed_base = {seed: result for seed, result in baseline if result.completed}
    found: list[WorseOff] = []
    for seed, result in treatment:
        base = by_seed_base.get(seed)
        if base is None or not result.completed:
            continue
        base_households = {item.household_id: item for item in base.households}
        if set(base_households) != {item.household_id for item in result.households}:
            continue
        for household in result.households:
            other = base_households[household.household_id]
            for outcome in outcomes:
                treated = _metric(household, outcome)
                starting = _metric(other, outcome)
                if treated is None or starting is None:
                    continue
                if treated > starting:
                    found.append(
                        WorseOff(
                            cell_id=cell_id,
                            household_id=household.household_id,
                            seed=seed,
                            outcome=outcome,
                            baseline=starting,
                            treatment=treated,
                        )
                    )
    found.sort(key=lambda item: (item.outcome, item.seed, item.household_id))
    return tuple(found)


def _metric(household: HouseholdMetric, outcome: str) -> float | None:
    for name, value in household.values:
        if name == outcome:
            if type(value) is bool or not isinstance(value, (int, float)):
                raise ExperimentError(f"{outcome} must be numeric")
            return float(value)
    return None


def _group_label(household: HouseholdMetric, dimension: str) -> str:
    if dimension == "income_band":
        label = household.income_band
    elif dimension == "household_size":
        if type(household.household_size) is not int or household.household_size < 1:
            raise ExperimentError("household_size must be a positive int")
        label = str(household.household_size)
    elif dimension == "area_id":
        label = household.area_id
    elif dimension == "mobility":
        label = household.mobility
    elif dimension == "school_eligible":
        label = "eligible" if household.school_eligible else "not_eligible"
    else:
        raise ExperimentError(f"unknown subgroup dimension {dimension}")
    if not label:
        raise ExperimentError(f"empty subgroup label for {dimension}")
    return label
