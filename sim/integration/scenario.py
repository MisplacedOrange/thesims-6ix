"""A connected, illustrative district day, using the four selected packages.

This is a produce-component model, not nutritional adequacy or observed
Toronto behavior. Existing active synthetic school assignments form the
baseline. Expansion changes eligibility; procurement mode is a nested contrast.
"""
from dataclasses import asdict, dataclass, replace
from decimal import Decimal

from sim.behavior.coordinator import BehaviorConfig, resolve_barrier
from sim.behavior.latent import LatentCoefficients, LatentState, update_latent
from sim.behavior.offers import build_choice_offer
from sim.behavior.panel import RosterHousehold, select_focal_panel
from sim.behavior.snapshot import (
    CatalogProduct, DecisionContext, HouseholdSnapshot, Member, RouteInfo, StoreInfo, StoreShelf,
)
from sim.core import (
    PHASE_CHOICE, PHASE_SETTLE, PurchaseLot, RecordChoice, ReleaseReservation,
    ReserveResources, empty_state, fold_events, invariant_problems, sha256_hex, state_hash,
)
from sim.district import attendance_present, build_population, load_snapshot, shortest_path
from sim.experiments.adapters import HouseholdMetric
from sim.experiments.design import cell_id_for, normalize_policies
from sim.integration.ledger import KernelLedger, KernelLogisticsPort
from sim.logistics.engine import LogisticsEngine
from sim.logistics.models import CarrierSpec, Corridor, DeliveryOrder, FleetConfig, ScenarioContext, straight_leg
from sim.policies.core_interface import plan_draw
from sim.policies.groceries import GroceryCommand, OverheadItem, Shopper
from sim.policies.processing import ProcessingCommand, apply_processing
from sim.policies.procurement import (
    DecentralizedArm, PooledArm, PriceBand, SiteDemand, SupplyContract, run_decentralized, run_pooled,
)
from sim.policies.school_meals import HouseholdNeed, Pupil, SchoolCommand, apply_school_day
from sim.policies.trading import GrocerySession


@dataclass(frozen=True)
class DistrictConfig:
    households: int = 250
    subsidy_cents: int = 60000
    price_support_cents: int = 10000
    municipal_access_seconds: int = 120
    procurement_mode: str = "decentralized"
    route_eligible: bool = False
    substitution_share: str = "0.5"
    participation: str = "0.8"

    def __post_init__(self):
        if type(self.households) is not int or not 1 <= self.households <= 250:
            raise ValueError("households must be 1..250 actual unweighted records")
        if self.procurement_mode not in {"decentralized", "pooled"}:
            raise ValueError("unknown procurement mode")
        for value in (self.subsidy_cents, self.price_support_cents, self.municipal_access_seconds):
            if type(value) is not int or value < 0:
                raise ValueError("funding must be nonnegative integer cents")
        if type(self.route_eligible) is not bool:
            raise ValueError("route eligibility must be boolean")
        for value in (self.substitution_share, self.participation):
            if not Decimal(value).is_finite() or not 0 <= Decimal(value) <= 1:
                raise ValueError("shares must be finite and inside [0,1]")


@dataclass
class DistrictRun:
    ledger: KernelLedger
    outcomes: dict
    households: tuple[HouseholdMetric, ...]
    decisions: tuple
    settlements: tuple
    journeys: tuple
    feelings: dict
    policy_results: dict
    logistics_state: dict
    economic_hash: str
    inputs: dict


def run_district(seed=17, enabled=(), config=None, shocks=()):
    from sim.behavior.determinism import draw_unit

    config = config or DistrictConfig()
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    enabled = normalize_policies(enabled)
    loaded = load_snapshot()
    population = build_population(loaded.controls, loaded.places)
    # Smaller checks select actual records across the frozen roster; no weights.
    households = tuple(population.households[i * 250 // config.households] for i in range(config.households))
    ids = {h.household_id for h in households}
    pupils = tuple(p for p in population.pupils if p.household_id in ids)
    schools = tuple(sorted({p.school_id for p in pupils}))
    ledger = KernelLedger(f"{cell_id_for(enabled).replace('+', '-')}-s{seed}")
    ledger.ensure_account("muni", "municipality")
    ledger.endow("muni", 1_000_000, memo="illustrative appropriation")
    income = next((Decimal(s.value) for s in shocks if s.actor == "district" and s.day_index == 0 and s.purpose == "income"), Decimal("0.5"))
    weather = next((Decimal(s.value) for s in shocks if s.actor == "district" and s.day_index == 0 and s.purpose == "weather"), Decimal("0.5"))
    for h in households:
        ledger.ensure_account(h.household_id, "household")
        # Explicit synthetic daily-budget shock, identical across treatments.
        ledger.endow(h.household_id, int(Decimal(h.food_budget_cents) / 7 * (Decimal("0.9") + income / 5)), memo="daily food budget")
    for account, kind, budget in (("hub", "hub", 150000), ("fleet", "carrier", 100000),
                                   ("processor", "processor", 1000)):
        ledger.ensure_account(account, kind)
        ledger.transfer("muni", account, budget, memo="program allocation")
    for school in schools:
        ledger.ensure_account(school, "school")
        ledger.transfer("muni", school, 20000, memo="school allocation")
    for store in loaded.places["stores"]:
        ledger.ensure_account(store["store_id"], "retailer")
        if store["operating"]:
            ledger.open_lot(product_id="produce.fresh", owner=store["store_id"], custody=store["store_id"],
                grams=store["opening_grams"], acquisition_cents=store["opening_grams"] * 30 // 100,
                unsafe_after=store["unsafe_after_second"], source_kind="opening", input_class="purchased")
    ledger.ensure_account("food-bank", "hub")
    donation = ledger.open_lot(product_id="produce.fresh", owner="donor", custody="donor",
        grams=100, acquisition_cents=0, unsafe_after=90000, source_kind="opening", input_class="rescued")
    donation_hold = ledger.reserve_lot(donation, "food-bank")
    surplus = ledger.open_lot(product_id="produce.fresh", owner="donor", custody="donor",
        grams=len(households) * 100, acquisition_cents=0, unsafe_after=90000,
        source_kind="opening", input_class="rescued")
    policy_results = {}
    if "processing" in enabled:
        command = ProcessingCommand("illustrative", "processor", "processor", "processor", 100,
            len(households) * 100, "process", 3, 4, "produce.prepared", 90000,
            50, "external:carrier", 0, 1, 80, "external:labor", False, 0,
            "produce.fresh", len(households) * 100, len(households) * 100,
            "hub", "hub", ("donor",), ("rescued",), ())
        policy_results["processing"] = asdict(ledger.policy(apply_processing, command))

    # Plan preparation before attendance is realized; absences become waste.
    participating = {p.member_id: draw_unit(seed, actor=p.member_id, day=0, purpose="participation") < float(config.participation) for p in pupils}
    eligible = {p.member_id: p.eligible or "school" in enabled for p in pupils}
    demand = {school: sum(300 for p in pupils if p.school_id == school and eligible[p.member_id] and participating[p.member_id]) for school in schools}
    ledger.at(200)
    for school in schools:
        target = demand[school]
        for lot in tuple(ledger.lots()):
            if lot.owner == "hub" and lot.product_id == "produce.prepared" and target:
                give = min(target, lot.grams)
                piece = ledger.take(lot.lot_id, give)
                ledger.transfer_lot(piece, owner=school, custody="hub")
                target -= give
        demand[school] = target
    contract = SupplyContract("illustrative", (PriceBand(0, 250), PriceBand(10000, 220)),
        0, 1, 1, 1, 1, 0, 1, "delivered", "external:supplier", "produce.prepared", 90000, 200)
    sites = tuple(SiteDemand(school, school, school, "hub", demand[school], index) for index, school in enumerate(schools))
    with ledger.atomic():
        if config.procurement_mode == "pooled":
            procurement = run_pooled(ledger, sites, PooledArm(contract, "hub", "hub", "hub",
                80, "external:labor", 0, "external:carrier", 0, "external:carrier"))
        else:
            procurement = run_decentralized(ledger, sites, DecentralizedArm(contract, 0, "external:carrier"))
    policy_results["procurement"] = asdict(procurement)

    transport = _deliver_school_food(ledger, seed, schools, ids,
        "drones" in enabled, config.route_eligible and weather >= Decimal("0.1"))
    ledger.at(28000)
    replaced, school_consumed = {}, {}
    substitution = int(Decimal(config.substitution_share) * 1000)
    for school in schools:
        selected = tuple(p for p in pupils if p.school_id == school)
        command = SchoolCommand("illustrative", school, school, school, "external:supplier",
            "produce.prepared", "on_hand", 300, 0, len(selected), 0, 1, 90000, 28000,
            tuple(Pupil(p.member_id, p.household_id, eligible[p.member_id], participating[p.member_id],
                attendance_present(seed, p.member_id, 0), True, index) for index, p in enumerate(selected)),
            tuple(HouseholdNeed(h.household_id, h.size * loaded.controls["daily_need_grams_per_person"], substitution, 1000) for h in households))
        served = ledger.policy(apply_school_day, command)
        policy_results[school] = asdict(served)
        for row in served.households:
            replaced[row.household_id] = replaced.get(row.household_id, 0) + row.replaced_grams
            school_consumed[row.household_id] = school_consumed.get(row.household_id, 0) + row.school_consumed_grams

    session = None
    if "groceries" in enabled:
        command = GroceryCommand("illustrative", config.subsidy_cents > 0, True, True, "muni", "store-municipal",
            "store-municipal", "store-municipal", config.subsidy_cents, config.price_support_cents,
            0, len(households) * 600, len(households) * 180, "external:supplier", "produce.fresh",
            90000, 29000, "subsidized_below_cost", 200, 500,
            (OverheadItem("labor", 500, "external:labor"),), (), 0, 0,
            "external:disposal", 0, 5000, "external:capital")
        session = GrocerySession.open(ledger, command)
        policy_results["groceries"] = asdict(session.opening_result)

    contexts = tuple(_context(ledger, loaded, h, replaced.get(h.household_id, 0), session, config) for h in households)
    offers = {ctx.household.household_id: build_choice_offer(ctx) for ctx in contexts}
    panel = select_focal_panel(tuple(RosterHousehold(h.household_id, h.income_band) for h in households), seed=seed)
    choices = resolve_barrier(contexts, config=BehaviorConfig(), panel=panel, master_seed=seed)
    receipts = {r.household_id: r for r in choices.receipts}
    ledger.at(36000)
    for receipt in choices.receipts:
        ledger._apply(RecordChoice(ledger._id("choice"), 36000, PHASE_CHOICE,
            receipt.decision_id, receipt.household_id, receipt.option_id, receipt.origin,
            receipt.observation_hash, receipt.revision, None))
    pending, settlements, journeys = [], [], []
    for rank, household_id in enumerate(choices.admission_order):
        receipt = receipts[household_id]
        option = next(o for o in offers[household_id].options if o.option_id == receipt.option_id)
        if not option.lines or option.store_id is None:
            settlements.append({"household_id": household_id, "status": "no_purchase", "paid_cents": 0, "travel_seconds": 0})
            continue
        grams = sum(line.grams for line in option.lines)
        draws = plan_draw(ledger, owner=option.store_id, product_id="produce.fresh", grams=grams, now=36000)
        if not draws:
            settlements.append({"household_id": household_id, "status": "stockout", "paid_cents": 0, "travel_seconds": 0})
            continue
        with ledger.atomic():
            reservations = []
            pieces = []
            for lot_id, take in draws:
                piece = ledger.take(lot_id, take)
                command_id = ledger._id("reserve")
                # Hold cash once and every finite stock fragment.
                cash = option.expected_payment_cents if not reservations else 0
                ledger._apply(ReserveResources(command_id, 36000, PHASE_SETTLE, household_id,
                    household_id if cash else None, cash, piece, take))
                reservations.append(f"rsv.{command_id}")
                pieces.append((piece, take))
        arrival = 36000 + option.total_seconds
        pending.append((arrival, rank, household_id, option, tuple(pieces), tuple(reservations)))
        journeys.append({"household_id": household_id, "store_id": option.store_id,
            "depart_second": 36000, "arrive_second": arrival,
            "reservation_ids": reservations, "cause_event_id": ledger.state.last_event_id})
    for arrival, rank, household_id, option, draws, reservations in sorted(pending):
        ledger.at(arrival)
        paid = 0
        status = "purchased"
        with ledger.atomic():
            for reservation in reservations:
                ledger._release(reservation)
            if option.store_id == "store-municipal":
                grams = sum(take for _, take in draws)
                quote = session.quote(ledger, grams, arrival)
                if quote is None or quote > option.expected_payment_cents:
                    status = "price_or_stock_changed"
                else:
                    sale = session.sell(ledger, Shopper(household_id, household_id, grams, rank,
                        (option.total_seconds + 59) // 60, (option.total_seconds + 59) // 60), arrival)
                    status = "purchased" if sale.outcome == "sold" else sale.outcome
                    paid = sale.paid_cents
            else:
                # The frozen offer prices each line in integer cents. The
                # single produce component may be split over several lots.
                total_grams = sum(take for _, take in draws)
                left = option.expected_payment_cents
                for index, (lot_id, take) in enumerate(draws):
                    price = left if index == len(draws) - 1 else option.expected_payment_cents * take // total_grams
                    ledger._apply(PurchaseLot(ledger._id("buy"), arrival, PHASE_SETTLE,
                        household_id, option.store_id, f"home:{household_id}", lot_id, take, price))
                    left -= price
                paid = option.expected_payment_cents
        settlements.append({"household_id": household_id, "status": status,
            "paid_cents": paid, "travel_seconds": option.total_seconds})

    ledger.at(72000)
    rows, feelings = [], {}
    settled = {row["household_id"]: row for row in settlements}
    for h in households:
        consumed = 0
        for lot in tuple(ledger.lots()):
            if lot.owner == h.household_id:
                consumed += lot.grams
                ledger.consume(lot.lot_id, lot.grams, reason="household produce use")
        daily_need = h.size * loaded.controls["daily_need_grams_per_person"]
        shortfall = max(0, daily_need - consumed - school_consumed.get(h.household_id, 0))
        result = settled[h.household_id]
        fulfilled = None if result["status"] == "no_purchase" else result["status"] == "purchased"
        latent = update_latent(LatentState(0.2, 0.5, 0.5), basket_shortfall_grams=shortfall,
            basket_need_grams=daily_need, unfunded_essentials_cents=0, essential_need_cents=0,
            time_overrun_seconds=max(0, result["travel_seconds"] - h.time_budget_seconds),
            time_budget_seconds=h.time_budget_seconds, fulfilled=fulfilled,
            expected_service=0.0 if fulfilled is None else 1.0,
            realized_service=0.0 if fulfilled is None or shortfall else 1.0,
            coefficients=LatentCoefficients(weight_financial=0))
        feelings[h.household_id] = {key: format(value, ".8f") for key, value in asdict(latent).items()}
        rows.append(HouseholdMetric(h.household_id, h.income_band, h.size, h.area_id, h.mobility,
            any(p.household_id == h.household_id and p.eligible for p in pupils),
            (("household_payment_cents", result["paid_cents"]), ("unmet_grams", shortfall),
             ("travel_seconds", result["travel_seconds"]))))
    # Existing donations remain delivered in both arms, never counted as new rescue.
    ledger.release_lot(donation_hold)
    ledger.transfer_lot(donation, owner="food-bank", custody="food-bank")
    if "processing" not in enabled:
        ledger.write_off(surplus, ledger.lot(surplus).grams, reason="unclaimed illustrative surplus")
    if ledger.state.reservations or invariant_problems(ledger.state):
        raise RuntimeError("integrated day failed its terminal accounting gate")
    initial = empty_state(run_id=ledger.state.run_id, scenario_id=ledger.state.scenario_id,
        catalog_id=ledger.state.catalog_id, catalog_sha256=ledger.state.catalog_sha256,
        known_product_ids=ledger.state.known_product_ids)
    if state_hash(fold_events(initial, ledger.events)) != state_hash(ledger.state):
        raise RuntimeError("integrated economic replay differs")
    public = {"muni", "hub", "fleet", "processor", "store-municipal", *schools}
    outcomes = {name: sum(dict(row.values)[name] for row in rows)
                for name in ("household_payment_cents", "unmet_grams", "travel_seconds")}
    outcomes.update(fiscal_outlay_cents=1_000_000 - sum(ledger.cash(a) for a in public),
        food_waste_grams=ledger.state.loss_grams,
        school_consumed_grams=sum(school_consumed.values()),
        subsidy_transfer_cents=session.opening_result.subsidy_transferred_cents if session else 0)
    if session:
        policy_results["groceries"].update(closing_price_support_cents=session.support_left,
            arrival_sales=[asdict(sale) for sale in session.sales])
    inputs = {"model_version": "connected-district-1", "seed": seed,
        "evidence_state": "illustrative", "snapshot_id": loaded.header["snapshot_id"],
        "catalog_sha256": loaded.catalog.sha256, "population_hash": population.population_hash,
        "household_ids": sorted(ids), "enabled_policies": enabled, "config": asdict(config),
        "window": "one synthetic school day; produce component only", "price_base_month": None,
        "source_manifest": loaded.manifest,
        "financial_strain_component": "disabled; non-food essential expenses are not modeled"}
    economic_hash = sha256_hex({"kernel": state_hash(ledger.state), "logistics": transport.canonical_state(),
        "support_left": session.support_left if session else 0, "feelings": feelings,
        "decisions": [receipt.to_payload() for receipt in choices.receipts], "inputs": inputs})
    return DistrictRun(ledger, outcomes, tuple(rows), choices.receipts, tuple(settlements),
        tuple(journeys), feelings, policy_results, transport.canonical_state(), economic_hash, inputs)


def _context(ledger, loaded, household, replaced, session, config):
    need = max(0, household.size * loaded.controls["daily_need_grams_per_person"] - replaced)
    # Product identity stays explicit. The 100 g catalog unit below rounds
    # shopping quantities upward after exact school-portion substitution.
    members = tuple(Member(m.member_id, m.age_band, None, False, False) for m in household.members)
    person = HouseholdSnapshot(household.household_id, household.area_id, household.income_band,
        members, ledger.spendable(household.household_id), 0, (), household.carry_grams,
        household.time_budget_seconds, household.habitual_store_id, (household.habitual_store_id,),
        (), (), household.cooking, 0.2, 0.5, 0.5, household.mobility)
    stores, shelves, routes = [], [], []
    for store in loaded.places["stores"]:
        municipal = store["store_id"] == "store-municipal"
        if municipal and session is None:
            continue
        found = shortest_path(loaded.network, household.area_id, store["area_id"] if municipal else store["store_id"])
        if found is None:
            continue
        travel = 2 * (household.access_seconds + found[1] + (config.municipal_access_seconds if municipal else 0)) * loaded.behavior["mobility_multiplier"][household.mobility] + 60
        stock = sum(lot.grams - ledger.reserved_grams(lot.lot_id) for lot in ledger.lots()
                    if lot.owner == store["store_id"] and lot.product_id == "produce.fresh")
        quote = session.quote(ledger, 100, 36000) if municipal else store["price_cents_per_100g"]
        if quote is None:
            continue
        stores.append(StoreInfo(store["store_id"], 28800, 72000, True, municipal))
        # Core prices are cents/100g. A 100g catalog unit rounds the required
        # produce basket upward explicitly; school substitution stays exact.
        shelves.append(StoreShelf(store["store_id"], "produce.fresh", stock, quote, 90000, 0.8, 0))
        routes.append(RouteInfo(store["store_id"], travel, True, "walk"))
    return DecisionContext(f"decision-{household.household_id}", ledger.state.next_sequence - 1,
        36000, 0, "routine_shop", person,
        (CatalogProduct("produce.fresh", 100, True, ("produce",)),),
        (("produce.fresh", need),) if need else (), household.size,
        tuple(stores), tuple(shelves), tuple(routes), None, None, ())


def _deliver_school_food(ledger, seed, schools, ids, use_drone, eligible):
    ledger.at(1000)
    fleet = FleetConfig("hub", (0, 0), "fleet", "external:carrier", 5, 10, 10,
        1, 1, 1, 1, 1, 50, "dispatch", 20, 1, 1)
    carriers = (
        CarrierSpec("van", "van", 100000, True, 10, 1000, 0, 86400, 0, 0, 0, 0, 0, (0, 0)),
        CarrierSpec("drone", "drone", 3000, True, 20, 1000, 0, 86400, 10000, 10000, 1, 100, 100, (0, 0)),
    )
    corridors = tuple(Corridor(f"corridor-{s}", "hub", s, ((0, 0), (300, 0)), 300,
        eligible, "approved_in_scenario" if eligible else "no_approval", 0, 86400, ()) for s in schools)
    transport = LogisticsEngine(ScenarioContext(seed, "synthetic-district", ledger.catalog.catalog_id,
        1792382400, tuple(sorted(ids | set(schools)))), fleet, carriers, corridors, KernelLogisticsPort(ledger))
    for school in schools:
        for index, lot in enumerate(tuple(ledger.lots())):
            if lot.owner != school or lot.custody != "hub":
                continue
            order = f"order-{school}-{index}"
            out = straight_leg(order + "-out", "hub", school, (0, 0), (300, 0), 300)
            back = straight_leg(order + "-back", school, "hub", (300, 0), (0, 0), 300)
            approach = straight_leg(order + "-approach", "hub", school, (0, 0), (300, 0), 300)
            stay = straight_leg(order + "-stay", school, school, (300, 0), (300, 0), 0)
            transport.submit_order(DeliveryOrder(order, school, "hub", school, (lot.lot_id,),
                lot.grams, "chilled", 1000, "drone" if use_drone else "ground", use_drone,
                "collect", 60, 1, f"corridor-{school}" if use_drone else None,
                school if use_drone else None, out, back,
                approach if use_drone else None, stay if use_drone else None,
                back if use_drone else None, stay if use_drone else None))
    with ledger.atomic():
        transport.advance_to(25000)
    if transport.actions or transport.waiting.entries:
        raise RuntimeError("school deliveries did not finish before meal service")
    return transport
