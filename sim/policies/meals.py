"""School meals, attendance, and household substitution.

An absent or ineligible pupil is not served. The school's payment is not
rewritten as a household purchase. Substitution can be zero.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core import (
    PHASE_CONSUME,
    PHASE_EXPIRY,
    PHASE_POLICY,
    PHASE_SETTLE,
    CAD_CENTS,
    COUNT,
    GRAMS,
    ApplyExpiry,
    ConsumeFood,
    IntroduceLot,
    Metric,
    OpenAccount,
    PurchaseLot,
    RecordChoice,
    TransferCash,
    lots_for_owner,
    sha256_hex,
)

from sim.policies.session import memo_cents, settle, world

PORTION_GRAMS = 200
STOCK_GRAMS = 250
FOOD_CENTS = 75
LABOR_CENTS = 40
SCHOOL_BUDGET_CENTS = 200
HOME_NEED_GRAMS = 400
HOME_PRICE_PER_100G = 50
HOME_STOCK_GRAMS = 2000
HOME_ACQUISITION_CENTS = 600


@dataclass(frozen=True, slots=True)
class MealDay:
    evidence_state: str
    state: object
    events: tuple
    meals_prepared: int
    meals_served: int
    meals_consumed: int
    substitution_grams: int
    household_purchase_grams: int
    household_payment_cents: int
    school_food_cents: int
    school_labor_cents: int
    school_cost_cents: int
    waste_grams: int
    metrics: tuple[Metric, ...]
    note: str


def run_school_day(*, substitution_grams: int, kitchen_capacity_grams: int = PORTION_GRAMS) -> MealDay:
    if substitution_grams < 0 or kitchen_capacity_grams < 0:
        raise ValueError("substitution and capacity must be >= 0")
    served = kitchen_capacity_grams >= PORTION_GRAMS
    replaced = min(PORTION_GRAMS, substitution_grams) if served else 0
    home_grams = HOME_NEED_GRAMS - replaced
    state = world("school-day", "school-only")
    commands: list = [
        OpenAccount("open-ext", 0, PHASE_POLICY, "acct-ext", "ext", "external", True),
        OpenAccount("open-m", 0, PHASE_POLICY, "acct-m", "muni", "municipality", False),
        OpenAccount("open-k", 0, PHASE_POLICY, "acct-k", "school-a", "school", False),
        OpenAccount("open-r", 0, PHASE_POLICY, "acct-r", "store-r", "retailer", False),
        OpenAccount("open-ha", 0, PHASE_POLICY, "acct-ha", "hh-a", "household", False),
        OpenAccount("open-hb", 0, PHASE_POLICY, "acct-hb", "hh-b", "household", False),
        OpenAccount("open-hc", 0, PHASE_POLICY, "acct-hc", "hh-c", "household", False),
        TransferCash("fund-m", 0, PHASE_POLICY, "acct-ext", "acct-m", SCHOOL_BUDGET_CENTS, "appropriation"),
        TransferCash("fund-k", 0, PHASE_POLICY, "acct-m", "acct-k", SCHOOL_BUDGET_CENTS, "operating_subsidy"),
    ]
    for owner, account in (("hh-a", "acct-ha"), ("hh-b", "acct-hb"), ("hh-c", "acct-hc")):
        commands.append(TransferCash(f"cash-{owner}", 0, PHASE_POLICY, "acct-ext", account, 1000, "opening_balance"))
    commands.extend(
        [
            TransferCash("k-food", 0, PHASE_POLICY, "acct-k", "acct-ext", FOOD_CENTS, "inventory_payment"),
            TransferCash("k-labor", 0, PHASE_POLICY, "acct-k", "acct-ext", LABOR_CENTS, "labor"),
            IntroduceLot("lot-k", 0, PHASE_POLICY, "lot-k", "produce.fresh", "school-a", "school-a", STOCK_GRAMS, FOOD_CENTS, 10),
            IntroduceLot(
                "lot-r",
                0,
                PHASE_POLICY,
                "lot-r",
                "produce.fresh",
                "store-r",
                "store-r",
                HOME_STOCK_GRAMS,
                HOME_ACQUISITION_CENTS,
                None,
            ),
            _choice("pupil-a", "hh-a", "meal:served" if served else "meal:unprepared", 4),
            _choice("pupil-b", "hh-b", "meal:absent", 4),
            _choice("pupil-c", "hh-c", "meal:ineligible", 4),
        ]
    )
    if served:
        commands.append(ConsumeFood("serve-a", 6, PHASE_CONSUME, "school-a", "lot-k", PORTION_GRAMS))
    commands.append(ApplyExpiry("waste-left", 10, PHASE_EXPIRY))
    for owner, account, grams in (
        ("hh-a", "acct-ha", home_grams),
        ("hh-b", "acct-hb", HOME_NEED_GRAMS),
        ("hh-c", "acct-hc", HOME_NEED_GRAMS),
    ):
        if grams <= 0:
            continue
        commands.append(
            PurchaseLot(
                f"buy-{owner}",
                12,
                PHASE_SETTLE,
                account,
                "acct-r",
                f"home-{owner}",
                "lot-r",
                grams,
                grams // 100 * HOME_PRICE_PER_100G,
            )
        )
    state, events = settle(state, commands)
    household_grams = sum(lot.grams for lot in lots_for_owner(state, "hh-a"))
    payment = memo_cents(state, "acct-ha", f"purchase:produce.fresh:{home_grams}", leaving=True) if home_grams else 0
    food = memo_cents(state, "acct-k", "inventory_payment", leaving=True)
    labor = memo_cents(state, "acct-k", "labor", leaving=True)
    waste = sum(movement.grams for movement in state.movements if movement.kind == "waste")
    consumed = state.consumed_grams
    meals_consumed = 1 if served and consumed == PORTION_GRAMS else 0
    return MealDay(
        evidence_state="illustrative",
        state=state,
        events=events,
        meals_prepared=1 if served else 0,
        meals_served=1 if served else 0,
        meals_consumed=meals_consumed,
        substitution_grams=replaced,
        household_purchase_grams=household_grams,
        household_payment_cents=payment,
        school_food_cents=food,
        school_labor_cents=labor,
        school_cost_cents=food + labor,
        waste_grams=waste,
        metrics=(
            Metric("meals_consumed", meals_consumed, COUNT),
            Metric("school_cost", food + labor, CAD_CENTS),
            Metric("household_payment", payment, CAD_CENTS),
            Metric("household_grams", household_grams, GRAMS),
        ),
        note=(
            "Pupil A is eligible and present. Pupil B is eligible and absent. Pupil C is present and ineligible. "
            "Only A can be served, and only when the kitchen can make one 200 g portion. "
            "Substitution reduces A's home purchase and does not move the school's cost onto A's account."
        ),
    )


def _choice(pupil: str, household: str, option: str, second: int) -> RecordChoice:
    return RecordChoice(
        command_id=f"choice-{pupil}",
        second=second,
        phase=4,
        decision_id=f"dec-{pupil}",
        household_id=household,
        option_id=option,
        origin="rule",
        observation_hash=sha256_hex({"pupil": pupil, "option": option}),
        revision=0,
        explanation=f"{pupil} {option}",
    )
