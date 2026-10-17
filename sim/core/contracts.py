"""DRAFT shared contract types.

These types are the proposal Person 2 and the policy, logistics, behavior, and
experiment packages should review. The narrative proposal is
``contracts/DRAFT-shared-contracts.md``. Wire compatibility is not frozen
beyond kernel version 0.1.0.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.core.models import Account, FoodLot, Reservation


@dataclass(frozen=True, slots=True)
class ObservedFact:
    fact_id: str
    value: str


@dataclass(frozen=True, slots=True)
class FeasibleOption:
    option_id: str
    summary: str


@dataclass(frozen=True, slots=True)
class ChoiceOffer:
    decision_id: str
    household_id: str
    revision: int
    known_facts: tuple[ObservedFact, ...]
    options: tuple[FeasibleOption, ...]


@dataclass(frozen=True, slots=True)
class ChoiceReceipt:
    decision_id: str
    option_id: str
    origin: str
    observation_hash: str
    explanation: str | None = None


class ChoiceOrigin:
    RULE = "rule"
    LLM = "llm"
    RECORDED = "recorded"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class SceneSnapshot:
    """Economic projection. Meshes, camera, and interpolation are not fields."""

    schema_version: int
    run_id: str
    scenario_id: str
    sequence: int
    second: int
    phase: int
    state_hash: str
    accounts: tuple[Account, ...]
    lots: tuple[FoodLot, ...]
    reservations: tuple[Reservation, ...]
    imported_grams: int
    added_grams: int
    consumed_grams: int
    loss_grams: int
    exported_grams: int
