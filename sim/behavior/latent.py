"""Illustrative strain, trust, and satisfaction proxies.

These are latent model variables. They are not clinical stress, diagnosed
hunger, or measured Toronto sentiment. Weights and persistence need sensitivity
analysis before any calibration claim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sim.behavior.errors import BehaviorError


@dataclass(frozen=True)
class LatentCoefficients:
    evidence_state: str = "illustrative"
    persistence: float = 0.6
    recovery: float = 0.05
    weight_food: float = 0.4
    weight_financial: float = 0.4
    weight_time: float = 0.2
    trust_fulfillment_gain: float = 0.1
    trust_break_loss: float = 0.2
    satisfaction_step: float = 0.1


@dataclass(frozen=True)
class LatentState:
    stress: float
    trust: float
    satisfaction: float


def clamp01(value: float) -> float:
    if not math.isfinite(value):
        raise BehaviorError("latent update received a non-finite value")
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return value


def normalized_strain(shortfall: int, need: int) -> float:
    if type(shortfall) is not int or type(need) is not int:
        raise BehaviorError("strain inputs must be ints")
    if shortfall < 0 or need < 0:
        raise BehaviorError("strain inputs cannot be negative")
    if need == 0:
        return 0.0
    return clamp01(shortfall / need)


def next_stress(
    stress: float,
    *,
    food_strain: float,
    financial_strain: float,
    time_strain: float,
    coefficients: LatentCoefficients,
) -> float:
    """``persistence * stress + weighted strains - recovery``, clamped to [0, 1]."""

    update = (
        coefficients.persistence * stress
        + coefficients.weight_food * food_strain
        + coefficients.weight_financial * financial_strain
        + coefficients.weight_time * time_strain
        - coefficients.recovery
    )
    return clamp01(update)


def next_trust(trust: float, *, fulfilled: bool | None, coefficients: LatentCoefficients) -> float:
    """Move trust from a recorded fulfillment or a broken expectation.

    ``fulfilled is None`` means the day had no relevant service event.
    """

    if fulfilled is True:
        return clamp01(trust + coefficients.trust_fulfillment_gain)
    if fulfilled is False:
        return clamp01(trust - coefficients.trust_break_loss)
    return clamp01(trust)


def next_satisfaction(
    satisfaction: float,
    *,
    expected: float,
    realized: float,
    coefficients: LatentCoefficients,
) -> float:
    """Compare expected and realized service. Both inputs are model scores in [0, 1]."""

    gap = clamp01(realized) - clamp01(expected)
    return clamp01(satisfaction + coefficients.satisfaction_step * gap)


def update_latent(
    state: LatentState,
    *,
    basket_shortfall_grams: int,
    basket_need_grams: int,
    unfunded_essentials_cents: int,
    essential_need_cents: int,
    time_overrun_seconds: int,
    time_budget_seconds: int,
    fulfilled: bool | None,
    expected_service: float,
    realized_service: float,
    coefficients: LatentCoefficients | None = None,
) -> LatentState:
    coeffs = coefficients or LatentCoefficients()
    return LatentState(
        stress=next_stress(
            state.stress,
            food_strain=normalized_strain(basket_shortfall_grams, basket_need_grams),
            financial_strain=normalized_strain(unfunded_essentials_cents, essential_need_cents),
            time_strain=normalized_strain(time_overrun_seconds, time_budget_seconds),
            coefficients=coeffs,
        ),
        trust=next_trust(state.trust, fulfilled=fulfilled, coefficients=coeffs),
        satisfaction=next_satisfaction(
            state.satisfaction,
            expected=expected_service,
            realized=realized_service,
            coefficients=coeffs,
        ),
    )
