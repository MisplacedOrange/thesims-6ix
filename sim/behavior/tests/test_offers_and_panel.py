"""Legal offers, knowledge limits, panel rotation, and provider fallbacks."""

from decimal import Decimal

from sim.behavior.budget import MemoryChargeReservation, TokenPrice, estimate_max_request_cad
from sim.behavior.coordinator import POLICY_FROZEN, POLICY_LIVE, BehaviorConfig, RecordedChoice, resolve_barrier
from sim.behavior.draft import ORIGIN_LLM, ORIGIN_RECORDED, GatewayResponse
from sim.behavior.errors import BehaviorError
from sim.behavior.latent import LatentCoefficients, LatentState, update_latent
from sim.behavior.offers import build_choice_offer
from sim.behavior.panel import allocate_seats, predeclare_live_subset
from sim.behavior.snapshot import StoreInfo, StoreShelf
from sim.behavior.tests.support import delivery_offer, panel_of, school_offer, shopping_context
from sim.behavior.utility import UtilityCoefficients

import pytest


def _quiet():
    return UtilityCoefficients(noise_amplitude=0)


def test_unknown_store_is_omitted_and_a_public_store_is_offered():
    base = shopping_context()
    cheap = shopping_context(
        stores=base.stores + (StoreInfo("store-cheap", 0, 100_000, False, False),),
        shelves=base.shelves
        + (
            StoreShelf("store-cheap", "staple", 5_000, 1, None, 0.9, 0),
            StoreShelf("store-cheap", "produce", 5_000, 1, None, 0.9, 0),
        ),
        routes=base.routes + (base.routes[0].__class__("store-cheap", 600, True, "walk"),),
    )
    hidden = build_choice_offer(cheap, _quiet())
    assert all(option.store_id != "store-cheap" for option in hidden.options)
    public = shopping_context(
        stores=base.stores + (StoreInfo("store-city", 0, 100_000, True, True),),
        shelves=base.shelves
        + (
            StoreShelf("store-city", "staple", 5_000, 50, None, 0.4, 0),
            StoreShelf("store-city", "produce", 5_000, 40, None, 0.4, 0),
        ),
        routes=base.routes + (base.routes[0].__class__("store-city", 600, True, "walk"),),
    )
    offer = build_choice_offer(public, _quiet())
    assert "shop:store-city:full" in {option.option_id for option in offer.options}


def test_closed_expired_unaffordable_and_inaccessible_trips_are_absent():
    closed = build_choice_offer(shopping_context(stores=(StoreInfo("store-retail", 0, 100, False, False),)), _quiet())
    assert {option.option_id for option in closed.options} == {"delay_purchase", "no_purchase"}
    arrival = 28_800 + 600
    expired = shopping_context(
        shelves=(
            StoreShelf("store-retail", "staple", 5_000, 100, arrival, 0.8, 0),
            StoreShelf("store-retail", "produce", 5_000, 80, None, 0.8, 0),
        )
    )
    expired_offer = build_choice_offer(expired, _quiet())
    assert "shop:store-retail:full" not in {option.option_id for option in expired_offer.options}
    poor = shopping_context(
        household=shopping_context().household.__class__(
            **{**shopping_context().household.__dict__, "spendable_cash_cents": 100}
        )
    )
    poor_offer = build_choice_offer(poor, _quiet())
    assert {option.kind for option in poor_offer.options} <= {"delay_purchase", "no_purchase"}
    blocked = shopping_context(routes=(shopping_context().routes[0].__class__("store-retail", 600, False, "walk"),))
    blocked_offer = build_choice_offer(blocked, _quiet())
    assert "shop:store-retail:full" not in {option.option_id for option in blocked_offer.options}


def test_explicit_credit_can_fund_a_basket_and_school_meal_is_not_a_purchase():
    funded = shopping_context(
        household=shopping_context().household.__class__(
            **{
                **shopping_context().household.__dict__,
                "spendable_cash_cents": 100,
                "credit_limit_cents": 1_000,
            }
        )
    )
    offer = build_choice_offer(funded, _quiet())
    assert "shop:store-retail:full" in {option.option_id for option in offer.options}
    meal = build_choice_offer(
        shopping_context(opportunity="school_meal_change", school=school_offer()),
        _quiet(),
    )
    school = next(option for option in meal.options if option.option_id == "school_meal")
    assert school.expected_payment_cents == 0
    assert dict(school.attributes)["household_payment_cents"] == "0"
    absent = shopping_context().household.members[1]
    members = (
        shopping_context().household.members[0],
        absent.__class__(**{**absent.__dict__, "attending_today": False}),
    )
    household = shopping_context().household.__class__(**{**shopping_context().household.__dict__, "members": members})
    skipped = build_choice_offer(
        shopping_context(opportunity="school_meal_change", school=school_offer(), household=household),
        _quiet(),
    )
    assert "school_meal" not in {option.option_id for option in skipped.options}


def test_drone_option_requires_the_scenario_route_flag():
    refused = build_choice_offer(
        shopping_context(opportunity="delivery_mode", delivery=delivery_offer(route_eligible=False)),
        _quiet(),
    )
    allowed = build_choice_offer(
        shopping_context(opportunity="delivery_mode", delivery=delivery_offer(route_eligible=True)),
        _quiet(),
    )
    assert "delivery:drone" not in {option.option_id for option in refused.options}
    assert "delivery:ground" in {option.option_id for option in refused.options}
    drone = next(option for option in allowed.options if option.option_id == "delivery:drone")
    assert dict(drone.attributes)["route_status"] == "modeling_condition_not_permission"


def test_granted_private_facts_are_labeled_and_withheld_by_default():
    granted = build_choice_offer(
        shopping_context(knowledge_grants=("other_balances", "tomorrow_stock")),
        _quiet(),
    )
    payload = str(granted.gateway_observation().to_payload())
    assert "hh-secret" in payload
    assert "scenario_grant" in payload
    withheld = build_choice_offer(shopping_context(), _quiet())
    assert "scenario_grant" not in str(withheld.gateway_observation().to_payload())


def test_fractional_cents_are_rejected():
    household = shopping_context().household.__class__(
        **{**shopping_context().household.__dict__, "spendable_cash_cents": 10.5}
    )
    with pytest.raises(BehaviorError):
        build_choice_offer(shopping_context(household=household), _quiet())


def test_panel_seats_and_rotation_match_the_declared_rule():
    assert allocate_seats({"low": 7, "high": 1}, 4) == {"low": 3, "high": 1}
    assert allocate_seats({"low": 7, "high": 1}, 1) == {"low": 1, "high": 0}
    assert allocate_seats({"high": 10, "low": 10}, 4) == {"high": 2, "low": 2}
    panel = panel_of(("hh-a", "low"), ("hh-b", "low"), ("hh-c", "high"), ("hh-d", "high"))
    candidates = ("hh-a", "hh-b", "hh-c", "hh-d")
    assert predeclare_live_subset(panel, day_index=0, opportunity="unfamiliar_store", candidates=candidates, max_live=2) == (
        "hh-c",
        "hh-a",
    )
    assert predeclare_live_subset(panel, day_index=0, opportunity="shortage", candidates=candidates, max_live=2) == (
        "hh-b",
        "hh-d",
    )
    assert predeclare_live_subset(panel, day_index=0, opportunity="routine_shop", candidates=candidates) == ()


def test_latent_update_clamps_and_repeats():
    state = LatentState(0.5, 0.4, 0.3)
    coeffs = LatentCoefficients()
    updated = update_latent(
        state,
        basket_shortfall_grams=10,
        basket_need_grams=10,
        unfunded_essentials_cents=10,
        essential_need_cents=10,
        time_overrun_seconds=10,
        time_budget_seconds=10,
        fulfilled=False,
        expected_service=0.8,
        realized_service=0.2,
        coefficients=coeffs,
    )
    assert updated.stress == 1.0
    assert updated.trust == pytest.approx(0.2)
    again = update_latent(
        state,
        basket_shortfall_grams=10,
        basket_need_grams=10,
        unfunded_essentials_cents=10,
        essential_need_cents=10,
        time_overrun_seconds=10,
        time_budget_seconds=10,
        fulfilled=False,
        expected_service=0.8,
        realized_service=0.2,
        coefficients=coeffs,
    )
    assert updated == again
    recovered = update_latent(
        LatentState(0.0, 0.0, 0.0),
        basket_shortfall_grams=0,
        basket_need_grams=10,
        unfunded_essentials_cents=0,
        essential_need_cents=10,
        time_overrun_seconds=0,
        time_budget_seconds=10,
        fulfilled=None,
        expected_service=0.0,
        realized_service=0.0,
        coefficients=coeffs,
    )
    assert recovered.stress == 0.0


class RecordingGateway:
    def __init__(self, status: str = "ok", option_id: str | None = None, explanation: str | None = None, extra=None):
        self.batches = []
        self.status = status
        self.option_id = option_id
        self.explanation = explanation
        self.extra = extra

    def dispatch_barrier(self, requests, *, deadline_seconds: float):
        self.batches.append((deadline_seconds, requests))
        responses = []
        for request in requests:
            chosen = self.option_id or "no_purchase"
            text = self.explanation
            if text is None:
                text = f"Household {request.observation.household_id} selected {chosen}. Expected payment 0 cents."
            responses.append(
                GatewayResponse(
                    decision_id=request.observation.decision_id,
                    option_id=chosen,
                    explanation=text,
                    status=self.status,
                    prompt_version="prompt-v0",
                    model_configuration="local-test",
                    raw_response=chosen,
                    input_tokens=12,
                    output_tokens=4,
                    actual_charge_cad="0.01",
                    latency_seconds=0.2,
                    revision=request.observation.revision,
                )
            )
        if self.extra is not None:
            responses.append(self.extra)
        return tuple(responses)


def _live_config():
    price = TokenPrice("illustrative_not_a_provider_quote", Decimal("1"), Decimal("0"), Decimal("0"), Decimal("0.01"))
    return BehaviorConfig(
        agent_policy=POLICY_LIVE,
        gateway_enabled=True,
        token_price=price,
        coefficients=_quiet(),
        run_budget_cad=Decimal("30"),
    )


def test_valid_llm_choice_is_kept_and_ungrounded_text_is_replaced():
    gateway = RecordingGateway(explanation="Expected payment 999 cents and evt-missing.")
    resolution = resolve_barrier(
        (shopping_context(opportunity="shortage"),),
        config=_live_config(),
        panel=panel_of(("hh-1", "low")),
        master_seed=3,
        gateway=gateway,
        budget=MemoryChargeReservation(Decimal("30")),
    )
    receipt = resolution.receipts[0]
    assert receipt.origin == ORIGIN_LLM
    assert receipt.option_id == "no_purchase"
    assert receipt.rule_option_id == "shop:store-retail:full"
    assert receipt.explanation_origin == "llm_replaced_ungrounded"
    assert "999" not in receipt.explanation
    assert receipt.synthetic_label == "rule explanation from the simulation"
    assert gateway.batches[0][0] == 10
    assert len(gateway.batches) == 1
    sent = str(gateway.batches[0][1][0].to_payload())
    assert "hh-secret" not in sent
    assert "424242" not in sent


def test_invalid_late_and_extra_responses_do_not_change_the_predeclared_set():
    late = RecordingGateway(status="timeout")
    late_resolution = resolve_barrier(
        (shopping_context(opportunity="shortage"),),
        config=_live_config(),
        panel=panel_of(("hh-1", "low")),
        master_seed=3,
        gateway=late,
        budget=MemoryChargeReservation(),
    )
    assert late_resolution.receipts[0].fallback_reason == "late"
    assert late_resolution.receipts[0].origin == "fallback"
    invalid = RecordingGateway(option_id="not-an-option")
    invalid_resolution = resolve_barrier(
        (shopping_context(opportunity="shortage"),),
        config=_live_config(),
        panel=panel_of(("hh-1", "low")),
        master_seed=3,
        gateway=invalid,
        budget=MemoryChargeReservation(),
    )
    assert invalid_resolution.receipts[0].fallback_reason == "invalid"
    assert invalid_resolution.receipts[0].option_id == invalid_resolution.receipts[0].rule_option_id


def test_budget_and_attempt_ceilings_trim_the_predeclared_order():
    names = ("hh-a", "hh-b", "hh-c", "hh-d")
    contexts = tuple(
        shopping_context(decision_id=f"d-{name}", opportunity="unfamiliar_store", household=_rename(name))
        for name in names
    )
    panel = panel_of(*((name, "low") for name in names))
    price = TokenPrice("illustrative_not_a_provider_quote", Decimal("1"), Decimal("0"), Decimal("0"), Decimal("0.03"))
    assert estimate_max_request_cad(price) == Decimal("0.030000")
    gateway = RecordingGateway()
    resolution = resolve_barrier(
        contexts,
        config=BehaviorConfig(
            agent_policy=POLICY_LIVE,
            gateway_enabled=True,
            token_price=price,
            coefficients=_quiet(),
            run_budget_cad=Decimal("0.05"),
        ),
        panel=panel,
        master_seed=1,
        gateway=gateway,
        budget=MemoryChargeReservation(Decimal("0.05")),
    )
    assert len(gateway.batches) == 1
    assert len(gateway.batches[0][1]) == 1
    assert resolution.dispatched_decision_ids == ("d-hh-a",)
    exhausted = [receipt for receipt in resolution.receipts if receipt.fallback_reason == "budget_exhausted"]
    assert len(exhausted) == 3
    assert all(receipt.fallback_reason != "late" for receipt in resolution.receipts)

    capped = RecordingGateway()
    capped_resolution = resolve_barrier(
        contexts,
        config=_live_config(),
        panel=panel,
        master_seed=1,
        gateway=capped,
        budget=MemoryChargeReservation(),
        attempts_used=1199,
    )
    assert capped_resolution.attempts_consumed == 1
    assert sum(receipt.fallback_reason == "attempt_ceiling" for receipt in capped_resolution.receipts) == 3


def test_frozen_receipt_is_used_only_when_the_observation_hash_matches():
    offer = build_choice_offer(shopping_context(), _quiet())
    gateway = RecordingGateway()
    matched = resolve_barrier(
        (shopping_context(),),
        config=BehaviorConfig(agent_policy=POLICY_FROZEN, gateway_enabled=False, coefficients=_quiet()),
        panel=panel_of(("hh-1", "low")),
        master_seed=1,
        gateway=gateway,
        recorded=(
            RecordedChoice(
                "d-1",
                "no_purchase",
                offer.gateway_observation().content_hash(),
                "Household hh-1 selected no_purchase. Expected payment 0 cents. Cited events: evt-1.",
                "prompt-v0",
                "recorded-config",
            ),
        ),
    )
    assert matched.gateway_dispatch_calls == 0
    assert matched.receipts[0].origin == ORIGIN_RECORDED
    assert matched.receipts[0].option_id == "no_purchase"
    stale = resolve_barrier(
        (shopping_context(),),
        config=BehaviorConfig(agent_policy=POLICY_FROZEN, coefficients=_quiet()),
        panel=panel_of(("hh-1", "low")),
        master_seed=1,
        recorded=(RecordedChoice("d-1", "no_purchase", "deadbeef"),),
    )
    assert stale.receipts[0].fallback_reason == "stale"
    assert stale.receipts[0].option_id == stale.receipts[0].rule_option_id


def test_tie_breaks_toward_the_smaller_option_id():
    from sim.behavior.draft import FeasibleOption
    from sim.behavior.utility import choose_rule

    options = (
        FeasibleOption("b", "no_purchase", None, (), 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, ()),
        FeasibleOption("a", "no_purchase", None, (), 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, ()),
    )
    chosen, _utility = choose_rule(
        options,
        master_seed=1,
        household_id="hh-1",
        day_index=0,
        income_band="low",
        coefficients=UtilityCoefficients(noise_amplitude=0),
    )
    assert chosen == "a"


def _rename(household_id: str):
    household = shopping_context().household
    return household.__class__(**{**household.__dict__, "household_id": household_id})
