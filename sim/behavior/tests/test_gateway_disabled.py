"""The choice path runs with the provider gateway disabled."""

from decimal import Decimal

import pytest

from sim.behavior.adapters import DisabledGateway
from sim.behavior.coordinator import (
    POLICY_LIVE,
    POLICY_RULES,
    BehaviorConfig,
    resolve_barrier,
)
from sim.behavior.draft import ORIGIN_FALLBACK, ORIGIN_RULE
from sim.behavior.errors import BehaviorError
from sim.behavior.panel import RosterHousehold, select_focal_panel
from sim.behavior.tests.support import panel_of, shopping_context
from sim.behavior.utility import UtilityCoefficients


class BombGateway:
    def dispatch_barrier(self, requests, *, deadline_seconds: float):
        raise AssertionError("gateway dispatch leaked")


def _quiet():
    return UtilityCoefficients(noise_amplitude=0)


def test_rule_policy_never_calls_the_gateway():
    ctx = shopping_context()
    panel = panel_of(("hh-1", "low"))
    resolution = resolve_barrier(
        (ctx,),
        config=BehaviorConfig(agent_policy=POLICY_RULES, gateway_enabled=False, coefficients=_quiet()),
        panel=panel,
        master_seed=1,
        gateway=BombGateway(),
    )
    receipt = resolution.receipts[0]
    assert resolution.gateway_dispatch_calls == 0
    assert receipt.origin == ORIGIN_RULE
    assert receipt.fallback_reason is None
    assert receipt.selection_reason == "rule_policy"
    assert receipt.option_id == "shop:store-retail:full"
    assert receipt.explanation_origin == "rule_template"
    assert "evt-1" in receipt.explanation
    assert receipt.input_tokens == 0
    assert receipt.legal_at_observation is True


def test_live_study_with_gateway_disabled_falls_back_without_a_timeout():
    contexts = tuple(
        shopping_context(
            decision_id=f"d-{name}",
            opportunity="unfamiliar_store",
            household=_household(name),
        )
        for name in ("hh-a", "hh-b", "hh-c", "hh-d", "hh-e")
    )
    panel = panel_of(*((name, "low") for name in ("hh-a", "hh-b", "hh-c", "hh-d", "hh-e")))
    resolution = resolve_barrier(
        contexts,
        config=BehaviorConfig(agent_policy=POLICY_LIVE, gateway_enabled=False, coefficients=_quiet()),
        panel=panel,
        master_seed=2,
        gateway=BombGateway(),
    )
    assert resolution.gateway_dispatch_calls == 0
    assert resolution.dispatched_decision_ids == ()
    reasons = {receipt.household_id: receipt.selection_reason for receipt in resolution.receipts}
    assert sum(reason == "gateway_disabled" for reason in reasons.values()) == 4
    assert sum(reason == "not_selected_for_live_barrier" for reason in reasons.values()) == 1
    for receipt in resolution.receipts:
        assert receipt.origin in {ORIGIN_FALLBACK, ORIGIN_RULE}
        assert receipt.fallback_reason != "late"
        assert receipt.option_id == receipt.rule_option_id
        if receipt.selection_reason == "not_selected_for_live_barrier":
            assert receipt.origin == ORIGIN_RULE
        if receipt.selection_reason == "gateway_disabled":
            assert receipt.origin == ORIGIN_FALLBACK
            assert receipt.fallback_reason == "gateway_disabled"


def test_disabled_gateway_object_raises_if_called_directly():
    with pytest.raises(RuntimeError, match="disabled"):
        DisabledGateway().dispatch_barrier((), deadline_seconds=10)


def test_unbounded_price_does_not_dispatch():
    ctx = shopping_context(opportunity="shortage")
    resolution = resolve_barrier(
        (ctx,),
        config=BehaviorConfig(
            agent_policy=POLICY_LIVE,
            gateway_enabled=True,
            token_price=None,
            coefficients=_quiet(),
        ),
        panel=panel_of(("hh-1", "low")),
        master_seed=1,
        gateway=BombGateway(),
    )
    receipt = resolution.receipts[0]
    assert receipt.fallback_reason == "unbounded_charges"
    assert resolution.gateway_dispatch_calls == 0


def test_routine_opportunity_stays_on_rules_inside_a_live_study():
    ctx = shopping_context(opportunity="routine_shop")
    resolution = resolve_barrier(
        (ctx,),
        config=BehaviorConfig(agent_policy=POLICY_LIVE, gateway_enabled=False, coefficients=_quiet()),
        panel=panel_of(("hh-1", "low")),
        master_seed=1,
        gateway=BombGateway(),
    )
    receipt = resolution.receipts[0]
    assert receipt.selection_reason == "not_a_live_opportunity"
    assert receipt.origin == ORIGIN_RULE
    assert receipt.fallback_reason is None


def test_retry_and_ceiling_overrides_are_rejected():
    with pytest.raises(BehaviorError):
        resolve_barrier(
            (shopping_context(),),
            config=BehaviorConfig(automatic_retries=1),
            panel=panel_of(("hh-1", "low")),
            master_seed=1,
        )
    with pytest.raises(BehaviorError):
        resolve_barrier(
            (shopping_context(),),
            config=BehaviorConfig(run_budget_cad=Decimal("30.01")),
            panel=panel_of(("hh-1", "low")),
            master_seed=1,
        )
    with pytest.raises(BehaviorError):
        select_focal_panel((RosterHousehold("hh-1", "low"),), seed=1, max_focal=41)


def _household(household_id: str):
    household = shopping_context().household
    return household.__class__(**{**household.__dict__, "household_id": household_id})
