"""Run-level live-choice ceiling.

Person 2 persists provider reservations and reconciles actual usage. This
module decides whether another live request would fit under the planning
ceiling, and offers an in-memory ledger so rule-only runs need no gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from sim.behavior.errors import BehaviorError

_QUANTUM = Decimal("0.000001")
RUN_BUDGET_CAD = Decimal("30")
MAX_INPUT_TOKENS = 1500
MAX_OUTPUT_TOKENS = 200
MAX_ATTEMPTS = 1200


def qcad(value: Decimal) -> Decimal:
    return value.quantize(_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TokenPrice:
    """Illustrative or quoted rates. A missing price cannot enable live calls.

    ``evidence_state`` must say when the numbers are not a provider quote.
    """

    evidence_state: str
    fx_to_cad: Decimal
    input_rate_per_million: Decimal
    output_rate_per_million: Decimal
    other_fees_cad: Decimal


def estimate_max_request_cad(
    price: TokenPrice,
    *,
    input_tokens: int = MAX_INPUT_TOKENS,
    output_tokens: int = MAX_OUTPUT_TOKENS,
) -> Decimal:
    """Maximum CAD reserved before one dispatch.

    ``estimated_CAD = FX * (input * rate + output * rate + other fees)`` with
    rates expressed per million tokens. A non-positive result does not bound
    the charge, so live dispatch stays off.
    """

    if price.fx_to_cad <= 0:
        raise BehaviorError("fx_to_cad must be positive")
    if price.input_rate_per_million < 0 or price.output_rate_per_million < 0:
        raise BehaviorError("token rates cannot be negative")
    if price.other_fees_cad < 0:
        raise BehaviorError("fees cannot be negative")
    raw = price.fx_to_cad * (
        Decimal(input_tokens) * price.input_rate_per_million / Decimal(1_000_000)
        + Decimal(output_tokens) * price.output_rate_per_million / Decimal(1_000_000)
        + price.other_fees_cad
    )
    amount = qcad(raw)
    if amount <= 0:
        raise BehaviorError("token price does not bound a positive charge")
    return amount


class ChargeReservation(Protocol):
    def remaining_cad(self) -> Decimal:
        """CAD still available for new maximum reservations."""

    def reserve_maximum(self, decision_id: str, amount_cad: Decimal) -> bool:
        """Reserve a maximum charge. False means the ceiling would be exceeded."""


@dataclass
class MemoryChargeReservation:
    """Process-local ceiling. Not a provider ledger and not durable."""

    ceiling_cad: Decimal = RUN_BUDGET_CAD
    _reserved: dict[str, Decimal] = field(default_factory=dict)

    def remaining_cad(self) -> Decimal:
        used = sum(self._reserved.values(), Decimal("0"))
        return self.ceiling_cad - used

    def reserve_maximum(self, decision_id: str, amount_cad: Decimal) -> bool:
        if amount_cad <= 0:
            raise BehaviorError("reservation must be positive")
        existing = self._reserved.get(decision_id)
        if existing is not None:
            return existing == amount_cad
        if amount_cad > self.remaining_cad():
            return False
        self._reserved[decision_id] = amount_cad
        return True
