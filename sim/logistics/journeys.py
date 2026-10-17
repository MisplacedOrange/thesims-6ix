"""A trip is a departure and a later arrival. Duration is at least one second."""

from __future__ import annotations

from sim.core import PHASE_ARRIVAL, PHASE_SETTLE, TransferLot


def depart_lot(
    command_id: str,
    second: int,
    lot_id: str,
    grams: int,
    owner_id: str,
    destination_place_id: str,
    journey_id: str,
) -> TransferLot:
    return TransferLot(
        command_id,
        second,
        PHASE_SETTLE,
        lot_id,
        grams,
        owner_id,
        destination_place_id,
        journey_id,
    )


def arrive_lot(
    command_id: str,
    second: int,
    lot_id: str,
    grams: int,
    consignee_id: str,
    place_id: str,
) -> TransferLot:
    if second < 1:
        raise ValueError("arrival must be at least one second after the epoch")
    return TransferLot(command_id, second, PHASE_ARRIVAL, lot_id, grams, consignee_id, place_id, None)


def child_lot_id(source_lot_id: str, depart_command_id: str) -> str:
    return f"{source_lot_id}.{depart_command_id}"
