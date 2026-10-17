"""One van, one shift, one payload. An order that does not fit is missed whole."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Carrier:
    carrier_id: str
    payload_grams: int
    shift_start: int
    shift_end: int


@dataclass(frozen=True, slots=True)
class LoadDecision:
    order_id: str
    grams: int
    status: str


def plan_loads(
    carrier: Carrier,
    orders: tuple[tuple[str, int], ...],
    departure_second: int,
) -> tuple[LoadDecision, ...]:
    if carrier.payload_grams < 1:
        raise ValueError("payload_grams must be >= 1")
    if carrier.shift_end <= carrier.shift_start:
        raise ValueError("shift must have positive length")
    outside = departure_second < carrier.shift_start or departure_second >= carrier.shift_end
    remaining = carrier.payload_grams
    decisions: list[LoadDecision] = []
    for order_id, grams in orders:
        if grams < 1:
            raise ValueError("order grams must be >= 1")
        if outside:
            decisions.append(LoadDecision(order_id, grams, "missed_shift"))
            continue
        if grams > remaining:
            decisions.append(LoadDecision(order_id, grams, "missed_payload"))
            continue
        remaining -= grams
        decisions.append(LoadDecision(order_id, grams, "loaded"))
    return tuple(decisions)
