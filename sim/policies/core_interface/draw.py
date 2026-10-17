"""Earliest-expiring eligible stock, with lot id as the tie break."""

from __future__ import annotations

from typing import Protocol

from sim.policies.core_interface.allocate import partial_acquisition


class _Drawable(Protocol):
    def lots(self): ...

    def reserved_grams(self, lot_id: str) -> int: ...


def plan_draw(
    ledger: _Drawable,
    *,
    owner: str,
    product_id: str,
    grams: int,
    now: int,
) -> tuple[tuple[str, int], ...] | None:
    """Plan an exact draw. A reserved or expired lot is not eligible.

    Returns ``None`` when available grams are short of the request. Callers
    treat the basket as indivisible and draw nothing in that case.
    """

    if grams < 0:
        raise ValueError("grams must be nonnegative")
    if grams == 0:
        return ()
    eligible = []
    for lot in ledger.lots():
        if lot.owner != owner or lot.product_id != product_id:
            continue
        if lot.unsafe_after <= now or ledger.reserved_grams(lot.lot_id) > 0:
            continue
        if lot.grams > 0:
            eligible.append(lot)
    eligible.sort(key=lambda lot: (lot.unsafe_after, lot.lot_id))
    remaining = grams
    draws: list[tuple[str, int]] = []
    for lot in eligible:
        if remaining == 0:
            break
        take_grams = min(lot.grams, remaining)
        draws.append((lot.lot_id, take_grams))
        remaining -= take_grams
    if remaining != 0:
        return None
    return tuple(draws)


def quote_acquisition(ledger: _Drawable, draws: tuple[tuple[str, int], ...]) -> int:
    """Acquisition cents a later ``take`` of these draws will move."""

    by_id = {lot.lot_id: lot for lot in ledger.lots()}
    total = 0
    for lot_id, grams in draws:
        lot = by_id[lot_id]
        total += partial_acquisition(lot.acquisition_cents, lot.grams, grams)
    return total
