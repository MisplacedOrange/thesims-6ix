"""Same inputs produce the same offers, scores, receipts, and admission order."""

from sim.behavior.adapters import DisabledGateway
from sim.behavior.coordinator import BehaviorConfig, resolve_barrier
from sim.behavior.determinism import STREAM_ALGORITHM, admission_rank, draw_unit
from sim.behavior.draft import CHOICE_FORMAT_STATUS, SCHEMA_VERSION
from sim.behavior.offers import build_choice_offer, scale_basket
from sim.behavior.panel import select_focal_panel
from sim.behavior.panel import RosterHousehold
from sim.behavior.tests.support import panel_of, shopping_context
from sim.behavior.utility import UtilityCoefficients, score_option


def test_scale_basket_uses_largest_remainder_grams():
    scaled = scale_basket((("produce", 50), ("staple", 100)), household_size=1, reference_household_size=3)
    assert scaled == (("produce", 17), ("staple", 33))
    assert sum(grams for _, grams in scaled) == 50


def test_price_coefficient_consumes_dollars_not_cents():
    from sim.behavior.draft import FeasibleOption

    def option(option_id: str, cents: int) -> FeasibleOption:
        return FeasibleOption(
            option_id, "shop", "store-retail", (), cents, 0, 0.0, 0.0, 0.0, 0.0, 0.0, ()
        )

    cheap = score_option(option("a", 100), price_sensitivity_per_dollar=1.0, time_sensitivity_per_minute=0.0, noise=0.0)
    dear = score_option(option("b", 200), price_sensitivity_per_dollar=1.0, time_sensitivity_per_minute=0.0, noise=0.0)
    assert cheap - dear == 1.0


def test_time_coefficient_consumes_minutes():
    from sim.behavior.draft import FeasibleOption

    def option(option_id: str, seconds: int) -> FeasibleOption:
        return FeasibleOption(option_id, "shop", None, (), 0, seconds, 0.0, 0.0, 0.0, 0.0, 0.0, ())

    short = score_option(option("a", 60), price_sensitivity_per_dollar=0.0, time_sensitivity_per_minute=0.15, noise=0.0)
    longer = score_option(option("b", 120), price_sensitivity_per_dollar=0.0, time_sensitivity_per_minute=0.15, noise=0.0)
    assert short - longer == 0.15


def test_offer_hash_ignores_seed_and_private_fields():
    ctx = shopping_context()
    first = build_choice_offer(ctx, UtilityCoefficients(noise_amplitude=0))
    second = build_choice_offer(ctx, UtilityCoefficients(noise_amplitude=0))
    assert first.gateway_observation().content_hash() == second.gateway_observation().content_hash()
    payload = str(first.gateway_observation().to_payload())
    assert "hh-secret" not in payload
    assert "424242" not in payload
    assert first.review_status == CHOICE_FORMAT_STATUS
    assert first.schema_version == SCHEMA_VERSION
    assert "no_purchase" in {option.option_id for option in first.options}
    assert "shop:store-retail:full" in {option.option_id for option in first.options}


def test_resolution_repeats_and_admission_ignores_household_id_order():
    ctx = shopping_context(opportunity="unfamiliar_store")
    other = shopping_context(
        decision_id="d-2",
        household=shopping_context().household.__class__(
            **{**shopping_context().household.__dict__, "household_id": "hh-2"}
        ),
    )
    panel = panel_of(("hh-1", "low"), ("hh-2", "low"))
    config = BehaviorConfig(coefficients=UtilityCoefficients(noise_amplitude=0))
    gateway = DisabledGateway()
    first = resolve_barrier((ctx, other), config=config, panel=panel, master_seed=7, gateway=gateway)
    second = resolve_barrier((other, ctx), config=config, panel=panel, master_seed=7, gateway=gateway)
    assert [receipt.to_payload() for receipt in first.receipts] == [
        receipt.to_payload() for receipt in sorted(second.receipts, key=lambda item: item.decision_id)
    ]
    expected = tuple(
        sorted(
            ("hh-1", "hh-2"),
            key=lambda household: (
                admission_rank(7, household_id=household, day=0, opportunity="unfamiliar_store"),
                household,
            ),
        )
    )
    assert first.admission_order == expected
    assert first.receipts[0].stream_algorithm == STREAM_ALGORITHM
    assert first.gateway_dispatch_calls == 0


def test_choice_noise_is_stable_per_seed_and_can_change_the_winner():
    from sim.behavior.draft import FeasibleOption
    from sim.behavior.utility import choose_rule

    options = (
        FeasibleOption("m", "shop", "store-a", (), 100, 60, 0.5, 0.0, 0.0, 0.0, 0.0, ()),
        FeasibleOption("n", "shop", "store-b", (), 100, 60, 0.5, 0.0, 0.0, 0.0, 0.0, ()),
    )
    coeffs = UtilityCoefficients(noise_amplitude=1.0)
    winners = set()
    for seed in range(30):
        first, _utility = choose_rule(
            options, master_seed=seed, household_id="hh-1", day_index=0, income_band="low", coefficients=coeffs
        )
        second, _utility = choose_rule(
            options, master_seed=seed, household_id="hh-1", day_index=0, income_band="low", coefficients=coeffs
        )
        assert first == second
        winners.add(first)
    assert winners == {"m", "n"}


def test_named_streams_do_not_depend_on_policy_text():
    left = draw_unit(11, actor="district", day=2, purpose="weather")
    right = draw_unit(11, actor="district", day=2, purpose="weather")
    other = draw_unit(11, actor="district", day=2, purpose="income")
    assert left == right
    assert left != other


def test_panel_membership_is_stable_when_the_roster_is_shuffled():
    roster = [RosterHousehold(f"hh-{index}", "low" if index < 7 else "high") for index in range(8)]
    forward = select_focal_panel(roster, seed=4, max_focal=4)
    backward = select_focal_panel(tuple(reversed(roster)), seed=4, max_focal=4)
    assert forward.household_ids == backward.household_ids
    assert len(forward.household_ids) == 4
