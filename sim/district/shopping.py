"""Rule-based store choice. The kernel settles the chosen grams and cents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sim.core import (
    available_grams,
    lots_for_owner,
    spendable_cents,
)
from sim.district.network import Network, shortest_path
from sim.district.population import Household


@dataclass(frozen=True, slots=True)
class ScoredOption:
    option_id: str
    store_id: str | None
    lot_id: str | None
    grams: int
    payment_cents: int
    travel_seconds: int
    score: int


@dataclass(frozen=True, slots=True)
class DayPlan:
    chosen: ScoredOption
    options: tuple[ScoredOption, ...]


def score_option(
    *,
    grams: int,
    payment_cents: int,
    travel_seconds: int,
    habit: bool,
    quality: int,
    preference: int,
    nutrition_per_gram: int,
    price_sensitivity_per_dollar: int,
    time_sensitivity_per_minute: int,
    habit_score: int,
    noise: int,
) -> int:
    """Integer score. Price points are per dollar. Time points are per minute."""

    return (
        nutrition_per_gram * grams
        + preference
        + quality
        + (habit_score if habit else 0)
        - price_sensitivity_per_dollar * payment_cents // 100
        - time_sensitivity_per_minute * travel_seconds // 60
        + noise
    )


def choice_noise(seed: int, household_id: str, day_index: int, option_id: str, span: int) -> int:
    if span <= 0:
        return 0
    digest = hashlib.sha256(f"{seed}|{household_id}|{day_index}|{option_id}|choice-noise".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % (2 * span + 1) - span


def choose(options: tuple[ScoredOption, ...]) -> ScoredOption:
    return min(options, key=lambda option: (-option.score, option.option_id))


def plan_household(
    state,
    household: Household,
    stores: tuple[dict, ...],
    network: Network,
    behavior: dict,
    *,
    day_index: int,
    run_seed: int,
    shop_offset: int,
    need_grams: int,
) -> DayPlan:
    account = _account(state, household.household_id)
    on_hand = sum(available_grams(lot) for lot in lots_for_owner(state, household.household_id))
    shortfall = max(0, need_grams - on_hand)
    package = behavior["package_grams"]
    multiplier = behavior["mobility_multiplier"][household.mobility]
    options: list[ScoredOption] = []
    if account is not None and shortfall >= package:
        for store in stores:
            if not store["operating"]:
                continue
            if not (store["open_offset_seconds"] <= shop_offset < store["close_offset_seconds"]):
                continue
            found = shortest_path(network, household.area_id, store["store_id"])
            if found is None:
                continue
            _path, path_seconds = found
            travel = (household.access_seconds + path_seconds) * multiplier
            if travel > household.time_budget_seconds:
                continue
            lot = _store_lot(state, store, package)
            if lot is None:
                continue
            affordable = (spendable_cents(account) // store["price_cents_per_100g"]) * package
            target = min(shortfall, household.carry_grams, affordable, available_grams(lot))
            target -= target % package
            if target < package:
                continue
            payment = (target // package) * store["price_cents_per_100g"]
            option_id = f"store:{store['store_id']}"
            noise = choice_noise(run_seed, household.household_id, day_index, option_id, behavior["noise_span"])
            score = score_option(
                grams=target,
                payment_cents=payment,
                travel_seconds=travel,
                habit=store["store_id"] == household.habitual_store_id,
                quality=store["quality_score"],
                preference=behavior["preference_score"],
                nutrition_per_gram=behavior["nutrition_score_per_gram"],
                price_sensitivity_per_dollar=household.price_sensitivity_per_dollar,
                time_sensitivity_per_minute=behavior["time_sensitivity_per_minute"],
                habit_score=behavior["habit_score"],
                noise=noise,
            )
            options.append(
                ScoredOption(option_id, store["store_id"], lot.lot_id, target, payment, travel, score)
            )
    options.append(ScoredOption("no-purchase", None, None, 0, 0, 0, 0))
    ranked = tuple(sorted(options, key=lambda option: option.option_id))
    return DayPlan(choose(ranked), ranked)


def _account(state, owner_id: str):
    for account in state.accounts:
        if account.owner_id == owner_id:
            return account
    return None


def _store_lot(state, store: dict, package: int):
    lots = [
        lot
        for lot in lots_for_owner(state, store["actor_id"])
        if lot.product_id == store["product_id"] and available_grams(lot) >= package
    ]
    if not lots:
        return None
    lots.sort(key=lambda lot: (lot.unsafe_after if lot.unsafe_after is not None else 10**12, lot.lot_id))
    return lots[0]
