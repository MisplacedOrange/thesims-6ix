"""Seeded queue order. Actor-id order is not the admission rule."""

from __future__ import annotations

from sim.core import seeded_admission_order


def queue_positions(seed: int, opportunity: str, actor_ids: tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    ordered = seeded_admission_order(seed, opportunity, actor_ids)
    return tuple((actor_id, rank) for rank, actor_id in enumerate(ordered))
