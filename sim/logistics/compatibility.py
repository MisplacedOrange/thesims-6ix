"""Paired runs must share a kernel, a catalog, and a population."""

from __future__ import annotations

from dataclasses import dataclass

from sim.core import Metric, paired_difference


@dataclass(frozen=True, slots=True)
class RunIdentity:
    kernel_version: str
    catalog_sha256: str
    population_hash: str


def compare_paired(
    baseline: tuple[Metric, ...],
    treatment: tuple[Metric, ...],
    baseline_id: RunIdentity,
    treatment_id: RunIdentity,
) -> tuple[Metric, ...]:
    if baseline_id.kernel_version != treatment_id.kernel_version:
        raise ValueError("kernel version mismatch")
    if baseline_id.catalog_sha256 != treatment_id.catalog_sha256:
        raise ValueError("catalog hash mismatch")
    if baseline_id.population_hash != treatment_id.population_hash:
        raise ValueError("population hash mismatch")
    return paired_difference(baseline, treatment)
