"""Paired-run compatibility.

A baseline and a treatment can be subtracted only when they describe the same
population, the same baseline, and the same units. Catalog version, scenario
epoch, and logistics model version are part of that contract: a difference
across them would mix two measurement systems.

Integer metrics subtract as treatment minus baseline. Rates stay rational.
A ratio that is undefined on either side does not become zero.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.logistics.errors import LogisticsError
from sim.logistics.metrics import Metric, MetricSet, Ratio


class CompatibilityError(LogisticsError):
    def __init__(self, reasons: tuple[str, ...], detail: str) -> None:
        self.reasons = reasons
        super().__init__(detail)


@dataclass(frozen=True)
class RunFingerprint:
    unit_system: str
    population_ids: tuple[str, ...]
    baseline_id: str
    catalog_version: str
    epoch_second: int
    model_version: str


@dataclass(frozen=True)
class LogisticsOutcome:
    fingerprint: RunFingerprint
    metrics: MetricSet
    economic_hash: str


@dataclass(frozen=True)
class MetricDelta:
    name: str
    unit: str
    baseline: int
    treatment: int
    difference: int


@dataclass(frozen=True)
class RatioDelta:
    name: str
    numerator_unit: str
    denominator_unit: str
    baseline_numerator: int
    baseline_denominator: int
    treatment_numerator: int
    treatment_denominator: int
    difference_numerator: int
    difference_denominator: int
    defined: bool


@dataclass(frozen=True)
class PairedDifference:
    """Treatment minus baseline. Integer differences keep their unit."""

    fingerprint: RunFingerprint
    metrics: tuple[MetricDelta, ...]
    ratios: tuple[RatioDelta, ...]


def paired_difference(baseline: LogisticsOutcome, treatment: LogisticsOutcome) -> PairedDifference:
    """Reject incompatible runs. Otherwise subtract treatment from baseline."""

    reasons = _fingerprint_reasons(baseline.fingerprint, treatment.fingerprint)
    metric_reasons, deltas = _metric_deltas(baseline.metrics, treatment.metrics)
    ratio_reasons, ratio_deltas = _ratio_deltas(baseline.metrics, treatment.metrics)
    reasons.extend(metric_reasons)
    reasons.extend(ratio_reasons)
    if reasons:
        unique = tuple(dict.fromkeys(reasons))
        raise CompatibilityError(unique, "paired runs are incompatible: " + ", ".join(unique))
    return PairedDifference(baseline.fingerprint, tuple(deltas), tuple(ratio_deltas))


def _fingerprint_reasons(baseline: RunFingerprint, treatment: RunFingerprint) -> list[str]:
    reasons: list[str] = []
    if baseline.unit_system != treatment.unit_system:
        reasons.append("units")
    if tuple(sorted(baseline.population_ids)) != tuple(sorted(treatment.population_ids)):
        reasons.append("population")
    if baseline.baseline_id != treatment.baseline_id:
        reasons.append("baseline")
    if baseline.catalog_version != treatment.catalog_version:
        reasons.append("catalog")
    if baseline.epoch_second != treatment.epoch_second:
        reasons.append("epoch")
    if baseline.model_version != treatment.model_version:
        reasons.append("model_version")
    return reasons


def _metric_deltas(baseline: MetricSet, treatment: MetricSet) -> tuple[list[str], list[MetricDelta]]:
    reasons: list[str] = []
    left = {item.name: item for item in baseline.integers()}
    right = {item.name: item for item in treatment.integers()}
    if set(left) != set(right):
        reasons.append("metric_set")
        return reasons, []
    deltas: list[MetricDelta] = []
    for name in sorted(left):
        before = left[name]
        after = right[name]
        if before.unit != after.unit:
            reasons.append("units")
            continue
        deltas.append(
            MetricDelta(
                name=name,
                unit=before.unit,
                baseline=before.value,
                treatment=after.value,
                difference=after.value - before.value,
            )
        )
    return reasons, deltas


def _ratio_deltas(baseline: MetricSet, treatment: MetricSet) -> tuple[list[str], list[RatioDelta]]:
    reasons: list[str] = []
    left = {item.name: item for item in baseline.ratios}
    right = {item.name: item for item in treatment.ratios}
    if set(left) != set(right):
        reasons.append("metric_set")
        return reasons, []
    deltas: list[RatioDelta] = []
    for name in sorted(left):
        before = left[name]
        after = right[name]
        if before.numerator_unit != after.numerator_unit or before.denominator_unit != after.denominator_unit:
            reasons.append("units")
            continue
        deltas.append(_one_ratio(before, after))
    return reasons, deltas


def _one_ratio(baseline: Ratio, treatment: Ratio) -> RatioDelta:
    defined = baseline.defined and treatment.defined
    if defined:
        difference_numerator = (
            treatment.numerator * baseline.denominator - baseline.numerator * treatment.denominator
        )
        difference_denominator = treatment.denominator * baseline.denominator
    else:
        difference_numerator = 0
        difference_denominator = 0
    return RatioDelta(
        name=baseline.name,
        numerator_unit=baseline.numerator_unit,
        denominator_unit=baseline.denominator_unit,
        baseline_numerator=baseline.numerator,
        baseline_denominator=baseline.denominator,
        treatment_numerator=treatment.numerator,
        treatment_denominator=treatment.denominator,
        difference_numerator=difference_numerator,
        difference_denominator=difference_denominator,
        defined=defined,
    )


def delta_by_name(difference: PairedDifference, name: str) -> MetricDelta:
    for item in difference.metrics:
        if item.name == name:
            return item
    raise KeyError(name)
