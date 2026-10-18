"""One synthetic six-hour day, one resident per household, one destination per trip.

Geometry is a frozen map input. Every operating and demographic value below is
an illustrative scenario assumption, never inferred from a Toronto directory.
The browser replays projections; only sim.core commits food and money.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
import random
from datetime import date, datetime, time, timedelta, timezone
from dataclasses import asdict, dataclass
from zoneinfo import ZoneInfo

from sim import core

HORIZON = 21600
DAY_SECONDS = 86400
ACTIVITY_START_LOCAL = time(8, 30)
ACTIVITY_WINDOW_SECONDS = HORIZON
MAX_POPULATION = 2400
PRODUCT = "produce.fresh"
PARAMETER = "pedestrian-food-day-v1"


@dataclass
class Site:
    id: str
    name: str
    type: str
    node: int
    opens: int
    closes: int
    price_cents_per_100g: int
    capacity: int
    service_seconds: int
    opening_grams: int
    eligible: str = "all"
    active_from: int = 0
    next_free: int = 0
    served: int = 0
    visits: int = 0
    denials: int = 0
    sold_grams: int = 0
    received_grams: int = 0
    revenue_cents: int = 0
    spending_cents: int = 0
    source_id: str | None = None
    source_record_id: str | None = None
    source_site_id: str | None = None
    source_url: str | None = None
    source_record_url: str | None = None
    source_snapshot_id: str | None = None
    source_retrieved_at: str | None = None
    source_published_at: str | None = None
    source_updated_at: str | None = None
    source_address: str | None = None
    source_quality_flags: list[str] | None = None
    location_evidence_state: str | None = None
    operations_evidence_state: str | None = None
    listing_current_status: str | None = None
    map_snap_distance_m: float | None = None
    point: list[float] | None = None
    network_point: list[float] | None = None
    organization_refs: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class MunicipalSiteSchedule:
    site_id: str
    location_id: str
    grant_cents: int
    stock_grams: int
    service_capacity: int
    readiness_second: int
    funding_second: int
    delivery_second: int
    commissioning_second: int
    open_second: int
    close_second: int
    blocker_reasons: tuple[str, ...] = ()
    organization_refs: tuple[tuple[str, str, str, str], ...] = ()


def _organization_refs_for(schedule: MunicipalSiteSchedule | None,
                           roles: tuple[str, ...]) -> list[dict[str, str]]:
    if schedule is None:
        return []
    wanted = set(roles)
    return [
        {"role": role, "organization_id": organization_id,
         "record_id": record_id, "sha256": digest}
        for role, organization_id, record_id, digest in schedule.organization_refs
        if role in wanted
    ]


class WalkingNetwork:
    def __init__(self, district: dict, closed_edges: tuple[tuple[int, int], ...]):
        self.nodes = district["walkNodes"]
        self.graph = [[] for _ in self.nodes]
        closed = {tuple(sorted(e)) for e in closed_edges}
        available = {tuple(sorted(e[:2])) for e in district["walkEdges"]}
        if not closed <= available:
            raise ValueError("closure references an unknown walking edge")
        for a, b, kind in district["walkEdges"]:
            distance = math.dist(self.nodes[a], self.nodes[b])
            delay = 12 if kind == "crossing" else 0
            self.graph[a].append((b, distance, delay))
            self.graph[b].append((a, distance, delay))
        seen = set()
        components = []
        for node in range(len(self.nodes)):
            if node in seen:
                continue
            component = [node]
            seen.add(node)
            for current in component:
                for neighbor, _, _ in self.graph[current]:
                    if neighbor not in seen:
                        component.append(neighbor)
                        seen.add(neighbor)
            components.append(component)
        self.usable = sorted(max(components, key=len))
        if len(self.usable) < 2:
            raise ValueError("walking network needs a connected pair of nodes")
        # Keep homes and site anchors fixed when an intervention closes an edge.
        # Closures change reachability, never the sampled population geography.
        for node, edges in enumerate(self.graph):
            self.graph[node] = [edge for edge in edges if tuple(sorted((node, edge[0]))) not in closed]
        self.trees = {}

    def nearest(self, point):
        return min(self.usable, key=lambda n: math.dist(point, self.nodes[n]))

    def route(self, home: int, target: int, speed: float):
        key = (target, speed)
        if key not in self.trees:
            distance = {target: 0}
            next_edge = {}
            heap = [(0, target)]
            while heap:
                cost, node = heapq.heappop(heap)
                if cost != distance[node]:
                    continue
                for neighbor, meters, wait in self.graph[node]:
                    candidate = cost + meters / speed + wait
                    if candidate < distance.get(neighbor, math.inf):
                        distance[neighbor] = candidate
                        next_edge[neighbor] = (node, meters, wait)
                        heapq.heappush(heap, (candidate, neighbor))
            self.trees[key] = next_edge
        tree = self.trees[key]
        if home != target and home not in tree:
            return None
        nodes, times, meters = [home], [0], 0
        current = home
        while current != target:
            neighbor, length, wait = tree[current]
            # Duplicate position records make the crossing wait visible in playback.
            if wait:
                nodes.append(current)
                times.append(times[-1] + wait)
            nodes.append(neighbor)
            times.append(times[-1] + max(1, math.ceil(length / speed)))
            meters += length
            current = neighbor
        if times[-1] == 0:
            nodes.append(home)
            times.append(1)
        return {"nodes": nodes, "times": times, "seconds": times[-1], "meters": round(meters)}


def _local_time_at(start_time: str, timezone_name: str, second: int) -> str:
    start = datetime.fromisoformat(start_time)
    if start.tzinfo is None:
        return (start + timedelta(seconds=second)).isoformat(timespec="seconds")
    zone = ZoneInfo(timezone_name)
    absolute = start.astimezone(timezone.utc) + timedelta(seconds=second)
    return absolute.astimezone(zone).isoformat(timespec="seconds")


def run(district: dict, population: int = 2400, seed: int = 2026,
        emergency: bool = False, closed_edges: tuple[tuple[int, int], ...] = (),
        site_snapshot: dict | None = None, site_snapshot_sha256: str | None = None,
        municipal_site: MunicipalSiteSchedule | None = None,
        council_run_ref: dict | None = None, *, horizon_seconds: int = HORIZON,
        activity_start_second: int = 0,
        start_time: str = "2026-10-17T08:30:00",
        timezone_name: str = "America/Toronto",
        local_date: str | None = None,
        end_time: str | None = None) -> dict:
    """Return a deterministic event trace and scene projection with a no-policy default."""
    core.require_int(population, "population")
    core.require_int(seed, "seed")
    core.require_int(horizon_seconds, "horizon_seconds")
    core.require_int(activity_start_second, "activity_start_second")
    if not 1 <= population <= MAX_POPULATION:
        raise ValueError(f"population must be between 1 and {MAX_POPULATION}")
    if horizon_seconds <= 0 or activity_start_second < 0:
        raise ValueError("horizon_seconds must be positive and activity_start_second cannot be negative")
    if activity_start_second + ACTIVITY_WINDOW_SECONDS > horizon_seconds:
        raise ValueError("the six-hour activity window must fit inside the run horizon")
    if not isinstance(start_time, str) or not start_time:
        raise ValueError("start_time must be an explicit ISO timestamp")
    try:
        zone = ZoneInfo(timezone_name)
        parsed_start = datetime.fromisoformat(start_time)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"unknown timezone: {timezone_name}") from exc
    if parsed_start.tzinfo is None:
        parsed_start = parsed_start.replace(tzinfo=zone)
    start_time = parsed_start.isoformat(timespec="seconds")
    if site_snapshot is not None and not site_snapshot_sha256:
        raise ValueError("a pinned site snapshot requires its content hash")
    if site_snapshot is None and site_snapshot_sha256 is not None:
        raise ValueError("site snapshot hash provided without a site snapshot")
    network = WalkingNetwork(district, closed_edges)
    scenario_id = (
        f"{PARAMETER}-{site_snapshot['snapshot_id']}" if site_snapshot is not None else PARAMETER
    )
    if council_run_ref is not None:
        if (council_run_ref.get("kind") != "council"
                or council_run_ref.get("arm") not in {"baseline", "intervention"}
                or not isinstance(council_run_ref.get("run_id"), str)):
            raise ValueError("invalid Council run identity")
        scenario_id = f"council-food-site-{council_run_ref['run_id']}"
    catalog = core.load_catalog()
    state = core.empty_state(run_id=f"walk-{seed}-{population}-{'aid' if emergency else 'base'}",
                            scenario_id=scenario_id, catalog_id=catalog.catalog_id,
                            catalog_sha256=catalog.sha256,
                            known_product_ids=tuple(p.product_id for p in catalog.products))
    kernel_events = []
    command_index = 0

    def commit(command_type, second, phase, **kwargs):
        nonlocal state, command_index
        command_index += 1
        transition = core.apply_command(state, command_type(
            command_id=f"cmd-{command_index}", second=second, phase=phase, **kwargs))
        if transition.status != "accepted":
            raise RuntimeError(f"{command_type.__name__}: {transition.reason}: {transition.detail}")
        state = transition.state
        kernel_events.extend(transition.events)

    def stock(owner, place=None):
        return sum(l.grams for l in state.lots if l.owner_id == owner and
                   (place is None or l.place_id == place) and l.journey_id is None)

    def cash(owner):
        return core.account_for_owner(state, owner).settled_cents

    def move_food(owner, receiver, place, grams, second, phase, price=0):
        remaining = grams
        # All baskets are 100 g multiples; one price is used across FIFO lots.
        for lot in core.lots_for_owner(state, owner):
            take = min(remaining, core.available_grams(lot))
            if not take:
                continue
            if price:
                commit(core.PurchaseLot, second, phase, buyer_account_id=receiver,
                       seller_account_id=owner, destination_place_id=place,
                       lot_id=lot.lot_id, grams=take, cents=take * price // 100)
            else:
                commit(core.TransferLot, second, phase, lot_id=lot.lot_id, grams=take,
                       new_owner_id=receiver, new_place_id=place)
            remaining -= take
            if not remaining:
                break
        if remaining:
            raise RuntimeError("food transfer exceeds available stock")

    # Synthetic operational sites are anchored to graph nodes, not asserted real operators.
    site_specs = [
        ("retail-west", "Scenario grocery · west", "retailer", [-750, 0], 0, 20000, 50, population, 45, population * 180),
        ("retail-east", "Scenario grocery · east", "retailer", [650, 100], 0, 20000, 35, population, 60, population * 220),
        ("support", "Scenario community pantry", "support", [-150, -250], 1200, 18000, 0, max(1, population // 5), 90, population * 100),
        ("school", "Scenario school nutrition", "school", [450, -550], 1800, 12600, 0, max(1, population // 4), 30, population * 100),
        ("emergency", "Temporary emergency food site", "emergency", [-500, 400], 3600, 18000, 0, max(1, population // 4), 60, 0),
    ]
    source_sites = site_snapshot.get("sites", {}) if site_snapshot else {}
    sites = []
    for site_id, name, site_type, anchor, opens, closes, price, capacity, service, opening_grams in site_specs:
        if site_type == "emergency" and not emergency:
            continue
        source = source_sites.get(site_id)
        point = source["scene_point"] if source else anchor
        node = network.nearest(point)
        network_point = list(network.nodes[node])
        snap_distance = math.dist(point, network_point)
        if source and snap_distance > 100:
            raise ValueError(
                f"source-listed site {source['source_site_id']} is {snap_distance:.1f} m from the walking graph; "
                "refusing to route across an unvalidated gap"
            )
        if source:
            name = source["display_name"]
        site = Site(
            site_id,
            name,
            site_type,
            node,
            opens + activity_start_second,
            closes + activity_start_second,
            price,
            capacity,
            service,
            opening_grams,
            "school" if site_type == "school" else "low-income" if site_type == "support" else "all",
            activity_start_second + 3600 if site_type == "emergency" else 0,
            source_id=source.get("source_id") if source else None,
            source_record_id=source.get("source_record_id") if source else None,
            source_site_id=source.get("source_site_id") if source else None,
            source_url=source.get("source_url") if source else None,
            source_record_url=source.get("source_record_url") if source else None,
            source_snapshot_id=source.get("source_snapshot_id") if source else None,
            source_retrieved_at=source.get("source_retrieved_at") if source else None,
            source_published_at=source.get("source_published_at") if source else None,
            source_updated_at=source.get("source_updated_at") if source else None,
            source_address=source.get("address") if source else None,
            source_quality_flags=source.get("quality_flags") if source else None,
            location_evidence_state=source.get("location_evidence_state") if source else None,
            operations_evidence_state=source.get("operations_evidence_state") if source else None,
            listing_current_status=source.get("listing_current_status") if source else None,
            map_snap_distance_m=round(snap_distance, 1) if source else None,
            point=list(source["scene_point"]) if source else network_point,
            network_point=network_point if source else None,
        )
        sites.append(site)
    if municipal_site is not None:
        if site_snapshot is None or municipal_site.location_id not in source_sites:
            raise ValueError("Council site requires a location from the pinned source snapshot")
        if any(s.id == municipal_site.site_id for s in sites):
            raise ValueError("Council site identifier collides with an existing scenario site")
        source = source_sites[municipal_site.location_id]
        point = source["scene_point"]
        node = network.nearest(point)
        network_point = list(network.nodes[node])
        snap_distance = math.dist(point, network_point)
        if snap_distance > 100:
            raise ValueError("Council source location is too far from the walking network")
        sites.append(Site(
            municipal_site.site_id,
            "Hypothetical municipal food site",
            "council",
            node,
            activity_start_second + municipal_site.open_second,
            activity_start_second + municipal_site.close_second,
            0,
            0,
            60,
            0,
            active_from=activity_start_second + municipal_site.open_second,
            source_id=source.get("source_id"),
            source_record_id=source.get("source_record_id"),
            source_site_id=source.get("source_site_id"),
            source_url=source.get("source_url"),
            source_record_url=source.get("source_record_url"),
            source_snapshot_id=source.get("source_snapshot_id"),
            source_retrieved_at=source.get("source_retrieved_at"),
            source_published_at=source.get("source_published_at"),
            source_updated_at=source.get("source_updated_at"),
            source_address=source.get("address"),
            source_quality_flags=source.get("quality_flags"),
            location_evidence_state=source.get("location_evidence_state"),
            operations_evidence_state=source.get("operations_evidence_state"),
            listing_current_status=source.get("listing_current_status"),
            map_snap_distance_m=round(snap_distance, 1),
            point=list(point),
            network_point=network_point,
            organization_refs=_organization_refs_for(municipal_site, ("site_operator",)),
        ))
    by_site = {s.id: s for s in sites}
    households = []
    rng = random.Random(seed)
    for resident in range(population):
        size = rng.randint(1, 4)
        band = rng.choice(["low", "low", "middle", "higher"])
        home = rng.choice(network.usable)
        mobility = rng.choice(["standard", "standard", "limited"])
        # Explicit synthetic eligibility; never personal assistance records.
        children = rng.randint(1, size) if size > 1 and rng.random() < 0.5 else 0
        households.append(dict(id=f"hh-{resident}", resident_id=resident, size=size,
                               income_band=band, mobility=mobility, children=children,
                               home_node=home, area="west" if network.nodes[home][0] < 0 else "east",
                               opening_cents=rng.randint(0, 350 if band == "low" else 1500),
                               opening_grams=rng.randrange(0, size * 3) * 100,
                               need_grams=size * 300, speed=0.9 if mobility == "limited" else 1.4,
                               time_budget_seconds=5400 if mobility == "limited" else 7200,
                               departure=activity_start_second + rng.randint(60, 7200)))

    # Opening endowments enter through a credit-enabled external funding account.
    owners = [("external", "external", True), ("city", "municipality", False),
              ("supplier", "external", False)]
    owners += [(s.id, "retailer" if s.type == "retailer" else "school" if s.type == "school" else "hub", False) for s in sites]
    owners += [(h["id"], "household", False) for h in households]
    for owner, kind, credit in owners:
        commit(core.OpenAccount, 0, core.PHASE_POLICY, account_id=owner, owner_id=owner, kind=kind, allows_credit=credit)
    opening_cash = {"city": 100000, "supplier": 0, **{s.id: 30000 if s.type == "retailer" else 0 for s in sites},
                    **{h["id"]: h["opening_cents"] for h in households}}
    for owner, cents in opening_cash.items():
        if cents:
            commit(core.TransferCash, 0, core.PHASE_POLICY, from_account_id="external", to_account_id=owner,
                   cents=cents, memo="illustrative opening endowment")
    food = [(s.id, s.id, s.opening_grams) for s in sites]
    food += [(h["id"], f"home-{h['id']}", h["opening_grams"]) for h in households]
    food += [("supplier", "supplier", population * 200)]
    for index, (owner, place, grams) in enumerate(food):
        if grams:
            commit(core.IntroduceLot, 0, core.PHASE_POLICY, lot_id=f"opening-{index}", product_id=PRODUCT,
                   owner_id=owner, place_id=place, grams=grams, acquisition_cents=0, unsafe_after=None)

    events, queue = [], []
    rollout_events = []
    schedule_index = 0
    journeys = {}
    consumed = {h["id"]: 0 for h in households}
    spent = {h["id"]: 0 for h in households}
    received = {h["id"]: 0 for h in households}
    purchased = {h["id"]: 0 for h in households}
    city_spending = 0
    council_blocker = None
    council_ready = council_funded = council_delivered = council_commissioned = False

    def household_view(h):
        pantry = stock(h["id"], f"home-{h['id']}")
        return dict(cash_cents=cash(h["id"]), pantry_grams=pantry,
                    carrying_grams=stock(h["id"]) - pantry, consumed_grams=consumed[h["id"]],
                    unmet_grams=max(0, h["need_grams"] - consumed[h["id"]]),
                    expenditure_cents=spent[h["id"]], received_grams=received[h["id"]],
                    purchased_grams=purchased[h["id"]])

    def site_view(s):
        return dict(stock_grams=stock(s.id), served=s.served, visits=s.visits, denials=s.denials,
                    sold_grams=s.sold_grams, received_grams=s.received_grams,
                    revenue_cents=s.revenue_cents, spending_cents=s.spending_cents,
                    price_cents_per_100g=s.price_cents_per_100g, capacity=s.capacity)

    initial_households = {h["id"]: household_view(h) for h in households}
    initial_sites = {s.id: site_view(s) for s in sites}

    def emit(second, action, result="completed", h=None, s=None, quantity=0, payment=0, reason=None, **extra):
        organization_refs = extra.pop("organization_refs", None)
        event = dict(event_id=f"evt-{len(events)}", simulation_time=second,
                     resident_id=h["resident_id"] if h else None, household_id=h["id"] if h else None,
                     site_id=s.id if s else f"home-{h['id']}" if h else None,
                     site_type=s.type if s else "home" if h else "institution",
                     action=action, decision_id=f"decision-{h['id']}" if h else None,
                     route_id=f"route-{h['id']}" if h and h["id"] in journeys else None,
                     travel_seconds=0, queue_seconds=0, service_seconds=0,
                     product_or_service_id=PRODUCT, quantity_grams=quantity, payment_cents=payment,
                     result=result, denial_or_failure_reason=reason, evidence_state="illustrative",
                     source_id=s.source_id if s else None, scenario_parameter_id=scenario_id)
        if s and s.source_id:
            event["source_record_id"] = s.source_record_id
            event["source_snapshot_id"] = s.source_snapshot_id
        if organization_refs is not None:
            event["organization_refs"] = [dict(item) for item in organization_refs]
        elif s and s.type == "council":
            event["organization_refs"] = [dict(item) for item in (s.organization_refs or [])]
        event.update(extra)
        if h:
            event["household_state"] = household_view(h)
        if s:
            event["site_state"] = site_view(s)
        event["public_spending_cents"] = city_spending
        events.append(event)

    def emit_rollout(stage, second, status, reason=None, s=None, amount_cents=0,
                     stock_grams=0):
        stage_roles = {
            "readiness": ("site_host", "site_operator"),
            "funding": ("city_funder",),
            "delivery": ("supplier_distributor", "site_operator"),
            "commissioning": ("site_operator",),
            "opening": ("site_operator",),
            "closure": ("site_operator",),
            "blocked": ("city_funder", "site_host", "site_operator", "supplier_distributor"),
            "no_launch": ("city_funder", "site_host", "site_operator", "supplier_distributor"),
        }
        organization_refs = _organization_refs_for(municipal_site, stage_roles.get(stage, ()))
        record = dict(event_id=f"rollout-{len(rollout_events)}", stage=stage,
                      simulation_time=second, status=status, reason=reason,
                      amount_cents=amount_cents, stock_grams=stock_grams,
                      capacity=s.capacity if s else 0,
                      organization_refs=organization_refs)
        rollout_events.append(record)
        if s is not None:
            emit(second, f"rollout_{stage}", status, s=s,
                 reason=reason, stage=stage, amount_cents=amount_cents,
                 stock_grams=stock_grams, capacity=s.capacity,
                 organization_refs=organization_refs)

    def schedule(second, phase, kind, h=None, payload=None):
        nonlocal schedule_index
        if second < 0 or second > horizon_seconds:
            raise ValueError(f"scheduled event second {second} is outside the run horizon")
        schedule_index += 1
        # Seeded ties avoid resident-id priority at contested service opportunities.
        rank = hashlib.sha256(f"{seed}|{second}|{h['id'] if h else kind}|admission".encode()).hexdigest()
        heapq.heappush(queue, (second, phase, rank, schedule_index, kind, h, payload))

    def return_home(h, second, result):
        trip = journeys[h["id"]]
        trip["return_start"] = second
        trip["home_at"] = second + trip["travel_seconds"]
        trip["result"] = result
        schedule(trip["home_at"], core.PHASE_ARRIVAL, "home", h)

    def deny(h, s, second, reason, **timing):
        s.denials += 1
        emit(second, "service", "denied", h, s, reason=reason, **timing)
        return_home(h, second, reason)

    for h in households:
        schedule(h["departure"], core.PHASE_CHOICE, "decide", h, False)
        schedule(horizon_seconds, core.PHASE_CONSUME, "consume", h)
    schedule(activity_start_second + 6000, core.PHASE_SETTLE, "delivery", payload=("retail-west", population * 60 // 100 * 100))
    schedule(activity_start_second + 9000, core.PHASE_POLICY, "price", payload=("retail-west", 65))
    if emergency:
        schedule(activity_start_second + 3600, core.PHASE_POLICY, "activate")
        schedule(activity_start_second + 3660, core.PHASE_SETTLE, "delivery", payload=("emergency", population * 100))
        schedule(activity_start_second + 18000, core.PHASE_POLICY, "shutdown")
    if municipal_site is not None:
        if municipal_site.blocker_reasons:
            for stage, second in (
                ("readiness", activity_start_second + municipal_site.readiness_second),
                ("funding", activity_start_second + municipal_site.funding_second),
                ("delivery", activity_start_second + municipal_site.delivery_second),
                ("commissioning", activity_start_second + municipal_site.commissioning_second),
                ("opening", activity_start_second + municipal_site.open_second),
                ("closure", activity_start_second + municipal_site.close_second),
            ):
                schedule(second, core.PHASE_POLICY, "council_no_launch",
                         payload=(municipal_site.site_id, stage, second))
        else:
            schedule(activity_start_second + municipal_site.readiness_second, core.PHASE_POLICY, "council_readiness")
            schedule(activity_start_second + municipal_site.funding_second, core.PHASE_POLICY, "council_funding")
            schedule(activity_start_second + municipal_site.delivery_second, core.PHASE_SETTLE, "council_delivery")
            schedule(activity_start_second + municipal_site.commissioning_second, core.PHASE_POLICY, "council_commissioning")
            schedule(activity_start_second + municipal_site.open_second, core.PHASE_POLICY, "council_open")
            schedule(activity_start_second + municipal_site.close_second, core.PHASE_POLICY, "council_close")

    while queue:
        second, phase, _, _, kind, h, payload = heapq.heappop(queue)
        if second > horizon_seconds:
            raise RuntimeError("scheduled interaction exceeds run horizon")
        if kind == "activate":
            city_spending = 30000
            commit(core.TransferCash, second, phase, from_account_id="city", to_account_id="emergency",
                   cents=city_spending, memo="illustrative emergency site grant")
            emit(second, "policy_activation", s=by_site["emergency"], budget_cents=30000,
                 funding_source="city", activation_date=_local_time_at(start_time, timezone_name, second),
                 shutdown_condition="13:30 simulation time", capacity_effect=by_site["emergency"].capacity)
        elif kind == "shutdown":
            emit(second, "policy_shutdown", s=by_site["emergency"])
        elif kind == "council_readiness":
            s = by_site[municipal_site.site_id]
            emit_rollout("readiness", second, "completed", s=s,
                         reason="site readiness is a scenario assumption; authority and current operation remain unknown")
            council_ready = True
        elif kind == "council_funding":
            s = by_site[municipal_site.site_id]
            if council_blocker:
                emit_rollout("funding", second, "not_started", council_blocker, s=s)
                continue
            if not council_ready or cash("city") < municipal_site.grant_cents:
                council_blocker = "readiness or scenario city funds are unavailable"
                emit_rollout("blocked", second, "blocked", council_blocker, s=s)
                emit_rollout("no_launch", second, "blocked", council_blocker, s=s)
                continue
            commit(core.TransferCash, second, phase, from_account_id="city", to_account_id=s.id,
                   cents=municipal_site.grant_cents, memo="illustrative Council scenario grant")
            city_spending += municipal_site.grant_cents
            council_funded = True
            emit_rollout("funding", second, "completed", s=s,
                         reason="scenario grant transferred through sim.core",
                         amount_cents=municipal_site.grant_cents)
        elif kind == "council_delivery":
            s = by_site[municipal_site.site_id]
            if council_blocker:
                emit_rollout("delivery", second, "not_started", council_blocker, s=s)
                continue
            required_cash = municipal_site.stock_grams * 20 // 100
            if not council_funded or stock("supplier") < municipal_site.stock_grams or cash(s.id) < required_cash:
                council_blocker = "full supplier quantity or procurement payment is unavailable"
                grant_balance = cash(s.id)
                if grant_balance:
                    commit(core.TransferCash, second, phase, from_account_id=s.id, to_account_id="city",
                           cents=grant_balance, memo="return unspent Council scenario grant")
                    city_spending -= grant_balance
                emit_rollout("blocked", second, "blocked", council_blocker, s=s)
                emit_rollout("no_launch", second, "blocked", council_blocker, s=s)
                continue
            move_food("supplier", s.id, s.id, municipal_site.stock_grams,
                      second, core.PHASE_SETTLE, 20)
            s.received_grams += municipal_site.stock_grams
            s.spending_cents += required_cash
            council_delivered = True
            emit_rollout("delivery", second, "completed", s=s,
                         reason="supplier stock and full payment settled through sim.core",
                         amount_cents=required_cash, stock_grams=municipal_site.stock_grams)
        elif kind == "council_commissioning":
            s = by_site[municipal_site.site_id]
            if council_blocker:
                emit_rollout("commissioning", second, "not_started", council_blocker, s=s)
                continue
            if not council_delivered or stock(s.id) < 100:
                council_blocker = "site has no delivered stock to commission"
                emit_rollout("blocked", second, "blocked", council_blocker, s=s)
                emit_rollout("no_launch", second, "blocked", council_blocker, s=s)
                continue
            council_commissioned = True
            emit_rollout("commissioning", second, "completed", s=s,
                         reason="commissioned; capacity remains zero until opening")
        elif kind == "council_open":
            s = by_site[municipal_site.site_id]
            if council_blocker:
                emit_rollout("opening", second, "not_started", council_blocker, s=s)
                continue
            if not council_commissioned:
                council_blocker = "site commissioning did not complete"
                emit_rollout("blocked", second, "blocked", council_blocker, s=s)
                emit_rollout("no_launch", second, "blocked", council_blocker, s=s)
                continue
            s.capacity = municipal_site.service_capacity
            emit_rollout("opening", second, "completed", s=s,
                         reason="hypothetical service opened under the approved scenario assumption")
        elif kind == "council_close":
            s = by_site[municipal_site.site_id]
            if council_blocker:
                emit_rollout("closure", second, "not_started", council_blocker, s=s)
                continue
            s.capacity = 0
            emit_rollout("closure", second, "completed", s=s,
                         reason="scenario service closed; no later service is available")
        elif kind == "council_no_launch":
            site_id, stage, stage_second = payload
            s = by_site[site_id]
            if stage == "readiness":
                emit_rollout("blocked", second, "blocked", "; ".join(municipal_site.blocker_reasons), s=s)
                emit_rollout("no_launch", second, "blocked", "; ".join(municipal_site.blocker_reasons), s=s)
            else:
                emit_rollout(stage, stage_second, "not_started",
                             "; ".join(municipal_site.blocker_reasons), s=s)
        elif kind == "price":
            s = by_site[payload[0]]
            s.price_cents_per_100g = payload[1]
            emit(second, "price_change", s=s)
        elif kind == "delivery":
            s, grams = by_site[payload[0]], payload[1]
            cost = grams * 20 // 100
            actual = min(grams, stock("supplier"), cash(s.id) // 20 * 100)
            if actual:
                move_food("supplier", s.id, s.id, actual, second, core.PHASE_SETTLE, 20)
                s.received_grams += actual
                s.spending_cents += actual * 20 // 100
            emit(second, "delivery", "completed" if actual == grams else "partial", s=s,
                 quantity=actual, payment=actual * 20 // 100, requested_grams=grams,
                 shortfall_grams=grams - actual, quoted_payment_cents=cost, supplier_id="supplier")
        elif kind == "decide":
            need = max(0, h["need_grams"] - stock(h["id"]) - consumed[h["id"]])
            if need == 0:
                emit(second, "chosen", h=h, option_id="no_purchase", reason="pantry_covers_need")
                continue
            offers, excluded = [], []
            for s in sites:
                reason = None
                route = network.route(h["home_node"], s.node, h["speed"])
                if (s.eligible == "school" and not h["children"]) or (s.eligible == "low-income" and h["income_band"] != "low"):
                    reason = "ineligible"
                elif s.type in {"emergency", "council"} and second < s.active_from:
                    reason = "inactive"
                elif route is None:
                    reason = "inaccessible_route"
                else:
                    arrival = second + route["seconds"]
                    total = route["seconds"] * 2 + max(0, s.next_free - arrival) + s.service_seconds
                    if total > h["time_budget_seconds"] or second + total >= horizon_seconds:
                        reason = "time_budget"
                    elif arrival < s.opens or arrival + s.service_seconds > s.closes:
                        reason = "closure"
                    elif s.served >= s.capacity:
                        reason = "capacity_denial"
                    elif stock(s.id) < 100:
                        reason = "stockout"
                    else:
                        limit = h["children"] * 300 if s.type == "school" else 1000
                        unit = 300 if s.type == "school" else 100
                        grams = min(math.ceil(need / unit) * unit, limit, stock(s.id)) // unit * unit
                        if s.type == "school":
                            grams = min(grams, (s.capacity - s.served) * 300)
                        if s.price_cents_per_100g:
                            grams = min(grams, cash(h["id"]) // s.price_cents_per_100g * 100)
                        if not grams:
                            reason = "unaffordable_basket"
                        else:
                            cost = grams * s.price_cents_per_100g // 100
                            offers.append(dict(option_id=s.id, quantity_grams=grams, payment_cents=cost,
                                               total_seconds=total, route=route,
                                               score=grams - cost - total / 20))
                if reason:
                    excluded.append(dict(site_id=s.id, reason=reason))
            emit(second, "offered", "offered", h=h,
                 options=[{k: v for k, v in o.items() if k not in {"route", "score"}} for o in offers] +
                         [dict(option_id="no_purchase"), dict(option_id="delay")], excluded=excluded)
            if not offers:
                later = max(second + 600, min([s.opens for s in sites if s.opens > second] +
                                               [activity_start_second + 6000]))
                if not payload and later < activity_start_second + 10000:
                    emit(second, "chosen", h=h, option_id="delay")
                    schedule(later, core.PHASE_CHOICE, "decide", h, True)
                else:
                    reason = next((x["reason"] for x in excluded if x["reason"] not in {"ineligible", "inactive"}), "no_feasible_option")
                    emit(second, "no_purchase", "denied", h=h, reason=reason)
                continue
            choice = min(offers, key=lambda o: (-o["score"], o["option_id"]))
            s = by_site[choice["option_id"]]
            route = choice["route"]
            trip = dict(route_id=f"route-{h['id']}", site_id=s.id, nodes=route["nodes"], times=route["times"],
                        meters=route["meters"], depart=second, arrival=second + route["seconds"],
                        travel_seconds=route["seconds"], return_start=horizon_seconds, home_at=horizon_seconds, result="pending")
            journeys[h["id"]] = trip
            emit(second, "chosen", "chosen", h, s, quantity=choice["quantity_grams"],
                 option_id=s.id, substitution=s.id == "retail-east", reduced_basket=choice["quantity_grams"] < need)
            schedule(trip["arrival"], core.PHASE_ARRIVAL, "arrive", h, choice)
        elif kind == "arrive":
            s = by_site[payload["option_id"]]
            s.visits += 1
            trip = journeys[h["id"]]
            start = max(second, s.next_free)
            finish = start + s.service_seconds
            if second < s.opens or finish > s.closes:
                deny(h, s, second, "closure", travel_seconds=trip["travel_seconds"])
            elif finish - trip["depart"] + trip["travel_seconds"] > h["time_budget_seconds"] or finish + trip["travel_seconds"] >= horizon_seconds:
                deny(h, s, second, "time_budget", travel_seconds=trip["travel_seconds"])
            else:
                s.next_free = finish
                trip["service_start"] = start
                emit(second, "queue", "waiting", h, s, travel_seconds=trip["travel_seconds"])
                schedule(finish, core.PHASE_SETTLE, "settle", h, payload)
        elif kind == "settle":
            s = by_site[payload["option_id"]]
            trip = journeys[h["id"]]
            grams = payload["quantity_grams"]
            units = grams // 300 if s.type == "school" else 1
            cost = grams * s.price_cents_per_100g // 100
            timing = dict(travel_seconds=trip["travel_seconds"],
                          queue_seconds=trip["service_start"] - trip["arrival"], service_seconds=s.service_seconds)
            reason = ("closure" if second > s.closes else "capacity_denial" if s.served + units > s.capacity
                      else "stockout" if stock(s.id) < grams else "unaffordable_basket" if cash(h["id"]) < cost else None)
            if reason:
                deny(h, s, second, reason, **timing)
                continue
            move_food(s.id, h["id"], s.id, grams, second, core.PHASE_SETTLE, s.price_cents_per_100g)
            spent[h["id"]] += cost
            (purchased if cost else received)[h["id"]] += grams
            s.served += units
            s.sold_grams += grams
            s.revenue_cents += cost
            emit(second, "purchase" if cost else "receive_service", h=h, s=s,
                 quantity=grams, payment=cost, portions=grams // 300 if s.type == "school" else 0, **timing)
            if s.type == "school":
                schedule(second, core.PHASE_CONSUME, "school_consume", h)
            return_home(h, second, "completed")
        elif kind == "school_consume":
            for lot in core.lots_for_owner(state, h["id"]):
                if lot.place_id == "school":
                    grams = lot.grams
                    commit(core.ConsumeFood, second, core.PHASE_CONSUME,
                           actor_id=h["id"], lot_id=lot.lot_id, grams=grams)
                    consumed[h["id"]] += grams
            emit(second, "school_meal", h=h, s=by_site["school"], quantity=consumed[h["id"]])
        elif kind == "home":
            for lot in core.lots_for_owner(state, h["id"]):
                if lot.place_id != f"home-{h['id']}":
                    commit(core.MoveLot, second, core.PHASE_ARRIVAL, lot_id=lot.lot_id,
                           owner_id=h["id"], place_id=f"home-{h['id']}", journey_id=None)
            emit(second, "return_home", h=h, travel_seconds=journeys[h["id"]]["travel_seconds"] * 2)
        elif kind == "consume":
            need = h["need_grams"] - consumed[h["id"]]
            total = 0
            for lot in core.lots_for_owner(state, h["id"]):
                if lot.place_id != f"home-{h['id']}":
                    continue
                grams = min(lot.grams, need)
                if grams:
                    commit(core.ConsumeFood, second, phase, actor_id=h["id"], lot_id=lot.lot_id, grams=grams)
                    consumed[h["id"]] += grams
                    total += grams
                    need -= grams
            emit(second, "consume", h=h, quantity=total)

    problems = core.invariant_problems(state)
    if problems:
        raise core.ConservationError(problems)
    terminal = {h["id"]: household_view(h) for h in households}
    result = dict(schema=1, scenario_id=scenario_id,
                policy="council" if council_run_ref is not None else "emergency" if emergency else "baseline", seed=seed,
                horizon_seconds=horizon_seconds, start_time=start_time, timezone=timezone_name,
                local_date=local_date, end_time_exclusive=end_time,
                activity_window=dict(start_second=activity_start_second,
                                     end_second=activity_start_second + ACTIVITY_WINDOW_SECONDS,
                                     start_local=ACTIVITY_START_LOCAL.isoformat(),
                                     duration_seconds=ACTIVITY_WINDOW_SECONDS),
                evidence_state="mixed" if site_snapshot else "illustrative",
                geography="downtown Toronto walking graph", population=population,
                map_sha256=hashlib.sha256(json.dumps(district, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                assumptions=dict(parameter_id=PARAMETER, food_use="300 g produce component per resident at school or day end",
                                 crossing_delay_seconds=12, closed_edges=closed_edges, rule="grams - cents - trip_seconds / 20",
                                 scope=("one local calendar day with a six-hour activity window; one shopping or service trip; "
                                        "no earnings or non-food essentials" if local_date else
                                        "one six-hour activity window; one shopping or service trip; no earnings or non-food essentials"),
                                 unknown_inputs=["observed prices", "operator inventory", "real eligibility", "observed capacities", "operating costs"]
                                 + (["source observation date", "current operating status"] if site_snapshot else [])),
                sites=[{key: value for key, value in asdict(s).items() if value is not None} for s in sites], households=households,
                initial_households=initial_households, initial_sites=initial_sites,
                journeys=journeys, events=events, terminal_households=terminal,
                accounting=dict(state_hash=core.state_hash(state), kernel_event_count=len(kernel_events),
                                imported_grams=state.imported_grams, consumed_grams=state.consumed_grams,
                                remaining_grams=sum(l.grams for l in state.lots),
                                total_cash_cents=sum(a.settled_cents for a in state.accounts),
                                invariant_problems=list(problems)))
    if council_run_ref is not None:
        result["run_id"] = council_run_ref["run_id"]
        result["run_ref"] = {key: value for key, value in council_run_ref.items()
                              if key in {"kind", "run_id", "arm"}}
        result["council_context"] = {
            "organization_refs": council_run_ref.get("organization_refs", []),
            "stakeholder_input_refs": council_run_ref.get("stakeholder_input_refs", []),
        }
        result["rollout_events"] = rollout_events
    if site_snapshot is not None:
        result["data_snapshot"] = {
            "content": site_snapshot,
            "content_sha256": site_snapshot_sha256,
        }
    return result


def run_day(district: dict, start_date: str, population: int = 2400, seed: int = 2026,
            emergency: bool = False, closed_edges: tuple[tuple[int, int], ...] = (),
            site_snapshot: dict | None = None, site_snapshot_sha256: str | None = None,
            municipal_site: MunicipalSiteSchedule | None = None,
            council_run_ref: dict | None = None,
            timezone_name: str = "America/Toronto") -> dict:
    """Execute one explicit local calendar day with the six-hour activity window intact."""
    try:
        calendar_date = date.fromisoformat(start_date)
        zone = ZoneInfo(timezone_name)
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("run_day requires an ISO date and installed IANA timezone") from exc
    start = datetime.combine(calendar_date, time.min, tzinfo=zone)
    following_midnight = datetime.combine(calendar_date + timedelta(days=1), time.min, tzinfo=zone)
    activity_start = datetime.combine(calendar_date, ACTIVITY_START_LOCAL, tzinfo=zone)
    horizon_seconds = int((following_midnight.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds())
    activity_start_second = int((activity_start.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds())
    return run(
        district,
        population,
        seed,
        emergency,
        closed_edges,
        site_snapshot,
        site_snapshot_sha256,
        municipal_site,
        council_run_ref,
        horizon_seconds=horizon_seconds,
        activity_start_second=activity_start_second,
        start_time=start.isoformat(timespec="seconds"),
        timezone_name=timezone_name,
        local_date=calendar_date.isoformat(),
        end_time=following_midnight.isoformat(timespec="seconds"),
    )
