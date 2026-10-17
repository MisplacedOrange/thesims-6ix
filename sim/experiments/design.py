"""Screening cells, matched seeds, and policy-independent shocks."""

from __future__ import annotations

from sim.behavior.canonical import canon_float, observation_hash
from sim.behavior.determinism import STREAM_ALGORITHM, draw_unit
from sim.experiments.adapters import ExternalShock
from sim.experiments.errors import ExperimentError

POLICIES = ("groceries", "processing", "school", "drones")
SCREENING_CELLS = 16
PLANNING_SEED_BLOCKS = 30


def seed_blocks(count: int = PLANNING_SEED_BLOCKS, origin: int = 1) -> tuple[int, ...]:
    if type(count) is not int or count < 1:
        raise ExperimentError("replication count must be a positive int")
    if type(origin) is not int or origin < 0:
        raise ExperimentError("seed origin must be a non-negative int")
    return tuple(range(origin, origin + count))


def cell_id_for(enabled: tuple[str, ...]) -> str:
    normalized = normalize_policies(enabled)
    if not normalized:
        return "baseline"
    return "+".join(normalized)


def normalize_policies(enabled: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    unknown = [name for name in enabled if name not in POLICIES]
    if unknown:
        raise ExperimentError(f"unknown policy {unknown[0]}")
    selected = set(enabled)
    return tuple(name for name in POLICIES if name in selected)


def screening_cells() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Sixteen mature-policy cells. Bit 0 is groceries and bit 3 is drones."""

    cells = []
    for mask in range(SCREENING_CELLS):
        enabled = tuple(name for index, name in enumerate(POLICIES) if mask & (1 << index))
        cells.append((cell_id_for(enabled), enabled))
    return tuple(cells)


def draw_shocks(
    seed: int,
    *,
    days: int,
    actors: tuple[str, ...],
    purposes: tuple[str, ...] = ("weather", "income"),
) -> tuple[ExternalShock, ...]:
    """Draw shocks without the policy in the key."""

    if days < 1:
        raise ExperimentError("shock window must cover at least one day")
    if not actors or not purposes:
        raise ExperimentError("shocks need actors and purposes")
    shocks: list[ExternalShock] = []
    for purpose in purposes:
        for actor in actors:
            for day in range(days):
                value = canon_float(draw_unit(seed, actor=actor, day=day, purpose=purpose))
                shocks.append(
                    ExternalShock(
                        shock_id=f"{purpose}:{actor}:{day}",
                        purpose=purpose,
                        actor=actor,
                        day_index=day,
                        value=value,
                    )
                )
    return tuple(shocks)


def shock_digest(shocks: tuple[ExternalShock, ...]) -> str:
    payload = {
        "algorithm": STREAM_ALGORITHM,
        "shocks": [{"id": shock.shock_id, "value": shock.value} for shock in shocks],
    }
    return observation_hash(payload)
