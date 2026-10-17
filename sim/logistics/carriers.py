"""Pure carrier constraint checks.

Payload and cold chain do not improve by waiting. Energy, shift, and downtime
are checked at a proposed start second against the energy the carrier will
have when it is next free.
"""

from __future__ import annotations

from sim.logistics.drones import windows_overlap
from sim.logistics.models import COLD_CLASSES, CarrierSpec
from sim.logistics.units import charge_seconds


def static_blocker(carrier: CarrierSpec, grams: int, storage_class: str) -> str | None:
    if grams > carrier.payload_grams:
        return "payload_grams"
    if storage_class in COLD_CLASSES and not carrier.cold_chain:
        return "cold_chain"
    return None


def energy_blocker(energy: int, distance_m: int, energy_per_metre: int, reserve_energy: int) -> str | None:
    consumption = distance_m * energy_per_metre
    if energy - consumption < reserve_energy:
        return "energy_reserve"
    return None


def shift_blocker(shift_start: int, shift_end: int, start: int, duration: int) -> str | None:
    if start < shift_start or start + duration > shift_end:
        return "shift"
    return None


def downtime_blocker(downtime: tuple[tuple[int, int], ...], start: int, end: int) -> str | None:
    if windows_overlap(downtime, start, end):
        return "maintenance"
    return None


def recharge_plan(energy_after: int, capacity: int, rate_per_second: int) -> tuple[int, int]:
    """Return ``(charge_seconds, energy_when_free)`` after a trip."""

    if energy_after >= capacity or rate_per_second <= 0:
        return (0, energy_after)
    deficit = capacity - energy_after
    seconds = charge_seconds(deficit, rate_per_second)
    restored = min(capacity, energy_after + rate_per_second * seconds)
    return (seconds, restored)
