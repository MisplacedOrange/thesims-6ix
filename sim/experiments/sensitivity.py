"""Illustrative one-at-a-time sensitivity ranges.

Every family includes a null case and an adverse case. These ranges are not
evidence that a policy succeeds. Observed operating parameters replace them
when a study says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.experiments.errors import ExperimentError


@dataclass(frozen=True)
class SensitivityLevel:
    name: str
    overrides: tuple[tuple[str, str], ...]
    evidence_state: str
    note: str


@dataclass(frozen=True)
class SensitivityFamily:
    family_id: str
    levels: tuple[SensitivityLevel, ...]


@dataclass(frozen=True)
class SensitivitySpread:
    family_id: str
    outcome: str
    level_means: tuple[tuple[str, float], ...]
    minimum: float
    maximum: float
    evidence_state: str
    cell_id: str = "baseline"
    estimand: str = "baseline outcome"


def _level(name: str, note: str, **overrides: str) -> SensitivityLevel:
    pairs = tuple(sorted(overrides.items()))
    return SensitivityLevel(name, pairs, "illustrative", note)


def default_families() -> tuple[SensitivityFamily, ...]:
    return (
        SensitivityFamily(
            "municipal_stores",
            (
                _level("null", "No municipal store is open and the subsidy is zero.", subsidy_cents="0", store_open="false"),
                _level("baseline", "Illustrative open store with a subsidy.", subsidy_cents="200", store_open="true"),
                _level(
                    "adverse",
                    "No subsidy, higher overhead, and a delayed opening.",
                    subsidy_cents="0",
                    store_open="true",
                    overhead_multiplier="2",
                    opening_delay_days="240",
                ),
            ),
        ),
        SensitivityFamily(
            "processing",
            (
                _level("null", "No extra processing capacity.", eligible_rescue_share="0", yield_share="0"),
                _level("baseline", "Illustrative eligible share and yield.", eligible_rescue_share="0.5", yield_share="0.75"),
                _level(
                    "adverse",
                    "Low eligible supply, low yield, and slow transport.",
                    eligible_rescue_share="0.1",
                    purchased_input_share="0.8",
                    yield_share="0.4",
                    transport_delay_days="5",
                ),
            ),
        ),
        SensitivityFamily(
            "school_meals",
            (
                _level("null", "No additional participation.", participation="0", substitution_share="0"),
                _level("baseline", "Illustrative participation and partial substitution.", participation="0.6", substitution_share="0.5"),
                _level(
                    "adverse",
                    "Low attendance, no home-food substitution, and a higher menu cost.",
                    participation="0.2",
                    attendance="0.5",
                    substitution_share="0",
                    menu_cost_cents="800",
                ),
            ),
        ),
        SensitivityFamily(
            "procurement",
            (
                _level("null", "No pooled discount.", discount_share="0"),
                _level("baseline", "Illustrative modest discount.", discount_share="0.05", storage_cost_cents="20"),
                _level(
                    "adverse",
                    "No discount, a large minimum order, and supplier failure.",
                    discount_share="0",
                    minimum_order_grams="100000",
                    storage_cost_cents="100",
                    supplier_failure="true",
                ),
            ),
        ),
        SensitivityFamily(
            "drones",
            (
                _level("null", "No route approval. Drone delivery is unavailable.", route_eligible="false"),
                _level("baseline", "Conditional modeling approval with ground fallback.", route_eligible="true", ground_fallback="true"),
                _level(
                    "adverse",
                    "Low payload, downtime, and failed handoff back to ground.",
                    route_eligible="true",
                    payload_grams="500",
                    downtime_share="0.5",
                    ground_fallback="true",
                    handoff_failure="true",
                ),
            ),
        ),
        SensitivityFamily(
            "households",
            (
                _level("null", "No extra price response or habit beyond the baseline score.", price_response="0", habit_bonus="0"),
                _level("baseline", "Illustrative price response and habit.", price_response="1", habit_bonus="0.4", knowledge_share="0.5"),
                _level(
                    "adverse",
                    "Tight time, strong habit, and little knowledge of the new store.",
                    income_rent_correlation="0.9",
                    time_budget_seconds="600",
                    price_response="2",
                    habit_bonus="1",
                    knowledge_share="0.1",
                ),
            ),
        ),
        SensitivityFamily(
            "human_response",
            (
                _level("null", "Proxies do not accumulate.", persistence="0", weight_food="0", weight_financial="0", weight_time="0"),
                _level("baseline", "Illustrative persistence and weights.", persistence="0.6", recovery="0.05"),
                _level(
                    "adverse",
                    "High persistence and no recovery.",
                    persistence="0.95",
                    recovery="0",
                    trust_break_loss="0.5",
                ),
            ),
        ),
    )


def families_by_id(selected: tuple[str, ...]) -> tuple[SensitivityFamily, ...]:
    catalog = {family.family_id: family for family in default_families()}
    if not selected:
        chosen = default_families()
    else:
        missing = [name for name in selected if name not in catalog]
        if missing:
            raise ExperimentError(f"unknown sensitivity family {missing[0]}")
        chosen = tuple(catalog[name] for name in selected)
    for family in chosen:
        names = {level.name for level in family.levels}
        if "null" not in names or "adverse" not in names:
            raise ExperimentError(f"{family.family_id} needs a null level and an adverse level")
    return chosen
