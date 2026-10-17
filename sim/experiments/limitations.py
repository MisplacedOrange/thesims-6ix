"""Limitations attached to every study report.

These statements are part of the result. A runner cannot omit them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Limitation:
    limitation_id: str
    statement: str


def required_limitations() -> tuple[Limitation, ...]:
    return (
        Limitation(
            "within_model",
            "Results are counterfactuals inside the declared model. They do not establish effects on real Toronto residents.",
        ),
        Limitation(
            "partial_equilibrium",
            "The model is a neighbourhood partial-equilibrium account. It does not produce employment multipliers, land prices, migration, clinical health, or Toronto GDP.",
        ),
        Limitation(
            "synthetic_population",
            "Households are synthetic records fit to aggregate controls when those controls exist. They are not reconstructed addresses or real intake records.",
        ),
        Limitation(
            "not_public_opinion",
            "Generated explanations are synthetic text grounded in the offer. They are not survey responses and they do not measure public opinion.",
        ),
        Limitation(
            "illustrative_behavior",
            "Utility coefficients, habit, knowledge limits, and latent stress, trust, and satisfaction proxies are illustrative until calibrated. The October 17, 2026 context snapshot is not a calibration set.",
        ),
        Limitation(
            "separate_uncertainties",
            "Simulation variation across seeds, parameter sensitivity, and model-form limits are separate. A narrow Monte Carlo interval does not show that the model matches Toronto.",
        ),
        Limitation(
            "no_composite_score",
            "Outcomes stay in their original units. The runner does not collapse them into a single policy score.",
        ),
        Limitation(
            "unweighted_households",
            "Households are unweighted. One record does not stand in for a large cohort.",
        ),
        Limitation(
            "cpi_not_shelf_prices",
            "National CPI is a time index. It is not a Toronto shelf-price list.",
        ),
        Limitation(
            "basket_not_spending",
            "A nutritious reference basket is not each household's observed spending.",
        ),
        Limitation(
            "foodbank_visits",
            "Food-bank visit counts are service events, not unique people or prevalence.",
        ),
        Limitation(
            "announced_not_operated",
            "Announced store, processing, and school capacity is not audited throughput. Baseline service and announced capacity stay distinct.",
        ),
        Limitation(
            "overlap",
            "School meals, rescued food, and cheaper stores can serve the same household. Interaction estimates exist so those paths are not added twice.",
        ),
        Limitation(
            "school_not_attendance",
            "School meals do not automatically raise attendance or educational attainment in this model.",
        ),
        Limitation(
            "substitution",
            "How far a school meal replaces home food is a sensitivity parameter and can be zero. The meal's procurement cost is not household cash savings.",
        ),
        Limitation(
            "drone_not_permission",
            "A drone route flag is a modeling condition. It is not Transport Canada permission, and Meituan operating times are not Toronto parameters.",
        ),
        Limitation(
            "no_approval_branch",
            "Drone studies include a no-approval case in which the corridor is unavailable.",
        ),
        Limitation(
            "short_window",
            "A 30-day run is not a school year. It omits winter, holidays, closures, and the capacity ramp of a dated rollout.",
        ),
        Limitation(
            "screening_is_hypothetical",
            "The 16-cell screen is a hypothetical mature-policy comparison. A dated rollout with approvals, staffing, and budget exhaustion is a different study.",
        ),
        Limitation(
            "receipts_do_not_transfer",
            "A choice receipt from one policy is not reused under another policy unless the observation hash still matches a legal option.",
        ),
        Limitation(
            "gateway_disabled",
            "Rule studies and gateway-disabled live studies make no provider calls. A seed does not reproduce a fresh live model response.",
        ),
        Limitation(
            "camera_not_sample",
            "The focal panel is fixed before the run. Camera or inspector selection does not change who can receive a live choice.",
        ),
        Limitation(
            "observation_time_feasibility",
            "An offer is feasible at observation time. Settlement must check cash and stock again. This package does not post journals.",
        ),
    )
