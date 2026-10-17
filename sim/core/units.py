"""Integer units and the documented rounding rules.

Money is integer Canadian cents. Food mass is integer grams. Time is integer
simulation seconds. Route length, when a caller records it, is integer metres.
Booleans are not integers. Floats are refused so a dollar value cannot slip
into a cent field.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,80}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def require_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def require_nonnegative(value: object, field: str) -> int:
    number = require_int(value, field)
    if number < 0:
        raise ValueError(f"{field} must be >= 0")
    return number


def valid_id(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def valid_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def allocate_largest_remainder(total: int, weights: Sequence[tuple[str, int]]) -> dict[str, int]:
    """Split ``total`` indivisible units across positive weights.

    Each key receives ``floor(total * weight / weight_sum)``. Leftover units
    go to the largest fractional remainders. Equal remainders break toward the
    smaller key, in lexicographic order.
    """

    total = require_nonnegative(total, "total")
    if not weights:
        raise ValueError("weights are required")
    cleaned: list[tuple[str, int]] = []
    seen: set[str] = set()
    for key, weight in weights:
        if not isinstance(key, str) or key == "":
            raise ValueError("weight key must be a non-empty string")
        if key in seen:
            raise ValueError(f"duplicate weight key {key}")
        seen.add(key)
        weight_i = require_int(weight, "weight")
        if weight_i <= 0:
            raise ValueError("weight must be > 0")
        cleaned.append((key, weight_i))
    ordered = tuple(sorted(cleaned, key=lambda item: item[0]))
    weight_sum = sum(weight for _, weight in ordered)
    floors: list[int] = []
    remainders: list[int] = []
    assigned = 0
    for _key, weight in ordered:
        numerator = total * weight
        floors.append(numerator // weight_sum)
        remainders.append(numerator % weight_sum)
        assigned += floors[-1]
    left = total - assigned
    ranking = sorted(range(len(ordered)), key=lambda index: (-remainders[index], ordered[index][0]))
    shares = {ordered[index][0]: floors[index] for index in range(len(ordered))}
    for index in ranking[:left]:
        shares[ordered[index][0]] += 1
    return shares


def split_mass_by_ratio(
    total_grams: int,
    numerator: int,
    denominator: int,
    remainder_to: str,
) -> tuple[int, int]:
    """Return ``(edible_grams, loss_grams)`` summing to ``total_grams``.

    ``numerator / denominator`` is the edible share. ``remainder_to`` names
    the bucket that receives the grams left by integer division:

    - ``process_loss``: edible is ``floor(total * numerator / denominator)``
    - ``edible_output``: loss is ``floor(total * (denominator - numerator) / denominator)``
    """

    total_grams = require_nonnegative(total_grams, "total_grams")
    numerator = require_nonnegative(numerator, "numerator")
    denominator = require_int(denominator, "denominator")
    if denominator <= 0:
        raise ValueError("denominator must be > 0")
    if numerator > denominator:
        raise ValueError("numerator cannot exceed denominator")
    if remainder_to == "process_loss":
        edible = (total_grams * numerator) // denominator
    elif remainder_to == "edible_output":
        loss = (total_grams * (denominator - numerator)) // denominator
        edible = total_grams - loss
    else:
        raise ValueError("remainder_to must be process_loss or edible_output")
    return edible, total_grams - edible
