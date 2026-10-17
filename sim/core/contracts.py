"""Read-only economic scene projection. Choice schemas live in sim.behavior.draft."""

from __future__ import annotations

from dataclasses import dataclass

from sim.core.models import Account, FoodLot, Reservation


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
