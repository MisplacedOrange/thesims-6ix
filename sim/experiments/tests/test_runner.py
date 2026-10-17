"""Replication design, matched shocks, and report determinism."""

from sim.behavior.adapters import DisabledGateway
from sim.behavior.coordinator import BehaviorConfig, resolve_barrier
from sim.behavior.offers import build_choice_offer
from sim.behavior.panel import RosterHousehold, select_focal_panel
from sim.behavior.snapshot import RouteInfo, StoreInfo, StoreShelf
from sim.behavior.tests.support import shopping_context
from sim.behavior.utility import UtilityCoefficients
from sim.experiments.adapters import HouseholdMetric, ReplicationResult
from sim.experiments.design import SCREENING_CELLS, cell_id_for, screening_cells, seed_blocks
from sim.experiments.limitations import required_limitations
from sim.experiments.report import render_report
from sim.experiments.errors import ExperimentError
from sim.experiments.runner import StudySpec, interaction_effect, planning_screening_spec, run_study

import pytest
from sim.experiments.sensitivity import default_families


class EchoExecutor:
    def __init__(self, values: dict[tuple[str, int], float], households=None, dispatch: int = 0, digest: str | None = None):
        self.values = values
        self.households = households or ()
        self.dispatch = dispatch
        self.digest = digest
        self.calls = []

    def execute(self, request):
        self.calls.append(request)
        if request.cell_id not in {cell for cell, _seed in self.values} and self.values:
            value = next(iter(self.values.values()))
        else:
            value = self.values.get((request.cell_id, request.seed), 0)
        if any(pair[0] == "store_open" and pair[1] == "false" for pair in request.parameter_overrides):
            value = 0
        elif request.parameter_overrides:
            value = value + 1
        return ReplicationResult(
            completed=True,
            failure_reason=None,
            outcomes=tuple((name, value) for name in request.outcome_names),
            households=self.households,
            shock_digest=self.digest if self.digest is not None else request.shock_digest,
            llm_dispatch_count=self.dispatch,
            economic_hash=f"hash-{request.cell_id}-{request.seed}",
        )


def test_screening_has_sixteen_cells_and_thirty_seed_blocks():
    cells = screening_cells()
    assert len(cells) == SCREENING_CELLS == 16
    assert cells[0] == ("baseline", ())
    assert cell_id_for(("school", "groceries")) == "groceries+school"
    assert cells[-1][0] == "groceries+processing+school+drones"
    assert seed_blocks() == tuple(range(1, 31))
    assert len(cells) * len(seed_blocks()) == 480


def test_a_rule_study_cannot_enable_the_gateway():
    spec = planning_screening_spec(gateway_enabled=True, seeds=(1,))
    with pytest.raises(ExperimentError, match="gateway"):
        run_study(spec, EchoExecutor({}))


def test_interaction_identity():
    assert interaction_effect(6, 7, 8, 10) == 1


def test_screening_run_is_deterministic_and_matches_shocks_across_policies():
    spec = planning_screening_spec()
    executor = EchoExecutor({})
    first = run_study(spec, executor)
    second_executor = EchoExecutor({})
    second = run_study(spec, second_executor)
    assert len(executor.calls) == 480
    assert first == second
    assert first.complete is True
    assert first.llm_dispatch_count == 0
    assert all(call.gateway_enabled is False and call.agent_policy == "rules" for call in executor.calls)
    digests: dict[int, str] = {}
    for call in executor.calls:
        digests.setdefault(call.seed, call.shock_digest)
        assert call.shock_digest == digests[call.seed]
        assert "groceries" not in call.shock_digest
    assert len(digests) == 30
    assert len(set(digests.values())) == 30
    text = render_report(first)
    assert "do not establish effects on real Toronto residents" in text
    assert "Completion marker: complete." in text
    assert {item.limitation_id for item in required_limitations()} <= {item.limitation_id for item in first.limitations}


def test_paired_difference_subgroups_and_practical_threshold():
    spec = StudySpec(
        study_id="groceries-paired",
        question="How does a municipal store change basket cost inside the model?",
        population="Synthetic neighbourhood households.",
        observation_window="30 model days",
        design="paired",
        outcomes=("basket_cost_cents",),
        units=(("basket_cost_cents", "cents"),),
        assumptions=("Rule choices. Gateway disabled.",),
        seeds=(1, 2),
        treatment=("groceries",),
        minimum_practical_difference=(("basket_cost_cents", 50),),
    )
    households = (
        HouseholdMetric("hh-low", "low", 2, "area-north", "unconstrained", True, (("basket_cost_cents", 100), ("unmet_grams", 4))),
        HouseholdMetric("hh-high", "high", 4, "area-south", "constrained", False, (("basket_cost_cents", 80), ("unmet_grams", 0))),
    )
    treatment_households = (
        HouseholdMetric("hh-low", "low", 2, "area-north", "unconstrained", True, (("basket_cost_cents", 90), ("unmet_grams", 6))),
        HouseholdMetric("hh-high", "high", 4, "area-south", "constrained", False, (("basket_cost_cents", 80), ("unmet_grams", 0))),
    )

    class Paired(EchoExecutor):
        def execute(self, request):
            self.calls.append(request)
            cost = 100 if request.cell_id == "baseline" else 97
            people = households if request.cell_id == "baseline" else treatment_households
            return ReplicationResult(
                True,
                None,
                (("basket_cost_cents", cost),),
                people,
                request.shock_digest,
                0,
                None,
            )

    report = run_study(spec, Paired({}))
    estimate = report.paired[0]
    assert estimate.cell_id == "groceries"
    assert estimate.mean == -3
    assert estimate.unit == "cents"
    assert estimate.exceeds_minimum_practical is False
    assert estimate.monte_carlo_low == estimate.monte_carlo_high == -3
    dimensions = {row.dimension for row in report.subgroups}
    assert dimensions == {"income_band", "household_size", "area_id", "mobility", "school_eligible"}
    harmed = [item for item in report.worse_off if item.outcome == "unmet_grams"]
    assert {item.household_id for item in harmed} == {"hh-low"}
    assert report.complete is True


def test_interaction_study_reports_the_cross_term():
    spec = StudySpec(
        study_id="meals-and-groceries",
        question="Do school meals and a municipal store interact inside the model?",
        population="Synthetic neighbourhood households.",
        observation_window="30 model days",
        design="interaction",
        outcomes=("basket_cost_cents",),
        units=(("basket_cost_cents", "cents"),),
        assumptions=("Equal seeds and equal external shocks.",),
        seeds=(4, 5),
        policy_a="groceries",
        policy_b="school",
    )
    values = {"baseline": 10, "groceries": 7, "school": 8, "groceries+school": 6}

    class Interaction(EchoExecutor):
        def execute(self, request):
            self.calls.append(request)
            return ReplicationResult(
                True,
                None,
                (("basket_cost_cents", values[request.cell_id]),),
                (),
                request.shock_digest,
                0,
                None,
            )

    report = run_study(spec, Interaction({}))
    assert report.interactions[0].mean == 1
    assert report.interactions[0].policies == ("groceries", "school")


def test_sensitivity_includes_null_and_adverse_cases():
    for family in default_families():
        names = {level.name for level in family.levels}
        assert {"null", "adverse"} <= names
    spec = StudySpec(
        study_id="sensitivity",
        question="How far does the basket cost move across illustrative store assumptions?",
        population="Synthetic neighbourhood households.",
        observation_window="30 model days",
        design="explicit",
        outcomes=("basket_cost_cents",),
        units=(("basket_cost_cents", "cents"),),
        assumptions=("One factor at a time.",),
        seeds=(1,),
        explicit_cells=(("baseline", ()),),
        run_sensitivity=True,
        sensitivity_families=("municipal_stores",),
    )
    report = run_study(spec, EchoExecutor({("baseline", 1): 10}))
    spread = report.sensitivity[0]
    levels = dict(spread.level_means)
    assert {"null", "adverse", "baseline"} <= set(levels)
    assert levels["null"] != levels["baseline"]
    assert spread.evidence_state == "illustrative"
    assert report.parameter_uncertainty_note != report.simulation_variation_label


def test_failed_replications_omit_the_completion_marker():
    spec = StudySpec(
        study_id="broken",
        question="What is recorded when a replication fails?",
        population="Synthetic neighbourhood households.",
        observation_window="30 model days",
        design="paired",
        outcomes=("basket_cost_cents",),
        units=(("basket_cost_cents", "cents"),),
        assumptions=(),
        seeds=(1,),
        treatment=("drones",),
    )
    mismatched = run_study(spec, EchoExecutor({("baseline", 1): 1, ("drones", 1): 1}, digest="not-the-shock"))
    assert mismatched.complete is False
    assert "shock_mismatch" in mismatched.failure_reasons[0][0]
    assert "omitted" in render_report(mismatched)
    leaked = run_study(spec, EchoExecutor({("baseline", 1): 1, ("drones", 1): 1}, dispatch=1))
    assert leaked.llm_dispatch_count == 2
    assert leaked.complete is False
    assert any("gateway_dispatch_while_disabled" in reason for reason, _count in leaked.failure_reasons)


def test_gateway_disabled_behavior_run_changes_the_grocery_outcome():
    spec = StudySpec(
        study_id="behavior-paired",
        question="Does the rule policy buy from a visible municipal store?",
        population="One synthetic household.",
        observation_window="1 model day",
        design="paired",
        outcomes=("basket_cost_cents",),
        units=(("basket_cost_cents", "cents"),),
        assumptions=("Gateway disabled.",),
        seeds=(1, 2),
        treatment=("groceries",),
        shock_days=1,
    )

    class BehaviorExecutor:
        def __init__(self):
            self.calls = []

        def execute(self, request):
            self.calls.append(request)
            ctx = _context("groceries" in request.enabled_policies)
            panel = select_focal_panel((RosterHousehold("hh-1", "low"),), seed=request.seed, max_focal=1)
            resolution = resolve_barrier(
                (ctx,),
                config=BehaviorConfig(
                    agent_policy="rules",
                    gateway_enabled=False,
                    coefficients=UtilityCoefficients(noise_amplitude=0),
                ),
                panel=panel,
                master_seed=request.seed,
                gateway=DisabledGateway(),
            )
            offer = build_choice_offer(ctx, UtilityCoefficients(noise_amplitude=0))
            chosen = next(option for option in offer.options if option.option_id == resolution.receipts[0].option_id)
            return ReplicationResult(
                True,
                None,
                (("basket_cost_cents", chosen.expected_payment_cents),),
                (
                    HouseholdMetric(
                        "hh-1",
                        "low",
                        2,
                        "area-north",
                        "unconstrained",
                        True,
                        (("basket_cost_cents", chosen.expected_payment_cents), ("unmet_grams", 0)),
                    ),
                ),
                request.shock_digest,
                resolution.gateway_dispatch_calls,
                resolution.receipts[0].observation_hash,
            )

    executor = BehaviorExecutor()
    report = run_study(spec, executor)
    again = run_study(spec, BehaviorExecutor())
    assert report == again
    assert report.complete is True
    assert report.llm_dispatch_count == 0
    assert report.paired[0].mean == -280
    assert all(call.gateway_enabled is False for call in executor.calls)
    assert "Gateway enabled: false" in render_report(report)


def _context(municipal: bool):
    base = shopping_context()
    if not municipal:
        return base
    return shopping_context(
        stores=base.stores + (StoreInfo("store-city", 0, 100_000, True, True),),
        shelves=base.shelves
        + (
            StoreShelf("store-city", "staple", 5_000, 50, None, 0.4, 0),
            StoreShelf("store-city", "produce", 5_000, 40, None, 0.4, 0),
        ),
        routes=base.routes + (RouteInfo("store-city", 600, True, "walk"),),
    )
