"""Decentralized and pooled procurement at the same served demand.

Each arm orders the smallest integer quantity that would meet site targets
after the expected delivery ratio and storage loss. The actual delivery can
be worse. A short delivery is not imported. Cash already paid for the missing
grams is a non-mass loss, not a second payment and not phantom inventory.

Volume discounts apply to the ordered quantity. Hub labor and extra handling
are explicit, so a lower unit price can still raise total cost. Sites are
filled in the supplied priority order when the pool is short.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.policies.core_interface import CoreLedger, largest_remainder
from sim.policies.evidence import require_evidence


@dataclass(frozen=True)
class PriceBand:
    min_grams: int
    cents_per_1000g: int


@dataclass(frozen=True)
class SiteDemand:
    site_id: str
    account: str
    owner: str
    custody: str
    target_grams: int
    priority: int


@dataclass(frozen=True)
class SupplyContract:
    evidence_state: str
    bands: tuple[PriceBand, ...]
    minimum_order_grams: int
    expected_receive_num: int
    expected_receive_den: int
    actual_receive_num: int
    actual_receive_den: int
    loss_num: int
    loss_den: int
    pay_for: str
    supplier_account: str
    product_id: str
    unsafe_after: int
    now: int


@dataclass(frozen=True)
class DecentralizedArm:
    contract: SupplyContract
    delivery_cents: int
    delivery_payee: str


@dataclass(frozen=True)
class PooledArm:
    contract: SupplyContract
    buyer_account: str
    hub_owner: str
    hub_custody: str
    labor_cents: int
    labor_payee: str
    inbound_cents: int
    inbound_payee: str
    outbound_cents: int
    outbound_payee: str


@dataclass(frozen=True)
class SiteResult:
    site_id: str
    ordered_grams: int
    served_grams: int
    unmet_grams: int
    residual_grams: int
    food_cents: int
    delivery_cents: int
    spoilage_grams: int
    shortage_grams: int
    shortage_loss_cents: int
    refused: bool
    refusal: str


@dataclass(frozen=True)
class ArmResult:
    evidence_state: str
    mode: str
    ordered_grams: int
    delivered_grams: int
    spoilage_grams: int
    shortage_grams: int
    served_grams: int
    residual_grams: int
    unmet_grams: int
    food_cents: int
    shortage_loss_cents: int
    labor_cents: int
    delivery_cents: int
    unpaid_fee_cents: int
    total_cents: int
    rate_cents_per_1000g: int
    discount_applied: bool
    refused: bool
    refusal: str
    sites: tuple[SiteResult, ...]


def run_decentralized(
    ledger: CoreLedger, sites: tuple[SiteDemand, ...], arm: DecentralizedArm
) -> ArmResult:
    """Each site orders and pays for its own target."""

    _validate_contract(arm.contract)
    if arm.delivery_cents < 0:
        raise ValueError("delivery fee cannot be negative")
    site_results = []
    unpaid_fees = 0
    for site in sorted(sites, key=lambda item: (item.priority, item.site_id)):
        site_result, unpaid = _fill_site(ledger, site, arm)
        site_results.append(site_result)
        unpaid_fees += unpaid
    rates = {
        _rate(arm.contract.bands, site.ordered_grams)
        for site in site_results
        if site.ordered_grams > 0
    }
    rate = next(iter(rates)) if len(rates) == 1 else None
    return _combine(
        "decentralized",
        arm.contract,
        tuple(site_results),
        labor=0,
        unpaid_fees=unpaid_fees,
        rate=rate,
    )


def run_pooled(ledger: CoreLedger, sites: tuple[SiteDemand, ...], arm: PooledArm) -> ArmResult:
    """One contract serves the same targets, then the hub distributes them."""

    _validate_contract(arm.contract)
    if any(value < 0 for value in (arm.labor_cents, arm.inbound_cents, arm.outbound_cents)):
        raise ValueError("hub fees cannot be negative")
    ordered_sites = tuple(sorted(sites, key=lambda item: (item.priority, item.site_id)))
    target = sum(site.target_grams for site in ordered_sites)
    if target == 0:
        empty = tuple(_empty_site(site, 0, False, "") for site in ordered_sites)
        return _combine("pooled", arm.contract, empty, labor=0, unpaid_fees=0)
    ordered = _minimal_order(
        target,
        arm.contract.loss_num,
        arm.contract.loss_den,
        arm.contract.expected_receive_num,
        arm.contract.expected_receive_den,
    )
    if ordered is None:
        return _refuse(arm, ordered_sites, "infeasible_yield")
    if ordered < arm.contract.minimum_order_grams:
        return _refuse(arm, ordered_sites, "below_minimum")
    rate = _rate(arm.contract.bands, ordered)
    pay = _contract_pay(arm.contract, ordered, rate)
    if ledger.spendable(arm.buyer_account) < pay:
        return _refuse(arm, ordered_sites, "unfunded")
    received = _receive(
        ledger,
        arm.contract,
        payer=arm.buyer_account,
        owner=arm.hub_owner,
        custody=arm.hub_custody,
        ordered=ordered,
        rate=rate,
    )
    assignments, residual = _allocate(ledger, arm, ordered_sites, received.remaining_grams)
    labor, labor_unpaid = _pay(ledger, arm.buyer_account, arm.labor_payee, arm.labor_cents, "hub labor")
    inbound, inbound_unpaid = _pay(
        ledger, arm.buyer_account, arm.inbound_payee, arm.inbound_cents, "hub inbound"
    )
    outbound_paid = 0
    outbound_unpaid = 0
    for site in ordered_sites:
        if site.target_grams <= 0:
            continue
        paid, unpaid = _pay(
            ledger,
            arm.buyer_account,
            arm.outbound_payee,
            arm.outbound_cents,
            f"hub outbound {site.site_id}",
        )
        outbound_paid += paid
        outbound_unpaid += unpaid
    sites_out = []
    for site, served in zip(ordered_sites, assignments, strict=True):
        sites_out.append(
            SiteResult(
                site.site_id,
                0,
                served,
                site.target_grams - served,
                0,
                0,
                0,
                0,
                0,
                0,
                False,
                "",
            )
        )
    result = _combine(
        "pooled",
        arm.contract,
        tuple(sites_out),
        labor=labor,
        unpaid_fees=labor_unpaid + inbound_unpaid + outbound_unpaid,
        ordered=ordered,
        delivered=received.delivered_grams,
        spoilage=received.spoilage_grams,
        shortage=received.shortage_grams,
        residual=residual,
        food=pay,
        shortage_loss=received.shortage_loss_cents,
        delivery=inbound + outbound_paid,
        rate=rate,
    )
    return result


def _fill_site(ledger: CoreLedger, site: SiteDemand, arm: DecentralizedArm) -> tuple[SiteResult, int]:
    if site.target_grams < 0:
        raise ValueError("target cannot be negative")
    if site.target_grams == 0:
        return _empty_site(site, 0, False, ""), 0
    ordered = _minimal_order(
        site.target_grams,
        arm.contract.loss_num,
        arm.contract.loss_den,
        arm.contract.expected_receive_num,
        arm.contract.expected_receive_den,
    )
    if ordered is None:
        return _empty_site(site, site.target_grams, True, "infeasible_yield"), 0
    if ordered < arm.contract.minimum_order_grams:
        return _empty_site(site, site.target_grams, True, "below_minimum"), 0
    rate = _rate(arm.contract.bands, ordered)
    pay = _contract_pay(arm.contract, ordered, rate)
    if ledger.spendable(site.account) < pay:
        return _empty_site(site, site.target_grams, True, "unfunded"), 0
    received = _receive(
        ledger,
        arm.contract,
        payer=site.account,
        owner=site.owner,
        custody=site.custody,
        ordered=ordered,
        rate=rate,
    )
    served = min(site.target_grams, received.remaining_grams)
    residual = received.remaining_grams - served
    delivery, unpaid = _pay(
        ledger, site.account, arm.delivery_payee, arm.delivery_cents, f"delivery {site.site_id}"
    )
    return SiteResult(
        site.site_id,
        ordered,
        served,
        site.target_grams - served,
        residual,
        pay,
        delivery,
        received.spoilage_grams,
        received.shortage_grams,
        received.shortage_loss_cents,
        False,
        "",
    ), unpaid


@dataclass(frozen=True)
class _Receipt:
    delivered_grams: int
    spoilage_grams: int
    remaining_grams: int
    shortage_grams: int
    shortage_loss_cents: int


def _receive(
    ledger: CoreLedger,
    contract: SupplyContract,
    *,
    payer: str,
    owner: str,
    custody: str,
    ordered: int,
    rate: int,
) -> _Receipt:
    delivered = ordered * contract.actual_receive_num // contract.actual_receive_den
    shortage = ordered - delivered
    pay = _contract_pay(contract, ordered, rate)
    acquisition, shortage_loss = _split_payment(pay, delivered, shortage)
    if delivered > 0:
        ledger.buy_lot(
            payer=payer,
            payee=contract.supplier_account,
            product_id=contract.product_id,
            owner=owner,
            custody=custody,
            grams=delivered,
            cents=acquisition,
            unsafe_after=contract.unsafe_after,
            source_kind="purchase",
            input_class="purchased",
            memo="procurement delivery",
        )
    if shortage_loss:
        ledger.transfer(payer, contract.supplier_account, shortage_loss, memo="prepaid shortage")
        ledger.recognize_non_mass_loss(shortage_loss, reason="supplier shortage")
    spoilage = delivered * contract.loss_num // contract.loss_den
    if spoilage:
        _write_owned(ledger, owner, contract.product_id, spoilage, contract.now)
    return _Receipt(delivered, spoilage, delivered - spoilage, shortage, shortage_loss)


def _allocate(
    ledger: CoreLedger,
    arm: PooledArm,
    sites: tuple[SiteDemand, ...],
    remaining: int,
) -> tuple[list[int], int]:
    left = remaining
    served = []
    for site in sites:
        give = min(site.target_grams, left)
        if give:
            _move(ledger, arm, site, give)
            left -= give
        served.append(give)
    return served, left


def _move(ledger: CoreLedger, arm: PooledArm, site: SiteDemand, grams: int) -> None:
    left = grams
    while left > 0:
        candidates = [
            lot
            for lot in ledger.lots()
            if lot.owner == arm.hub_owner
            and lot.product_id == arm.contract.product_id
            and lot.unsafe_after > arm.contract.now
            and ledger.reserved_grams(lot.lot_id) == 0
        ]
        if not candidates:
            raise RuntimeError("hub lost grams it had just received")
        candidates.sort(key=lambda lot: (lot.unsafe_after, lot.lot_id))
        lot = candidates[0]
        take_grams = min(lot.grams, left)
        piece = ledger.take(lot.lot_id, take_grams)
        ledger.transfer_lot(piece, owner=site.owner, custody=site.custody)
        left -= take_grams


def _write_owned(ledger: CoreLedger, owner: str, product_id: str, grams: int, now: int) -> None:
    left = grams
    while left > 0:
        candidates = [
            lot
            for lot in ledger.lots()
            if lot.owner == owner and lot.product_id == product_id and lot.unsafe_after > now
        ]
        if not candidates:
            raise RuntimeError("spoilage exceeded the delivery")
        candidates.sort(key=lambda lot: (lot.unsafe_after, lot.lot_id))
        lot = candidates[0]
        take_grams = min(lot.grams, left)
        ledger.write_off(lot.lot_id, take_grams, reason="procurement_spoilage")
        left -= take_grams


def _contract_pay(contract: SupplyContract, ordered: int, rate: int) -> int:
    if contract.pay_for == "ordered":
        base = ordered
    elif contract.pay_for == "delivered":
        base = ordered * contract.actual_receive_num // contract.actual_receive_den
    else:
        raise ValueError("pay_for must be ordered or delivered")
    return base * rate // 1000


def _split_payment(pay: int, delivered: int, shortage: int) -> tuple[int, int]:
    if delivered == 0:
        return 0, pay
    weights = {"delivered": delivered}
    if shortage > 0:
        weights["shortage"] = shortage
    parts = largest_remainder(pay, weights)
    return parts["delivered"], parts.get("shortage", 0)


def _minimal_order(
    target: int, loss_num: int, loss_den: int, receive_num: int, receive_den: int
) -> int | None:
    if target == 0:
        return 0
    if receive_num <= 0 or receive_den <= 0 or loss_den <= 0 or loss_num < 0 or loss_num >= loss_den:
        return None

    def served(ordered: int) -> int:
        delivered = ordered * receive_num // receive_den
        return delivered - delivered * loss_num // loss_den

    cap = (target + 1) * (receive_den + 1) * (loss_den + 1)
    if served(cap) < target:
        return None
    low = 0
    high = 1
    while served(high) < target:
        high = min(cap, high * 2)
    while low + 1 < high:
        mid = (low + high) // 2
        if served(mid) >= target:
            high = mid
        else:
            low = mid
    return high


def _rate(bands: tuple[PriceBand, ...], grams: int) -> int:
    applicable = [band for band in bands if grams >= band.min_grams]
    if not applicable:
        raise ValueError("no price band covers the order")
    chosen = max(applicable, key=lambda band: band.min_grams)
    return chosen.cents_per_1000g


def _base_rate(bands: tuple[PriceBand, ...]) -> int:
    return min(bands, key=lambda band: band.min_grams).cents_per_1000g


def _pay(ledger: CoreLedger, src: str, dst: str, cents: int, memo: str) -> tuple[int, int]:
    if cents <= 0:
        return 0, 0
    if ledger.spendable(src) < cents:
        return 0, cents
    ledger.transfer(src, dst, cents, memo=memo)
    return cents, 0


def _validate_contract(contract: SupplyContract) -> None:
    require_evidence(contract.evidence_state)
    if not contract.bands:
        raise ValueError("contract needs a price band")
    if any(band.min_grams < 0 or band.cents_per_1000g < 0 for band in contract.bands):
        raise ValueError("price bands must be nonnegative")
    if contract.minimum_order_grams < 0:
        raise ValueError("minimum order cannot be negative")
    if contract.pay_for not in ("ordered", "delivered"):
        raise ValueError("pay_for must be ordered or delivered")
    for numerator, denominator in (
        (contract.expected_receive_num, contract.expected_receive_den),
        (contract.actual_receive_num, contract.actual_receive_den),
        (contract.loss_num, contract.loss_den),
    ):
        if denominator <= 0 or numerator < 0:
            raise ValueError("contract fraction is invalid")
    if contract.loss_num >= contract.loss_den:
        raise ValueError("loss must leave some delivered food")


def _empty_site(site: SiteDemand, unmet: int, refused: bool, refusal: str) -> SiteResult:
    return SiteResult(site.site_id, 0, 0, unmet, 0, 0, 0, 0, 0, 0, refused, refusal)


def _refuse(arm: PooledArm, sites: tuple[SiteDemand, ...], refusal: str) -> ArmResult:
    site_results = tuple(_empty_site(site, site.target_grams, True, refusal) for site in sites)
    return _combine("pooled", arm.contract, site_results, labor=0, unpaid_fees=0, refused=True, refusal=refusal)


def _combine(
    mode: str,
    contract: SupplyContract,
    sites: tuple[SiteResult, ...],
    *,
    labor: int,
    unpaid_fees: int,
    ordered: int | None = None,
    delivered: int | None = None,
    spoilage: int | None = None,
    shortage: int | None = None,
    residual: int | None = None,
    food: int | None = None,
    shortage_loss: int | None = None,
    delivery: int | None = None,
    rate: int | None = None,
    refused: bool = False,
    refusal: str = "",
) -> ArmResult:
    ordered_grams = sum(site.ordered_grams for site in sites) if ordered is None else ordered
    food_cents = sum(site.food_cents for site in sites) if food is None else food
    delivery_cents = sum(site.delivery_cents for site in sites) if delivery is None else delivery
    if spoilage is None:
        spoilage = sum(site.spoilage_grams for site in sites)
    if shortage is None:
        shortage = sum(site.shortage_grams for site in sites)
    if shortage_loss is None:
        shortage_loss = sum(site.shortage_loss_cents for site in sites)
    if delivered is None:
        delivered = sum(site.served_grams + site.residual_grams + site.spoilage_grams for site in sites)
    if rate is None and ordered_grams > 0 and not refused:
        rate = _rate(contract.bands, ordered_grams)
    discount = False
    if rate is not None and ordered_grams > 0 and not refused:
        discount = rate < _base_rate(contract.bands)
    every_site_refused = bool(sites) and all(site.refused for site in sites)
    return ArmResult(
        evidence_state=contract.evidence_state,
        mode=mode,
        ordered_grams=ordered_grams,
        delivered_grams=delivered,
        spoilage_grams=spoilage,
        shortage_grams=shortage,
        served_grams=sum(site.served_grams for site in sites),
        residual_grams=sum(site.residual_grams for site in sites) if residual is None else residual,
        unmet_grams=sum(site.unmet_grams for site in sites),
        food_cents=food_cents,
        shortage_loss_cents=shortage_loss,
        labor_cents=labor,
        delivery_cents=delivery_cents,
        unpaid_fee_cents=unpaid_fees,
        total_cents=food_cents + labor + delivery_cents,
        rate_cents_per_1000g=0 if rate is None else rate,
        discount_applied=discount,
        refused=refused or every_site_refused,
        refusal=refusal,
        sites=sites,
    )
