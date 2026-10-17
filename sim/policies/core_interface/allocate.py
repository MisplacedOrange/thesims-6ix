"""Integer allocation rules shared by the ledger and the policies.

Fractional cents and grams use the largest-remainder (Hamilton) method.
Ties break by key ascending. Lot splits use floor division and leave the
remainder on the source lot so the last grams carry the remaining cents.
"""

from __future__ import annotations


def largest_remainder(total: int, weights: dict[str, int]) -> dict[str, int]:
    """Allocate a nonnegative integer ``total`` in proportion to ``weights``."""

    if total < 0:
        raise ValueError("total must be nonnegative")
    if any(weight < 0 for weight in weights.values()):
        raise ValueError("weights must be nonnegative")
    result = {key: 0 for key in weights}
    positive = {key: weight for key, weight in weights.items() if weight > 0}
    weight_sum = sum(positive.values())
    if weight_sum == 0:
        if total != 0:
            raise ValueError("cannot allocate a positive total across zero weights")
        return result
    base: dict[str, int] = {}
    remainders: list[tuple[int, str]] = []
    allocated = 0
    for key in sorted(positive):
        numerator = total * positive[key]
        quantity = numerator // weight_sum
        base[key] = quantity
        allocated += quantity
        remainders.append((numerator % weight_sum, key))
    leftover = total - allocated
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for index in range(leftover):
        base[remainders[index][1]] += 1
    result.update(base)
    return result


def partial_acquisition(acquisition_cents: int, grams: int, take_grams: int) -> int:
    """Cents that move with ``take_grams``. The complement stays on the source."""

    if acquisition_cents < 0 or grams <= 0 or take_grams < 0 or take_grams > grams:
        raise ValueError("invalid lot split")
    if take_grams == grams:
        return acquisition_cents
    return acquisition_cents * take_grams // grams
