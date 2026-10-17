"""Replicated study runner.

Matched seeds and shock digests are shared across policy cells. The executor
owns the world. This module records paired differences, interactions, subgroup
rows, and sensitivity spreads, and it refuses to mark a partial run complete.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sim.behavior.determinism import STREAM_ALGORITHM
from sim.experiments.adapters import (
    HouseholdMetric,
    ReplicationRequest,
    ReplicationResult,
    RunExecutor,
    failed_result,
)
from sim.experiments.design import (
    PLANNING_SEED_BLOCKS,
    cell_id_for,
    draw_shocks,
    normalize_policies,
    screening_cells,
    seed_blocks,
    shock_digest,
)
from sim.experiments.errors import ExperimentError
from sim.experiments.limitations import Limitation, required_limitations
from sim.experiments.sensitivity import SensitivitySpread, families_by_id
from sim.experiments.subgroups import DIMENSIONS, SubgroupRow, WorseOff, subgroup_report, worse_off

SIMULATION_VARIATION_LABEL = (
    "Monte Carlo interval for simulation variation across matched seeds. "
    "This is not parameter uncertainty and it is not evidence that the model matches Toronto."
)
PARAMETER_NOTE = (
    "Parameter spreads come from the named sensitivity levels. "
    "They are separate from the Monte Carlo interval and from external validity."
)


@dataclass(frozen=True)
class StudySpec:
    study_id: str
    question: str
    population: str
    observation_window: str
    design: str
    outcomes: tuple[str, ...]
    units: tuple[tuple[str, str], ...]
    assumptions: tuple[str, ...]
    seeds: tuple[int, ...]
    agent_policy: str = "rules"
    gateway_enabled: bool = False
    treatment: tuple[str, ...] = ()
    policy_a: str = ""
    policy_b: str = ""
    explicit_cells: tuple[tuple[str, tuple[str, ...]], ...] = ()
    baseline_cell_id: str = "baseline"
    minimum_practical_difference: tuple[tuple[str, float], ...] = ()
    worse_when_higher: tuple[str, ...] = ("unmet_grams", "travel_seconds", "basket_cost_cents")
    shock_actors: tuple[str, ...] = ("district",)
    shock_days: int = 30
    shock_purposes: tuple[str, ...] = ("weather", "income")
    run_sensitivity: bool = False
    sensitivity_families: tuple[str, ...] = ()
    sensitivity_seeds: tuple[int, ...] = ()


@dataclass(frozen=True)
class PairedEstimate:
    cell_id: str
    outcome: str
    unit: str
    differences: tuple[tuple[int, float], ...]
    mean: float
    monte_carlo_low: float | None
    monte_carlo_high: float | None
    label: str
    exceeds_minimum_practical: bool | None


@dataclass(frozen=True)
class InteractionEstimate:
    policies: tuple[str, str]
    outcome: str
    unit: str
    by_seed: tuple[tuple[int, float], ...]
    mean: float


@dataclass(frozen=True)
class StoredRun:
    request: ReplicationRequest
    result: ReplicationResult


@dataclass(frozen=True)
class StudyReport:
    package_version: str
    study_id: str
    question: str
    population: str
    observation_window: str
    baseline_cell_id: str
    agent_policy: str
    gateway_enabled: bool
    stream_algorithm: str
    seeds: tuple[int, ...]
    cells: tuple[str, ...]
    paired: tuple[PairedEstimate, ...]
    interactions: tuple[InteractionEstimate, ...]
    subgroups: tuple[SubgroupRow, ...]
    worse_off: tuple[WorseOff, ...]
    sensitivity: tuple[SensitivitySpread, ...]
    simulation_variation_label: str
    parameter_uncertainty_note: str
    limitations: tuple[Limitation, ...]
    assumptions: tuple[str, ...]
    llm_dispatch_count: int
    completed_runs: int
    failed_runs: int
    failure_reasons: tuple[tuple[str, int], ...]
    economic_hashes: tuple[tuple[str, int, str], ...]
    complete: bool
    notes: tuple[str, ...]


def planning_screening_spec(**overrides: object) -> StudySpec:
    """The 16-cell, 30-seed rule study. Callers still supply the question."""

    base = dict(
        study_id="screening",
        question="How do the four mature policy switches change model outcomes?",
        population="Synthetic neighbourhood households.",
        observation_window="Declared model window. A 30-day window is not a school year.",
        design="screening",
        outcomes=("basket_cost_cents",),
        units=(("basket_cost_cents", "cents"),),
        assumptions=("Rule-based choices. Gateway disabled.",),
        seeds=seed_blocks(PLANNING_SEED_BLOCKS),
        agent_policy="rules",
        gateway_enabled=False,
    )
    base.update(overrides)
    return StudySpec(**base)  # type: ignore[arg-type]


def run_study(spec: StudySpec, executor: RunExecutor) -> StudyReport:
    from sim.experiments import PACKAGE_VERSION

    validate_spec(spec)
    notes: list[str] = []
    if spec.design == "screening" and len(spec.seeds) < PLANNING_SEED_BLOCKS:
        notes.append(
            f"Planning default is {PLANNING_SEED_BLOCKS} matched seed blocks. This run used {len(spec.seeds)}."
        )
    if not spec.minimum_practical_difference:
        notes.append("No minimum practical difference was declared, so replication count is not a finalized power target.")
    shocks_by_seed = {
        seed: draw_shocks(seed, days=spec.shock_days, actors=spec.shock_actors, purposes=spec.shock_purposes)
        for seed in spec.seeds
    }
    cells = cells_for(spec)
    stored: list[StoredRun] = []
    for cell_id, enabled in cells:
        for seed in spec.seeds:
            request = _request(spec, cell_id, enabled, seed, shocks_by_seed[seed], None, None, ())
            stored.append(StoredRun(request, _execute(spec, request, executor)))
    sensitivity_runs: list[StoredRun] = []
    if spec.run_sensitivity:
        sensitivity_seeds = spec.sensitivity_seeds or spec.seeds
        extra_seeds = [seed for seed in sensitivity_seeds if seed not in shocks_by_seed]
        for seed in extra_seeds:
            shocks_by_seed[seed] = draw_shocks(
                seed, days=spec.shock_days, actors=spec.shock_actors, purposes=spec.shock_purposes
            )
        for family in families_by_id(spec.sensitivity_families):
            for level in family.levels:
                for cell_id, enabled in cells:
                    for seed in sensitivity_seeds:
                        request = _request(spec, cell_id, enabled, seed, shocks_by_seed[seed],
                            family.family_id, level.name, level.overrides)
                        sensitivity_runs.append(StoredRun(request, _execute(spec, request, executor)))
    return _report(spec, stored, sensitivity_runs, cells, notes, PACKAGE_VERSION)


def validate_spec(spec: StudySpec) -> None:
    if not spec.study_id or not spec.question or not spec.population or not spec.observation_window:
        raise ExperimentError("a study needs an id, question, population, and observation window")
    if spec.design not in {"screening", "paired", "interaction", "explicit"}:
        raise ExperimentError(f"unknown design {spec.design}")
    if not spec.outcomes:
        raise ExperimentError("a study needs at least one outcome")
    if not spec.seeds or len(set(spec.seeds)) != len(spec.seeds):
        raise ExperimentError("seeds must be unique")
    for seed in spec.seeds:
        if type(seed) is not int or seed < 0:
            raise ExperimentError("seeds must be non-negative ints")
    if spec.agent_policy not in {"rules", "live_llm", "frozen_receipts"}:
        raise ExperimentError("unknown agent policy")
    if spec.agent_policy == "rules" and spec.gateway_enabled:
        raise ExperimentError("a rule study cannot enable the gateway")
    units = dict(spec.units)
    for outcome in spec.outcomes:
        if outcome not in units or not units[outcome]:
            raise ExperimentError(f"outcome {outcome} needs a unit")
    cells_for(spec)


def cells_for(spec: StudySpec) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if spec.design == "screening":
        cells = screening_cells()
    elif spec.design == "paired":
        treatment = normalize_policies(spec.treatment)
        if not treatment:
            raise ExperimentError("a paired study needs a treatment")
        cells = (("baseline", ()), (cell_id_for(treatment), treatment))
    elif spec.design == "interaction":
        policy_a = normalize_policies((spec.policy_a,))
        policy_b = normalize_policies((spec.policy_b,))
        if len(policy_a) != 1 or len(policy_b) != 1 or policy_a == policy_b:
            raise ExperimentError("an interaction study needs two distinct policies")
        both = normalize_policies(policy_a + policy_b)
        cells = (
            ("baseline", ()),
            (cell_id_for(policy_a), policy_a),
            (cell_id_for(policy_b), policy_b),
            (cell_id_for(both), both),
        )
    else:
        cells = tuple((cell_id, normalize_policies(enabled)) for cell_id, enabled in spec.explicit_cells)
        if not cells:
            raise ExperimentError("an explicit study needs cells")
    ids = [cell_id for cell_id, _ in cells]
    if len(ids) != len(set(ids)):
        raise ExperimentError("duplicate cell id")
    if spec.baseline_cell_id not in ids:
        raise ExperimentError("baseline cell is missing")
    return cells


def interaction_effect(outcome_ab: float, outcome_a: float, outcome_b: float, outcome_base: float) -> float:
    """``AB - A - B + baseline``."""

    return outcome_ab - outcome_a - outcome_b + outcome_base


def _request(
    spec: StudySpec,
    cell_id: str,
    enabled: tuple[str, ...],
    seed: int,
    shocks,
    family: str | None,
    level: str | None,
    overrides: tuple[tuple[str, str], ...],
) -> ReplicationRequest:
    return ReplicationRequest(
        study_id=spec.study_id,
        cell_id=cell_id,
        enabled_policies=enabled,
        seed=seed,
        stream_algorithm=STREAM_ALGORITHM,
        shock_digest=shock_digest(shocks),
        shocks=shocks,
        parameter_overrides=tuple(sorted(overrides)),
        sensitivity_family=family,
        sensitivity_level=level,
        agent_policy=spec.agent_policy,
        gateway_enabled=spec.gateway_enabled,
        outcome_names=spec.outcomes,
    )


def _execute(spec: StudySpec, request: ReplicationRequest, executor: RunExecutor) -> ReplicationResult:
    try:
        result = executor.execute(request)
    except Exception as exc:  # noqa: BLE001 â€” one failed world must not drop the rest of the study
        return failed_result(f"executor_error:{exc.__class__.__name__}", request.shock_digest)
    reasons: list[str] = []
    if result.shock_digest != request.shock_digest:
        reasons.append("shock_mismatch")
    if not spec.gateway_enabled and result.llm_dispatch_count != 0:
        reasons.append("gateway_dispatch_while_disabled")
    if result.completed:
        present = {name for name, _ in result.outcomes}
        missing = [name for name in spec.outcomes if name not in present]
        if missing:
            reasons.append("missing_outcome:" + ",".join(missing))
        try:
            _validate_households(result.households)
        except ExperimentError:
            reasons.append("invalid_household_records")
        if any(type(value) is bool or not isinstance(value, (int, float)) or not math.isfinite(value)
               for _, value in result.outcomes):
            reasons.append("invalid_outcome")
    if reasons:
        return ReplicationResult(
            completed=False,
            failure_reason=";".join(reasons) if result.failure_reason is None else result.failure_reason + ";" + ";".join(reasons),
            outcomes=result.outcomes,
            households=result.households,
            shock_digest=result.shock_digest,
            llm_dispatch_count=result.llm_dispatch_count,
            economic_hash=result.economic_hash,
        )
    if not result.completed and not result.failure_reason:
        return ReplicationResult(
            completed=False,
            failure_reason="incomplete",
            outcomes=result.outcomes,
            households=result.households,
            shock_digest=result.shock_digest,
            llm_dispatch_count=result.llm_dispatch_count,
            economic_hash=result.economic_hash,
        )
    return result


def _validate_households(households: tuple[HouseholdMetric, ...]) -> None:
    seen: set[str] = set()
    for household in households:
        if household.household_id in seen:
            raise ExperimentError("duplicate household in a replication")
        seen.add(household.household_id)


def _report(
    spec: StudySpec,
    stored: list[StoredRun],
    sensitivity_runs: list[StoredRun],
    cells: tuple[tuple[str, tuple[str, ...]], ...],
    notes: list[str],
    package_version: str,
) -> StudyReport:
    by_cell: dict[str, list[tuple[int, ReplicationResult]]] = {cell_id: [] for cell_id, _ in cells}
    for run in stored:
        by_cell[run.request.cell_id].append((run.request.seed, run.result))
    units = dict(spec.units)
    paired = _paired(spec, by_cell, units)
    interactions = _interactions(spec, cells, by_cell, units)
    subgroups: list[SubgroupRow] = []
    harmed: list[WorseOff] = []
    for cell_id, _enabled in cells:
        subgroups.extend(subgroup_report(tuple(by_cell[cell_id]), cell_id=cell_id, outcomes=spec.outcomes))
        if cell_id != spec.baseline_cell_id:
            harmed.extend(
                worse_off(
                    tuple(by_cell[spec.baseline_cell_id]),
                    tuple(by_cell[cell_id]),
                    cell_id=cell_id,
                    outcomes=spec.worse_when_higher,
                )
            )
    sensitivity = _sensitivity(spec, sensitivity_runs)
    all_runs = stored + sensitivity_runs
    failures: dict[str, int] = {}
    completed = 0
    failed = 0
    dispatches = 0
    hashes: list[tuple[str, int, str]] = []
    for run in all_runs:
        dispatches += run.result.llm_dispatch_count
        if run.result.economic_hash:
            hashes.append((run.request.cell_id, run.request.seed, run.result.economic_hash))
        if run.result.completed:
            completed += 1
        else:
            failed += 1
            reason = run.result.failure_reason or "incomplete"
            failures[reason] = failures.get(reason, 0) + 1
    if not any(result.households for _, result in by_cell[spec.baseline_cell_id]):
        notes.append("No household-level records were returned, so subgroup rows only appear when an executor supplies them.")
    return StudyReport(
        package_version=package_version,
        study_id=spec.study_id,
        question=spec.question,
        population=spec.population,
        observation_window=spec.observation_window,
        baseline_cell_id=spec.baseline_cell_id,
        agent_policy=spec.agent_policy,
        gateway_enabled=spec.gateway_enabled,
        stream_algorithm=STREAM_ALGORITHM,
        seeds=spec.seeds,
        cells=tuple(cell_id for cell_id, _ in cells),
        paired=paired,
        interactions=interactions,
        subgroups=tuple(subgroups),
        worse_off=tuple(harmed),
        sensitivity=sensitivity,
        simulation_variation_label=SIMULATION_VARIATION_LABEL,
        parameter_uncertainty_note=PARAMETER_NOTE,
        limitations=required_limitations(),
        assumptions=spec.assumptions,
        llm_dispatch_count=dispatches,
        completed_runs=completed,
        failed_runs=failed,
        failure_reasons=tuple(sorted(failures.items())),
        economic_hashes=tuple(hashes),
        complete=failed == 0,
        notes=tuple(notes),
    )


def _paired(
    spec: StudySpec,
    by_cell: dict[str, list[tuple[int, ReplicationResult]]],
    units: dict[str, str],
) -> tuple[PairedEstimate, ...]:
    thresholds = dict(spec.minimum_practical_difference)
    estimates: list[PairedEstimate] = []
    baseline = {seed: result for seed, result in by_cell[spec.baseline_cell_id]}
    for cell_id, rows in by_cell.items():
        if cell_id == spec.baseline_cell_id:
            continue
        for outcome in spec.outcomes:
            differences: list[tuple[int, float]] = []
            for seed, result in rows:
                base = baseline.get(seed)
                if base is None or not base.completed or not result.completed:
                    continue
                treated = _outcome(result, outcome)
                starting = _outcome(base, outcome)
                if treated is None or starting is None:
                    continue
                differences.append((seed, treated - starting))
            if not differences:
                continue
            mean, low, high = _monte_carlo([value for _, value in differences])
            threshold = thresholds.get(outcome)
            exceeds = None if threshold is None else abs(mean) >= threshold
            estimates.append(
                PairedEstimate(
                    cell_id=cell_id,
                    outcome=outcome,
                    unit=units[outcome],
                    differences=tuple(differences),
                    mean=mean,
                    monte_carlo_low=low,
                    monte_carlo_high=high,
                    label=SIMULATION_VARIATION_LABEL,
                    exceeds_minimum_practical=exceeds,
                )
            )
    return tuple(estimates)


def _interactions(
    spec: StudySpec,
    cells: tuple[tuple[str, tuple[str, ...]], ...],
    by_cell: dict[str, list[tuple[int, ReplicationResult]]],
    units: dict[str, str],
) -> tuple[InteractionEstimate, ...]:
    enabled = {cell_id: policies for cell_id, policies in cells}
    pairs: list[tuple[str, str]] = []
    if spec.design == "interaction":
        pairs.append((spec.policy_a, spec.policy_b))
    elif spec.design == "screening":
        for index, left in enumerate(POLICIES_ORDER()):
            for right in POLICIES_ORDER()[index + 1 :]:
                pairs.append((left, right))
    estimates: list[InteractionEstimate] = []
    for left, right in pairs:
        both = cell_id_for(normalize_policies((left, right)))
        left_id = cell_id_for(normalize_policies((left,)))
        right_id = cell_id_for(normalize_policies((right,)))
        if not {both, left_id, right_id, spec.baseline_cell_id} <= set(enabled):
            continue
        for outcome in spec.outcomes:
            by_seed: list[tuple[int, float]] = []
            for seed, _result in by_cell[both]:
                values = []
                ok = True
                for cell_id in (both, left_id, right_id, spec.baseline_cell_id):
                    result = dict(by_cell[cell_id]).get(seed)
                    if result is None or not result.completed:
                        ok = False
                        break
                    value = _outcome(result, outcome)
                    if value is None:
                        ok = False
                        break
                    values.append(value)
                if not ok:
                    continue
                by_seed.append((seed, interaction_effect(values[0], values[1], values[2], values[3])))
            if not by_seed:
                continue
            mean, _low, _high = _monte_carlo([value for _, value in by_seed])
            estimates.append(
                InteractionEstimate(
                    policies=tuple(normalize_policies((left, right))),
                    outcome=outcome,
                    unit=units[outcome],
                    by_seed=tuple(by_seed),
                    mean=mean,
                )
            )
    return tuple(estimates)


def _sensitivity(spec: StudySpec, runs: list[StoredRun]) -> tuple[SensitivitySpread, ...]:
    # Match baseline and treatment at the SAME parameter level and seed.
    # A baseline-only explicit design still reports its baseline outcome.
    results = {(r.request.sensitivity_family, r.request.sensitivity_level,
                r.request.cell_id, r.request.seed): r.result for r in runs}
    grouped = {}
    for run in runs:
        req, result = run.request, run.result
        if not result.completed:
            continue
        for outcome in spec.outcomes:
            value = _outcome(result, outcome)
            if value is None:
                continue
            if req.cell_id != spec.baseline_cell_id:
                baseline = results.get((req.sensitivity_family, req.sensitivity_level,
                                        spec.baseline_cell_id, req.seed))
                if baseline is None or not baseline.completed:
                    continue
                starting = _outcome(baseline, outcome)
                if starting is None:
                    continue
                value -= starting
            key = (req.sensitivity_family, req.cell_id, outcome, req.sensitivity_level)
            grouped.setdefault(key, []).append(value)
    spreads = []
    groups = sorted({key[:3] for key in grouped})
    for family, cell_id, outcome in groups:
        levels = sorted(key[3] for key in grouped if key[:3] == (family, cell_id, outcome))
        means = tuple((level, sum(grouped[(family, cell_id, outcome, level)]) /
                       len(grouped[(family, cell_id, outcome, level)])) for level in levels)
        spreads.append(SensitivitySpread(family, outcome, means,
            min(value for _, value in means), max(value for _, value in means),
            "illustrative", cell_id,
            "baseline outcome" if cell_id == spec.baseline_cell_id else "treatment minus matched baseline"))
    return tuple(spreads)


def _outcome(result: ReplicationResult, outcome: str) -> float | None:
    for name, value in result.outcomes:
        if name == outcome:
            if type(value) is bool or not isinstance(value, (int, float)):
                raise ExperimentError(f"{outcome} must be numeric")
            return float(value)
    return None


def _monte_carlo(values: list[float]) -> tuple[float, float | None, float | None]:
    count = len(values)
    mean = sum(values) / count
    if count < 2:
        return mean, None, None
    variance = sum((value - mean) ** 2 for value in values) / (count - 1)
    half = 1.96 * math.sqrt(variance) / math.sqrt(count)
    return mean, mean - half, mean + half


def POLICIES_ORDER() -> tuple[str, ...]:
    from sim.experiments.design import POLICIES

    return POLICIES


# Re-export the dimension list for report readers.
SUBGROUP_DIMENSIONS = DIMENSIONS
