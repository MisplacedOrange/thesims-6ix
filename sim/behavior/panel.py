"""Focal panel and the live barrier. Both are fixed before any provider call."""

from __future__ import annotations

from sim.core import allocate_largest_remainder, seeded_admission_order


def select_panel(households: tuple[tuple[str, str], ...], size: int, seed: int) -> tuple[str, ...]:
    """Return household ids, stratified by the income label in each pair.

    Extra seats go by largest remainder, with ties broken toward the smaller
    income label. Within a band, admission is the seeded order.
    """

    if size < 1:
        raise ValueError("size must be >= 1")
    bands: dict[str, list[str]] = {}
    for household_id, income in households:
        bands.setdefault(income, []).append(household_id)
    if size > len(households):
        raise ValueError("panel cannot be larger than the population")
    quotas = allocate_largest_remainder(size, tuple((band, 1) for band in bands))
    chosen: list[str] = []
    for band in sorted(bands):
        ordered = seeded_admission_order(seed, f"panel-{band}", tuple(bands[band]))
        chosen.extend(ordered[: quotas[band]])
    return tuple(chosen)


def live_barrier(panel: tuple[str, ...], day: int, max_live: int = 4) -> tuple[str, ...]:
    if max_live < 1:
        raise ValueError("max_live must be >= 1")
    if not panel:
        return ()
    width = min(max_live, len(panel))
    start = (day * width) % len(panel)
    return tuple(panel[(start + offset) % len(panel)] for offset in range(width))
