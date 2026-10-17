"""Versioned deterministic streams.

Draws are keyed by master seed, actor, day, purpose, and draw index. The key
does not include the policy, so a treatment that creates extra events does not
shift weather, income, or another actor's noise. The algorithm is SHA-256 and
does not use ``random.Random``, whose streams can change across Python versions.
"""

from __future__ import annotations

import hashlib
import math

STREAM_ALGORITHM = "sha256-unit-v1"

_UNIT = 1 << 64


def stream_key(
    master_seed: int,
    *,
    actor: str,
    day: int,
    purpose: str,
    draw: int = 0,
) -> str:
    if type(master_seed) is not int or master_seed < 0:
        raise ValueError("master_seed must be a non-negative int")
    if type(day) is not int or day < 0 or type(draw) is not int or draw < 0:
        raise ValueError("day and draw must be non-negative ints")
    _token("actor", actor)
    _token("purpose", purpose)
    return f"{STREAM_ALGORITHM}|{master_seed}|{actor}|{day}|{purpose}|{draw}"


def draw_unit(
    master_seed: int,
    *,
    actor: str,
    day: int,
    purpose: str,
    draw: int = 0,
) -> float:
    """Return a value in ``[0, 1)``."""

    digest = hashlib.sha256(
        stream_key(master_seed, actor=actor, day=day, purpose=purpose, draw=draw).encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big") / _UNIT


def draw_rank(
    master_seed: int,
    *,
    actor: str,
    day: int,
    purpose: str,
    draw: int = 0,
) -> int:
    """Return a 64-bit rank. Lower ranks sort first."""

    digest = hashlib.sha256(
        stream_key(master_seed, actor=actor, day=day, purpose=purpose, draw=draw).encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big")


def choice_noise(
    master_seed: int,
    *,
    household_id: str,
    option_id: str,
    day: int,
    amplitude: float,
) -> float:
    """Option-specific noise in ``[-amplitude, amplitude)``.

    Keying by option id keeps a household's noise for that option stable when
    another option appears or disappears.
    """

    if amplitude < 0 or not math.isfinite(amplitude):
        raise ValueError("noise amplitude must be finite and non-negative")
    unit = draw_unit(
        master_seed,
        actor=f"{household_id}:{option_id}",
        day=day,
        purpose="choice_noise",
    )
    return (unit * 2.0 - 1.0) * amplitude


def admission_rank(
    master_seed: int,
    *,
    household_id: str,
    day: int,
    opportunity: str,
) -> int:
    """Seeded contention rank for one decision opportunity.

    Core must allocate contested lots in this order. Actor-id order and provider
    response order are not admission rules.
    """

    return draw_rank(
        master_seed,
        actor=household_id,
        day=day,
        purpose=f"admission:{opportunity}",
    )


def _token(label: str, value: str) -> None:
    if type(value) is not str or not value or any(ch.isspace() for ch in value) or "|" in value:
        raise ValueError(f"{label} must be a non-empty token without whitespace or '|'")
