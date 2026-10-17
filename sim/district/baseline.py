"""Reproducible 250-household baseline.

The run seed changes admission order and choice noise. It does not change
who the households are. School meals, subsidies, and vehicle routes are not
settled here.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sim.core import (
    PHASE_CHOICE,
    PHASE_CONSUME,
    PHASE_POLICY,
    PHASE_SETTLE,
    KERNEL_VERSION,
    ChoiceOffer,
    ConsumeFood,
    FeasibleOption,
    IntroduceLot,
    ObservedFact,
    OpenAccount,
    PurchaseLot,
    RecordChoice,
    ReserveResources,
    TransferCash,
    account_for_owner,
    apply_command,
    available_grams,
    empty_state,
    fold_events,
    invariant_problems,
    lots_for_owner,
    scene_snapshot,
    second_in_day,
    seeded_admission_order,
    sha256_hex,
    state_hash,
)
from sim.district.network import shortest_path
from sim.district.population import Household, Population, Pupil, attendance_present, build_population
from sim.district.shopping import DayPlan, plan_household
from sim.district.snapshot import Snapshot, load_snapshot


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class Trip:
    household_id: str
    day_index: int
    store_id: str | None
    travel_seconds: int
    payment_cents: int
    grams: int
    option_id: str


@dataclass(frozen=True, slots=True)
class BaselineReport:
    schema_version: int
    completion: bool
    run_id: str
    run_seed: int
    population_seed: int
    scenario_id: str
    catalog_id: str
    catalog_sha256: str
    snapshot_id: str
    kernel_version: str
    state_hash: str
    scene_hash: str
    population_hash: str
    event_count: int
    household_count: int
    pupil_count: int
    eligible_pupil_count: int
    present_pupil_days: int
    choice_count: int
    purchase_count: int
    rejection_count: int
    total_need_grams: int
    household_food_spend_cents: int
    municipal_spend_cents: int
    grams_purchased: int
    grams_consumed: int
    grams_unmet: int
    shopping_travel_seconds: int
    school_access_seconds: int
    closing_store_grams: int
    checks: tuple[Check, ...]


@dataclass(frozen=True, slots=True)
class BaselineResult:
    report: BaselineReport
    state: object
    events: tuple
    trips: tuple[Trip, ...]
    population: Population
    rejections: tuple[tuple[str, str], ...]


def run_baseline(seed: int = 17, snapshot: Snapshot | None = None) -> BaselineResult:
    loaded = snapshot or load_snapshot()
    population = build_population(loaded.controls, loaded.places)
    catalog = loaded.catalog
    run_id = f"baseline-{seed}"
    state = empty_state(
        run_id=run_id,
        scenario_id=loaded.header["scenario_id"],
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog.sha256,
        known_product_ids=tuple(product.product_id for product in catalog.products),
    )
    opening = _opening_commands(loaded, population)
    events: list = []
    rejections: list[tuple[str, str]] = []
    for command in opening:
        state, ok = _apply(state, command, events, rejections)
        if not ok:
            raise RuntimeError(f"opening command rejected: {rejections[-1]}")
    households = {household.household_id: household for household in population.households}
    order_ids = [household.household_id for household in population.households]
    trips: list[Trip] = []
    spend_by_income: Counter[str] = Counter()
    grams_by_income: Counter[str] = Counter()
    unmet_by_income: Counter[str] = Counter()
    total_need = 0
    total_consumed = 0
    shop_offset = loaded.behavior["shop_offset_seconds"]
    daily_need = loaded.controls["daily_need_grams_per_person"]
    for day in loaded.days:
        admission = seeded_admission_order(seed, f"shop-day-{day.day_index}", order_ids)
        for rank, household_id in enumerate(admission):
            household = households[household_id]
            second = second_in_day(day, shop_offset + rank)
            need = daily_need * household.size
            total_need += need
            plan = plan_household(
                state,
                household,
                tuple(loaded.places["stores"]),
                loaded.network,
                loaded.behavior,
                day_index=day.day_index,
                run_seed=seed,
                shop_offset=shop_offset,
                need_grams=need,
            )
            state, ok = _apply(state, _choice_command(state, household, plan, day.day_index, second), events, rejections)
            bought = 0
            if ok and plan.chosen.store_id is not None and plan.chosen.lot_id is not None:
                reserve_id = f"reserve-{household_id}-d{day.day_index}"
                state, reserved = _apply(
                    state,
                    ReserveResources(
                        reserve_id,
                        second,
                        PHASE_SETTLE,
                        household_id,
                        f"acct-{household_id}",
                        plan.chosen.payment_cents,
                        plan.chosen.lot_id,
                        plan.chosen.grams,
                    ),
                    events,
                    rejections,
                )
                if reserved:
                    state, purchased = _apply(
                        state,
                        PurchaseLot(
                            f"buy-{household_id}-d{day.day_index}",
                            second,
                            PHASE_SETTLE,
                            f"acct-{household_id}",
                            _seller_account(loaded, plan.chosen.store_id),
                            f"home-{household_id}",
                            plan.chosen.lot_id,
                            plan.chosen.grams,
                            plan.chosen.payment_cents,
                            f"rsv.{reserve_id}",
                        ),
                        events,
                        rejections,
                    )
                    if purchased:
                        bought = plan.chosen.grams
                        trips.append(
                            Trip(
                                household_id,
                                day.day_index,
                                plan.chosen.store_id,
                                plan.chosen.travel_seconds,
                                plan.chosen.payment_cents,
                                plan.chosen.grams,
                                plan.chosen.option_id,
                            )
                        )
                        spend_by_income[household.income_band] += plan.chosen.payment_cents
                        grams_by_income[household.income_band] += plan.chosen.grams
                    else:
                        state, _released = _apply(
                            state,
                            _release(reserve_id, second),
                            events,
                            rejections,
                        )
            consumed = _consume(state, household_id, min(need, _on_hand(state, household_id)), second, day.day_index, events, rejections)
            state = consumed[0]
            total_consumed += consumed[1]
            unmet_by_income[household.income_band] += need - consumed[1]
    report = _report(
        loaded,
        population,
        state,
        events,
        trips,
        rejections,
        seed,
        total_need,
        total_consumed,
        spend_by_income,
        grams_by_income,
        unmet_by_income,
    )
    return BaselineResult(report, state, tuple(events), tuple(trips), population, tuple(rejections))


def _opening_commands(snapshot: Snapshot, population: Population) -> list:
    places = snapshot.places
    commands: list = [
        OpenAccount("open-ext", 0, PHASE_POLICY, "acct-external-opening", "external", "external", True),
        OpenAccount(
            "open-muni",
            0,
            PHASE_POLICY,
            places["municipality"]["account_id"],
            places["municipality"]["actor_id"],
            "municipality",
            False,
        ),
    ]
    for school in places["schools"]:
        commands.append(
            OpenAccount(
                f"open-{school['account_id']}",
                0,
                PHASE_POLICY,
                school["account_id"],
                school["actor_id"],
                "school",
                False,
            )
        )
    for store in places["stores"]:
        commands.append(
            OpenAccount(
                f"open-{store['account_id']}",
                0,
                PHASE_POLICY,
                store["account_id"],
                store["actor_id"],
                "retailer",
                False,
            )
        )
    for household in population.households:
        commands.append(
            OpenAccount(
                f"open-acct-{household.household_id}",
                0,
                PHASE_POLICY,
                f"acct-{household.household_id}",
                household.household_id,
                "household",
                False,
            )
        )
        commands.append(
            TransferCash(
                f"cash-{household.household_id}",
                0,
                PHASE_POLICY,
                "acct-external-opening",
                f"acct-{household.household_id}",
                household.food_budget_cents,
                "opening_balance",
            )
        )
    for store in places["stores"]:
        if store["opening_grams"] <= 0:
            continue
        grams = store["opening_grams"]
        acquisition = (grams // 100) * store["acquisition_cents_per_100g"]
        commands.append(
            IntroduceLot(
                f"open-{store['lot_id']}",
                0,
                PHASE_POLICY,
                store["lot_id"],
                store["product_id"],
                store["actor_id"],
                store["place_id"],
                grams,
                acquisition,
                store["unsafe_after_second"],
            )
        )
    return commands


def _choice_command(state, household: Household, plan: DayPlan, day_index: int, second: int) -> RecordChoice:
    offer = ChoiceOffer(
        decision_id=f"dec-{household.household_id}-d{day_index}",
        household_id=household.household_id,
        revision=state.next_sequence - 1,
        known_facts=(
            ObservedFact("household_id", household.household_id),
            ObservedFact("day_index", str(day_index)),
            ObservedFact("income_band", household.income_band),
        ),
        options=tuple(
            FeasibleOption(
                option.option_id,
                f"grams={option.grams};cents={option.payment_cents};seconds={option.travel_seconds}",
            )
            for option in plan.options
        ),
    )
    chosen = plan.chosen
    return RecordChoice(
        command_id=f"choice-{household.household_id}-d{day_index}",
        second=second,
        phase=PHASE_CHOICE,
        decision_id=offer.decision_id,
        household_id=household.household_id,
        option_id=chosen.option_id,
        origin="rule",
        observation_hash=sha256_hex(offer),
        revision=offer.revision,
        explanation=(
            f"rule {chosen.option_id} payment_cents={chosen.payment_cents} "
            f"travel_seconds={chosen.travel_seconds} grams={chosen.grams}"
        ),
    )


def _release(reserve_id: str, second: int):
    from sim.core import ReleaseReservation

    return ReleaseReservation(f"release-{reserve_id}", second, PHASE_SETTLE, f"rsv.{reserve_id}")


def _seller_account(snapshot: Snapshot, store_id: str) -> str:
    for store in snapshot.places["stores"]:
        if store["store_id"] == store_id:
            return store["account_id"]
    raise KeyError(store_id)


def _on_hand(state, owner_id: str) -> int:
    return sum(available_grams(lot) for lot in lots_for_owner(state, owner_id))


def _consume(state, household_id: str, grams: int, second: int, day_index: int, events: list, rejections: list) -> tuple[object, int]:
    remaining = grams
    taken = 0
    lots = sorted(
        (lot for lot in lots_for_owner(state, household_id) if available_grams(lot) > 0),
        key=lambda lot: (lot.unsafe_after if lot.unsafe_after is not None else 10**12, lot.lot_id),
    )
    for index, lot in enumerate(lots):
        if remaining <= 0:
            break
        bite = min(available_grams(lot), remaining)
        state, ok = _apply(
            state,
            ConsumeFood(
                f"eat-{household_id}-d{day_index}-{index}",
                second,
                PHASE_CONSUME,
                household_id,
                lot.lot_id,
                bite,
            ),
            events,
            rejections,
        )
        if not ok:
            break
        remaining -= bite
        taken += bite
    return state, taken


def _apply(state, command, events: list, rejections: list[tuple[str, str]]):
    transition = apply_command(state, command)
    if transition.status != "accepted":
        rejections.append((command.command_id, transition.reason or transition.status))
        return state, False
    events.extend(transition.events)
    return transition.state, True


def _report(
    snapshot: Snapshot,
    population: Population,
    state,
    events: list,
    trips: list[Trip],
    rejections: list[tuple[str, str]],
    seed: int,
    total_need: int,
    total_consumed: int,
    spend_by_income: Counter[str],
    grams_by_income: Counter[str],
    unmet_by_income: Counter[str],
) -> BaselineReport:
    del spend_by_income, grams_by_income, unmet_by_income
    problems = invariant_problems(state)
    journal_spend = 0
    for entry in state.journal:
        for line in entry.lines:
            if line.memo.startswith("purchase:") and line.cents < 0:
                journal_spend += -line.cents
    trip_spend = sum(trip.payment_cents for trip in trips)
    trip_grams = sum(trip.grams for trip in trips)
    purchased_moves = sum(
        movement.grams
        for movement in state.movements
        if movement.kind == "transfer" and movement.to_owner_id is not None and movement.to_owner_id.startswith("hh-")
    )
    travel_ok = True
    households = {household.household_id: household for household in population.households}
    for trip in trips:
        household = households[trip.household_id]
        if trip.store_id is None:
            travel_ok = False
            break
        found = shortest_path(snapshot.network, household.area_id, trip.store_id)
        if found is None:
            travel_ok = False
            break
        multiplier = snapshot.behavior["mobility_multiplier"][household.mobility]
        expected = (household.access_seconds + found[1]) * multiplier
        if expected != trip.travel_seconds or trip.payment_cents * 100 != trip.grams * _price(snapshot, trip.store_id):
            travel_ok = False
            break
    school_access, school_ok = _school_access(snapshot, population)
    present = sum(
        1
        for pupil in population.pupils
        for day in snapshot.days
        if attendance_present(population.population_seed, pupil.member_id, day.day_index)
    )
    member_ids = {member.member_id for household in population.households for member in household.members}
    owners = {account.owner_id for account in state.accounts}
    school_age = {
        member.member_id
        for household in population.households
        for member in household.members
        if member.age_band in set(snapshot.controls["school_age_bands"])
    }
    pupil_ids = [pupil.member_id for pupil in population.pupils]
    schools = {school["school_id"]: school for school in snapshot.places["schools"]}
    assignment_ok = pupil_ids == list(dict.fromkeys(pupil_ids)) and set(pupil_ids) == school_age
    eligible_ok = all(
        pupil.eligible == (schools[pupil.school_id]["program_status"] == "active")
        and pupil.school_id == _area_school(snapshot, households[pupil.household_id].area_id)
        for pupil in population.pupils
    )
    margins_ok = _margins(population, snapshot.controls)
    municipal = next(store for store in snapshot.places["stores"] if store["store_id"] == "store-municipal")
    municipal_closed = (not municipal["operating"]) and municipal["opening_grams"] == 0 and not lots_for_owner(state, "store-municipal")
    municipal_cash = account_for_owner(state, "muni")
    replayed = fold_events(
        empty_state(
            run_id=state.run_id,
            scenario_id=state.scenario_id,
            catalog_id=state.catalog_id,
            catalog_sha256=state.catalog_sha256,
            known_product_ids=state.known_product_ids,
        ),
        tuple(events),
    )
    checks = (
        Check("household_count", len(population.households) == 250, str(len(population.households))),
        Check("margins", margins_ok, "size, income, tenure, and area match the frozen quotas"),
        Check("pupil_assignment", assignment_ok and eligible_ok, f"{len(population.pupils)} pupils"),
        Check("no_pupil_accounts", member_ids.isdisjoint(owners), "children are not account owners"),
        Check("invariants", problems == (), "; ".join(problems) or "balanced"),
        Check("no_overspend", problems == (), "spendable cash stays non-negative for accounts without credit"),
        Check("food_conservation", problems == (), "opening imports equal stock plus consumption plus waste"),
        Check("reservations_released", state.reservations == (), str(len(state.reservations))),
        Check("zero_rejections", not rejections, str(rejections[:3])),
        Check("spending_reconciled", journal_spend == trip_spend, f"journal {journal_spend} trips {trip_spend}"),
        Check("stock_reconciled", purchased_moves == trip_grams, f"moved {purchased_moves} trips {trip_grams}"),
        Check("travel_reconciled", travel_ok, f"{sum(trip.travel_seconds for trip in trips)} seconds"),
        Check("school_access_reconciled", school_ok, f"{school_access} seconds"),
        Check("choices_complete", len(state.choices) == len(population.households) * len(snapshot.days), str(len(state.choices))),
        Check("municipal_spend_zero", municipal_cash is not None and municipal_cash.settled_cents == 0, "no baseline subsidy"),
        Check("municipal_candidate_closed", municipal_closed, "store-municipal is not operating and holds no stock"),
        Check(
            "recorded_attributes_not_settled",
            all("nonfood" not in line.memo and "cooking" not in line.memo for entry in state.journal for line in entry.lines),
            "essential non-food cents and cooking access are recorded and not posted",
        ),
        Check("meals_not_served", all(account.kind != "school" or account.settled_cents == 0 for account in state.accounts), "school meal service is outside this baseline"),
        Check("evidence_illustrative", snapshot.header["evidence_state"] == "illustrative", snapshot.header["evidence_state"]),
        Check("replay_matches", state_hash(replayed) == state_hash(state), "folded events reproduce the economic state"),
        Check("nominal_cents", snapshot.header["price_base_month"] is None, "no real-dollar rewrite"),
    )
    closing_store = sum(
        lot.grams for lot in state.lots if lot.owner_id.startswith("store-")
    )
    return BaselineReport(
        schema_version=1,
        completion=all(check.passed for check in checks),
        run_id=state.run_id,
        run_seed=seed,
        population_seed=population.population_seed,
        scenario_id=state.scenario_id,
        catalog_id=state.catalog_id,
        catalog_sha256=state.catalog_sha256,
        snapshot_id=snapshot.header["snapshot_id"],
        kernel_version=KERNEL_VERSION,
        state_hash=state_hash(state),
        scene_hash=scene_snapshot(state).state_hash,
        population_hash=population.population_hash,
        event_count=len(events),
        household_count=len(population.households),
        pupil_count=len(population.pupils),
        eligible_pupil_count=sum(1 for pupil in population.pupils if pupil.eligible),
        present_pupil_days=present,
        choice_count=len(state.choices),
        purchase_count=len(trips),
        rejection_count=len(rejections),
        total_need_grams=total_need,
        household_food_spend_cents=trip_spend,
        municipal_spend_cents=0 if municipal_cash is not None and municipal_cash.settled_cents == 0 else -1,
        grams_purchased=trip_grams,
        grams_consumed=total_consumed,
        grams_unmet=total_need - total_consumed,
        shopping_travel_seconds=sum(trip.travel_seconds for trip in trips),
        school_access_seconds=school_access,
        closing_store_grams=closing_store,
        checks=checks,
    )


def _margins(population: Population, controls: dict) -> bool:
    size_counts = Counter(str(household.size) for household in population.households)
    income_counts = Counter(household.income_band for household in population.households)
    tenure_counts = Counter(household.tenure for household in population.households)
    area_counts = Counter(household.area_id for household in population.households)
    return (
        _same(size_counts, controls["size"])
        and _same(income_counts, controls["income"])
        and _same(tenure_counts, controls["tenure"])
        and _same(area_counts, controls["area"])
    )


def _same(actual: Counter[str], pairs: list) -> bool:
    return all(actual[str(key)] == count for key, count in pairs) and sum(actual.values()) == sum(count for _, count in pairs)


def _price(snapshot: Snapshot, store_id: str) -> int:
    for store in snapshot.places["stores"]:
        if store["store_id"] == store_id:
            return store["price_cents_per_100g"]
    raise KeyError(store_id)


def _area_school(snapshot: Snapshot, area_id: str) -> str:
    for area in snapshot.places["areas"]:
        if area["area_id"] == area_id:
            return area["school_id"]
    raise KeyError(area_id)


def _school_access(snapshot: Snapshot, population: Population) -> tuple[int, bool]:
    households = {household.household_id: household for household in population.households}
    total = 0
    for pupil in population.pupils:
        household = households[pupil.household_id]
        found = shortest_path(snapshot.network, household.area_id, pupil.school_id)
        if found is None:
            return total, False
        total += household.access_seconds + found[1]
    return total, True
