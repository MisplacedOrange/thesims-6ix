"""Fixtures for behaviour tests. Not a world model."""

from __future__ import annotations

from sim.behavior.panel import FocalPanel
from sim.behavior.snapshot import (
    CatalogProduct,
    DecisionContext,
    DeliveryOffer,
    HouseholdSnapshot,
    Member,
    RouteInfo,
    SchoolOffer,
    StoreInfo,
    StoreShelf,
    VisibleEvent,
)


def shopping_context(**overrides: object) -> DecisionContext:
    household = HouseholdSnapshot(
        household_id="hh-1",
        area_id="area-north",
        income_band="low",
        members=(
            Member("hh-1-a", "adult", None, False, False),
            Member("hh-1-c", "child", "school-1", True, True),
        ),
        spendable_cash_cents=5_000,
        credit_limit_cents=0,
        pantry=(),
        pantry_capacity_grams=10_000,
        time_budget_seconds=7_200,
        habit_store_id="store-retail",
        known_store_ids=("store-retail",),
        dietary_excluded_tags=(),
        preference_weights=(),
        cooking_access=True,
        stress=0.2,
        trust=0.4,
        satisfaction=0.5,
        mobility="unconstrained",
    )
    ctx = DecisionContext(
        decision_id="d-1",
        revision=3,
        sim_second=28_800,
        day_index=0,
        opportunity="routine_shop",
        household=household,
        catalog=(
            CatalogProduct("staple", 100, True, ("staple",)),
            CatalogProduct("produce", 100, True, ("produce",)),
        ),
        reference_basket=(("staple", 400), ("produce", 200)),
        reference_household_size=2,
        stores=(
            StoreInfo("store-retail", 0, 100_000, False, False),
        ),
        shelves=(
            StoreShelf("store-retail", "staple", 5_000, 100, None, 0.8, 0),
            StoreShelf("store-retail", "produce", 5_000, 80, None, 0.8, 0),
        ),
        routes=(RouteInfo("store-retail", 600, True, "walk"),),
        school=None,
        delivery=None,
        visible_events=(VisibleEvent("evt-1", "purchase", "previous purchase settled"),),
        foreign_balances=(("hh-secret", 424_242),),
        tomorrow_stock=(("store-retail", "staple", 424_242),),
        knowledge_grants=(),
    )
    return _apply(ctx, overrides)


def _apply(ctx: DecisionContext, overrides: dict[str, object]) -> DecisionContext:
    if not overrides:
        return ctx
    data = ctx.__dict__.copy()
    data.update(overrides)
    return DecisionContext(**data)


def panel_of(*pairs: tuple[str, str], seed: int = 1) -> FocalPanel:
    ordered = tuple(sorted(pairs, key=lambda item: (item[1], item[0])))
    return FocalPanel(
        household_ids=tuple(household for household, _stratum in ordered),
        stratum_by_household=tuple((household, stratum) for household, stratum in ordered),
        seed=seed,
        max_focal=40,
    )


def school_offer() -> SchoolOffer:
    return SchoolOffer("school-1", 350, True, True, 0.5)


def delivery_offer(*, route_eligible: bool) -> DeliveryOffer:
    return DeliveryOffer(
        ground_seconds=900,
        ground_fee_cents=200,
        ground_available=True,
        drone_seconds=400,
        drone_fee_cents=150,
        route_eligible=route_eligible,
        locker_accessible=True,
        weather_excluded=False,
    )
