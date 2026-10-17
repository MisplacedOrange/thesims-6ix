"""Drone corridors are a scenario flag. No-approval is the default branch.

Times and cents are illustrative. They are not Meituan operating data and
not a Transport Canada permission.
"""

from __future__ import annotations

from dataclasses import dataclass

MODES = ("no_approval", "approved", "handoff_failure", "weather_closed", "no_ground", "stranded")
ORDER_COUNT = 3
ORDER_GRAMS = 400
PAYLOAD_GRAMS = 500
MAX_FLIGHTS = 2
DRONE_WINDOW_CENTS = 1200
GROUND_ORDER_CENTS = 300
DOOR_TO_COLLECTION_SECONDS = 60 + 30 + 30 + 180 + 30 + 120


@dataclass(frozen=True, slots=True)
class DroneResult:
    mode: str
    evidence_state: str
    eligible: bool
    flights: int
    drone_completed: int
    ground_completed: int
    handoff_failures: int
    unserved: int
    door_to_collection_seconds: int | None
    allocated_cents: int
    cost_per_completed_cents: int | None
    remainder_cents: int
    note: str


def run_drones(mode: str) -> DroneResult:
    if mode not in MODES:
        raise ValueError(mode)
    eligible = mode not in {"no_approval", "stranded"}
    weather_open = mode != "weather_closed"
    ground = mode not in {"no_ground", "stranded"}
    capacity = MAX_FLIGHTS if eligible and weather_open else 0
    flights = 0
    drone_completed = 0
    ground_completed = 0
    handoff_failures = 0
    unserved = 0
    for _index in range(ORDER_COUNT):
        if flights < capacity and ORDER_GRAMS <= PAYLOAD_GRAMS:
            flights += 1
            failed = mode == "handoff_failure" and flights == 1
            if failed:
                handoff_failures += 1
                if ground:
                    ground_completed += 1
                else:
                    unserved += 1
            else:
                drone_completed += 1
            continue
        if ground:
            ground_completed += 1
        else:
            unserved += 1
    completed = drone_completed + ground_completed
    allocated = (DRONE_WINDOW_CENTS if flights else 0) + GROUND_ORDER_CENTS * ground_completed
    if completed == 0:
        per_order = None
        remainder = 0
    else:
        per_order = allocated // completed
        remainder = allocated % completed
    return DroneResult(
        mode=mode,
        evidence_state="illustrative",
        eligible=eligible,
        flights=flights,
        drone_completed=drone_completed,
        ground_completed=ground_completed,
        handoff_failures=handoff_failures,
        unserved=unserved,
        door_to_collection_seconds=DOOR_TO_COLLECTION_SECONDS if drone_completed else None,
        allocated_cents=allocated,
        cost_per_completed_cents=per_order,
        remainder_cents=remainder,
        note=(
            "Eligible means the scenario record allows the corridor. It is not flight permission. "
            "A failed handoff is completed by ground when a van is available. "
            "Cost per completed order excludes unserved orders. The window cost is charged only when a flight launches."
        ),
    )
