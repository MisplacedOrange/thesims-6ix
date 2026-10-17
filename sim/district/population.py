"""Deterministic synthetic population. Margins match the frozen quotas exactly."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sim.core import sha256_hex


@dataclass(frozen=True, slots=True)
class Member:
    member_id: str
    household_id: str
    role: str
    age_band: str


@dataclass(frozen=True, slots=True)
class Household:
    household_id: str
    size: int
    income_band: str
    tenure: str
    area_id: str
    food_budget_cents: int
    essential_nonfood_cents: int
    mobility: str
    cooking: bool
    diet: str
    habitual_store_id: str
    carry_grams: int
    time_budget_seconds: int
    price_sensitivity_per_dollar: int
    access_seconds: int
    members: tuple[Member, ...]


@dataclass(frozen=True, slots=True)
class Pupil:
    member_id: str
    household_id: str
    school_id: str
    age_band: str
    eligible: bool


@dataclass(frozen=True, slots=True)
class Population:
    households: tuple[Household, ...]
    pupils: tuple[Pupil, ...]
    population_seed: int
    generator_version: str
    population_hash: str


def build_population(controls: dict, places: dict) -> Population:
    count = controls["household_count"]
    sizes = _blocked(controls["size"], count)
    incomes = _striped(controls["income"], controls["income_spread_stride"], count)
    tenures = _striped(controls["tenure"], controls["tenure_spread_stride"], count)
    areas = _striped(controls["area"], controls["area_spread_stride"], count)
    area_by_id = {area["area_id"]: area for area in places["areas"]}
    schools = {school["school_id"]: school for school in places["schools"]}
    seed = controls["population_seed"]
    child_bands = tuple(controls["child_age_bands"])
    school_bands = set(controls["school_age_bands"])
    households: list[Household] = []
    pupils: list[Pupil] = []
    child_ordinal = 0
    size2_seen = 0
    for index in range(count):
        household_id = f"hh-{index:03d}"
        size = int(sizes[index])
        area_id = areas[index]
        area = area_by_id[area_id]
        mobility = "limited" if _mille(seed, household_id, "mobility") < controls["mobility_limited_per_mille"] else "walk"
        diet_bucket = _mille(seed, household_id, "diet")
        if diet_bucket < controls["diet_none_below_per_mille"]:
            diet = "none"
        elif diet_bucket < controls["diet_vegetarian_below_per_mille"]:
            diet = "vegetarian"
        else:
            diet = "dairy_free"
        members: list[Member] = []
        child_count = 0
        if size == 1:
            adult_count = 1
        elif size == 2:
            if size2_seen < controls["size2_with_child"]:
                adult_count = 1
                child_count = 1
            else:
                adult_count = 2
            size2_seen += 1
        else:
            adult_count = 2
            child_count = size - 2
        for member_index in range(adult_count):
            members.append(Member(f"{household_id}-m{member_index}", household_id, "adult", "18+"))
        for child_index in range(child_count):
            age_band = child_bands[child_ordinal % len(child_bands)]
            child_ordinal += 1
            member = Member(f"{household_id}-m{adult_count + child_index}", household_id, "child", age_band)
            members.append(member)
            if age_band in school_bands:
                school = schools[area["school_id"]]
                pupils.append(
                    Pupil(
                        member_id=member.member_id,
                        household_id=household_id,
                        school_id=school["school_id"],
                        age_band=age_band,
                        eligible=school["program_status"] == "active" and age_band in school["age_bands"],
                    )
                )
        income = incomes[index]
        households.append(
            Household(
                household_id=household_id,
                size=size,
                income_band=income,
                tenure=tenures[index],
                area_id=area_id,
                food_budget_cents=controls["food_budget_cents"][income],
                essential_nonfood_cents=controls["essential_nonfood_cents"][income],
                mobility=mobility,
                cooking=_mille(seed, household_id, "cooking") < controls["cooking_per_mille"],
                diet=diet,
                habitual_store_id=area["store_id"],
                carry_grams=controls["carry_grams"][mobility],
                time_budget_seconds=controls["time_budget_seconds"][mobility],
                price_sensitivity_per_dollar=controls["price_sensitivity_per_100_cents"][income],
                access_seconds=60 + (_mille(seed, household_id, "access") % 5) * 30,
                members=tuple(members),
            )
        )
    population = Population(
        households=tuple(households),
        pupils=tuple(pupils),
        population_seed=seed,
        generator_version=controls["generator_version"],
        population_hash="",
    )
    digest = sha256_hex(_hashable(population))
    return Population(
        households=population.households,
        pupils=population.pupils,
        population_seed=seed,
        generator_version=population.generator_version,
        population_hash=digest,
    )


def attendance_present(population_seed: int, member_id: str, day_index: int) -> bool:
    """About four of five pupil-days are present. The draw is the population seed, not the run seed."""

    digest = hashlib.sha256(f"{population_seed}|{member_id}|{day_index}|attendance".encode("utf-8")).digest()
    return digest[0] % 5 != 0


def _blocked(pairs: list, count: int) -> list[str]:
    labels: list[str] = []
    for key, size in pairs:
        labels.extend([str(key)] * int(size))
    if len(labels) != count:
        raise ValueError("quota does not sum to the household count")
    return labels


def _striped(pairs: list, stride: int, count: int) -> list[str]:
    labels = _blocked(pairs, count)
    order = sorted(range(count), key=lambda index: (index * int(stride)) % count)
    return [labels[index] for index in order]


def _mille(seed: int, household_id: str, purpose: str) -> int:
    digest = hashlib.sha256(f"{seed}|{household_id}|{purpose}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % 1000


def _hashable(population: Population) -> list[dict[str, object]]:
    rows = []
    for household in population.households:
        rows.append(
            {
                "household_id": household.household_id,
                "size": household.size,
                "income_band": household.income_band,
                "tenure": household.tenure,
                "area_id": household.area_id,
                "food_budget_cents": household.food_budget_cents,
                "mobility": household.mobility,
                "diet": household.diet,
                "members": [member.member_id + ":" + member.age_band for member in household.members],
            }
        )
    return rows
