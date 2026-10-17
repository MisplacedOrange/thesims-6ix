"""Legal offers at a decision barrier.

An option is one store trip, a school meal, a delivery mode, a delay, or no
purchase. Multi-stop tours are not generated. Unknown stores stay out of the
offer unless they are publicly known or a knowledge grant says otherwise.
Expired lots are never offered. A school meal has a zero household payment.
"""

from __future__ import annotations

import math

from sim.behavior.draft import (
    CHOICE_FORMAT_STATUS,
    OFFER_SCHEMA_ID,
    SCHEMA_VERSION,
    BasketLine,
    ChoiceOffer,
    FeasibleOption,
    ObservedFact,
)
from sim.behavior.errors import BehaviorError
from sim.behavior.snapshot import (
    GRANT_OTHER_BALANCES,
    GRANT_TOMORROW_STOCK,
    CatalogProduct,
    DecisionContext,
    HouseholdSnapshot,
    RouteInfo,
    StoreInfo,
    StoreShelf,
    validate_context,
)
from sim.behavior.utility import UtilityCoefficients

_NO_PURCHASE = "no_purchase"
_DELAY = "delay_purchase"


def collection_seconds(raw_seconds: int) -> int:
    """A trip lasts at least one second. Zero-length travel is not a trip."""

    if type(raw_seconds) is not int or raw_seconds < 0:
        raise BehaviorError("travel seconds must be a non-negative int")
    if raw_seconds == 0:
        return 1
    return raw_seconds


def scale_basket(
    lines: tuple[tuple[str, int], ...],
    *,
    household_size: int,
    reference_household_size: int,
) -> tuple[tuple[str, int], ...]:
    """Scale a reference basket with integer largest-remainder grams.

    ``total = (reference_grams * household_size) // reference_household_size``.
    That total is then split across lines in proportion to the reference line
    grams. Ties in the fractional part break by product id ascending.
    """

    if household_size < 1 or reference_household_size < 1:
        raise BehaviorError("household sizes must be positive")
    if not lines:
        return ()
    total_reference = sum(grams for _, grams in lines)
    total = (total_reference * household_size) // reference_household_size
    return _largest_remainder(lines, total)


def build_choice_offer(ctx: DecisionContext, coefficients: UtilityCoefficients | None = None) -> ChoiceOffer:
    validate_context(ctx)
    coeffs = coefficients or UtilityCoefficients()
    household = ctx.household
    catalog = {product.product_id: product for product in ctx.catalog}
    need = scale_basket(
        ctx.reference_basket,
        household_size=len(household.members),
        reference_household_size=ctx.reference_household_size,
    )
    visible_stores = _visible_stores(ctx)
    shelves = {(shelf.store_id, shelf.product_id): shelf for shelf in ctx.shelves}
    routes = {route.store_id: route for route in ctx.routes}
    options: list[FeasibleOption] = []
    if ctx.opportunity == "delivery_mode":
        options.extend(_delivery_options(ctx, coeffs))
    else:
        if ctx.opportunity == "school_meal_change":
            school_option = _school_option(ctx, coeffs)
            if school_option is not None:
                options.append(school_option)
        options.extend(_shop_options(ctx, coeffs, catalog, need, visible_stores, shelves, routes))
        options.append(_delay_option(coeffs))
    options.append(_no_purchase_option(coeffs))
    options_by_id = {option.option_id: option for option in options}
    if len(options_by_id) != len(options):
        raise BehaviorError("duplicate option id")
    ordered = tuple(options_by_id[option_id] for option_id in sorted(options_by_id))
    facts = _facts(ctx, ordered, visible_stores, shelves)
    events = tuple(sorted(event.event_id for event in ctx.visible_events))
    return ChoiceOffer(
        schema_id=OFFER_SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        review_status=CHOICE_FORMAT_STATUS,
        decision_id=ctx.decision_id,
        household_id=household.household_id,
        revision=ctx.revision,
        sim_second=ctx.sim_second,
        day_index=ctx.day_index,
        opportunity=ctx.opportunity,
        stratum=household.income_band,
        known_facts=facts,
        recent_event_ids=events,
        options=ordered,
    )


def _largest_remainder(lines: tuple[tuple[str, int], ...], total: int) -> tuple[tuple[str, int], ...]:
    ordered = tuple(sorted(lines, key=lambda item: item[0]))
    weight = sum(grams for _, grams in ordered)
    if total == 0 or weight == 0:
        return tuple((product_id, 0) for product_id, _ in ordered)
    quotas = [(product_id, total * grams / weight) for product_id, grams in ordered]
    floors = {product_id: int(math.floor(quota)) for product_id, quota in quotas}
    leftover = total - sum(floors.values())
    ranked = sorted(quotas, key=lambda item: (-(item[1] - math.floor(item[1])), item[0]))
    for index in range(leftover):
        floors[ranked[index][0]] += 1
    return tuple((product_id, floors[product_id]) for product_id, _ in ordered)


def _visible_stores(ctx: DecisionContext) -> dict[str, StoreInfo]:
    known = set(ctx.household.known_store_ids)
    visible = {}
    for store in ctx.stores:
        if store.store_id in known or store.publicly_known:
            visible[store.store_id] = store
    return visible


def _shop_options(
    ctx: DecisionContext,
    coeffs: UtilityCoefficients,
    catalog: dict[str, CatalogProduct],
    need: tuple[tuple[str, int], ...],
    stores: dict[str, StoreInfo],
    shelves: dict[tuple[str, str], StoreShelf],
    routes: dict[str, RouteInfo],
) -> list[FeasibleOption]:
    built: list[FeasibleOption] = []
    for store_id in sorted(stores):
        route = routes.get(store_id)
        if route is None:
            continue
        if not route.accessible:
            continue
        seconds = collection_seconds(route.total_seconds)
        if seconds > ctx.household.time_budget_seconds:
            continue
        arrival = ctx.sim_second + seconds
        store = stores[store_id]
        if not (store.open_from <= ctx.sim_second and arrival < store.open_until):
            continue
        full = _basket_at_store(
            ctx,
            store_id,
            need,
            catalog,
            shelves,
            arrival,
            essential_only=False,
        )
        essentials_need = tuple(
            (product_id, grams)
            for product_id, grams in need
            if catalog[product_id].essential
        )
        essentials = _basket_at_store(
            ctx,
            store_id,
            essentials_need,
            catalog,
            shelves,
            arrival,
            essential_only=True,
        )
        if full is not None:
            lines, omitted = full
            built.append(
                _shop_option(
                    ctx,
                    coeffs,
                    store,
                    route.mode,
                    seconds,
                    lines,
                    kind="dietary_basket" if omitted else "full_basket",
                    suffix="allowed" if omitted else "full",
                )
            )
        if essentials is not None and (full is None or essentials[0] != full[0]):
            lines, omitted = essentials
            built.append(
                _shop_option(
                    ctx,
                    coeffs,
                    store,
                    route.mode,
                    seconds,
                    lines,
                    kind="dietary_basket" if omitted else "essentials_basket",
                    suffix="allowed" if omitted else "essentials",
                )
            )
    return built


def _basket_at_store(
    ctx: DecisionContext,
    store_id: str,
    need: tuple[tuple[str, int], ...],
    catalog: dict[str, CatalogProduct],
    shelves: dict[tuple[str, str], StoreShelf],
    arrival: int,
    *,
    essential_only: bool,
) -> tuple[tuple[BasketLine, ...], bool] | None:
    if not need:
        return None
    household = ctx.household
    omitted = False
    cash = household.spendable_cash_cents + household.credit_limit_cents
    storage = household.pantry_capacity_grams - sum(lot.grams for lot in household.pantry)
    if storage < 0:
        storage = 0
    lines: list[BasketLine] = []
    for product_id, need_grams in need:
        product = catalog[product_id]
        if essential_only and not product.essential:
            continue
        if _excluded(product, household):
            omitted = True
            continue
        shelf = shelves.get((store_id, product_id))
        if shelf is None or shelf.available_grams <= 0:
            return None
        if shelf.unsafe_after is not None and shelf.unsafe_after <= arrival:
            return None
        units_needed = (need_grams + product.unit_grams - 1) // product.unit_grams
        units_stock = shelf.available_grams // product.unit_grams
        units_storage = storage // product.unit_grams
        if shelf.price_cents_per_unit == 0:
            units_cash = units_needed
        else:
            units_cash = cash // shelf.price_cents_per_unit
        units = min(units_needed, units_stock, units_storage, units_cash)
        if units < units_needed:
            return None
        grams = units * product.unit_grams
        price = units * shelf.price_cents_per_unit
        cash -= price
        storage -= grams
        lines.append(BasketLine(product_id=product_id, grams=grams, price_cents=price))
    if not lines:
        return None
    return tuple(lines), omitted


def _excluded(product: CatalogProduct, household: HouseholdSnapshot) -> bool:
    tags = set(product.tags)
    if tags & set(household.dietary_excluded_tags):
        return True
    if not household.cooking_access and "requires_cooking" in tags:
        return True
    return False


def _shop_option(
    ctx: DecisionContext,
    coeffs: UtilityCoefficients,
    store: StoreInfo,
    mode: str,
    seconds: int,
    lines: tuple[BasketLine, ...],
    *,
    kind: str,
    suffix: str,
) -> FeasibleOption:
    household = ctx.household
    known = store.store_id in household.known_store_ids
    payment = sum(line.price_cents for line in lines)
    tight = False
    qualities: list[float] = []
    stale = False
    for line in lines:
        shelf = next(
            shelf
            for shelf in ctx.shelves
            if shelf.store_id == store.store_id and shelf.product_id == line.product_id
        )
        if shelf.available_grams < line.grams * 2:
            tight = True
        qualities.append(shelf.quality)
        if shelf.price_day is not None and shelf.price_day < ctx.day_index:
            stale = True
    habit = coeffs.habit_bonus if store.store_id == household.habit_store_id else 0.0
    quality = sum(qualities) / len(qualities) if known and qualities else 0.0
    uncertainty = 0.0
    if not known:
        uncertainty += coeffs.unknown_store_penalty
    if stale:
        uncertainty += coeffs.stale_price_penalty
    attributes = [("mode", mode), ("basket", suffix)]
    if store.is_municipal:
        attributes.append(("municipal", "true"))
    return FeasibleOption(
        option_id=f"shop:{store.store_id}:{suffix}",
        kind=kind,
        store_id=store.store_id,
        lines=lines,
        expected_payment_cents=payment,
        total_seconds=seconds,
        preference_fit=_preference_fit(lines, ctx, household),
        habit_value=habit,
        known_quality=quality,
        stockout_penalty=coeffs.tight_stock_penalty if tight else 0.0,
        uncertainty_penalty=uncertainty,
        attributes=tuple(attributes),
    )


def _preference_fit(
    lines: tuple[BasketLine, ...],
    ctx: DecisionContext,
    household: HouseholdSnapshot,
) -> float:
    weights = dict(household.preference_weights)
    catalog = {product.product_id: product for product in ctx.catalog}
    scores: list[float] = []
    for line in lines:
        tags = catalog[line.product_id].tags
        if not tags:
            scores.append(0.5)
            continue
        scores.append(sum(weights.get(tag, 0.5) for tag in tags) / len(tags))
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _delay_option(coeffs: UtilityCoefficients) -> FeasibleOption:
    return FeasibleOption(
        option_id=_DELAY,
        kind="delay_purchase",
        store_id=None,
        lines=(),
        expected_payment_cents=0,
        total_seconds=0,
        preference_fit=0.0,
        habit_value=0.0,
        known_quality=0.0,
        stockout_penalty=coeffs.delay_penalty,
        uncertainty_penalty=0.0,
        attributes=(("covers_need", "false"),),
    )


def _no_purchase_option(coeffs: UtilityCoefficients) -> FeasibleOption:
    return FeasibleOption(
        option_id=_NO_PURCHASE,
        kind="no_purchase",
        store_id=None,
        lines=(),
        expected_payment_cents=0,
        total_seconds=0,
        preference_fit=0.0,
        habit_value=0.0,
        known_quality=0.0,
        stockout_penalty=coeffs.unmet_need_penalty,
        uncertainty_penalty=0.0,
        attributes=(("covers_need", "false"),),
    )


def _school_option(ctx: DecisionContext, coeffs: UtilityCoefficients) -> FeasibleOption | None:
    school = ctx.school
    if school is None or not school.meal_offered_today or not school.dietary_ok:
        return None
    children = [
        member
        for member in ctx.household.members
        if member.school_eligible and member.attending_today and member.school_id == school.school_id
    ]
    if not children:
        return None
    portion = school.portion_grams * len(children)
    replaced = _grams_replaced(portion, school.substitution_share)
    return FeasibleOption(
        option_id="school_meal",
        kind="school_meal",
        store_id=None,
        lines=(),
        expected_payment_cents=0,
        total_seconds=0,
        preference_fit=1.0 if school.dietary_ok else 0.0,
        habit_value=0.0,
        known_quality=0.0,
        stockout_penalty=0.0,
        uncertainty_penalty=0.0,
        attributes=(
            ("school_id", school.school_id),
            ("portion_grams", str(portion)),
            ("replaced_home_grams", str(replaced)),
            ("household_payment_cents", "0"),
            ("note", "school_meal_is_not_a_household_purchase"),
        ),
    )


def _grams_replaced(portion: int, share: float) -> int:
    return int(math.floor(portion * share + 0.5))


def _delivery_options(ctx: DecisionContext, coeffs: UtilityCoefficients) -> list[FeasibleOption]:
    delivery = ctx.delivery
    if delivery is None:
        return []
    options: list[FeasibleOption] = []
    if delivery.ground_available:
        seconds = collection_seconds(delivery.ground_seconds)
        if seconds <= ctx.household.time_budget_seconds and delivery.ground_fee_cents <= _spendable(ctx.household):
            options.append(_delivery_option("ground", seconds, delivery.ground_fee_cents, coeffs, eligible="true"))
    drone_legal = delivery.route_eligible and delivery.locker_accessible and not delivery.weather_excluded
    if drone_legal:
        seconds = collection_seconds(delivery.drone_seconds)
        if seconds <= ctx.household.time_budget_seconds and delivery.drone_fee_cents <= _spendable(ctx.household):
            options.append(
                _delivery_option(
                    "drone",
                    seconds,
                    delivery.drone_fee_cents,
                    coeffs,
                    eligible="modeling_condition_not_permission",
                )
            )
    return options


def _delivery_option(
    mode: str,
    seconds: int,
    fee_cents: int,
    coeffs: UtilityCoefficients,
    *,
    eligible: str,
) -> FeasibleOption:
    return FeasibleOption(
        option_id=f"delivery:{mode}",
        kind=f"delivery_{mode}",
        store_id=None,
        lines=(),
        expected_payment_cents=fee_cents,
        total_seconds=seconds,
        preference_fit=0.5,
        habit_value=coeffs.habit_bonus if mode == "ground" else 0.0,
        known_quality=0.0,
        stockout_penalty=0.0,
        uncertainty_penalty=coeffs.unknown_store_penalty if mode == "drone" else 0.0,
        attributes=(
            ("mode", mode),
            ("route_status", eligible),
        ),
    )


def _spendable(household: HouseholdSnapshot) -> int:
    return household.spendable_cash_cents + household.credit_limit_cents


def _facts(
    ctx: DecisionContext,
    options: tuple[FeasibleOption, ...],
    stores: dict[str, StoreInfo],
    shelves: dict[tuple[str, str], StoreShelf],
) -> tuple[ObservedFact, ...]:
    household = ctx.household
    facts = [
        ObservedFact(
            "own-cash",
            "own_cash",
            (("cents", str(household.spendable_cash_cents)), ("credit_limit_cents", str(household.credit_limit_cents))),
        ),
        ObservedFact(
            "own-time",
            "own_time",
            (("seconds", str(household.time_budget_seconds)), ("mobility", household.mobility)),
        ),
        ObservedFact(
            "own-pantry",
            "own_pantry",
            tuple(
                sorted(
                    (f"grams:{lot.product_id}", str(lot.grams)) for lot in household.pantry
                )
            )
            or (("grams_total", "0"),),
        ),
    ]
    if household.habit_store_id is not None:
        facts.append(ObservedFact("habit-store", "habit", (("store_id", household.habit_store_id),)))
    for store_id in sorted(stores):
        store = stores[store_id]
        facts.append(
            ObservedFact(
                f"store-hours:{store_id}",
                "store_hours",
                (
                    ("store_id", store_id),
                    ("open_from", str(store.open_from)),
                    ("open_until", str(store.open_until)),
                    ("publicly_known", "true" if store.publicly_known else "false"),
                    ("municipal", "true" if store.is_municipal else "false"),
                    ("known_personally", "true" if store_id in household.known_store_ids else "false"),
                ),
            )
        )
    quoted: set[tuple[str, str]] = set()
    for option in options:
        if option.store_id is None:
            continue
        for line in option.lines:
            quoted.add((option.store_id, line.product_id))
    for store_id, product_id in sorted(quoted):
        shelf = shelves[(store_id, product_id)]
        facts.append(
            ObservedFact(
                f"store-price:{store_id}:{product_id}",
                "store_price",
                (
                    ("store_id", store_id),
                    ("product_id", product_id),
                    ("cents_per_unit", str(shelf.price_cents_per_unit)),
                    ("available_grams", str(shelf.available_grams)),
                    ("price_day", "" if shelf.price_day is None else str(shelf.price_day)),
                ),
            )
        )
    for event in sorted(ctx.visible_events, key=lambda item: item.event_id):
        facts.append(
            ObservedFact(
                f"event:{event.event_id}",
                "event",
                (("event_id", event.event_id), ("event_kind", event.kind), ("summary", event.summary)),
            )
        )
    if ctx.school is not None and ctx.opportunity == "school_meal_change":
        facts.append(
            ObservedFact(
                "school-meal",
                "school_meal",
                (
                    ("school_id", ctx.school.school_id),
                    ("offered", "true" if ctx.school.meal_offered_today else "false"),
                    ("portion_grams", str(ctx.school.portion_grams)),
                ),
            )
        )
    grants = set(ctx.knowledge_grants)
    if GRANT_OTHER_BALANCES in grants:
        for household_id, cents in sorted(ctx.foreign_balances):
            facts.append(
                ObservedFact(
                    f"granted-balance:{household_id}",
                    "scenario_grant_balance",
                    (("household_id", household_id), ("cents", str(cents)), ("source", "scenario_grant")),
                )
            )
    if GRANT_TOMORROW_STOCK in grants:
        for store_id, product_id, grams in sorted(ctx.tomorrow_stock):
            facts.append(
                ObservedFact(
                    f"granted-tomorrow:{store_id}:{product_id}",
                    "scenario_grant_tomorrow_stock",
                    (
                        ("store_id", store_id),
                        ("product_id", product_id),
                        ("grams", str(grams)),
                        ("source", "scenario_grant"),
                    ),
                )
            )
    facts.sort(key=lambda fact: fact.fact_id)
    return tuple(facts)
