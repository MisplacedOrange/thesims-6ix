"""Text rendering of a study report.

The opening states the question, the modeled population, the baseline, and the
result. Limitations stay beside the numbers. A partial run does not receive a
completion marker.
"""

from __future__ import annotations

from sim.experiments.runner import StudyReport


def render_report(report: StudyReport) -> str:
    lines = [
        f"# {report.study_id}",
        "",
        f"Question: {report.question}",
        f"Modeled population: {report.population}",
        f"Observation window: {report.observation_window}",
        f"Baseline cell: {report.baseline_cell_id}",
        f"Agent policy: {report.agent_policy}",
        f"Gateway enabled: {str(report.gateway_enabled).lower()}",
        f"Stream algorithm: {report.stream_algorithm}",
        f"Seeds: {', '.join(str(seed) for seed in report.seeds)}",
        "",
        "These figures are model estimates for the declared synthetic population.",
        "They do not establish effects on real Toronto residents.",
        "",
        "## Paired differences",
        "",
    ]
    if not report.paired:
        lines.append("No completed paired differences were available.")
    for estimate in report.paired:
        lines.append(
            f"- {estimate.cell_id} / {estimate.outcome}: mean difference {estimate.mean} {estimate.unit}."
        )
        if estimate.monte_carlo_low is None:
            lines.append(f"  One seed only, so simulation variation is not estimated. {estimate.label}")
        else:
            lines.append(
                f"  Monte Carlo interval {estimate.monte_carlo_low} to {estimate.monte_carlo_high}. {estimate.label}"
            )
        if estimate.exceeds_minimum_practical is True:
            lines.append("  The mean difference meets the declared minimum practical difference.")
        elif estimate.exceeds_minimum_practical is False:
            lines.append("  The mean difference is below the declared minimum practical difference.")
    lines.extend(["", "## Interactions", ""])
    if not report.interactions:
        lines.append("No two-policy interaction was estimated.")
    for item in report.interactions:
        joined = " and ".join(item.policies)
        lines.append(f"- {joined} / {item.outcome}: mean interaction {item.mean} {item.unit}.")
    lines.extend(["", "## Subgroups", ""])
    if not report.subgroups:
        lines.append("No household-level records were returned.")
    else:
        lines.append("Households are unweighted. Dimensions: income band, household size, area, mobility, school eligibility.")
        for row in report.subgroups:
            lines.append(
                f"- {row.cell_id} / {row.dimension}={row.group} / {row.outcome}: "
                f"n={row.count}, mean={row.mean}, min={row.minimum}, max={row.maximum}."
            )
    lines.extend(["", "## Households with a higher burden", ""])
    if not report.worse_off:
        lines.append("No household-seed record showed a higher value on a burden outcome.")
    for item in report.worse_off:
        lines.append(
            f"- {item.cell_id} seed {item.seed} {item.household_id} {item.outcome}: "
            f"{item.baseline} baseline, {item.treatment} treatment."
        )
    lines.extend(["", "## Sensitivity", "", report.parameter_uncertainty_note, ""])
    if not report.sensitivity:
        lines.append("No sensitivity levels were run.")
    for spread in report.sensitivity:
        rendered = ", ".join(f"{name}={value}" for name, value in spread.level_means)
        lines.append(
            f"- {spread.family_id} / {spread.cell_id} / {spread.outcome} [{spread.estimand}] ({spread.evidence_state}): {rendered}. "
            f"Spread {spread.minimum} to {spread.maximum}."
        )
    lines.extend(["", "## Simulation variation and parameter uncertainty", "", report.simulation_variation_label, ""])
    lines.extend(["## Limitations", ""])
    for limitation in report.limitations:
        lines.append(f"- {limitation.limitation_id}: {limitation.statement}")
    lines.extend(["", "## Run status", ""])
    lines.append(f"Completed replications: {report.completed_runs}.")
    lines.append(f"Failed replications: {report.failed_runs}.")
    lines.append(f"LLM dispatches recorded by executors: {report.llm_dispatch_count}.")
    if report.complete:
        lines.append("Completion marker: complete.")
    else:
        lines.append("Completion marker: omitted because at least one replication failed.")
    for note in report.notes:
        lines.append(note)
    lines.append("")
    return "\n".join(lines)
