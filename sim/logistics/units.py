"""Integer units for logistics.

Money is Canadian cents, food mass is grams, time is simulation seconds, and
route geometry is metres. Durations that represent real travel round upward.
A positive distance takes at least one second. A zero distance is not travel
and takes zero seconds. Service durations configured on a fleet are validated
to be at least one second at the boundary, so the engine does not quietly
rewrite a caller's clock.
"""

from __future__ import annotations

from sim.logistics.errors import UnitError

UNIT_SYSTEM = "cents|grams|seconds|metres"


def require_int(name: str, value: int) -> int:
    """Reject bools and non-integers. Bool is a subclass of int."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise UnitError(f"{name} must be an integer number of its declared unit")
    return value


def require_nonnegative(name: str, value: int) -> int:
    number = require_int(name, value)
    if number < 0:
        raise UnitError(f"{name} must be >= 0")
    return number


def require_positive(name: str, value: int) -> int:
    number = require_int(name, value)
    if number <= 0:
        raise UnitError(f"{name} must be >= 1")
    return number


def travel_seconds(distance_m: int, speed_m_per_s: int, congestion_milli: int) -> int:
    """Ceiling of distance times congestion, divided by speed.

    ``congestion_milli`` of 1000 means a factor of 1. The result is an integer
    number of seconds. Zero distance yields 0. Any positive distance yields
    at least 1.
    """

    distance = require_nonnegative("distance_m", distance_m)
    speed = require_positive("speed_m_per_s", speed_m_per_s)
    congestion = require_positive("congestion_milli", congestion_milli)
    if distance == 0:
        return 0
    numerator = distance * congestion
    denominator = speed * 1000
    seconds = (numerator + denominator - 1) // denominator
    return max(1, seconds)


def charge_seconds(deficit: int, rate_per_second: int) -> int:
    """Seconds to recover ``deficit`` energy units at an integer rate.

    A positive deficit with a positive rate takes at least one second. A zero
    deficit, or a carrier that does not recharge, takes zero seconds.
    """

    missing = require_nonnegative("energy_deficit", deficit)
    rate = require_nonnegative("charge_per_second", rate_per_second)
    if missing == 0 or rate == 0:
        return 0
    return max(1, (missing + rate - 1) // rate)
