"""Behavioural comparison keeps timeouts apart from unselected households."""

from sim.behavior.compare import DivergenceRange, compare_receipts, disproportionate_strata
from sim.behavior.draft import LABEL_RULE, ChoiceReceipt


def _receipt(**overrides: object) -> ChoiceReceipt:
    base = dict(
        schema_id="sim6ix.choice_receipt",
        schema_version="0-draft",
        review_status="DRAFT_JOINT_REVIEW_PERSON_2",
        decision_id="d-1",
        household_id="hh-1",
        revision=1,
        day_index=0,
        stratum="low",
        opportunity="shortage",
        option_id="no_purchase",
        rule_option_id="shop:store-retail:full",
        origin="llm",
        selection_reason="dispatched",
        fallback_reason=None,
        observation_hash="abc",
        prompt_version="prompt-v0",
        model_configuration="local",
        raw_response="no_purchase",
        explanation="generated",
        explanation_origin="llm_grounded",
        synthetic_label="generated from the simulation",
        cited_event_ids=(),
        input_tokens=10,
        output_tokens=2,
        reserved_charge_cad="0.01",
        actual_charge_cad="0.01",
        latency_seconds=0.4,
        utility=-1.0,
        stream_algorithm="sha256-unit-v1",
        legal_at_observation=True,
    )
    base.update(overrides)
    return ChoiceReceipt(**base)


def test_comparison_separates_selection_timeouts_and_budget_concentration():
    rows = [
        _receipt(decision_id="d-1", household_id="hh-1", stratum="low", day_index=1),
        _receipt(
            decision_id="d-2",
            household_id="hh-2",
            stratum="low",
            day_index=20,
            origin="fallback",
            selection_reason="dispatched",
            fallback_reason="late",
            option_id="shop:store-retail:full",
            explanation_origin="rule_template",
            synthetic_label=LABEL_RULE,
            latency_seconds=None,
            actual_charge_cad=None,
            input_tokens=0,
            output_tokens=0,
        ),
        _receipt(
            decision_id="d-3",
            household_id="hh-3",
            stratum="high",
            origin="rule",
            selection_reason="not_selected_for_live_barrier",
            option_id="shop:store-retail:full",
            fallback_reason=None,
            latency_seconds=None,
            actual_charge_cad=None,
            input_tokens=0,
            output_tokens=0,
        ),
        _receipt(
            decision_id="d-4",
            household_id="hh-4",
            stratum="low",
            day_index=0,
            origin="fallback",
            selection_reason="budget_exhausted",
            fallback_reason="budget_exhausted",
            option_id="shop:store-retail:full",
            latency_seconds=None,
            actual_charge_cad=None,
            input_tokens=0,
            output_tokens=0,
        ),
        _receipt(
            decision_id="d-5",
            household_id="hh-5",
            stratum="low",
            day_index=20,
            origin="fallback",
            selection_reason="budget_exhausted",
            fallback_reason="budget_exhausted",
            option_id="shop:store-retail:full",
            latency_seconds=None,
            actual_charge_cad=None,
            input_tokens=0,
            output_tokens=0,
        ),
        _receipt(
            decision_id="d-6",
            household_id="hh-6",
            stratum="low",
            day_index=21,
            origin="fallback",
            selection_reason="budget_exhausted",
            fallback_reason="budget_exhausted",
            option_id="shop:store-retail:full",
            latency_seconds=None,
            actual_charge_cad=None,
            input_tokens=0,
            output_tokens=0,
        ),
    ]
    comparison = compare_receipts(rows, divergence_range=DivergenceRange("illustrative", 0.1))
    assert comparison.timeouts == 1
    assert comparison.not_selected_for_live_barrier == 1
    assert comparison.dispatched == 2
    assert comparison.divergence_share == 1 / 6
    assert comparison.divergence_within_range is False
    assert comparison.late_days_carry_more_exhaustion is True
    assert "low" in disproportionate_strata(comparison)
    uncalibrated = compare_receipts(rows)
    assert uncalibrated.divergence_within_range is None
    assert uncalibrated.range_evidence_state == "uncalibrated"
