"""Transparent discrete-choice score.

``price_sensitivity_per_dollar`` is utility per Canadian dollar. Payments stay
in integer cents until this function divides by 100. A coefficient must not be
applied to raw cents.

``time_sensitivity_per_minute`` is utility per minute. Collection time stays in
integer seconds until this function divides by 60.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sim.behavior.determinism import STREAM_ALGORITHM, choice_noise
from sim.behavior.draft import FeasibleOption
from sim.behavior.errors import BehaviorError


@dataclass(frozen=True)
class UtilityCoefficients:
    evidence_state: str = "illustrative"
    price_sensitivity_per_dollar: float = 1.0
    time_sensitivity_per_minute: float = 0.15
    noise_amplitude: float = 0.05
    habit_bonus: float = 0.4
    unknown_store_penalty: float = 0.3
    stale_price_penalty: float = 0.1
    tight_stock_penalty: float = 0.1
    unmet_need_penalty: float = 20.0
    delay_penalty: float = 12.0
    price_sensitivity_by_income_band: tuple[tuple[str, float], ...] = ()
    calibration_note: str = (
        "Illustrative until a documented calibration source exists. "
        "The October 17, 2026 context snapshot is not a calibration set. "
        "Income does not set this coefficient unless a study names a mechanism. "
        "The delay and unmet-need penalties are large enough that an ordinary "
        "basket beats leaving without food. They are not estimated welfare weights."
    )

    def price_sensitivity(self, income_band: str) -> float:
        for band, value in self.price_sensitivity_by_income_band:
            if band == income_band:
                return value
        return self.price_sensitivity_per_dollar


def validate_coefficients(coeffs: UtilityCoefficients) -> None:
    for name, value in (
        ("price_sensitivity_per_dollar", coeffs.price_sensitivity_per_dollar),
        ("time_sensitivity_per_minute", coeffs.time_sensitivity_per_minute),
        ("noise_amplitude", coeffs.noise_amplitude),
        ("habit_bonus", coeffs.habit_bonus),
        ("unknown_store_penalty", coeffs.unknown_store_penalty),
        ("stale_price_penalty", coeffs.stale_price_penalty),
        ("tight_stock_penalty", coeffs.tight_stock_penalty),
        ("unmet_need_penalty", coeffs.unmet_need_penalty),
        ("delay_penalty", coeffs.delay_penalty),
    ):
        if type(value) is bool or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise BehaviorError(f"{name} must be finite")
        if float(value) < 0:
            raise BehaviorError(f"{name} cannot be negative")
    for band, value in coeffs.price_sensitivity_by_income_band:
        if not band or float(value) < 0 or not math.isfinite(float(value)):
            raise BehaviorError("income-band price sensitivity is invalid")


def score_option(
    option: FeasibleOption,
    *,
    price_sensitivity_per_dollar: float,
    time_sensitivity_per_minute: float,
    noise: float,
) -> float:
    dollars = option.expected_payment_cents / 100.0
    minutes = option.total_seconds / 60.0
    return (
        option.preference_fit
        + option.habit_value
        + option.known_quality
        - price_sensitivity_per_dollar * dollars
        - time_sensitivity_per_minute * minutes
        - option.stockout_penalty
        - option.uncertainty_penalty
        + noise
    )


def utility_of(
    option: FeasibleOption,
    *,
    master_seed: int,
    household_id: str,
    day_index: int,
    income_band: str,
    coefficients: UtilityCoefficients,
) -> float:
    noise = choice_noise(
        master_seed,
        household_id=household_id,
        option_id=option.option_id,
        day=day_index,
        amplitude=coefficients.noise_amplitude,
    )
    return score_option(
        option,
        price_sensitivity_per_dollar=coefficients.price_sensitivity(income_band),
        time_sensitivity_per_minute=coefficients.time_sensitivity_per_minute,
        noise=noise,
    )


def choose_rule(
    options: tuple[FeasibleOption, ...],
    *,
    master_seed: int,
    household_id: str,
    day_index: int,
    income_band: str,
    coefficients: UtilityCoefficients,
) -> tuple[str, float]:
    """Pick the highest score. Equal scores break toward the smaller option id."""

    if not options:
        raise BehaviorError("rule choice needs at least one option")
    price_sensitivity = coefficients.price_sensitivity(income_band)
    scored: list[tuple[float, str]] = []
    for option in options:
        noise = choice_noise(
            master_seed,
            household_id=household_id,
            option_id=option.option_id,
            day=day_index,
            amplitude=coefficients.noise_amplitude,
        )
        utility = score_option(
            option,
            price_sensitivity_per_dollar=price_sensitivity,
            time_sensitivity_per_minute=coefficients.time_sensitivity_per_minute,
            noise=noise,
        )
        scored.append((utility, option.option_id))
    utility, option_id = min(scored, key=lambda item: (-item[0], item[1]))
    return option_id, utility


RULE_STREAM = STREAM_ALGORITHM
