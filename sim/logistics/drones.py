"""Drone corridor eligibility.

A corridor is eligible only when the scenario says so. ``no_approval`` is the
study branch in which Toronto has not authorized the route. Meituan timings
are not used. Flight duration comes from the corridor's declared metres and
the carrier's speed.

Weather and site-hour windows are half-open: a flight that begins at the
window's end does not overlap it.
"""

from __future__ import annotations

from sim.logistics.models import APPROVALS, Corridor


def permission_blocker(corridor: Corridor) -> str | None:
    """Return a reason when the scenario does not allow this corridor to fly."""

    if corridor.approval not in APPROVALS:
        return "ineligible"
    if corridor.approval == "no_approval":
        return "no_approval"
    if not corridor.eligible:
        return "ineligible"
    return None


def windows_overlap(windows: tuple[tuple[int, int], ...], start: int, end: int) -> bool:
    """True when half-open ``[start, end)`` overlaps any half-open window."""

    if end <= start:
        return False
    return any(start < window_end and window_start < end for window_start, window_end in windows)


def weather_blocker(corridor: Corridor, flight_start: int, flight_end: int) -> str | None:
    if windows_overlap(corridor.weather, flight_start, flight_end):
        return "weather"
    return None


def site_hours_blocker(corridor: Corridor, arrival: int, unload_seconds: int) -> str | None:
    """The locker must be open for the whole unload interval ``[arrival, arrival + unload)``."""

    if unload_seconds < 1:
        return "site_hours"
    if arrival < corridor.site_open_second or arrival + unload_seconds > corridor.site_close_second:
        return "site_hours"
    return None
