"""School meals, kitchen limits, and household substitution.

Eligible, participating, menu-compatible pupils are planned in admission
order until kitchen capacity, program cash, or ingredient stock binds.
Absence is applied after the meal is prepared: an absent pupil cannot eat,
and that portion is waste. Plate waste is separate. The program pays for
ingredients. The household does not.

Substitution says how much eaten school food replaces a home purchase. It
can be zero. Replaced grams are capped by the household need. Cash saved on
the smaller home basket is not the program's procurement cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.policies.core_interface import CoreLedger, plan_draw
from sim.policies.evidence import require_evidence


@dataclass(frozen=True)
class Pupil:
    pupil_id: str
    household_id: str
    eligible: bool
    participating: bool
    present: bool
    menu_compatible: bool
    admission_rank: int


@dataclass(frozen=True)
class HouseholdNeed:
    household_id: str
    need_grams: int
    substitution_num: int
    substitution_den: int


@dataclass(frozen=True)
class SchoolCommand:
    evidence_state: str
    program_account: str
    school_owner: str
    school_custody: str
    supplier_account: str
    product_id: str
    food_source: str
    portion_grams: int
    ingredient_cents_per_portion: int
    kitchen_capacity: int
    plate_waste_num: int
    plate_waste_den: int
    unsafe_after: int
    now: int
    pupils: tuple[Pupil, ...]
    households: tuple[HouseholdNeed, ...]


@dataclass(frozen=True)
class PupilResult:
    pupil_id: str
    household_id: str
    outcome: str
    prepared_grams: int
    consumed_grams: int
    waste_grams: int


@dataclass(frozen=True)
class HouseholdFoodResult:
    household_id: str
    need_grams: int
    school_consumed_grams: int
    replaced_grams: int
    substitution_num: int
    substitution_den: int


@dataclass(frozen=True)
class SchoolDayResult:
    evidence_state: str
    binding_constraints: tuple[str, ...]
    meals_prepared: int
    meals_served: int
    meals_consumed: int
    absence_waste_meals: int
    grams_prepared: int
    grams_consumed: int
    grams_waste: int
    ingredient_cents: int
    pupils: tuple[PupilResult, ...]
    households: tuple[HouseholdFoodResult, ...]


@dataclass(frozen=True)
class HomePurchasePlan:
    household_id: str
    account: str
    store_owner: str
    store_account: str
    product_id: str
    price_cents_per_1000g: int
    home_custody: str


@dataclass(frozen=True)
class HomePurchaseResult:
    household_id: str
    need_grams: int
    school_consumed_grams: int
    replaced_grams: int
    purchased_grams: int
    paid_cents: int
    counterfactual_cents: int
    cash_savings_cents: int
    shortfall_grams: int
    outcome: str


def apply_school_day(ledger: CoreLedger, command: SchoolCommand) -> SchoolDayResult:
    """Prepare and serve one school day. Home baskets are settled separately."""

    _validate(command)
    needs = {item.household_id: item for item in command.households}
    candidates = [
        pupil
        for pupil in command.pupils
        if pupil.eligible and pupil.participating and pupil.menu_compatible
    ]
    candidates.sort(key=lambda pupil: (pupil.admission_rank, pupil.pupil_id))
    limits: dict[str, int] = {
        "demand": len(candidates),
        "capacity": command.kitchen_capacity,
    }
    if command.food_source == "on_hand":
        limits["food"] = _available_grams(ledger, command) // command.portion_grams
    if command.food_source == "purchase" and command.ingredient_cents_per_portion > 0:
        limits["budget"] = ledger.spendable(command.program_account) // command.ingredient_cents_per_portion
    meals = min(limits.values())
    binding = tuple(
        name
        for name in ("capacity", "budget", "food", "demand")
        if limits.get(name) == meals
    )
    cut_reason = next((name for name in ("capacity", "budget", "food") if name in binding), "")
    planned = candidates[:meals]
    planned_ids = {pupil.pupil_id for pupil in planned}
    ingredient = 0
    if command.food_source == "purchase" and meals > 0:
        ingredient = meals * command.ingredient_cents_per_portion
        ledger.buy_lot(
            payer=command.program_account,
            payee=command.supplier_account,
            product_id=command.product_id,
            owner=command.school_owner,
            custody=command.school_custody,
            grams=meals * command.portion_grams,
            cents=ingredient,
            unsafe_after=command.unsafe_after,
            source_kind="purchase",
            input_class="purchased",
            memo="school ingredients",
        )
    pupil_results = [
        _serve_or_skip(ledger, command, pupil, pupil.pupil_id in planned_ids, cut_reason)
        for pupil in sorted(command.pupils, key=lambda item: (item.admission_rank, item.pupil_id))
    ]
    consumed_by_household: dict[str, int] = {}
    for result in pupil_results:
        consumed_by_household[result.household_id] = (
            consumed_by_household.get(result.household_id, 0) + result.consumed_grams
        )
    households = tuple(
        _household_food(needs[household_id], consumed_by_household.get(household_id, 0))
        for household_id in sorted(needs)
    )
    return SchoolDayResult(
        evidence_state=command.evidence_state,
        binding_constraints=binding,
        meals_prepared=meals,
        meals_served=sum(1 for result in pupil_results if result.outcome == "served"),
        meals_consumed=sum(1 for result in pupil_results if result.consumed_grams > 0),
        absence_waste_meals=sum(1 for result in pupil_results if result.outcome == "absent"),
        grams_prepared=sum(result.prepared_grams for result in pupil_results),
        grams_consumed=sum(result.consumed_grams for result in pupil_results),
        grams_waste=sum(result.waste_grams for result in pupil_results),
        ingredient_cents=ingredient,
        pupils=tuple(pupil_results),
        households=households,
    )


def settle_home_purchases(
    ledger: CoreLedger,
    day: SchoolDayResult,
    plans: tuple[HomePurchasePlan, ...],
    *,
    now: int,
) -> tuple[HomePurchaseResult, ...]:
    """Buy the home grams that school food did not replace.

    Households settle in household-id order. A failed purchase does not count
    as cash saved.
    """

    food = {item.household_id: item for item in day.households}
    ordered = sorted(plans, key=lambda plan: plan.household_id)
    settled = []
    for plan in ordered:
        household = food[plan.household_id]
        if plan.price_cents_per_1000g < 0:
            raise ValueError("home price cannot be negative")
        buy = max(0, household.need_grams - household.replaced_grams)
        counterfactual = household.need_grams * plan.price_cents_per_1000g // 1000
        if buy == 0:
            settled.append(_home_result(household, 0, 0, counterfactual, "no_purchase", counterfactual))
            continue
        price = buy * plan.price_cents_per_1000g // 1000
        draws = plan_draw(
            ledger,
            owner=plan.store_owner,
            product_id=plan.product_id,
            grams=buy,
            now=now,
        )
        if draws is None or ledger.spendable(plan.account) < price:
            outcome = "stockout" if draws is None else "unaffordable"
            settled.append(_home_result(household, 0, 0, counterfactual, outcome, 0))
            continue
        ledger.transfer(plan.account, plan.store_account, price, memo=f"home basket {plan.household_id}")
        for lot_id, grams in draws:
            piece = ledger.take(lot_id, grams)
            ledger.transfer_lot(piece, owner=plan.household_id, custody=plan.home_custody)
        settled.append(_home_result(household, buy, price, counterfactual, "purchased", counterfactual - price))
    return tuple(settled)


def _validate(command: SchoolCommand) -> None:
    require_evidence(command.evidence_state)
    if command.food_source not in ("purchase", "on_hand"):
        raise ValueError("food source must be purchase or on_hand")
    if command.portion_grams <= 0 or command.kitchen_capacity < 0:
        raise ValueError("portion and capacity are invalid")
    if command.ingredient_cents_per_portion < 0:
        raise ValueError("ingredient cost cannot be negative")
    if command.plate_waste_den <= 0 or not 0 <= command.plate_waste_num <= command.plate_waste_den:
        raise ValueError("plate waste fraction is invalid")
    seen = set()
    for household in command.households:
        if household.household_id in seen:
            raise ValueError("duplicate household")
        seen.add(household.household_id)
        if household.need_grams < 0:
            raise ValueError("need cannot be negative")
        if household.substitution_den <= 0 or not 0 <= household.substitution_num <= household.substitution_den:
            raise ValueError("substitution fraction is invalid")
    for pupil in command.pupils:
        if pupil.household_id not in seen:
            raise ValueError("pupil household is missing")


def _available_grams(ledger: CoreLedger, command: SchoolCommand) -> int:
    total = 0
    for lot in ledger.lots():
        if lot.owner != command.school_owner or lot.product_id != command.product_id:
            continue
        if lot.unsafe_after <= command.now or ledger.reserved_grams(lot.lot_id) > 0:
            continue
        total += lot.grams
    return total


def _serve_or_skip(
    ledger: CoreLedger,
    command: SchoolCommand,
    pupil: Pupil,
    planned: bool,
    cut_reason: str,
) -> PupilResult:
    if not planned:
        if not pupil.eligible:
            outcome = "ineligible"
        elif not pupil.participating:
            outcome = "not_participating"
        elif not pupil.menu_compatible:
            outcome = "menu_conflict"
        else:
            outcome = cut_reason or "unserved"
        return PupilResult(pupil.pupil_id, pupil.household_id, outcome, 0, 0, 0)
    draws = plan_draw(
        ledger,
        owner=command.school_owner,
        product_id=command.product_id,
        grams=command.portion_grams,
        now=command.now,
    )
    if draws is None:
        raise RuntimeError("planned meal had no ingredients")
    if pupil.present:
        waste = command.portion_grams * command.plate_waste_num // command.plate_waste_den
        consumed = command.portion_grams - waste
        _fate(ledger, draws, waste, consumed, "plate_waste")
        return PupilResult(
            pupil.pupil_id, pupil.household_id, "served", command.portion_grams, consumed, waste
        )
    _fate(ledger, draws, command.portion_grams, 0, "absence")
    return PupilResult(
        pupil.pupil_id, pupil.household_id, "absent", command.portion_grams, 0, command.portion_grams
    )


def _fate(
    ledger: CoreLedger,
    draws: tuple[tuple[str, int], ...],
    waste_grams: int,
    consume_grams: int,
    waste_reason: str,
) -> None:
    pieces = [ledger.take(lot_id, grams) for lot_id, grams in draws]
    left_waste = waste_grams
    left_consume = consume_grams
    for piece in pieces:
        if left_waste <= 0:
            break
        available = _grams(ledger, piece)
        take_grams = min(available, left_waste)
        if take_grams:
            ledger.write_off(piece, take_grams, reason=waste_reason)
            left_waste -= take_grams
    for piece in pieces:
        if left_consume <= 0:
            break
        available = _grams(ledger, piece)
        take_grams = min(available, left_consume)
        if take_grams:
            ledger.consume(piece, take_grams, reason="school meal")
            left_consume -= take_grams
    if left_waste != 0 or left_consume != 0:
        raise RuntimeError("meal portion was not fully assigned")


def _grams(ledger: CoreLedger, lot_id: str) -> int:
    for lot in ledger.lots():
        if lot.lot_id == lot_id:
            return lot.grams
    return 0


def _household_food(need: HouseholdNeed, consumed: int) -> HouseholdFoodResult:
    replaced = min(
        need.need_grams,
        consumed * need.substitution_num // need.substitution_den,
    )
    return HouseholdFoodResult(
        need.household_id,
        need.need_grams,
        consumed,
        replaced,
        need.substitution_num,
        need.substitution_den,
    )


def _home_result(
    household: HouseholdFoodResult,
    purchased: int,
    paid: int,
    counterfactual: int,
    outcome: str,
    savings: int,
) -> HomePurchaseResult:
    shortfall = max(0, household.need_grams - household.school_consumed_grams - purchased)
    return HomePurchaseResult(
        household.household_id,
        household.need_grams,
        household.school_consumed_grams,
        household.replaced_grams,
        purchased,
        paid,
        counterfactual,
        savings,
        shortfall,
        outcome,
    )
