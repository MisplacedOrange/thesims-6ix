"""Read-only barrier snapshot the kernel adapts into.

``sim/core`` owns world state. It fills these records at a decision barrier.
Fields named ``foreign_balances`` and ``tomorrow_stock`` exist so knowledge
rules can prove they were withheld. They are not household knowledge unless
``knowledge_grants`` names the matching grant.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.behavior.errors import BehaviorError

OPPORTUNITIES = (
    "routine_shop",
    "unfamiliar_store",
    "shortage",
    "school_meal_change",
    "delivery_mode",
)
LIVE_OPPORTUNITIES = (
    "unfamiliar_store",
    "shortage",
    "school_meal_change",
    "delivery_mode",
)
GRANT_OTHER_BALANCES = "other_balances"
GRANT_TOMORROW_STOCK = "tomorrow_stock"
KNOWN_GRANTS = (GRANT_OTHER_BALANCES, GRANT_TOMORROW_STOCK)


@dataclass(frozen=True)
class Member:
    member_id: str
    age_band: str
    school_id: str | None
    school_eligible: bool
    attending_today: bool


@dataclass(frozen=True)
class PantryLot:
    product_id: str
    grams: int


@dataclass(frozen=True)
class CatalogProduct:
    product_id: str
    unit_grams: int
    essential: bool
    tags: tuple[str, ...]


@dataclass(frozen=True)
class StoreInfo:
    store_id: str
    open_from: int
    open_until: int
    publicly_known: bool
    is_municipal: bool


@dataclass(frozen=True)
class StoreShelf:
    """One posted quote for a store and product, net of reservations."""

    store_id: str
    product_id: str
    available_grams: int
    price_cents_per_unit: int
    unsafe_after: int | None
    quality: float
    price_day: int | None


@dataclass(frozen=True)
class RouteInfo:
    store_id: str
    total_seconds: int
    accessible: bool
    mode: str


@dataclass(frozen=True)
class HouseholdSnapshot:
    household_id: str
    area_id: str
    income_band: str
    members: tuple[Member, ...]
    spendable_cash_cents: int
    credit_limit_cents: int
    pantry: tuple[PantryLot, ...]
    pantry_capacity_grams: int
    time_budget_seconds: int
    habit_store_id: str | None
    known_store_ids: tuple[str, ...]
    dietary_excluded_tags: tuple[str, ...]
    preference_weights: tuple[tuple[str, float], ...]
    cooking_access: bool
    stress: float
    trust: float
    satisfaction: float
    mobility: str


@dataclass(frozen=True)
class SchoolOffer:
    school_id: str
    portion_grams: int
    dietary_ok: bool
    meal_offered_today: bool
    substitution_share: float


@dataclass(frozen=True)
class DeliveryOffer:
    ground_seconds: int
    ground_fee_cents: int
    ground_available: bool
    drone_seconds: int
    drone_fee_cents: int
    route_eligible: bool
    locker_accessible: bool
    weather_excluded: bool


@dataclass(frozen=True)
class VisibleEvent:
    event_id: str
    kind: str
    summary: str


@dataclass(frozen=True)
class DecisionContext:
    decision_id: str
    revision: int
    sim_second: int
    day_index: int
    opportunity: str
    household: HouseholdSnapshot
    catalog: tuple[CatalogProduct, ...]
    reference_basket: tuple[tuple[str, int], ...]
    reference_household_size: int
    stores: tuple[StoreInfo, ...]
    shelves: tuple[StoreShelf, ...]
    routes: tuple[RouteInfo, ...]
    school: SchoolOffer | None
    delivery: DeliveryOffer | None
    visible_events: tuple[VisibleEvent, ...]
    foreign_balances: tuple[tuple[str, int], ...] = ()
    tomorrow_stock: tuple[tuple[str, str, int], ...] = ()
    knowledge_grants: tuple[str, ...] = ()


def require_int(name: str, value: object, *, minimum: int = 0) -> int:
    if type(value) is not int:
        raise BehaviorError(f"{name} must be an int")
    if value < minimum:
        raise BehaviorError(f"{name} is below {minimum}")
    return value


def require_token(name: str, value: object) -> str:
    if type(value) is not str or not value or any(ch.isspace() for ch in value):
        raise BehaviorError(f"{name} must be a non-empty token")
    return value


def require_unit_interval(name: str, value: object) -> float:
    if type(value) is bool or not isinstance(value, (int, float)):
        raise BehaviorError(f"{name} must be a number")
    number = float(value)
    if number < 0 or number > 1:
        raise BehaviorError(f"{name} must be between 0 and 1")
    return number


def validate_context(ctx: DecisionContext) -> None:
    require_token("decision_id", ctx.decision_id)
    require_int("revision", ctx.revision)
    require_int("sim_second", ctx.sim_second)
    require_int("day_index", ctx.day_index)
    if ctx.opportunity not in OPPORTUNITIES:
        raise BehaviorError(f"unknown opportunity {ctx.opportunity}")
    _validate_household(ctx.household)
    _unique("product", [product.product_id for product in ctx.catalog])
    catalog_ids = set()
    for product in ctx.catalog:
        require_token("product_id", product.product_id)
        require_int("unit_grams", product.unit_grams, minimum=1)
        catalog_ids.add(product.product_id)
        for tag in product.tags:
            require_token("tag", tag)
    if ctx.reference_household_size < 1 or type(ctx.reference_household_size) is not int:
        raise BehaviorError("reference_household_size must be a positive int")
    seen_lines: set[str] = set()
    for product_id, grams in ctx.reference_basket:
        require_token("reference product", product_id)
        require_int("reference grams", grams, minimum=1)
        if product_id not in catalog_ids:
            raise BehaviorError(f"reference product {product_id} is not in the catalog")
        if product_id in seen_lines:
            raise BehaviorError(f"duplicate reference line {product_id}")
        seen_lines.add(product_id)
    _unique("store", [store.store_id for store in ctx.stores])
    stores = {}
    for store in ctx.stores:
        require_token("store_id", store.store_id)
        require_int("open_from", store.open_from)
        require_int("open_until", store.open_until)
        if store.open_until <= store.open_from:
            raise BehaviorError(f"store {store.store_id} has an empty opening interval")
        stores[store.store_id] = store
    shelf_keys: set[tuple[str, str]] = set()
    for shelf in ctx.shelves:
        require_token("shelf store", shelf.store_id)
        require_token("shelf product", shelf.product_id)
        if shelf.store_id not in stores:
            raise BehaviorError(f"shelf store {shelf.store_id} has no store record")
        if shelf.product_id not in catalog_ids:
            raise BehaviorError(f"shelf product {shelf.product_id} is not in the catalog")
        key = (shelf.store_id, shelf.product_id)
        if key in shelf_keys:
            raise BehaviorError("core must send one shelf quote per store and product")
        shelf_keys.add(key)
        require_int("available_grams", shelf.available_grams)
        require_int("price_cents_per_unit", shelf.price_cents_per_unit)
        if shelf.unsafe_after is not None:
            require_int("unsafe_after", shelf.unsafe_after)
        require_unit_interval("quality", shelf.quality)
        if shelf.price_day is not None:
            require_int("price_day", shelf.price_day)
    route_stores: set[str] = set()
    for route in ctx.routes:
        require_token("route store", route.store_id)
        if route.store_id not in stores:
            raise BehaviorError(f"route store {route.store_id} has no store record")
        if route.store_id in route_stores:
            raise BehaviorError(f"duplicate route for {route.store_id}")
        route_stores.add(route.store_id)
        require_int("total_seconds", route.total_seconds)
        require_token("mode", route.mode)
    if ctx.school is not None:
        require_token("school_id", ctx.school.school_id)
        require_int("portion_grams", ctx.school.portion_grams, minimum=1)
        require_unit_interval("substitution_share", ctx.school.substitution_share)
    if ctx.delivery is not None:
        require_int("ground_seconds", ctx.delivery.ground_seconds)
        require_int("ground_fee_cents", ctx.delivery.ground_fee_cents)
        require_int("drone_seconds", ctx.delivery.drone_seconds)
        require_int("drone_fee_cents", ctx.delivery.drone_fee_cents)
    _unique("event", [event.event_id for event in ctx.visible_events])
    for event in ctx.visible_events:
        require_token("event_id", event.event_id)
        require_token("event kind", event.kind)
    for household_id, cents in ctx.foreign_balances:
        require_token("foreign household", household_id)
        require_int("foreign cents", cents)
        if household_id == ctx.household.household_id:
            raise BehaviorError("foreign balance repeats the deciding household")
    for store_id, product_id, grams in ctx.tomorrow_stock:
        require_token("tomorrow store", store_id)
        require_token("tomorrow product", product_id)
        require_int("tomorrow grams", grams)
    for grant in ctx.knowledge_grants:
        if grant not in KNOWN_GRANTS:
            raise BehaviorError(f"unknown knowledge grant {grant}")


def _validate_household(household: HouseholdSnapshot) -> None:
    require_token("household_id", household.household_id)
    require_token("area_id", household.area_id)
    require_token("income_band", household.income_band)
    require_token("mobility", household.mobility)
    if not household.members:
        raise BehaviorError("household needs at least one member")
    _unique("member", [member.member_id for member in household.members])
    for member in household.members:
        require_token("member_id", member.member_id)
        require_token("age_band", member.age_band)
        if member.school_id is not None:
            require_token("school_id", member.school_id)
    require_int("spendable_cash_cents", household.spendable_cash_cents)
    require_int("credit_limit_cents", household.credit_limit_cents)
    require_int("pantry_capacity_grams", household.pantry_capacity_grams)
    require_int("time_budget_seconds", household.time_budget_seconds)
    for lot in household.pantry:
        require_token("pantry product", lot.product_id)
        require_int("pantry grams", lot.grams)
    if household.habit_store_id is not None:
        require_token("habit_store_id", household.habit_store_id)
    for store_id in household.known_store_ids:
        require_token("known store", store_id)
    for tag in household.dietary_excluded_tags:
        require_token("excluded tag", tag)
    for tag, weight in household.preference_weights:
        require_token("preference tag", tag)
        require_unit_interval(f"preference {tag}", weight)
    require_unit_interval("stress", household.stress)
    require_unit_interval("trust", household.trust)
    require_unit_interval("satisfaction", household.satisfaction)


def _unique(label: str, values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise BehaviorError(f"duplicate {label} id")
