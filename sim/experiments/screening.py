"""Matched-seed screening totals.

The planning catalog calls for 16 cells and 30 seed blocks, 480 runs.
This report executes the 16 cells at the seeds it is given. The default
demonstration uses two seeds. It does not re-simulate the 250-household
week 480 times.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sim.core import CAD_CENTS, Metric, paired_difference, sha256_hex

SWITCHES = ("groceries", "processing", "school", "drones")
PLANNED_SEED_BLOCKS = 30
PLANNED_RUNS = 16 * PLANNED_SEED_BLOCKS


@dataclass(frozen=True, slots=True)
class CellResult:
    enabled: tuple[str, ...]
    seed: int
    household_payment_cents: int
    fiscal_outlay_cents: int


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    study_id: str
    question: str
    evidence_state: str
    seeds: tuple[int, ...]
    planned_runs: int
    executed_runs: int
    interaction_cents: int
    cells: tuple[CellResult, ...]
    limitations: tuple[str, ...]
    report_hash: str


def all_cells() -> tuple[tuple[str, ...], ...]:
    cells = []
    for mask in range(16):
        enabled = tuple(switch for bit, switch in enumerate(SWITCHES) if mask & (1 << bit))
        cells.append(enabled)
    return tuple(cells)


def shock_cents(seed: int) -> int:
    digest = hashlib.sha256(f"{seed}|screening|shock".encode("utf-8")).digest()
    return digest[0] % 5


def cell_outcome(enabled: tuple[str, ...], seed: int) -> CellResult:
    noise = shock_cents(seed)
    payment = 200 + noise
    fiscal = 0
    turned = set(enabled)
    if "groceries" in turned:
        payment -= 80
        fiscal += 580
    if "school" in turned:
        payment -= 50
        fiscal += 115
    if "groceries" in turned and "school" in turned:
        payment += 30
    if "processing" in turned:
        fiscal += 220
    if "drones" in turned:
        fiscal += 1200
    return CellResult(tuple(enabled), seed, payment, fiscal)


def interaction(cells: tuple[CellResult, ...], seed: int) -> int:
    by_key = {result.enabled: result for result in cells if result.seed == seed}

    def payment(names: tuple[str, ...]) -> int:
        return by_key[tuple(sorted(names, key=SWITCHES.index))].household_payment_cents

    both = payment(("groceries", "school"))
    groceries = payment(("groceries",))
    school = payment(("school",))
    baseline = payment(())
    return both - groceries - school + baseline


def run_screening(seeds: tuple[int, ...] = (17, 18)) -> ExperimentReport:
    if not seeds:
        raise ValueError("at least one seed is required")
    cells = []
    for seed in seeds:
        for enabled in all_cells():
            cells.append(cell_outcome(enabled, seed))
    ordered = tuple(cells)
    interactions = {seed: interaction(ordered, seed) for seed in seeds}
    if len(set(interactions.values())) != 1:
        raise RuntimeError("matched seeds did not share an interaction")
    limitations = (
        "illustrative screening totals, not a causal estimate for Toronto residents",
        "16 cells by 30 seed blocks would be 480 runs; this report executes only the seeds it is given",
        "the 250-household week is not repeated inside every cell",
        "the LLM gateway is disabled; these totals use the declared rule outcome",
        "no Toronto drone route approval is established",
        "price_base_month is null",
    )
    body = {
        "study_id": "screening-v1",
        "seeds": seeds,
        "planned_runs": PLANNED_RUNS,
        "executed_runs": len(ordered),
        "interaction_cents": interactions[seeds[0]],
        "cells": [
            {
                "enabled": result.enabled,
                "seed": result.seed,
                "household_payment_cents": result.household_payment_cents,
                "fiscal_outlay_cents": result.fiscal_outlay_cents,
            }
            for result in ordered
        ],
        "limitations": limitations,
    }
    return ExperimentReport(
        study_id="screening-v1",
        question="Within the model, how do the four switches change household payment and fiscal outlay?",
        evidence_state="illustrative",
        seeds=tuple(seeds),
        planned_runs=PLANNED_RUNS,
        executed_runs=len(ordered),
        interaction_cents=interactions[seeds[0]],
        cells=ordered,
        limitations=limitations,
        report_hash=sha256_hex(body),
    )


def payment_metrics(report: ExperimentReport, seed: int) -> tuple[Metric, ...]:
    rows = [result for result in report.cells if result.seed == seed]
    return tuple(
        Metric("+".join(result.enabled) or "baseline", result.household_payment_cents, CAD_CENTS) for result in rows
    )


def compare_seed_payments(report: ExperimentReport) -> tuple[Metric, ...]:
    if len(report.seeds) != 2:
        raise ValueError("this comparison expects two seeds")
    return paired_difference(payment_metrics(report, report.seeds[0]), payment_metrics(report, report.seeds[1]))
